"""
infrastructure/supabase_db/user_repository.py
Supabase기반 UserRepository 구현
"""
import logging
from typing import Optional
from supabase import Client
from infrastructure.cache.supabase_cache import SupabaseCacheRepository

logger = logging.getLogger(__name__)

class SupabaseUserRepository:
    """Supabase를 사용하는 UserRepository 구현체"""

    def __init__(self):
        self._client: Client = SupabaseCacheRepository.get_client()

    async def get_user_by_username(self, username: str) -> Optional[dict]:
        """사용자 이름으로 사용자 조회"""
        if not self._client: return None
        try:
            response = self._client.table("auth_user").select("*").eq("username", username).single().execute()
            return response.data
        except Exception as e:
            logger.error(f"[Supabase] get_user_by_username 오류: {e}")
            return None

    async def get_user_by_id(self, user_id: int) -> Optional[dict]:
        """ID로 사용자 조회"""
        if not self._client: return None
        try:
            response = self._client.table("auth_user").select("*").eq("id", user_id).single().execute()
            return response.data
        except Exception as e:
            logger.error(f"[Supabase] get_user_by_id 오류: {e}")
            return None

    async def get_profile_by_user_id(self, user_id: int) -> Optional[dict]:
        """사용자 ID로 프로필 조회"""
        if not self._client: return None
        try:
            response = self._client.table("user_profile").select("*").eq("user_id", user_id).single().execute()
            return response.data
        except Exception as e:
            logger.error(f"[Supabase] get_profile_by_user_id 오류: {e}")
            return None

    async def update_profile(self, user_id: int, medications: str, allergies: str, diseases: str) -> bool:
        """프로필 정보 업데이트"""
        if not self._client: return False
        try:
            payload = {
                "user_id": user_id,
                "current_medications": medications,
                "allergies": allergies,
                "chronic_diseases": diseases
            }
            self._client.table("user_profile").upsert(payload, on_conflict="user_id").execute()
            return True
        except Exception as e:
            logger.error(f"[Supabase] update_profile 오류: {e}")
            return False
