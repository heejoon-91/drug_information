import os
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from infrastructure.supabase_db.user_repository import SupabaseUserRepository

user_repo = SupabaseUserRepository()

# --- Configuration ---
SECRET_KEY = os.getenv("SECRET_KEY", "u2983y8923u8923u8923u8923u8923") # Fallback for dev
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

class AuthService:
    oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    @staticmethod
    async def authenticate_user(username, password):
        # Supabase를 통한 간단한 인증 시뮬레이션 (실제로는 Supabase Auth API를 쓰는 것이 좋음)
        user = await user_repo.get_user_by_username(username)
        if user and user.get("password") == password: # 해싱 처리 권장
            return user
        return None

    @staticmethod
    async def get_user(username):
        return await user_repo.get_user_by_username(username)

    @staticmethod
    async def verify_token(token: str):
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id: str = payload.get("sub")
            if user_id is None:
                raise HTTPException(status_code=401, detail="Invalid token")
            return int(user_id)
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid token")

async def get_current_user_from_token(token: str):
    """
    Decodes the JWT token and retrieves the user.
    This function is used for dependency injection in endpoints.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        user_id = await AuthService.verify_token(token)
    except Exception:
        raise credentials_exception
        
    user = await user_repo.get_user_by_id(user_id)
    if user is None:
        raise credentials_exception
    return user

async def get_current_user_optional(token: Optional[str] = None):
    """
    Returns user if token is valid, else None.
    Used for templates where login is optional.
    """
    if not token:
        return None
    try:
        user_id = await AuthService.verify_token(token)
        user = await user_repo.get_user_by_id(user_id)
        return user
    except Exception:
        return None
