import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.rate_limiter import auth_limit
from app.core.redis import get_redis, incr_with_ttl, safe_redis
from app.database import get_db
from app.repositories.user_repo import UserRepository
from app.schemas import (
    UserRegister, UserLogin, TokenResponse, UserResponse,
    PasswordChangeRequest, PasswordChangeResponse,
    UserPreferenceUpdate, UserPreferenceResponse,
    ForgotPasswordRequest, SecurityQuestionResponse,
    ResetPasswordRequest, ResetPasswordResponse,
    SetSecurityQuestionRequest, SetSecurityQuestionResponse,
    SecurityQuestionStatusResponse,
    RefreshTokenRequest,
)
from app.utils.security import verify_password, create_access_token, create_refresh_token, get_password_hash
from app.api.dependencies import get_current_user
from app.models import User
from app.models.user_memory import UserMemoryORM
from datetime import datetime, timedelta
from app.config import get_settings
import uuid

router = APIRouter()
settings = get_settings()


# ── 登录失败锁定（Redis 计数，固定窗口；Redis 不可用时降级放行）──────────


def _login_lock_key(username: str) -> str:
    return f"login_fail_lock:{username.lower()}"


def _login_fail_key(username: str) -> str:
    return f"login_fail:{username.lower()}"


async def _is_login_locked(username: str) -> bool:
    """查锁定 key，存在则拒绝登录（统一文案，不暴露剩余时间）"""
    locked = await safe_redis(lambda: get_redis().get(_login_lock_key(username)))
    return bool(locked)


async def _record_login_failure(username: str) -> None:
    """记录失败：原子计数（SET NX EX + INCR，固定窗口，防“4 次/14.5 分钟”节奏永久爆破）；
    达阈值后写锁定 key。"""
    count = await incr_with_ttl(
        _login_fail_key(username), settings.LOGIN_LOCKOUT_MINUTES * 60
    )
    if count is None:  # Redis 降级：放行
        return
    if count >= settings.LOGIN_MAX_FAILURES:
        await safe_redis(
            lambda: get_redis().set(
                _login_lock_key(username),
                "1",
                ex=settings.LOGIN_LOCKOUT_MINUTES * 60,
            )
        )


async def _clear_login_failures(username: str) -> None:
    """登录成功后清零计数"""
    await safe_redis(lambda: get_redis().delete(_login_fail_key(username)))


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@auth_limit
async def register(request: Request, user_data: UserRegister, db: AsyncSession = Depends(get_db)):
    """Register a new user"""
    user_repo = UserRepository(db)
    
    # Check if user already exists
    existing_user = await user_repo.get_by_username(user_data.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已被注册"
        )
    
    # Create new user
    user = await user_repo.create(
        username=user_data.username,
        password=user_data.password,
        security_question=user_data.security_question,
        security_answer=user_data.security_answer,
    )
    await db.commit()
    await db.refresh(user)
    
    return user


@router.post("/login", response_model=TokenResponse)
@auth_limit
async def login(request: Request, login_data: UserLogin, db: AsyncSession = Depends(get_db)):
    """Login and get access token"""
    user_repo = UserRepository(db)

    # 登录失败锁定：已锁定直接拒绝（统一文案，不区分密码错误/已锁定以外信息）
    if await _is_login_locked(login_data.username):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="尝试次数过多，请稍后再试"
        )

    # Find user by username
    user = await user_repo.get_by_username(login_data.username)
    if not user:
        await _record_login_failure(login_data.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )

    # Verify password（bcrypt 同步 CPU 密集，放线程池避免阻塞事件循环）
    if not await asyncio.to_thread(
        verify_password, login_data.password, user.hashed_password
    ):
        await _record_login_failure(login_data.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )

    # 登录成功：清零失败计数
    await _clear_login_failures(login_data.username)
    
    # Create tokens
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=access_token_expires
    )
    refresh_token = create_refresh_token(data={"sub": str(user.id)})
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@router.post("/refresh", response_model=TokenResponse)
@auth_limit
async def refresh_token(request: Request, refresh_data: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    """Refresh access token"""
    try:
        from app.utils.security import decode_token
        payload = decode_token(refresh_data.refresh_token)
        
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        
        # 回库校验：被删/禁用用户的 refresh token 不得续命（api-abuse-protection）
        try:
            user_uuid = uuid.UUID(user_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        user_result = await db.execute(select(User).where(User.id == user_uuid))
        refresh_user = user_result.scalar_one_or_none()
        if not refresh_user or not refresh_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        
        # Create new tokens
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        new_access_token = create_access_token(
            data={"sub": user_id},
            expires_delta=access_token_expires
        )
        new_refresh_token = create_refresh_token(data={"sub": user_id})
        
        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer"
        }
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    # Ensure all required fields are present
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        is_active=current_user.is_active,
        created_at=current_user.created_at or datetime.utcnow()
    )


