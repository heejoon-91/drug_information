import os
import asyncio
from supabase import create_client, Client
from services.ai_service import AIService

class SupabaseService:
    _client = None

    @classmethod
    def get_client(cls) -> Client:
        if cls._client:
            return cls._client
        
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        
        if not url or not key:
            print("Error: SUPABASE_URL and SUPABASE_KEY must be set in .env")
            return None
            
        cls._client = create_client(url, key)
        return cls._client

    @classmethod
    async def get_dur_by_ingr(cls, ingr_text: str):
        """
        [DrugService.get_dur_by_ingr 대체]
        제품 검색 시 성분 텍스트(예: "Acetaminophen, Caffeine")로 DUR 조회
        """
        if not ingr_text:
            return []
            
        # Parse ingredients
        ingr_list = [i.strip() for i in ingr_text.replace(',', '/').split('/') if len(i.strip()) > 1]
        
        # Use common logic
        dur_data = await cls._get_dur_data_from_supabase(ingr_list)
        
        # Convert to expected format for search_result.html
        # Expected: { "type", "ingr_name", "warning_msg", "severity" }
        results = []
        for d in dur_data:
            results.append({
                "type": d['dur_type'],
                "ingr_name": d['ingr_kor_name'],
                "warning_msg": d['prohbt_content'] or d['remark'],
                "severity": d['critical_value']
            })
        return results

    @classmethod
    async def get_enriched_dur_info(cls, ingr_list: list):
        """
        [DrugService.get_enriched_dur_info 대체]
        LangGraph 등에서 사용하는 상세 정보 조회 (FDA Warning + DUR)
        """
        # 1. 고유 성분명으로 정리
        unique_ingrs = sorted(list(set([i.upper() for i in ingr_list])))
        enriched_data = []
        
        # DrugService uses DrugService.get_fda_warnings_by_ingr(ingr)
        # We need to import DrugService to reuse FDA part? 
        # Or just reimplement/import strictly.
        # Since we are monkey-patching DrugService, calling DrugService inside here might be recursive if not careful.
        # But FDA part in DrugService is fine to reuse if we didn't patch it.
        # Wait, if we patch DrugService methods, we overwrite them.
        # So we should copy FDA logic here or keep FDA logic in DrugService and ONLY patch DUR methods.
        
        # Strategy: We will ONLY patch 'get_dur_by_ingr' and 'get_enriched_dur_info'.
        # But 'get_enriched_dur_info' calls 'get_fda_warnings_by_ingr'.
        # If we patch 'get_enriched_dur_info', we can call 'DrugService.get_fda_warnings_by_ingr' provided we didn't patch THAT one.
        
        # However, to avoid circular imports or issues, let's just use httpx for FDA directly or assume DrugService.get_fda_warnings_by_ingr is available.
        # Actually, best validation is to look at DrugService.
        from services.drug_service import DrugService as OriginalDrugService

        for ingr in unique_ingrs:
            # 2. KR DUR 조회 (Supabase)
            durs = await cls._get_kr_durs_supabase(ingr)
            
            # 3. FDA Warning 조회 (Reuse existing logic)
            fda_warn = await OriginalDrugService.get_fda_warnings_by_ingr(ingr)
            
            if fda_warn:
                summary = await AIService.summarize_fda_warning(fda_warn)
                if summary:
                    fda_warn = summary
            
            enriched_data.append({
                "ingredient": ingr,
                "kr_durs": durs,
                "fda_warning": fda_warn
            })
            
        return enriched_data

    @classmethod
    async def _get_kr_durs_supabase(cls, ingr_name):
        """
        단일 성분에 대해 Supabase DUR 조회 및 그룹화 (DrugService._get_kr_durs_async 로직 재현)
        """
        if not ingr_name: return []
        
        # Clean
        target_name = ingr_name.strip().lower()
        if not target_name: return []

        # (Synonyms logic omitted for brevity, or can be added if needed. Supabase has limited "OR" querying flexibility compared to Django Q objects)
        # For this version, we stick to simple ILIKE matching
        
        client = cls.get_client()
        if not client: return []

        dur_list = []
        try:
           response = client.table("dur_master") \
               .select("*") \
               .ilike("ingr_eng_name", f"%{target_name}%") \
               .execute()
           dur_list = response.data
        except Exception as e:
            print(f"[Supabase] Error: {e}")
            return []
            
        # Group & Translation Logic (Copied from DrugService)
        DUR_TYPE_KOR_MAP = {
            "PREGNANCY": "임부 금기/주의",
            "COMBINED": "병용 금기",
            "AGE_SPECIFIC": "연령 금기",
            "ELDERLY": "노인 주의",
            "MAX_CAPACITY": "용량 주의",
            "MAX_DURATION": "투여 기간 주의",
            "EFFICACY_DUPLICATE": "효능 중복 주의",
            "DOSAGE_DUPLICATE": "용법 주의",
            "ADMINISTRATION_DUPLICATE": "투여 경로 주의",
            "LACTATION": "수유부 주의",
            "WEIGHT": "체중 주의",
            "KIDNEY": "신장 질환 주의",
            "LIVER": "간 질환 주의",
            "G6PD": "특정 효소 결핍 주의",
            "PEDIATRIC": "소아 주의",
        }
        
        grouped_results = {}
        for d in dur_list:
            d_type = d['dur_type']
            kor_type = DUR_TYPE_KOR_MAP.get(d_type, d_type)
            content = (d['prohbt_content'] or d['remark'] or "").strip()
            
            if not content: continue
            
            if kor_type not in grouped_results:
                grouped_results[kor_type] = {
                    "type": kor_type,
                    "original_type": d_type,
                    "kor_name": d['ingr_kor_name'],
                    "warnings": set()
                }
            grouped_results[kor_type]["warnings"].add(content)
            
        results = []
        for key, val in grouped_results.items():
            combined_warning = "\n".join(sorted(list(val["warnings"])))
            results.append({
                "type": val["type"],
                "kor_name": val["kor_name"],
                "warning": combined_warning
            })
            
        return results

    @classmethod
    async def _get_dur_data_from_supabase(cls, ingr_list: list):
        """
        Helper to get raw DUR data from Supabase for multiple ingredients
        """
        client = cls.get_client()
        if not client: return []
        
        all_results = []
        for ingr in ingr_list:
            if not ingr: continue
            try:
                response = client.table("dur_master") \
                    .select("*") \
                    .ilike("ingr_eng_name", f"%{ingr.strip()}%") \
                    .execute()
                if response.data:
                    all_results.extend(response.data)
            except Exception as e:
                print(f"[Supabase] Batch Error: {e}")
                
        return all_results
