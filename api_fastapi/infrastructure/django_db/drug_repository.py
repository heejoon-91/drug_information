"""
infrastructure/django_db/drug_repository.py
DrugRepository 구현 - Django ORM 기반
"""
import logging
from typing import Optional
from asgiref.sync import sync_to_async
from django.db.models import Q

from domain.drug.entities import DrugEntity
from domain.drug.repositories import DrugRepository

logger = logging.getLogger(__name__)


class DjangoDrugRepository(DrugRepository):
    """Django ORM을 사용하는 DrugRepository 구현체"""

    async def find_by_keyword(self, keyword: str, limit: int = 100) -> list[DrugEntity]:
        """DrugPermitInfo에서 제품명/업체명으로 약품 검색"""
        return await sync_to_async(self._find_by_keyword_sync)(keyword, limit)

    def _find_by_keyword_sync(self, keyword: str, limit: int) -> list[DrugEntity]:
        from drugs.models import DrugPermitInfo

        keyword = keyword.strip()
        if keyword:
            qs = DrugPermitInfo.objects.filter(
                Q(item_name__icontains=keyword) | Q(entp_name__icontains=keyword)
            )[:limit]
        else:
            qs = DrugPermitInfo.objects.all()[:limit]

        return [
            DrugEntity(
                item_seq=item.item_seq,
                item_name=item.item_name,
                entp_name=item.entp_name,
            )
            for item in qs
        ]

    async def find_by_item_seq(self, item_seq: str) -> Optional[DrugEntity]:
        """품목기준코드로 단건 조회"""
        return await sync_to_async(self._find_by_item_seq_sync)(item_seq)

    def _find_by_item_seq_sync(self, item_seq: str) -> Optional[DrugEntity]:
        from drugs.models import UnifiedDrugInfo

        try:
            item = UnifiedDrugInfo.objects.get(item_seq=item_seq)
            return DrugEntity(
                item_seq=item.item_seq,
                item_name=item.item_name,
                entp_name=item.entp_name,
                etc_otcc_name=item.etc_otcc_name,
                main_ingr_eng=item.main_ingr_eng,
                main_ingr_kor=item.main_ingr_kor,
                efficacy=item.efficacy,
                use_method=item.use_method,
                precautions=item.precautions,
                interaction=item.interaction,
                side_effects=item.side_effects,
                item_image=item.item_image,
            )
        except Exception:
            return None
