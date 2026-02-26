"""
infrastructure/django_db/dur_repository.py
DurRepository 구현 - Django ORM + 도메인 서비스 활용
"""
import logging
from asgiref.sync import sync_to_async
from django.db.models import Q

from domain.drug.entities import DurInfoEntity
from domain.drug.repositories import DurRepository
from domain.drug.services import DurAnalysisService

logger = logging.getLogger(__name__)


class DjangoDurRepository(DurRepository):
    """Django ORM을 사용하는 DurRepository 구현체"""

    def __init__(self):
        self._domain_service = DurAnalysisService()

    async def find_by_ingredient_name(self, ingr_name: str) -> list[DurInfoEntity]:
        """성분명으로 DUR 조회 (동의어 포함)"""
        if not ingr_name:
            return []

        candidates = self._domain_service.resolve_synonyms(ingr_name)
        return await sync_to_async(self._query_dur_sync)(candidates)

    async def find_by_ingredient_names(self, ingr_names: list[str]) -> list[DurInfoEntity]:
        """복수 성분명으로 DUR 일괄 조회"""
        all_results: list[DurInfoEntity] = []
        for name in ingr_names:
            results = await self.find_by_ingredient_name(name)
            all_results.extend(results)
        return all_results

    def _query_dur_sync(self, candidates: set[str]) -> list[DurInfoEntity]:
        from drugs.models import DurMaster

        q_obj = Q()
        for cand in candidates:
            q_obj |= Q(ingr_eng_name__icontains=cand)
            q_obj |= Q(ingr_kor_name__icontains=cand)

        qs = DurMaster.objects.filter(q_obj).distinct()

        return [
            DurInfoEntity(
                dur_type=d.dur_type or "",
                ingr_kor_name=d.ingr_kor_name,
                ingr_eng_name=d.ingr_eng_name,
                prohbt_content=d.prohbt_content,
                remark=d.remark,
                critical_value=d.critical_value,
                grade=d.grade,
                mixture_ingr_kor_name=d.mixture_ingr_kor_name,
                mixture_ingr_eng_name=d.mixture_ingr_eng_name,
            )
            for d in qs
        ]
