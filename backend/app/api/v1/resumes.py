"""
简历管理 API 路由
提供简历上传、解析、查询等功能
"""
import asyncio
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.dependencies import get_current_user
from app.models import User, Resume, ResumeAnalysis
from app.services.resume_upload_service import ResumeUploadService
from app.services.resume_parser_service import ResumeParserService
from app.services.resume_evaluation_service import ResumeEvaluationService
from app.services.intent_file_service import IntentFileService
from app.utils.logger import get_logger
from pydantic import BaseModel, Field, ConfigDict

logger = get_logger()

router = APIRouter(prefix="/resumes", tags=["resumes"])

# 初始化服务
upload_service = ResumeUploadService()
parser_service = ResumeParserService()
evaluation_service = ResumeEvaluationService()


# Pydantic 模型
class ResumeResponse(BaseModel):
    """简历响应模型"""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    filename: str
    file_size: int
    content_type: str
    uploaded_at: str
    status: Optional[str] = None
    score: Optional[int] = None
    is_default: bool = False


class AnalysisResponse(BaseModel):
    """分析结果响应模型"""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    resume_id: str
    parsed_data: Optional[dict] = None
    evaluation: Optional[dict] = None
    status: str
    error_message: Optional[str] = None


class UploadResponse(BaseModel):
    """上传响应模型"""
    resume: dict  # 简历详细信息
    task_id: str
    message: str


