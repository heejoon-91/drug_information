"""
infrastructure/cache/supabase_cache.py
Supabase 캐시 구현 (기존 SupabaseService의 캐시 관련 메서드 이동)
"""
import os
import re
import logging
from supabase import create_client, Client

logger = logging.getLogger(__name__)


from domain.drug.repositories import CacheRepository

class SupabaseCacheRepository(CacheRepository):
    """Supabase 기반 캐시 저장소"""

    _client: Client | None = None

    @classmethod
    def get_client(cls) -> Client | None:
        if cls._client:
            return cls._client
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        if not url or not key:
            logger.error("SUPABASE_URL과 SUPABASE_KEY가 설정되지 않았습니다.")
            return None
        cls._client = create_client(url, key)
        return cls._client

    # ─── DUR 조회 ──────────────────────────────────────────────────────────────

    async def get_dur_by_ingredient(self, ingr_text: str) -> list[dict]:
        """성분 텍스트로 Supabase DUR 조회 (검색 결과 형식)"""
        if not ingr_text:
            return []

        ingr_list = [i.strip() for i in ingr_text.replace(',', '/').split('/') if len(i.strip()) > 1]
        raw_data = await self._fetch_raw_dur(ingr_list)

        return [
            {
                "type": d['dur_type'],
                "ingr_name": d['ingr_kor_name'],
                "warning_msg": d['prohbt_content'] or d['remark'],
                "severity": d['critical_value'],
            }
            for d in raw_data
        ]

    async def get_enriched_dur(self, ingr_name: str) -> list[dict]:
        """단일 성분에 대해 Supabase DUR 조회 및 그룹화"""
        if not ingr_name:
            return []

        target = ingr_name.strip()
        if not target:
            return []

        client = self.get_client()
        if not client:
            return []

        dur_list = []
        try:
            is_korean = bool(re.search('[가-힣]', target))
            if is_korean:
                response = client.table("dur_master") \
                    .select("*") \
                    .ilike("ingr_kor_name", f"%{target}%") \
                    .execute()
            else:
                response = client.table("dur_master") \
                    .select("*") \
                    .ilike("ingr_eng_name", f"%{target.lower()}%") \
                    .execute()
            dur_list = response.data
        except Exception as e:
            logger.error(f"[Supabase] DUR 조회 오류 ('{target}'): {e}")
            return []

        return self._group_and_translate(dur_list)

    def _group_and_translate(self, dur_list: list[dict]) -> list[dict]:
        """DUR 목록 그룹화 및 한국어 변환"""
        DUR_TYPE_KOR_MAP = {
            "PREGNANCY": "임부 금기/주의", "COMBINED": "병용 금기",
            "AGE_SPECIFIC": "연령 금기", "ELDERLY": "노인 주의",
            "MAX_CAPACITY": "용량 주의", "MAX_DURATION": "투여 기간 주의",
            "EFFICACY_DUPLICATE": "효능 중복 주의", "DOSAGE_DUPLICATE": "용법 주의",
            "ADMINISTRATION_DUPLICATE": "투여 경로 주의", "LACTATION": "수유부 주의",
            "WEIGHT": "체중 주의", "KIDNEY": "신장 질환 주의",
            "LIVER": "간 질환 주의", "G6PD": "특정 효소 결핍 주의",
            "PEDIATRIC": "소아 주의",
        }

        grouped: dict[str, dict] = {}
        for d in dur_list:
            d_type = d['dur_type']
            kor_type = DUR_TYPE_KOR_MAP.get(d_type, d_type)
            content = (d.get('prohbt_content') or d.get('remark') or "").strip()
            if not content:
                continue
            if kor_type not in grouped:
                grouped[kor_type] = {"type": kor_type, "kor_name": d['ingr_kor_name'], "warnings": set()}
            grouped[kor_type]["warnings"].add(content)

        return [
            {
                "type": val["type"],
                "kor_name": val["kor_name"],
                "warning": "\n".join(sorted(val["warnings"])),
            }
            for val in grouped.values()
        ]

    async def _fetch_raw_dur(self, ingr_list: list[str]) -> list[dict]:
        client = self.get_client()
        if not client:
            return []

        all_results = []
        for ingr in ingr_list:
            target = ingr.strip()
            try:
                if bool(re.search('[가-힣]', target)):
                    response = client.table("dur_master").select("*").ilike("ingr_kor_name", f"%{target}%").execute()
                else:
                    response = client.table("dur_master").select("*").ilike("ingr_eng_name", f"%{target.lower()}%").execute()
                if response.data:
                    all_results.extend(response.data)
            except Exception as e:
                logger.error(f"[Supabase] 배치 DUR 조회 오류 ('{target}'): {e}")

        return all_results

    # ─── 캐시 CRUD ─────────────────────────────────────────────────────────────

    async def get_symptom_cache(self, query_text: str) -> dict | None:
        client = self.get_client()
        if not client:
            return None
        try:
            response = client.table("search_cache").select("*").eq("query_text", query_text).limit(1).execute()
            if response.data:
                logger.info(f"[Cache Hit] query='{query_text}'")
                return response.data[0]
        except Exception as e:
            logger.error(f"[Cache] 조회 오류 ('{query_text}'): {e}")
        return None

    async def set_symptom_cache(
        self, query_text: str, category: str,
        fda_data: list, dur_data: list,
        final_answer: str, recommended_ingredients: list
    ) -> bool:
        client = self.get_client()
        if not client:
            return False
        try:
            payload = {
                "query_text": query_text,
                "category": category,
                "fda_data": fda_data or [],
                "dur_data": dur_data or [],
                "final_answer": final_answer,
                "recommended_ingredients": recommended_ingredients or [],
            }
            client.table("search_cache").upsert(payload, on_conflict="query_text").execute()
            logger.info(f"[Cache Saved] query='{query_text}'")
            return True
        except Exception as e:
            logger.error(f"[Cache] 저장 오류 ('{query_text}'): {e}")
            return False

    async def get_roadmap_cache(self, query_text: str) -> dict | None:
        client = self.get_client()
        if not client:
            return None
        try:
            response = client.table("roadmap_cache").select("*").eq("query_text", query_text).limit(1).execute()
            if response.data:
                logger.info(f"[Roadmap Cache Hit] query='{query_text}'")
                return response.data[0]
        except Exception as e:
            logger.error(f"[Roadmap Cache] 조회 오류 ('{query_text}'): {e}")
        return None

    async def set_roadmap_cache(
        self, query_text: str, mapping_result: dict,
        pharmacist_card: dict, dosage_warnings: list
    ) -> bool:
        client = self.get_client()
        if not client:
            return False
        try:
            payload = {
                "query_text": query_text,
                "mapping_result": mapping_result or {},
                "pharmacist_card": pharmacist_card or {},
                "dosage_warnings": dosage_warnings or [],
            }
            client.table("roadmap_cache").insert(payload).execute()
            logger.info(f"[Roadmap Cache Saved] query='{query_text}'")
            return True
        except Exception as e:
            logger.error(f"[Roadmap Cache] 저장 오류 ('{query_text}'): {e}")
            return False
