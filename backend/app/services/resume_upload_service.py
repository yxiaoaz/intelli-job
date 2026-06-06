"""
简历上传服务
处理文件验证、存储和元数据管理
"""
import os
import uuid
from datetime import datetime
from pathlib import Path
from fastapi import UploadFile, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Resume
from app.utils.logger import get_logger

logger = get_logger()


class ResumeUploadService:
    """简历文件上传服务"""
    
    # 支持的文件类型
    ALLOWED_CONTENT_TYPES = {
        "application/pdf": ".pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    }
    
    # 最大文件大小：10MB
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    
    def __init__(self, storage_root: str = None):
        """
        初始化上传服务
        
        Args:
            storage_root: 文件存储根目录，默认为项目根目录下的 files/resumes
        """
        if storage_root is None:
            # 默认存储路径：backend/files/resumes
            backend_dir = Path(__file__).parent.parent.parent
            self.storage_root = backend_dir / "files" / "resumes"
        else:
            self.storage_root = Path(storage_root)
        
        # 确保存储目录存在
        self.storage_root.mkdir(parents=True, exist_ok=True)
        logger.info(f"简历存储根目录: {self.storage_root}")
    
    def validate_file(self, file: UploadFile) -> None:
        """
        验证上传文件
        
        Args:
            file: 上传的文件对象
            
        Raises:
            HTTPException: 文件验证失败时抛出
        """
        # 检查文件大小
        if file.size and file.size > self.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"文件大小不能超过 {self.MAX_FILE_SIZE // (1024*1024)}MB"
            )
        
        # 检查文件类型
        if file.content_type not in self.ALLOWED_CONTENT_TYPES:
            allowed_types = ", ".join(self.ALLOWED_CONTENT_TYPES.keys())
            raise HTTPException(
                status_code=415,
                detail=f"不支持的文件类型。仅支持: {allowed_types}"
            )
    
    async def save_file(self, file: UploadFile, user_id: uuid.UUID) -> dict:
        """
        保存上传的简历文件
        
        Args:
            file: 上传的文件对象
            user_id: 用户ID
            
        Returns:
            dict: 包含文件信息的字典
        """
        # 验证文件
        self.validate_file(file)
        
        # 生成唯一文件名
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        original_filename = file.filename or "resume"
        file_extension = self.ALLOWED_CONTENT_TYPES.get(file.content_type, ".pdf")
        unique_filename = f"{timestamp}_{uuid.uuid4().hex[:8]}_{original_filename}"
        
        # 创建用户专属目录
        user_dir = self.storage_root / str(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)
        
        # 完整文件路径
        file_path = user_dir / unique_filename
        
        # 读取并保存文件
        content = await file.read()
        
        # 再次检查文件大小（防止流式上传绕过验证）
        if len(content) > self.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"文件大小不能超过 {self.MAX_FILE_SIZE // (1024*1024)}MB"
            )
        
        with open(file_path, "wb") as f:
            f.write(content)
        
        logger.info(f"文件已保存: {file_path}, 大小: {len(content)} bytes")
        
        return {
            "filename": unique_filename,
            "original_filename": original_filename,
            "file_path": str(file_path),
            "file_size": len(content),
            "content_type": file.content_type,
        }
    
    async def create_resume_record(
        self, 
        session: AsyncSession, 
        user_id: uuid.UUID, 
        file_info: dict
    ) -> Resume:
        """
        创建简历数据库记录
        
        Args:
            session: 数据库会话
            user_id: 用户ID
            file_info: 文件信息字典
            
        Returns:
            Resume: 创建的简历对象
        """
        resume = Resume(
            user_id=user_id,
            filename=file_info["original_filename"],
            file_path=file_info["file_path"],
            file_size=file_info["file_size"],
            content_type=file_info["content_type"],
            resume_name=file_info["original_filename"],
            uploaded_at=datetime.utcnow(),
        )
        
        session.add(resume)
        await session.flush()  # 获取生成的 ID
        
        logger.info(f"简历记录已创建: resume_id={resume.id}")
        return resume
    
    def delete_file(self, file_path: str) -> bool:
        """
        删除物理文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 是否成功删除
        """
        try:
            path = Path(file_path)
            if path.exists():
                path.unlink()
                logger.info(f"文件已删除: {file_path}")
                return True
            else:
                logger.warning(f"文件不存在: {file_path}")
                return False
        except Exception as e:
            logger.error(f"删除文件失败: {e}")
            return False

