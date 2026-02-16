import os
import sys
import django
import logging
from dotenv import load_dotenv

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 1. Django 초기화 및 환경변수 로드
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(os.path.join(project_root, 'backend_django'))

# .env 파일 명시적 로드
env_path = os.path.join(project_root, '.env')
load_dotenv(env_path)
logger.info(f"Loading .env from: {env_path}")

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from fastapi import FastAPI, Request, HTTPException, APIRouter
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

# 2. 서비스 로드
from services.drug_service import DrugService
from services.ai_service import AIService

app = FastAPI(title="Global Drug Safety Intelligence")
templates = Jinja2Templates(directory=os.path.join(current_dir, "templates"))
router = APIRouter()

@app.on_event("startup")
async def startup_event():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("CRITICAL: OPENAI_API_KEY is missing! Chatbot features will not work.")
    else:
        logger.info(f"OPENAI_API_KEY loaded successfully. (Starts with: {api_key[:7]}...)")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/web-search/{drug_name}", response_class=HTMLResponse)
async def product_search(request: Request, drug_name: str):
    """제품명 기반 검색 (웹 화면용)"""
    # 비동기 서비스 호출
    logger.info(f"Searching FDA for Product: {drug_name}")
    fda_result = await DrugService.search_fda(drug_name)
    
    if not fda_result:
        return templates.TemplateResponse("error.html", {
            "request": request, "message": f"'{drug_name}' 정보를 FDA에서 찾을 수 없습니다."
        })
    
    kr_dur = await DrugService.get_dur_by_ingr(fda_result['active_ingredients'])
    
    return templates.TemplateResponse("search_result.html", {
        "request": request, 
        "drug_name": drug_name, 
        "ingredients": fda_result['active_ingredients'],
        "us_guideline": fda_result, 
        "kr_dur": kr_dur, 
        "dur_count": len(kr_dur)
    })

@app.get("/smart-search", response_class=HTMLResponse)
async def smart_search(request: Request, q: str):
    """지능형 RAG 검색 (증상 -> 영어 쿼리 -> FDA -> DUR)"""
    if not q: return HTMLResponse("<script>alert('검색어를 입력하세요.'); history.back();</script>")

    logger.info(f"User Query: {q}")

    # STEP 1: AI 의도 분류
    intent = await AIService.classify_intent(q)
    logger.info(f"Classified Intent: {intent}")

    
    category = intent.get("category")
    if category == "SYMPTOM_RELIEF":
        symptom = intent.get("symptom") or q
        eng_kw = intent.get("fda_search_keywords", ["pain"])
        logger.info(f"Processing Symptom: {symptom}, Keywords: {eng_kw}")

        
        # STEP 2: FDA 관련 성분 추출 (비동기)
        fda_ingrs = await DrugService.get_ingrs_from_fda_by_symptoms(eng_kw)
        
        # STEP 3: 성분 -> DUR 매핑 (FDA 정보 포함)
        dur_data = await DrugService.get_enriched_dur_info(fda_ingrs)
        
        # AI 답변 생성을 위한 요약 데이터 생성
        summary_for_ai = []
        for item in dur_data:
            summary = f"Ingredient: {item['ingredient']}\n"
            summary += f"FDA Warning: {item['fda_warning'][:200] if item['fda_warning'] else 'None'}\n"
            kr_warnings = [f"{d['type']}: {d['warning']}" for d in item['kr_durs']]
            summary += f"KR DUR: {', '.join(kr_warnings)}"
            summary_for_ai.append(summary)
        
        # STEP 4: 답변 생성
        answer = await AIService.generate_symptom_answer(symptom, "\n---\n".join(summary_for_ai))
        
        return templates.TemplateResponse("symptom_result.html", {
            "request": request, 
            "symptom": symptom, 
            "answer": answer,
            "dur_details": dur_data  # 팝업용 상세 데이터 전달
        })

    # 제품 검색 혹은 일반 상담
    target = intent.get("target_drug") or q
    return await product_search(request, target)

# API 엔드포인트 (JSON 반환용)
@router.get("/global-search/{drug_name}")
async def global_drug_search(drug_name: str):
    fda_result = await DrugService.search_fda(drug_name)
    if not fda_result:
        raise HTTPException(status_code=404, detail="FDA info not found")
    
    kr_dur_result = await DrugService.get_dur_by_ingr(fda_result['active_ingredients'])
    
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

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)