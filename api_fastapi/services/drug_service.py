import requests
from asgiref.sync import sync_to_async
from django.db.models import Q

class DrugService:
    @staticmethod
    def search_fda(name: str):
        """특정 제품명으로 FDA 정보 검색"""
        url = f"https://api.fda.gov/drug/label.json?search=openfda.brand_name:\"{name}\"&limit=1"
        try:
            res = requests.get(url, timeout=10)
            if res.status_code != 200: return None
            data = res.json()['results'][0]
            openfda = data.get('openfda', {})
            return {
                "brand_name": name,
                "ingredients": ", ".join(openfda.get('generic_name', ["N/A"])),
                "indications": data.get('indications_and_usage', ["N/A"])[0],
                "warnings": data.get('warnings', ["N/A"])[0],
                "dosage": data.get('dosage_and_administration', ["N/A"])[0]
            }
        except: return None

    @staticmethod
    def get_ingrs_from_fda_by_symptoms(keywords: list):
        """영어 증상 키워드로 FDA 관련 성분명 추출"""
        all_ingrs = set()
        for kw in keywords:
            url = f"https://api.fda.gov/drug/label.json?search=indications_and_usage:{kw}&limit=3"
            try:
                res = requests.get(url, timeout=5)
                if res.status_code == 200:
                    for item in res.json().get('results', []):
                        ingrs = item.get('openfda', {}).get('generic_name', [])
                        for i in ingrs: all_ingrs.add(i.upper())
            except: continue
        return list(all_ingrs)

    @staticmethod
    @sync_to_async
    def get_dur_by_ingr(ingr_text):
        """제품 검색 시 성분 텍스트로 한국 DUR 조회"""
        from drugs.models import DurMaster
        query = Q()
        for i in ingr_text.replace(',', '/').split('/'):
            if len(i.strip()) > 1:
                query |= Q(ingr_eng_name__icontains=i.strip().lower())
        durs = list(DurMaster.objects.filter(query))
        return [{
            "type": d.dur_type,
            "ingr_name": d.ingr_kor_name,
            "warning_msg": d.prohbt_content or d.remark
        } for d in durs]

    @staticmethod
    @sync_to_async
    def get_dur_by_english_ingr_list(ingr_list):
        """영어 성분명 리스트를 한국 DUR 데이터와 매핑"""
        from drugs.models import DurMaster
        query = Q()
        for eng_name in ingr_list:
            clean_name = eng_name.split()[0].lower() # 'IBUPROFEN TABLET' -> 'ibuprofen'
            query |= Q(ingr_eng_name__icontains=clean_name)
        
        durs = list(DurMaster.objects.filter(query))
        return [{
            "ingredient": d.ingr_kor_name,
            "type": d.dur_type,
            "warning": d.prohbt_content or d.remark
        } for d in durs]