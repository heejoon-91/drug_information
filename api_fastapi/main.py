import os
import sys
import django
import json
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

# 1. Django 초기화
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(os.path.join(project_root, 'backend_django'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

# 2. 서비스 로드
from services.drug_service import DrugService
from services.ai_service import AIService

app = FastAPI(title="Global Drug Safety Intelligence")
templates = Jinja2Templates(directory=os.path.join(current_dir, "templates"))

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/web-search/{drug_name}", response_class=HTMLResponse)
async def product_search(request: Request, drug_name: str):
    """제품명 기반 검색"""
    fda_result = DrugService.search_fda(drug_name)
    if not fda_result:
        return templates.TemplateResponse("error.html", {
            "request": request, "message": f"'{drug_name}' 정보를 FDA에서 찾을 수 없습니다."
        })
    
    kr_dur = await DrugService.get_dur_by_ingr(fda_result['ingredients'])
    return templates.TemplateResponse("search_result.html", {
        "request": request, "drug_name": drug_name, "ingredients": fda_result['ingredients'],
        "us_guideline": fda_result, "kr_dur": kr_dur, "dur_count": len(kr_dur)
    })

@app.get("/smart-search", response_class=HTMLResponse)
async def smart_search(request: Request, q: str):
    """지능형 RAG 검색 (증상 -> 영어 쿼리 -> FDA -> DUR)"""
    if not q: return HTMLResponse("<script>alert('검색어를 입력하세요.'); history.back();</script>")

    # STEP 1: AI 의도 분류 및 영어 검색 키워드 확보
    intent = await AIService.classify_intent(q)
    category = intent.get("category")

    if category == "SYMPTOM_RELIEF":
        symptom = intent.get("symptom") or q
        # LLM이 생성한 영어 키워드 사용 (예: ["headache", "fever"])
        eng_kw = intent.get("fda_search_keywords", ["pain"])
        
        # STEP 2: FDA에서 관련 영어 성분 추출
        fda_ingrs = DrugService.get_ingrs_from_fda_by_symptoms(eng_kw)
        
        # STEP 3: 영어 성분 -> 한국 DUR 매핑
        dur_data = await DrugService.get_dur_by_english_ingr_list(fda_ingrs)
        
        # STEP 4: 최종 답변 생성
        answer = await AIService.generate_symptom_answer(symptom, dur_data)
        
        return templates.TemplateResponse("symptom_result.html", {
            "request": request, "symptom": symptom, "answer": answer
        })

    # 제품 검색 혹은 일반 상담
    target = intent.get("target_drug") or q
    return await product_search(request, target)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)