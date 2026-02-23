import logging
from .state import AgentState
from services.ai_service_v2 import AIService
from services.drug_service import DrugService

logger = logging.getLogger(__name__)

async def classify_node(state: AgentState) -> AgentState:
    """Classify user query and extract keywords"""
    query = state["query"]
    intent = await AIService.classify_intent(query)
    
    category = intent.get("category", "invalid")
    keyword = intent.get("keyword", "")
    
    # Validation logic
    if category == "symptom_recommendation":
        symptom = query
    else:
        symptom = None
        
    return {
        "category": category,
        "keyword": keyword,
        "symptom": symptom
    }

async def retrieve_fda_node(state: AgentState) -> AgentState:
    """Retrieve FDA data based on category"""
    category = state["category"]
    keyword = state["keyword"]
    query = state["query"]
    
    fda_data = None
    
    if category == "symptom_recommendation":
        # Symptom search logic
        eng_kw = [keyword] if keyword and keyword != "none" else ["pain"]
        fda_ingrs = await DrugService.get_ingrs_from_fda_by_symptoms(eng_kw)
        
        # [Agentic Fallback]
        # FDA 검색 결과가 없으면, AI에게 성분 추천을 요청하여 DUR 검사를 진행할 수 있도록 함
        if not fda_ingrs:
            logger.info(f"FDA search failed for '{keyword}'. Requesting AI recommendation.")
            fda_ingrs = await AIService.recommend_ingredients_for_symptom(keyword or query)
            logger.info(f"AI recommended ingredients: {fda_ingrs}")
            
        fda_data = fda_ingrs # Store ingredients list
        
    elif category == "product_request":
        # Product search logic
        target = keyword if keyword and keyword != "none" else query
        fda_result = await DrugService.search_fda(target)
        fda_data = fda_result # Store full dict
        
    return {"fda_data": fda_data}

async def retrieve_dur_node(state: AgentState) -> AgentState:
    """Retrieve DUR data based on FDA ingredients"""
    category = state["category"]
    fda_data = state["fda_data"]
    
    dur_data = []
    
    if not fda_data:
        return {"dur_data": []}
        
    if category == "symptom_recommendation":
        # fda_data is list of ingredients
        if isinstance(fda_data, list):
            dur_data = await DrugService.get_enriched_dur_info(fda_data)
            
    elif category == "product_request":
        # fda_data is dict with 'active_ingredients'
        if isinstance(fda_data, dict):
            ingrs = fda_data.get('active_ingredients', '')
            dur_data = await DrugService.get_dur_by_ingr(ingrs)
            
    return {"dur_data": dur_data}

async def generate_symptom_answer_node(state: AgentState) -> AgentState:
    """Generate answer for symptom queries"""
    symptom = state["symptom"]
    dur_data = state["dur_data"]
    
    if not dur_data:
        # Fallback to general AI answer if DB search yields no results
        fallback_query = f"The user asked about '{symptom}' but I couldn't find specific drugs in the FDA/DUR database. Please provide general medical advice or common over-the-counter ingredients for this symptom. (User query: {state['query']})"
        answer = await AIService.generate_general_answer(fallback_query)
        prefix = "해당 증상에 대한 FDA/DUR 기반의 정확한 의약품 정보는 찾을 수 없었지만, 일반적인 정보를 안내해 드립니다.\n\n"
        return {"final_answer": prefix + answer}
        
    # [V2 최적화] JSON 원본 데이터를 그대로 AI에게 전달하여 사용자 특이사항 필터링
    ai_result = await AIService.generate_symptom_answer(symptom, dur_data, state.get("user_profile"))
    
    if isinstance(ai_result, dict):
        answer = ai_result.get("answer", "정보 처리에 문제가 발생했습니다.")
        safe_ingredients = ai_result.get("safe_ingredients", [])
        unsafe_ingredients = ai_result.get("unsafe_ingredients", [])
        
        print(f"AI Filtered Safe: {safe_ingredients}, Unsafe: {unsafe_ingredients}")
        
        # 필터링 짓거리를 버리고, LLM이 추천한 안전 성분으로 DB를 직접 조회 (이름 기반)
        filtered_dur = []
        if safe_ingredients:
            # 사용자 요구사항 반영: 성분명이 나오면 DB의 dur_master 테이블에서 검색하여 동일 성분명의 DUR 정보들을 다 출력
            filtered_dur = await DrugService.get_enriched_dur_info(safe_ingredients)
            
        # 보정: DB 조회가 안됐거나 빈 값일 경우 최후의 수단으로 원본 데이터에서 unsafe만 제외
        if not filtered_dur and unsafe_ingredients:
            unsafe_lower = [u.lower() for u in unsafe_ingredients]
            filtered_dur = [
                d for d in dur_data 
                if not any(u in d.get('ingredient', '').lower() for u in unsafe_lower)
            ]
            
        # unsafe 목록도 없고 DB 매칭도 안 됐다면, 그냥 원본을 반환 (빈칸 방지)
        if not filtered_dur:
            filtered_dur = dur_data
    else:
        # Fallback (구 버전 호환성)
        answer = str(ai_result)
        filtered_dur = dur_data
    
    # [V2 최적화] 필터링된 안전망 원본 JSON 데이터를 State에 보존하여 UI 엔진으로 토스
    return {"final_answer": answer, "dur_data": filtered_dur, "fda_data": state["fda_data"]}

async def generate_product_answer_node(state: AgentState) -> AgentState:
    """Generate answer for product queries (simple format for now, or use AI?)"""
    fda_data = state["fda_data"]
    dur_data = state["dur_data"]
    
    if not fda_data:
        return {"final_answer": "해당 의약품 정보를 찾을 수 없습니다."}
        
    brand_name = fda_data.get('brand_name')
    indications = fda_data.get('indications')
    
    answer = f"**{brand_name}** 정보입니다.\n\n**효능/효과**:\n{indications}\n\n**DUR/주의사항**:\n"
    for d in dur_data:
        answer += f"- {d['ingr_name']} ({d['type']}): {d['warning_msg']}\n"
        
    return {"final_answer": answer}

async def generate_general_answer_node(state: AgentState) -> AgentState:
    """Generate answer for general medical queries"""
    query = state["query"]
    answer = await AIService.generate_general_answer(query)
    return {"final_answer": answer}

async def generate_error_node(state: AgentState) -> AgentState:
    """Handle invalid queries"""
    return {"final_answer": "죄송합니다. 질문을 이해하지 못하거나 의약품과 관련이 없는 질문입니다."}