@router.put("/password", response_model=PasswordChangeResponse)
async def change_password(
    request: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Change user password"""
    # Verify old password（bcrypt 同步 CPU 密集，放线程池避免阻塞事件循环）
    if not await asyncio.to_thread(
        verify_password, request.old_password, current_user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="旧密码错误"
        )
    
    # Update password
    user_repo = UserRepository(db)
    await user_repo.update_password(current_user.id, request.new_password)
    await db.commit()
    
    return PasswordChangeResponse(message="密码修改成功")


@router.get("/preferences", response_model=UserPreferenceResponse)
async def get_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user job preferences（从 UserMemoryORM 读取）"""
    result = await db.execute(
        select(UserMemoryORM).where(UserMemoryORM.user_id == current_user.id)
    )
    mem = result.scalar_one_or_none()

    if not mem:
        return UserPreferenceResponse(
            id=current_user.id,
            user_id=current_user.id,
            intended_company=[],
            intended_company_type=[],
            intended_location=[],
            intended_industry=[],
            intended_position=[],
            job_type=[],
            updated_at=datetime.utcnow()
        )

    # 从嵌套 JSONB 展平为前端 schema
    prefs = mem.long_term_preferences or {}
    return UserPreferenceResponse(
        id=current_user.id,
        user_id=current_user.id,
        intended_company=prefs.get("target_companies", []),
        intended_company_type=prefs.get("target_company_types", []),
        intended_location=prefs.get("locations", []),
        intended_industry=prefs.get("industries", []),
        intended_position=prefs.get("target_roles", []),
        job_type=prefs.get("recruitment_types", []),
        updated_at=mem.last_updated_at or datetime.utcnow()
    )


@router.put("/preferences", response_model=UserPreferenceResponse)
async def update_preferences(
    request: UserPreferenceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update user job preferences（写入 UserMemoryORM.long_term_preferences）"""
    result = await db.execute(
        select(UserMemoryORM).where(UserMemoryORM.user_id == current_user.id)
    )
    mem = result.scalar_one_or_none()

    if not mem:
        # 首次创建
        mem = UserMemoryORM(user_id=current_user.id)
        db.add(mem)

    # 读取现有 JSONB，合并更新
    prefs = dict(mem.long_term_preferences or {})
    if request.intended_position is not None:
        prefs["target_roles"] = request.intended_position
    if request.intended_company is not None:
        prefs["target_companies"] = request.intended_company
    if request.intended_company_type is not None:
        prefs["target_company_types"] = request.intended_company_type
    if request.intended_location is not None:
        prefs["locations"] = request.intended_location
    if request.intended_industry is not None:
        prefs["industries"] = request.intended_industry
    if request.job_type is not None:
        prefs["recruitment_types"] = request.job_type

    mem.long_term_preferences = prefs
    mem.last_updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(mem)

    # 构造响应
    return UserPreferenceResponse(
        id=current_user.id,
        user_id=current_user.id,
        intended_company=prefs.get("target_companies", []),
        intended_company_type=prefs.get("target_company_types", []),
        intended_location=prefs.get("locations", []),
        intended_industry=prefs.get("industries", []),
        intended_position=prefs.get("target_roles", []),
        job_type=prefs.get("recruitment_types", []),
        updated_at=mem.last_updated_at
    )


@router.post("/forgot-password", response_model=SecurityQuestionResponse)
@auth_limit
async def forgot_password(request: Request, password_request: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Request security question for password reset
    
    安全加固：无论用户是否存在，均返回相同响应，避免用户名枚举。
    当用户不存在时，返回一个占位的安全问题，后续 reset-password 会统一拒绝。
    """
    user_repo = UserRepository(db)
    user = await user_repo.get_by_username(password_request.username)
    
    # 用户不存在或未设置安全问题时，返回通用占位响应（不泄露用户是否存在）
    if not user or not user.security_question:
        return SecurityQuestionResponse(
            username=password_request.username,
            security_question="请联系管理员重置密码",
        )
    
    return SecurityQuestionResponse(
        username=user.username,
        security_question=user.security_question,
    )


@router.post("/reset-password", response_model=ResetPasswordResponse)
@auth_limit
async def reset_password(request: Request, reset_request: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Reset password using security question answer"""
    user_repo = UserRepository(db)
    user = await user_repo.get_by_username(reset_request.username)
    
    if not user or not user.security_answer_hash:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="该用户名未注册或未设置安全问题"
        )
    
    # Verify security answer (case-insensitive, trimmed; bcrypt 放线程池避免阻塞事件循环)
    answer = reset_request.security_answer.strip().lower()
    if not await asyncio.to_thread(verify_password, answer, user.security_answer_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="安全问题答案错误"
        )
    
    # Reset password
    await user_repo.update_password(user.id, reset_request.new_password)
    await db.commit()
    
    return ResetPasswordResponse(message="密码重置成功，请使用新密码登录")


@router.get("/security-question/status", response_model=SecurityQuestionStatusResponse)
async def get_security_question_status(current_user: User = Depends(get_current_user)):
    """Check if current user has set a security question"""
    return SecurityQuestionStatusResponse(
        has_security_question=bool(current_user.security_question)
    )


@router.post("/security-question", response_model=SetSecurityQuestionResponse)
async def set_security_question(
    request: SetSecurityQuestionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Set or update security question for current user"""
    user_repo = UserRepository(db)
    answer = request.security_answer.strip().lower()
    await user_repo.set_security_question(current_user.id, request.security_question, answer)
    await db.commit()
    
    return SetSecurityQuestionResponse(message="安全问题设置成功")
