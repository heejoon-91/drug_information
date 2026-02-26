from fastapi import APIRouter, Depends
from application.services.auth_service import AuthService
from application.services.user_service import UserService

router = APIRouter(prefix="/api/user", tags=["user"])

@router.get("/me")
async def get_user_me(token: str = Depends(AuthService.oauth2_scheme)):
    """현재 로그인한 사용자 정보 조회"""
    user_id = await AuthService.verify_token(token)
    user_info = await UserService.get_user_info(user_id)
    return user_info
