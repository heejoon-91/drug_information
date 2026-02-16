import httpx
from asgiref.sync import sync_to_async
from django.db.models import Q
import asyncio

class DrugService:
    FDA_BASE_URL = "https://api.fda.gov/drug/label.json"
    
    # 성분명 매핑 테이블 (FDA generic_name -> KR DUR ingr_eng_name)
    MANUAL_INGR_MAPPING = {
        "DIVALPROEX SODIUM": "VALPROIC ACID",
        "DIVALPROEX": "VALPROIC ACID",
        # 필요 시 추가
    }

    @classmethod
    async def search_fda(cls, name: str):
        """
        특정 제품명으로 FDA 정보 검색 (비동기)
        상세 정보(적응증, 경고, 용법)를 포함하여 반환
        """
        params = {
            'search': f'openfda.brand_name:"{name}"',
            'limit': 1
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                res = await client.get(cls.FDA_BASE_URL, params=params)
                if res.status_code != 200:
                    return None
                
                data = res.json().get('results', [])
                if not data:
                    return None
                
                result = data[0]
                openfda = result.get('openfda', {})
                
                # 성분명 추출 (generic_name, substance_name 모두 포함)
                # substance_name이 DUR DB의 'Active Moiety'와 일치할 확률이 높음 (예: DIVALPROEX -> VALPROIC ACID)
                generic_names = openfda.get('generic_name', [])
                substance_names = openfda.get('substance_name', [])
                
                combined_ingrs = list(set(generic_names + substance_names))
                
                if not combined_ingrs:
                    combined_ingrs = result.get('active_ingredient', [])
                
                ingr_text = ", ".join(combined_ingrs) if isinstance(combined_ingrs, list) else str(combined_ingrs)

                return {
                    "brand_name": name,
                    "active_ingredients": ingr_text or "Ingredient Not Found",
                    "ingredients": ingr_text, # 호환성을 위해 유지
                    "indications": result.get('indications_and_usage', ["Indications not provided"])[0],
                    "warnings": result.get('warnings', ["Warnings not provided"])[0],
                    "dosage": result.get('dosage_and_administration', ["Dosage info not provided"])[0]
                }
            except Exception as e:
                print(f"Error searching FDA: {e}")
                return None

    @classmethod
    async def get_ingrs_from_fda_by_symptoms(cls, keywords: list):
        """
        영어 증상 키워드로 FDA 관련 성분명 추출 (비동기 + 병렬 처리)
        """
        all_ingrs = set()
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            tasks = []
            for kw in keywords:
                url = f"{cls.FDA_BASE_URL}?search=indications_and_usage:{kw}&limit=3"
                tasks.append(client.get(url))
            
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            for res in responses:
                if isinstance(res, httpx.Response) and res.status_code == 200:
                    try:
                        results = res.json().get('results', [])
                        for item in results:
                            openfda = item.get('openfda', {})
                            # generic_name과 substance_name 모두 수집
                            generics = openfda.get('generic_name', [])
                            substances = openfda.get('substance_name', [])
                            
                            for i in generics + substances:
                                all_ingrs.add(i.upper())
                    except:
                        continue
                        
        return list(all_ingrs)

    @staticmethod
    @sync_to_async
    def get_dur_by_ingr(ingr_text):
        """제품 검색 시 성분 텍스트로 한국 DUR 조회"""
        from drugs.models import DurMaster
        if not ingr_text:
            return []
            
        query = Q()
        for i in ingr_text.replace(',', '/').split('/'):
            target = i.strip().lower()
            if len(target) > 1:
                query |= Q(ingr_eng_name__icontains=target)
        
        # 쿼리셋 평가를 위해 list()로 변환
        durs = list(DurMaster.objects.filter(query))
        
        return [{
            "type": d.dur_type,
            "ingr_name": d.ingr_kor_name,
            "warning_msg": d.prohbt_content or d.remark,
            "severity": d.critical_value
        } for d in durs]

    @classmethod
    async def get_fda_warnings_by_ingr(cls, ingr_name: str):
        """
        성분명으로 FDA 경고(Warnings) 정보 조회
        """
        params = {
            'search': f'openfda.generic_name:"{ingr_name}"',
            'limit': 1
        }
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                res = await client.get(cls.FDA_BASE_URL, params=params)
                if res.status_code == 200:
                    data = res.json().get('results', [])
                    if data:
                        return data[0].get('warnings', ["No FDA warning found."])[0]
            except Exception:
                pass
        return None

    @classmethod
    async def get_enriched_dur_info(cls, ingr_list: list):
        """
        영어 성분명 리스트를 받아 KR DUR 및 FDA Warning 정보를 병합하여 반환
        """
        from drugs.models import DurMaster
        enriched_data = []

        # 1. 고유 성분명으로 정리
        unique_ingrs = sorted(list(set([i.upper() for i in ingr_list])))

        for ingr in unique_ingrs:
            # 2. KR DUR 조회 (동기 DB 호출을 비동기로 래핑해야 함 - 여기서는 sync_to_async 사용 권장되지만, loop 내 호출이므로 주의)
            # 성능을 위해 전체 쿼리를 먼저 하고 매핑하는 것이 좋지만, 일단 간단 구현
            durs = await cls._get_kr_durs_async(ingr)
            
            # 3. FDA Warning 조회
            fda_warn = await cls.get_fda_warnings_by_ingr(ingr)
            
            enriched_data.append({
                "ingredient": ingr,
                "kr_durs": durs,
                "fda_warning": fda_warn
            })
            
        return enriched_data

    @classmethod
    @sync_to_async
    def _get_kr_durs_async(cls, ingr_name):
        """비동기 문맥에서 DB 호출을 위한 헬퍼"""
        from drugs.models import DurMaster
        
        # 매핑 적용 (수동 매핑은 제거하고 FDA 데이터에 의존)
        # upper_name = ingr_name.upper()
        # target_name = cls.MANUAL_INGR_MAPPING.get(upper_name, upper_name)
        
        clean_name = ingr_name.split()[0].lower() # target_name -> ingr_name
        if not clean_name: return []
        
        durs = DurMaster.objects.filter(ingr_eng_name__icontains=clean_name)
        return [{
            "type": d.dur_type,
            "kor_name": d.ingr_kor_name,
            "warning": d.prohbt_content or d.remark
        } for d in durs]

    @staticmethod
    @sync_to_async
    def get_dur_by_english_ingr_list(ingr_list):
        """(Legacy) 영어 성분명 리스트를 한국 DUR 데이터와 매핑"""
        from drugs.models import DurMaster
        if not ingr_list:
            return []

        query = Q()
        for eng_name in ingr_list:
            clean_name = eng_name.split()[0].lower()
            if clean_name:
                query |= Q(ingr_eng_name__icontains=clean_name)
        
        durs = list(DurMaster.objects.filter(query))
        return [{
            "ingredient": d.ingr_kor_name,
            "type": d.dur_type,
            "warning": d.prohbt_content or d.remark
        } for d in durs]