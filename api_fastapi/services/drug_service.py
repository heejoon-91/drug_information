from asgiref.sync import sync_to_async
from django.db.models import Q
import requests

class DrugService:
    @staticmethod
    def search_fda(name: str):
        """미국 FDA API 호출"""
        url = f"https://api.fda.gov/drug/label.json?search=openfda.brand_name:\"{name}\"&limit=1"
        try:
            res = requests.get(url, timeout=10)
            if res.status_code != 200: return None
            data = res.json()['results'][0]
            openfda = data.get('openfda', {})
            return {
                "name": name,
                "ingredients": ", ".join(openfda.get('generic_name', ["N/A"])),
                "indications": data.get('indications_and_usage', ["N/A"])[0],
                "warnings": data.get('warnings', ["N/A"])[0],
                "dosage": data.get('dosage_and_administration', ["N/A"])[0]
            }
        except: return None

    @staticmethod
    @sync_to_async
    def get_data_by_symptom(keyword):
        """증상(Efficacy)으로 성분 및 DUR 추출"""
        from drugs.models import EYakInfo, DurMaster
        # 1. 증상이 포함된 약 찾기
        related_drugs = EYakInfo.objects.filter(efficacy__icontains=keyword)[:10]
        
        # 2. 고유 성분 추출
        unique_ingrs = set()
        for d in related_drugs:
            for i in d.main_ingr_name.replace(',', '/').split('/'):
                if len(i.strip()) > 1: unique_ingrs.add(i.strip())
        
        # 3. 성분별 DUR 매핑
        result = []
        for ingr in unique_ingrs:
            durs = DurMaster.objects.filter(ingr_kor_name__icontains=ingr)
            result.append({
                "ingredient": ingr,
                "dur_info": [{"type": d.dur_type, "warning": d.prohbt_content or d.remark} for d in durs]
            })
        return result

    @staticmethod
    @sync_to_async
    def get_dur_by_ingr(ingr_text):
        """특정 성분의 DUR 목록 추출"""
        from drugs.models import DurMaster
        query = Q()
        for i in ingr_text.replace(',', '/').split('/'):
            if len(i.strip()) > 1: query |= Q(ingr_eng_name__icontains=i.strip().lower())
        
        durs = list(DurMaster.objects.filter(query))
        return [{
            "type": d.dur_type,
            "ingr_name": d.ingr_kor_name,
            "warning_msg": d.prohbt_content or d.remark or "상세 주의사항 없음"
        } for d in durs]

# api_fastapi/services/drug_service.py 내부에 추가

class DrugService:
    @staticmethod
    def get_ingredients_from_fda(eng_keywords: list):
        """영어 증상 키워드로 FDA에서 관련 성분명 추출"""
        unique_ingredients = set()
        for kw in eng_keywords:
            url = f"https://api.fda.gov/drug/label.json?search=indications_and_usage:{kw}&limit=5"
            try:
                res = requests.get(url, timeout=5)
                if res.status_code == 200:
                    results = res.json().get('results', [])
                    for item in results:
                        ingrs = item.get('openfda', {}).get('generic_name', [])
                        for i in ingrs: unique_ingredients.add(i.upper())
            except: continue
        return list(unique_ingredients) # ['IBUPROFEN', 'ACETAMINOPHEN']