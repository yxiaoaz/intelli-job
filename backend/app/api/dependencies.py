from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.repositories.user_repo import UserRepository
from app.utils.security import decode_token
from app.models import User
import logging

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current authenticated user from JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        token_type = payload.get("type")
        
        logger.debug(f"Token decoded: user_id={user_id}, type={token_type}")
        
        if user_id is None or token_type != "access":
            logger.warning(f"Invalid token: user_id={user_id}, type={token_type}")
            raise credentials_exception
    except ValueError as e:
        logger.warning(f"Token decode failed: {e}")
        raise credentials_exception
    
    try:
        user_repo = UserRepository(db)
        user = await user_repo.get_by_id(user_id)
        
        if user is None:
            logger.warning(f"User not found: user_id={user_id}")
            raise credentials_exception
        
        if not user.is_active:
            logger.warning(f"Inactive user: user_id={user_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Inactive user"
            )
        
        logger.debug(f"User authenticated successfully: {user.username}")
        return user
    except Exception as e:
        logger.error(f"Database query failed for user_id={user_id}: {type(e).__name__}: {e}")
        raise credentials_exception


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Ensure user is active"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user
