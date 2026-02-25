"""
infrastructure/supabase_db/drug_repository.py
Supabase기반 DrugRepository 구현
"""
import logging
from typing import Optional
from supabase import Client
from infrastructure.cache.supabase_cache import SupabaseCacheRepository
from domain.drug.entities import DrugEntity
from domain.drug.repositories import DrugRepository

logger = logging.getLogger(__name__)

class SupabaseDrugRepository(DrugRepository):
    """Supabase를 사용하는 DrugRepository 구현체"""

    def __init__(self):
        self._client: Client = SupabaseCacheRepository.get_client()

    async def find_by_keyword(self, keyword: str, limit: int = 100) -> list[DrugEntity]:
        """Supabase 테이블에서 제품명/업체명으로 약품 검색"""
        if not self._client:
            return []
            
        keyword = keyword.strip()
        try:
            query = self._client.table("UnifiedDrugInfo").select("item_seq, item_name, entp_name")
            
            if keyword:
                # item_name 또는 entp_name에 키워드 포함여부 필터링 (OR 조건은 ilike 사용)
                # Supabase Python SDK에서 complex OR filter: .or_(f"item_name.ilike.%{keyword}%,entp_name.ilike.%{keyword}%")
                response = query.or_(f"item_name.ilike.%{keyword}%,entp_name.ilike.%{keyword}%").limit(limit).execute()
            else:
                response = query.limit(limit).execute()

            return [
                DrugEntity(
                    item_seq=item.get("item_seq"),
                    item_name=item.get("item_name"),
                    entp_name=item.get("entp_name"),
                )
                for item in response.data
            ]
        except Exception as e:
            logger.error(f"[Supabase] find_by_keyword 오류: {e}")
            return []

    async def find_by_item_seq(self, item_seq: str) -> Optional[DrugEntity]:
        """품목기준코드로 단건 조회"""
        if not self._client:
            return None
            
        try:
            response = self._client.table("unified_drug_info").select("*").eq("item_seq", item_seq).single().execute()
            item = response.data
            if not item:
                return None
                
            return DrugEntity(
                item_seq=item.get("item_seq"),
                item_name=item.get("item_name"),
                entp_name=item.get("entp_name"),
                etc_otcc_name=item.get("etc_otcc_name"),
                main_ingr_eng=item.get("main_ingr_eng"),
                main_ingr_kor=item.get("main_ingr_kor"),
                efficacy=item.get("efficacy"),
                use_method=item.get("use_method"),
                precautions=item.get("precautions"),
                interaction=item.get("interaction"),
                side_effects=item.get("side_effects"),
                item_image=item.get("item_image"),
            )
        except Exception as e:
            logger.error(f"[Supabase] find_by_item_seq 오류: {e}")
            return None
