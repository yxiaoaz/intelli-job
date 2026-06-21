from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
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
)
from app.utils.security import verify_password, create_access_token, create_refresh_token, get_password_hash
from app.api.dependencies import get_current_user
from app.models import User, UserQueryPreference
from datetime import datetime, timedelta
from app.config import get_settings
import uuid

router = APIRouter()
settings = get_settings()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister, db: AsyncSession = Depends(get_db)):
    """Register a new user"""
    user_repo = UserRepository(db)
    
    # Check if user already exists
    existing_user = await user_repo.get_by_email(user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    user = await user_repo.create(
        email=user_data.email,
        password=user_data.password,
        security_question=user_data.security_question,
        security_answer=user_data.security_answer,
    )
    await db.commit()
    await db.refresh(user)
    
    return user


@router.post("/login", response_model=TokenResponse)
async def login(login_data: UserLogin, db: AsyncSession = Depends(get_db)):
    """Login and get access token"""
    user_repo = UserRepository(db)
    
    # Find user by email
    user = await user_repo.get_by_email(login_data.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Verify password
    if not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    
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
async def refresh_token(refresh_token: str):
    """Refresh access token"""
    try:
        from app.utils.security import decode_token
        payload = decode_token(refresh_token)
        
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
    return current_user


@router.put("/password", response_model=PasswordChangeResponse)
async def change_password(
    request: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Change user password"""
    # Verify old password
    if not verify_password(request.old_password, current_user.hashed_password):
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
    """Get user query preferences"""
    result = await db.execute(
        select(UserQueryPreference).where(UserQueryPreference.user_id == current_user.id)
    )
    pref = result.scalar_one_or_none()
    
    if not pref:
        # Return empty preference
        return UserPreferenceResponse(
            id=uuid.uuid4(),
            user_id=current_user.id,
            intended_company=[],
            intended_company_type=[],
            intended_location=[],
            intended_industry=[],
            intended_position=[],
            job_type=[],
            updated_at=datetime.utcnow()
        )
    
    return pref


@router.put("/preferences", response_model=UserPreferenceResponse)
async def update_preferences(
    request: UserPreferenceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update user query preferences"""
    result = await db.execute(
        select(UserQueryPreference).where(UserQueryPreference.user_id == current_user.id)
    )
    pref = result.scalar_one_or_none()
    
    if not pref:
        # Create new preference
        pref = UserQueryPreference(
            user_id=current_user.id,
            intended_company=request.intended_company or [],
            intended_company_type=request.intended_company_type or [],
            intended_location=request.intended_location or [],
            intended_industry=request.intended_industry or [],
            intended_position=request.intended_position or [],
            job_type=request.job_type or [],
        )
        db.add(pref)
    else:
        # Update existing preference
        if request.intended_company is not None:
            pref.intended_company = request.intended_company
        if request.intended_company_type is not None:
            pref.intended_company_type = request.intended_company_type
        if request.intended_location is not None:
            pref.intended_location = request.intended_location
        if request.intended_industry is not None:
            pref.intended_industry = request.intended_industry
        if request.intended_position is not None:
            pref.intended_position = request.intended_position
        if request.job_type is not None:
            pref.job_type = request.job_type
    
    await db.commit()
    await db.refresh(pref)
    
    return pref


@router.post("/forgot-password", response_model=SecurityQuestionResponse)
async def forgot_password(request: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Request security question for password reset"""
    user_repo = UserRepository(db)
    user = await user_repo.get_by_email(request.email)
    
    # Always return a generic message to avoid email enumeration
    if not user or not user.security_question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="该邮箱未注册或未设置安全问题"
        )
    
    return SecurityQuestionResponse(
        email=user.email,
        security_question=user.security_question,
    )


@router.post("/reset-password", response_model=ResetPasswordResponse)
async def reset_password(request: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Reset password using security question answer"""
    user_repo = UserRepository(db)
    user = await user_repo.get_by_email(request.email)
    
    if not user or not user.security_answer_hash:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="该邮箱未注册或未设置安全问题"
        )
    
    # Verify security answer (case-insensitive, trimmed)
    answer = request.security_answer.strip().lower()
    if not verify_password(answer, user.security_answer_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="安全问题答案错误"
        )
    
    # Reset password
    await user_repo.update_password(user.id, request.new_password)
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
