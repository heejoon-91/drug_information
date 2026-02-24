"""
application/use_cases/drug_search.py
약품 검색 유스케이스
"""
import logging
from domain.drug.entities import DrugEntity
from domain.drug.repositories import DrugRepository

logger = logging.getLogger(__name__)


class DrugSearchUseCase:
    """
    의약품 검색 유스케이스
    - DrugPermitInfo에서 제품명/업체명으로 검색
    - Repository 인터페이스에 의존 (구현체는 DI로 주입)
    """

    def __init__(self, drug_repo: DrugRepository):
        self._drug_repo = drug_repo

    async def execute(self, keyword: str, limit: int = 100) -> list[dict]:
        """
        키워드로 약품 검색 후 dict 목록 반환
        (기존 drug_router의 search_drugs 로직)
        """
        try:
            results: list[DrugEntity] = await self._drug_repo.find_by_keyword(keyword, limit)
            return [
                {
                    "item_seq": drug.item_seq,
                    "item_name": drug.item_name,
                    "entp_name": drug.entp_name,
                }
                for drug in results
            ]
        except Exception as e:
            logger.error(f"[DrugSearchUseCase] 검색 오류: {e}")
            return []
