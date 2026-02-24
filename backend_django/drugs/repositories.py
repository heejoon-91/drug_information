from typing import List, Optional
from django.db import models
from .models import UnifiedDrugInfo, DurMaster

class DrugRepository:
    """의약품 정보 조회를 위한 레포지토리 (Django 측)"""
    
    @staticmethod
    def search_by_keyword(query: str, limit: int = 50) -> List[UnifiedDrugInfo]:
        """제품명 또는 성분명으로 약품 검색"""
        return UnifiedDrugInfo.objects.filter(
            models.Q(item_name__icontains=query) |
            models.Q(main_ingr_kor__icontains=query) |
            models.Q(main_ingr_eng__icontains=query)
        )[:limit]

    @staticmethod
    def get_by_item_seq(item_seq: str) -> Optional[UnifiedDrugInfo]:
        """품목기준코드로 약품 조회"""
        try:
            return UnifiedDrugInfo.objects.get(item_seq=item_seq)
        except UnifiedDrugInfo.DoesNotExist:
            return None

class DurRepository:
    """DUR 금기 정보 조회를 위한 레포지토리 (Django 측)"""
    
    @staticmethod
    def find_by_ingredient(ingr_name: str) -> List[DurMaster]:
        """성분명으로 DUR 정보 검색"""
        return DurMaster.objects.filter(
            models.Q(ingr_kor_name__icontains=ingr_name) |
            models.Q(ingr_eng_name__icontains=ingr_name)
        )
