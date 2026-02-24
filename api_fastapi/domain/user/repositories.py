"""
domain/user/repositories.py
사용자 저장소 인터페이스
"""
from abc import ABC, abstractmethod
from typing import Optional
from domain.user.entities import UserProfileEntity


class UserRepository(ABC):
    """사용자 프로필 저장소 인터페이스"""

    @abstractmethod
    async def find_by_user_id(self, user_id: int) -> Optional[UserProfileEntity]:
        """user_id로 프로필 조회"""
        ...

    @abstractmethod
    async def save(self, profile: UserProfileEntity) -> UserProfileEntity:
        """프로필 저장/업데이트"""
        ...
