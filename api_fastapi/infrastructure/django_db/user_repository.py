"""
infrastructure/django_db/user_repository.py
UserRepository 구현 - Django ORM 기반
"""
import logging
from typing import Optional
from asgiref.sync import sync_to_async

from domain.user.entities import UserProfileEntity
from domain.user.repositories import UserRepository

logger = logging.getLogger(__name__)


class DjangoUserRepository(UserRepository):
    """Django ORM을 사용하는 UserRepository 구현체"""

    async def find_by_user_id(self, user_id: int) -> Optional[UserProfileEntity]:
        return await sync_to_async(self._find_sync)(user_id)

    def _find_sync(self, user_id: int) -> Optional[UserProfileEntity]:
        from drugs.models import UserProfile

        try:
            profile = UserProfile.objects.get(user_id=user_id)
            return UserProfileEntity(
                user_id=user_id,
                current_medications=profile.current_medications,
                allergies=profile.allergies,
                chronic_diseases=profile.chronic_diseases,
            )
        except UserProfile.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"UserRepository 조회 오류 (user_id={user_id}): {e}")
            return None

    async def save(self, profile: UserProfileEntity) -> UserProfileEntity:
        return await sync_to_async(self._save_sync)(profile)

    def _save_sync(self, profile: UserProfileEntity) -> UserProfileEntity:
        from drugs.models import UserProfile
        from django.contrib.auth.models import User

        try:
            user = User.objects.get(pk=profile.user_id)
            obj, _ = UserProfile.objects.update_or_create(
                user=user,
                defaults={
                    "current_medications": profile.current_medications,
                    "allergies": profile.allergies,
                    "chronic_diseases": profile.chronic_diseases,
                }
            )
            return profile
        except Exception as e:
            logger.error(f"UserRepository 저장 오류: {e}")
            raise
