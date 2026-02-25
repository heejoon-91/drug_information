"""
infrastructure/supabase_db/dur_repository.py
Supabase기반 DurRepository 구현
"""
import logging
import re
from supabase import Client
from infrastructure.cache.supabase_cache import SupabaseCacheRepository
from domain.drug.entities import DurInfoEntity
from domain.drug.repositories import DurRepository
from domain.drug.services import DurAnalysisService

logger = logging.getLogger(__name__)

class SupabaseDurRepository(DurRepository):
    """Supabase를 사용하는 DurRepository 구현체"""

    def __init__(self):
        self._client: Client = SupabaseCacheRepository.get_client()
        self._domain_service = DurAnalysisService()

    async def find_by_ingredient_name(self, ingr_name: str) -> list[DurInfoEntity]:
        """성분명으로 DUR 조회 (동의어 포함)"""
        if not ingr_name or not self._client:
            return []

        candidates = self._domain_service.resolve_synonyms(ingr_name)
        all_results = []
        
        for cand in candidates:
            try:
                # 한글 포함 여부 확인하여 검색 필드 결정
                is_korean = bool(re.search('[가-힣]', cand))
                if is_korean:
                    response = self._client.table("dur_master").select("*").ilike("ingr_kor_name", f"%{cand}%").execute()
                else:
                    response = self._client.table("dur_master").select("*").ilike("ingr_eng_name", f"%{cand}%").execute()
                
                if response.data:
                    for d in response.data:
                        all_results.append(
                            DurInfoEntity(
                                dur_type=d.get('dur_type') or "",
                                ingr_kor_name=d.get('ingr_kor_name'),
                                ingr_eng_name=d.get('ingr_eng_name'),
                                prohbt_content=d.get('prohbt_content'),
                                remark=d.get('remark'),
                                critical_value=d.get('critical_value'),
                                grade=d.get('grade'),
                                mixture_ingr_kor_name=d.get('mixture_ingr_kor_name'),
                                mixture_ingr_eng_name=d.get('mixture_ingr_eng_name'),
                            )
                        )
            except Exception as e:
                logger.error(f"[Supabase] DUR 조회 오류 ('{cand}'): {e}")

        # 중복 제거 (필요한 경우)
        return all_results

    async def find_by_ingredient_names(self, ingr_names: list[str]) -> list[DurInfoEntity]:
        """복수 성분명으로 DUR 일괄 조회"""
        all_results: list[DurInfoEntity] = []
        for name in ingr_names:
            results = await self.find_by_ingredient_name(name)
            all_results.extend(results)
        return all_results
