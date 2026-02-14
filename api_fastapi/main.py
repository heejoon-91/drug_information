import os, sys, django
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

app = FastAPI()
templates = Jinja2Templates(directory=os.path.join(current_dir, "templates"))

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/web-search/{drug_name}", response_class=HTMLResponse)
async def product_search(request: Request, drug_name: str):
    """1번 케이스: 특정 제품 검색"""
    fda = DrugService.search_fda(drug_name)
    if not fda: return HTMLResponse("<h1>FDA 정보를 찾을 수 없습니다.</h1>")
    
    kr_dur = await DrugService.get_dur_by_ingr(fda['ingredients'])
    return templates.TemplateResponse("search_result.html", {
        "request": request, "drug_name": drug_name, "ingredients": fda['ingredients'],
        "us_guideline": fda, "kr_dur": kr_dur, "dur_count": len(kr_dur)
    })

@app.get("/smart-search", response_class=HTMLResponse)
async def smart_search(request: Request, q: str):
    # 1. AI에게 질문의 의도를 물어봅니다.
    intent = await AIService.classify_intent(q)
    category = intent.get("category")
    
    print(f"--- [DEBUG] 분류 결과: {category} ---") # 터미널에서 확인용

    if category == "SYMPTOM_RELIEF":
        symptom = intent.get("symptom") or q
        # 2. 증상 기반 DB 데이터 추출
        raw_data = await DrugService.get_data_by_symptom(symptom)
        # 3. AI 답변 생성 (symptom_result.html로 이동)
        answer = await AIService.generate_symptom_answer(symptom, raw_data)
        
    # main.py의 SYMPTOM_RELIEF 분기 부분
    elif category == "SYMPTOM_RELIEF":
        symptom = intent.get("symptom") or q
        
        # 1. 증상을 영어 키워드로 변환 (LLM)
        eng_keywords = await AIService.translate_symptom_to_eng(symptom)
    
    # 2. FDA에서 관련 성분들 찾아오기 (FDA API)
    fda_ingrs = DrugService.get_ingredients_from_fda(eng_keywords)
    
    # 3. 찾은 성분들로 한국 DUR 정보 매핑 (Local DB)
    # 이 과정에서 영어 성분명을 한국어로 매핑하는 간단한 변환기가 필요할 수 있습니다.
    raw_dur_data = await DrugService.get_dur_by_ingr_list(fda_ingrs)
    
    # 4. 최종 AI 답변 생성
    answer = await AIService.generate_symptom_answer(symptom, raw_dur_data)
    
    return templates.TemplateResponse("symptom_result.html", {
        "request": request, "symptom": symptom, "answer": answer
    })

    # PRODUCT_SPECIFIC 이거나 분류에 실패한 경우 기존 제품 검색 실행
    drug_name = intent.get("target_drug") or q
    return await product_search(request, drug_name)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)