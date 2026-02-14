import os
import sys
import django
import requests
from fastapi import FastAPI, APIRouter, HTTPException
# [핵심] 비동기 환경에서 Django DB를 사용하기 위한 도구
from asgiref.sync import sync_to_async

from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request

templates = Jinja2Templates(directory="templates")

# 1. 경로 설정 및 Django 초기화
current_dir = os.path.abspath(os.path.dirname(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(os.path.join(project_root, 'backend_django'))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

# 2. 모델 임포트
try:
    from drugs.models import DurMaster, EYakInfo
    print("--- [DEBUG] Django Models Loaded Successfully ---")
except ImportError as e:
    print(f"--- [DEBUG] Import Error: {e} ---")
    raise

# 3. FastAPI 앱 및 라우터 정의
app = FastAPI(title="Global Drug Safety Search Engine")
router = APIRouter()

# 4. 서비스 클래스 정의
class GlobalDrugService:
    def __init__(self):
        self.fda_url = "https://api.fda.gov/drug/label.json"

    def search_fda_by_name(self, brand_name: str):
        params = {
            'search': f'openfda.brand_name:"{brand_name}"',
            'limit': 1
        }
        try:
            response = requests.get(self.fda_url, params=params, timeout=10)
            if response.status_code != 200:
                print(f"--- [DEBUG] FDA API Status: {response.status_code} ---")
                return None
            
            results = response.json().get('results', [])
            if not results:
                return None
            
            data = results[0]
            openfda = data.get('openfda', {})
            ingr_list = openfda.get('generic_name', [])
            if not ingr_list:
                ingr_list = data.get('active_ingredient', [])
            
            ingr_text = ", ".join(ingr_list) if isinstance(ingr_list, list) else str(ingr_list)
            
            return {
                "brand_name": brand_name,
                "active_ingredients": ingr_text or "Ingredient Not Found",
                "indications": data.get('indications_and_usage', ["Indications not provided"])[0],
                "warnings": data.get('warnings', ["Warnings not provided"])[0],
                "dosage": data.get('dosage_and_administration', ["Dosage info not provided"])[0]
            }
        except Exception as e:
            print(f"--- [DEBUG] FDA Parsing Error: {e} ---")
            return None

    # [수정] DB 조회 로직 분리 (sync_to_async 처리를 위해)
    def _fetch_korean_dur_sync(self, ingredient_en: str):
        if not ingredient_en:
            return []
        from django.db.models import Q
        query = Q()
        # 여러 성분이 콤마로 구분되어 올 경우를 대비
        for ingr in ingredient_en.replace(',', '/').split('/'):
            target = ingr.strip().lower()
            if len(target) > 1:
                query |= Q(ingr_eng_name__icontains=target)
        
        # [핵심] list()로 감싸서 쿼리셋을 즉시 실행(Evaluate)해야 에러가 안 납니다.
        durs = list(DurMaster.objects.filter(query))
        
        return [
            {
                "type": d.dur_type,
                "ingr_name": d.ingr_kor_name,
                "warning_msg": d.prohbt_content or d.remark,
                "severity": d.critical_value
            } for d in durs
        ]

# 5. API 엔드포인트 정의
@router.get("/global-search/{drug_name}")
async def global_drug_search(drug_name: str):
    service = GlobalDrugService()
    
    # 1. FDA API 호출
    fda_result = service.search_fda_by_name(drug_name)
    if not fda_result:
        raise HTTPException(status_code=404, detail="미국 FDA에서 정보를 찾을 수 없습니다.")
    
    # [수정] 2. 한국 DUR 조회를 비동기로 전환 (sync_to_async 적용)
    # thread_sensitive=True를 주어 Django DB 연결을 안전하게 관리합니다.
    get_dur_async = sync_to_async(service._fetch_korean_dur_sync, thread_sensitive=True)
    kr_dur_result = await get_dur_async(fda_result['active_ingredients'])
    
    return {
        "status": "success",
        "origin": "USA",
        "drug_identity": {
            "name": fda_result['brand_name'],
            "ingredients": fda_result['active_ingredients']
        },
        "us_guideline": {
            "purpose": fda_result['indications'],
            "fda_warnings": fda_result['warnings']
        },
        "kr_safety_standard": {
            "dur_count": len(kr_dur_result),
            "dur_details": kr_dur_result
        }
    }

# 웹 브라우저 화면용 경로
@app.get("/web-search/{drug_name}", response_class=HTMLResponse)
async def web_search(request: Request, drug_name: str):
    service = GlobalDrugService()
    
    # 1. 미국 정보 가져오기
    fda_result = service.search_fda_by_name(drug_name)
    if not fda_result:
        return HTMLResponse("<h1>FDA 정보를 찾을 수 없습니다.</h1>")
    
    # 2. 한국 DUR 정보 가져오기
    get_dur_async = sync_to_async(service._fetch_korean_dur_sync, thread_sensitive=True)
    kr_dur_result = await get_dur_async(fda_result['active_ingredients'])
    
    # 3. HTML 템플릿 파일(search_result.html)에 데이터 채워서 보내기
    return templates.TemplateResponse("search_result.html", {
        "request": request,
        "drug_name": drug_name,
        "ingredients": fda_result['active_ingredients'],
        "us_guideline": fda_result,
        "kr_dur": kr_dur_result,
        "dur_count": len(kr_dur_result)
    })
    
# 6. 라우터 등록 및 서버 실행
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)