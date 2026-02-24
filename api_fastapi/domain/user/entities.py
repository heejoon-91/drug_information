"""
domain/user/entities.py
사용자 도메인 엔티티
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class UserProfileEntity:
    """사용자 건강 정보 프로필 엔티티"""
    user_id: int
    current_medications: Optional[str] = None   # 복용 중인 약
    allergies: Optional[str] = None             # 알러지
    chronic_diseases: Optional[str] = None      # 기저질환

    def to_dict(self) -> dict:
        return {
            "current_medications": self.current_medications,
            "allergies": self.allergies,
            "chronic_diseases": self.chronic_diseases,
        }