@router.post("/upload", response_model=UploadResponse)
async def upload_resume(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = None
):
    """
    上传简历文件并触发异步解析
    
    - **file**: PDF 或 DOCX 格式的简历文件（最大 10MB）
    """
    try:
        # 1. 保存文件
        file_info = await upload_service.save_file(file, current_user.id)
        
        # 2. 创建数据库记录
        resume = await upload_service.create_resume_record(session, current_user.id, file_info)
        
        # 3. 创建初始分析记录（状态：pending）
        analysis = await parser_service.create_analysis_record(
            session, resume.id, {}, status="pending"
        )
        await session.commit()
        
        # 4. Add to FastAPI managed background tasks
        if background_tasks:
            background_tasks.add_task(
                process_resume_async,
                str(resume.id),
                str(analysis.id),
                file_info["file_path"],
                file_info["content_type"]
            )
            logger.info(f"简历处理任务已添加到后台队列: resume_id={resume.id}")
        else:
            logger.warning("BackgroundTasks not available, processing will not start")
        
        logger.info(f"简历上传成功: resume_id={resume.id}, user_id={current_user.id}")
        
        return {
            "resume": {
                "id": str(resume.id),
                "filename": file_info["filename"],
                "file_size": file_info["file_size"],
                "content_type": file_info["content_type"],
                "uploaded_at": resume.uploaded_at.isoformat() if resume.uploaded_at else "",
                "status": "pending",
                "score": None
            },
            "task_id": str(analysis.id),
            "message": "简历上传成功，正在解析中..."
        }
        
    except HTTPException:
        raise
    except ValueError as e:
        # 文件验证错误（大小、类型等）
        logger.warning(f"简历上传验证失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"简历上传失败: {e}")
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


async def process_resume_async(
    resume_id: str,
    analysis_id: str,
    file_path: str,
    content_type: str
):
    """
    异步处理简历：提取文本 -> LLM 解析 -> 评估
    
    Args:
        resume_id: 简历ID
        analysis_id: 分析记录ID
        file_path: 文件路径
        content_type: 文件类型
    """
    from app.database import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        try:
            # 1. 更新状态为 processing
            await parser_service.update_analysis_status(session, analysis_id, "processing")
            await session.commit()
            
            # 2. 提取文本
            logger.info(f"开始提取文本: resume_id={resume_id}")
            resume_text = parser_service.extract_text(file_path, content_type)
            
            # 3. LLM 解析
            logger.info(f"开始 LLM 解析: resume_id={resume_id}")
            parsed_data = await parser_service.parse_with_llm(resume_text)
            
            # 4. 保存解析结果
            await parser_service.update_analysis_status(
                session, analysis_id, "parsed", parsed_data=parsed_data
            )
            await session.commit()
            
            # 5. 生成评估报告
            logger.info(f"开始生成评估报告: resume_id={resume_id}")
            evaluation = await evaluation_service.generate_evaluation_report(parsed_data)
            
            # 6. 保存评估结果并标记完成
            await evaluation_service.update_analysis_with_evaluation(session, analysis_id, evaluation)
            await parser_service.update_analysis_status(session, analysis_id, "completed")
            
            # 7. 触发 Profile 初始化/更新 + 偏好抽取
            try:
                intent_service = IntentFileService()
                # 重新查询以获取 user_id
                from sqlalchemy import select
                res_result = await session.execute(select(Resume).where(Resume.id == resume_id))
                resume_obj = res_result.scalar_one_or_none()
                if resume_obj:
                    user_id = resume_obj.user_id
                    intent_service.initialize_profile(str(user_id), parsed_data)

                    # 7.5 偏好抽取（失败不阻塞）
                    try:
                        from app.services.preference_extraction_service import PreferenceExtractionService
                        from app.memory.service import MemoryService
                        from app.memory.schemas import UserMemory

                        pref_svc = PreferenceExtractionService()
                        pref = await pref_svc.extract(parsed_data, uuid.UUID(resume_id), user_id)
                        if pref:
                            mem_service = MemoryService(
                                session,
                                base_dir=intent_service.base_dir,
                            )
                            user_mem = await mem_service.get_user_memory(user_id) or UserMemory()
                            user_mem.long_term_preferences = pref
                            await mem_service.write_user_memory(user_id, user_mem)
                            logger.info("resume_preference_extracted", resume_id=resume_id)
                    except Exception as pref_err:
                        logger.warning("resume_preference_extraction_failed", error=str(pref_err))
            except Exception as profile_err:
                logger.error(f"Profile 初始化失败: {profile_err}")
            
            await session.commit()
            
            logger.info(f"简历处理完成: resume_id={resume_id}")
            
        except Exception as e:
            logger.error(f"简历处理失败: resume_id={resume_id}, error={e}")
            async with AsyncSessionLocal() as error_session:
                await parser_service.update_analysis_status(
                    error_session, analysis_id, "failed", error_message=str(e)
                )
                await error_session.commit()


@router.get("", response_model=list[ResumeResponse])
@router.get("/", response_model=list[ResumeResponse])
async def list_resumes(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 10
):
    """
    获取当前用户的简历列表
    
    - **skip**: 跳过数量（分页）
    - **limit**: 返回数量（分页）
    """
    from sqlalchemy import select, desc
    
    result = await session.execute(
        select(Resume)
        .where(Resume.user_id == current_user.id)
        .order_by(desc(Resume.uploaded_at))
        .offset(skip)
        .limit(limit)
    )
    resumes = result.scalars().all()
    
    # 批量获取这批简历的分析记录，按时间降序，首次出现即最新（避免 N+1 查询）
    resume_ids = [r.id for r in resumes]
    analysis_map = {}
    if resume_ids:
        analysis_result = await session.execute(
            select(ResumeAnalysis)
            .where(ResumeAnalysis.resume_id.in_(resume_ids))
            .order_by(desc(ResumeAnalysis.created_at))
        )
        for a in analysis_result.scalars():
            analysis_map.setdefault(a.resume_id, a)

    resume_responses = []
    for resume in resumes:
        analysis = analysis_map.get(resume.id)

        score = None
        if analysis and analysis.evaluation:
            score = analysis.evaluation.get("overall_score")
        
        resume_responses.append(ResumeResponse(
            id=str(resume.id),
            filename=resume.filename or "",
            file_size=resume.file_size or 0,
            content_type=resume.content_type or "",
            uploaded_at=resume.uploaded_at.isoformat() if resume.uploaded_at else "",
            status=analysis.status if analysis else None,
            score=score,
            is_default=resume.active_status or False
        ))
    
    return resume_responses


@router.get("/{resume_id}", response_model=dict)
async def get_resume_detail(
    resume_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    获取简历详情和分析结果
    
    - **resume_id**: 简历ID
    """
    from sqlalchemy import select, desc
    
    # 查询简历
    result = await session.execute(
        select(Resume).where(
            Resume.id == resume_id,
            Resume.user_id == current_user.id
        )
    )
    resume = result.scalar_one_or_none()
    
    if not resume:
        raise HTTPException(status_code=404, detail="简历不存在或无权访问")
    
    # 查询最新分析结果
    analysis_result = await session.execute(
        select(ResumeAnalysis)
        .where(ResumeAnalysis.resume_id == resume_id)
        .order_by(desc(ResumeAnalysis.created_at))
        .limit(1)
    )
    analysis = analysis_result.scalar_one_or_none()
    
    return {
        "resume": {
            "id": str(resume.id),
            "filename": resume.filename,
            "file_size": resume.file_size,
            "content_type": resume.content_type,
            "uploaded_at": resume.uploaded_at.isoformat() if resume.uploaded_at else None,
        },
        "analysis": {
            "id": str(analysis.id) if analysis else None,
            "parsed_data": analysis.parsed_data if analysis else None,
            "evaluation": analysis.evaluation if analysis else None,
            "status": analysis.status if analysis else "pending",
            "error_message": analysis.error_message if analysis else None,
        }
    }


@router.delete("/{resume_id}")
async def delete_resume(
    resume_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    删除简历及其分析记录
    
    - **resume_id**: 简历ID
    """
    from sqlalchemy import select, delete
    
    # 查询简历
    result = await session.execute(
        select(Resume).where(
            Resume.id == resume_id,
            Resume.user_id == current_user.id
        )
    )
    resume = result.scalar_one_or_none()
    
    if not resume:
        raise HTTPException(status_code=404, detail="简历不存在或无权访问")
    
    # 删除物理文件
    if resume.file_path:
        upload_service.delete_file(resume.file_path)
    
    # 删除数据库记录（级联删除分析记录）
    await session.delete(resume)
    await session.commit()
    
    logger.info(f"简历已删除: resume_id={resume_id}")
    return {"message": "简历已删除"}


@router.post("/{resume_id}/reparse")
async def reparse_resume(
    resume_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    重新解析简历
    
    - **resume_id**: 简历ID
    """
    from sqlalchemy import select
    
    # 查询简历
    result = await session.execute(
        select(Resume).where(
            Resume.id == resume_id,
            Resume.user_id == current_user.id
        )
    )
    resume = result.scalar_one_or_none()
    
    if not resume:
        raise HTTPException(status_code=404, detail="简历不存在或无权访问")
    
    if not resume.file_path:
        raise HTTPException(status_code=400, detail="简历文件路径不存在")
    
    # 创建新的分析记录
    analysis = await parser_service.create_analysis_record(
        session, resume.id, {}, status="pending"
    )
    await session.commit()
    
    # 后台任务：重新解析（使用 asyncio.create_task）
    import asyncio
    asyncio.create_task(
        process_resume_async(
            str(resume.id),
            str(analysis.id),
            resume.file_path,
            resume.content_type
        )
    )
    
    return {
        "task_id": str(analysis.id),
        "message": "重新解析任务已启动"
    }


@router.post("/{resume_id}/set-default")
async def set_default_resume(
    resume_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    设置默认简历
    
    - **resume_id**: 简历ID
    """
    from sqlalchemy import select, update
    
    # 查询简历
    result = await session.execute(
        select(Resume).where(
            Resume.id == resume_id,
            Resume.user_id == current_user.id
        )
    )
    resume = result.scalar_one_or_none()
    
    if not resume:
        raise HTTPException(status_code=404, detail="简历不存在或无权访问")
    
    # 先将该用户的所有简历设为非默认
    await session.execute(
        update(Resume)
        .where(Resume.user_id == current_user.id)
        .values(active_status=False)
    )
    
    # 再设置当前简历为默认
    resume.active_status = True
    await session.commit()
    
    # 触发 Profile 更新（因为激活简历变了）
    try:
        intent_service = IntentFileService()
        # 获取该简历的解析数据
        analysis_result = await session.execute(
            select(ResumeAnalysis)
            .where(ResumeAnalysis.resume_id == resume_id)
            .order_by(desc(ResumeAnalysis.created_at))
            .limit(1)
        )
        analysis = analysis_result.scalar_one_or_none()
        if analysis and analysis.parsed_data:
            await asyncio.to_thread(intent_service.initialize_profile, str(current_user.id), analysis.parsed_data)
    except Exception as profile_err:
        logger.error(f"切换简历时 Profile 更新失败: {profile_err}")
    
    logger.info(f"默认简历已设置: resume_id={resume_id}")
    return {"message": "默认简历已设置", "resume_id": resume_id}


@router.get("/{resume_id}/matches")
async def get_job_matches(
    resume_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    limit: int = 20
):
    """
    基于简历获取匹配的岗位列表
    
    - **resume_id**: 简历ID
    - **limit**: 返回岗位数量
    """
    from sqlalchemy import select, desc
    from app.services.job_matching_service import JobMatchingService
    from app.repositories.job_repo import JobRepository
    
    # 查询简历和分析结果
    result = await session.execute(
        select(Resume).where(
            Resume.id == resume_id,
            Resume.user_id == current_user.id
        )
    )
    resume = result.scalar_one_or_none()
    
    if not resume:
        raise HTTPException(status_code=404, detail="简历不存在或无权访问")
    
    # 获取最新分析结果
    analysis_result = await session.execute(
        select(ResumeAnalysis)
        .where(ResumeAnalysis.resume_id == resume_id)
        .order_by(desc(ResumeAnalysis.created_at))
        .limit(1)
    )
    analysis = analysis_result.scalar_one_or_none()
    
    if not analysis or analysis.status != "completed" or not analysis.parsed_data:
        raise HTTPException(
            status_code=400,
            detail="简历尚未完成解析或解析失败"
        )
    
    # 使用岗位匹配服务
    matching_service = JobMatchingService()
    job_repo = JobRepository(session)
    
    try:
        matched_jobs = await matching_service.match_jobs(
            user_query_preference={},  # 可以后续从用户偏好中获取
            user_resume_profile=analysis.parsed_data,
            search_mode="hybrid",
            top_k=limit,
            hard_filters={},
            job_repo=job_repo,
            skip_enhancement=True  # 无搜索关键词，跳过 LLM 增强
        )
        
        logger.info(f"岗位匹配完成: resume_id={resume_id}, 匹配数={len(matched_jobs)}")
        
        return {
            "resume_id": resume_id,
            "total_matches": len(matched_jobs),
            "jobs": matched_jobs
        }
        
    except Exception as e:
        logger.error(f"岗位匹配失败: {e}")
        raise HTTPException(status_code=500, detail=f"匹配失败: {str(e)}")


@router.get("/{resume_id}/export/json")
async def export_resume_json(
    resume_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    导出简历解析结果为 JSON
    
    - **resume_id**: 简历ID
    """
    from fastapi.responses import JSONResponse
    from sqlalchemy import select, desc
    
    # 查询简历
    result = await session.execute(
        select(Resume).where(
            Resume.id == resume_id,
            Resume.user_id == current_user.id
        )
    )
    resume = result.scalar_one_or_none()
    
    if not resume:
        raise HTTPException(status_code=404, detail="简历不存在或无权访问")
    
    # 获取最新分析结果
    analysis_result = await session.execute(
        select(ResumeAnalysis)
        .where(ResumeAnalysis.resume_id == resume_id)
        .order_by(desc(ResumeAnalysis.created_at))
        .limit(1)
    )
    analysis = analysis_result.scalar_one_or_none()
    
    if not analysis or not analysis.parsed_data:
        raise HTTPException(status_code=400, detail="暂无解析数据可导出")
    
    export_data = {
        "resume_info": {
            "filename": resume.filename,
            "uploaded_at": resume.uploaded_at.isoformat() if resume.uploaded_at else None,
        },
        "parsed_data": analysis.parsed_data,
        "evaluation": analysis.evaluation,
    }
    
    return JSONResponse(
        content=export_data,
        headers={"Content-Disposition": f"attachment; filename=resume_{resume_id}.json"}
    )

