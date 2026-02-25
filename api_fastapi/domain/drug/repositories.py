"""
domain/drug/repositories.py
Repository 인터페이스 (ABC) - 구현은 infrastructure/ 계층에서
"""
from abc import ABC, abstractmethod
from typing import Optional
from domain.drug.entities import DrugEntity, DurInfoEntity


class DrugRepository(ABC):
    """의약품 정보 저장소 인터페이스"""

    @abstractmethod
    async def find_by_keyword(self, keyword: str, limit: int = 100) -> list[DrugEntity]:
        """제품명 또는 업체명으로 약품 검색"""
        ...

    @abstractmethod
    async def find_by_item_seq(self, item_seq: str) -> Optional[DrugEntity]:
        """품목기준코드로 단건 조회"""
        ...


class DurRepository(ABC):
    """DUR 금기 정보 저장소 인터페이스"""

    @abstractmethod
    async def find_by_ingredient_name(self, ingr_name: str) -> list[DurInfoEntity]:
        """성분명(영문 또는 한글)으로 DUR 목록 조회"""
        ...

    @abstractmethod
    async def find_by_ingredient_names(self, ingr_names: list[str]) -> list[DurInfoEntity]:
        """복수 성분명으로 DUR 목록 일괄 조회"""
        ...


class CacheRepository(ABC):
    """검색 결과 캐시 저장소 인터페이스"""

    @abstractmethod
    async def get_symptom_cache(self, query_text: str) -> Optional[dict]:
        """표준화된 쿼리 키로 캐시 조회"""
        ...

    @abstractmethod
    async def set_symptom_cache(
        self, query_text: str, category: str,
        fda_data: list, dur_data: list,
        final_answer: str, recommended_ingredients: list,
        data_hash: Optional[str] = None,
        logic_version: Optional[str] = None
    ) -> bool:
        """결과 데이터 캐시 저장 (무결성 검증용 해시/버전 포함)"""
        ...
