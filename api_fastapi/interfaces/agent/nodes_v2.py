import logging
import asyncio
from .state import AgentState
from application.services.ai_service import AIService
from application.use_cases.drug_search import DrugSearchUseCase
from application.use_cases.symptom_recommend import SymptomRecommendUseCase
from application.use_cases.dur_inquiry import DurInquiryUseCase
from infrastructure.django_db.drug_repository import DjangoDrugRepository
from infrastructure.django_db.dur_repository import DjangoDurRepository
from infrastructure.external_api.fda_client import FdaClient

from infrastructure.cache.supabase_cache import SupabaseCacheRepository

logger = logging.getLogger(__name__)

# 의존성 조립
drug_repo = DjangoDrugRepository()
dur_repo = DjangoDurRepository()
fda_client = FdaClient()
cache_repo = SupabaseCacheRepository()

drug_search_use_case = DrugSearchUseCase(drug_repo)
symptom_recommend_use_case = SymptomRecommendUseCase(
    dur_repo=dur_repo,
    fda_client=fda_client,
    ai_service=AIService,
    cache=cache_repo
)
dur_inquiry_use_case = DurInquiryUseCase(dur_repo)

async def classify_node(state: AgentState) -> AgentState:
    """Classify user query and extract keywords"""
    query = state["query"]
    cache_key = await AIService.normalize_symptom_query(query)
    logger.info(f"Classifying query (cache_key: {cache_key})")
    
    # 캐시 확인 (Symptom Recommendation 한정)
    cached_data = await cache_repo.get_symptom_cache(cache_key)
    if cached_data:
        final_ans = cached_data.get("final_answer", "")
        # 지능형 캐시 갱신: 새로운 프롬프트 형식(### 1. 상황별)이 없는 구버전 캐시는 무시
        if "### 1. 상황별" in final_ans:
            logger.info(f"Cache Hit (v2 format) for key: {cache_key}")
            return {
                "category": cached_data.get("category", "symptom_recommendation"),
                "keyword": "",
                "symptom": query,
                "cache_key": cache_key,
                "is_cached": True,
                "fda_data": cached_data.get("fda_data"),
                "dur_data": cached_data.get("dur_data"),
                "final_answer": final_ans,
                "ingredients_data": cached_data.get("recommended_ingredients")
            }
        else:
            logger.info(f"Obsolete cache found for key {cache_key}. Forcing refresh.")

    intent = await AIService.classify_intent(query)
    category = intent.get("category", "invalid")
    keyword = intent.get("keyword", "")
    return {
        "category": category,
        "keyword": keyword,
        "symptom": query if category == "symptom_recommendation" else None,
        "cache_key": cache_key if category == "symptom_recommendation" else None,
        "is_cached": False
    }

async def retrieve_fda_node(state: AgentState) -> AgentState:
    """Retrieve FDA data based on category"""
    category = state["category"]
    keyword = state["keyword"]
    query = state["query"]
    fda_data = None
    if category == "symptom_recommendation":
        keyword = keyword or query
        fda_data = await symptom_recommend_use_case.get_fda_ingredients_for_symptom(keyword)
    elif category == "product_request":
        target = keyword if keyword and keyword != "none" else query
        fda_data = await fda_client.search_by_name(target)
    return {"fda_data": fda_data}

async def retrieve_dur_node(state: AgentState) -> AgentState:
    """Retrieve DUR data based on FDA ingredients"""
    category = state["category"]
    fda_data = state["fda_data"]
    if not fda_data:
        return {"dur_data": []}
    dur_data = []
    if category == "symptom_recommendation" and isinstance(fda_data, list):
        dur_data = await symptom_recommend_use_case.get_enriched_dur_for_ingredients(fda_data)
    elif category == "product_request" and isinstance(fda_data, dict):
        ingrs = fda_data.get('active_ingredients', '')
        dur_data = await dur_inquiry_use_case.get_by_ingredient_text(ingrs)
    return {"dur_data": dur_data}

async def generate_symptom_answer_node(state: AgentState) -> AgentState:
    """Generate per-ingredient safety guidance and fetch OTC product names (Optimized Bulk)"""
    symptom = state["symptom"]
    dur_data = state["dur_data"]
    fda_data = state.get("fda_data", [])

    if state.get("is_cached", False):
        return {
            "final_answer": state.get("final_answer", ""),
            "dur_data": dur_data,
            "fda_data": fda_data,
            "ingredients_data": state.get("ingredients_data", [])
        }

    if not dur_data:
        fallback_query = (
            f"The user asked about '{symptom}' but I couldn't find specific drugs in the FDA/DUR database. "
            f"Please provide general medical advice or common over-the-counter ingredients for this symptom. "
            f"(User query: {state['query']})"
        )
        answer = await AIService.generate_general_answer(fallback_query)
        prefix = "해당 증상에 대한 FDA/DUR 기반의 정확한 의약품 정보는 찾을 수 없었지만, 일반적인 정보를 안내해 드립니다.\\n\\n"
        return {"final_answer": prefix + answer, "ingredients_data": []}

    # 1. AI 답변 생성 (구조화된 가이드)
    ai_result = await AIService.generate_symptom_answer(symptom, dur_data, state.get("user_profile"))
    if not isinstance(ai_result, dict):
        return {"final_answer": str(ai_result), "dur_data": dur_data, "ingredients_data": []}
    
    summary = ai_result.get("summary", "")
    ai_ingredients = ai_result.get("ingredients", [])
    dur_map = {item["ingredient"].upper(): item for item in dur_data}
    safe_names = [ing["name"].upper() for ing in ai_ingredients if ing.get("can_take", False)]
    
    # 2. 제품 정보 수집 (번역 없이 병렬로 고속 수집)
    from application.services.map_service import MapService
    async def fetch_raw_products(ingr_name: str):
        try:
            # translate=False 파라미터로 AI 번역 지연 제거
            res = await MapService.get_us_otc_products_by_ingredient(ingr_name, translate=False)
            return ingr_name, res.get("products", [])
        except Exception as e:
            logger.warning(f"Failed to fetch raw products for '{ingr_name}': {e}")
            return ingr_name, []

    raw_results = await asyncio.gather(*[fetch_raw_products(n) for n in safe_names])
    products_by_ingr = dict(raw_results)

    # 3. 벌크 번역 (Bulk Translation) - 모든 제품의 purpose를 한 번에 번역
    all_purposes = []
    purpose_refs = [] # (ingr_name, product_index)
    for ingr_name in safe_names:
        prods = products_by_ingr.get(ingr_name, [])
        for idx, p in enumerate(prods):
            all_purposes.append(p.get("purpose", ""))
            purpose_refs.append((ingr_name, idx))

    if all_purposes:
        logger.info(f"Bulk translating {len(all_purposes)} purposes at once...")
        translated_list = await AIService.translate_purposes(all_purposes)
        # 번역 결과 다시 매핑
        for i, trans_text in enumerate(translated_list):
            ingr_name, idx = purpose_refs[i]
            products_by_ingr[ingr_name][idx]["purpose"] = trans_text

    # 4. 최종 데이터 조합
    ingredients_data = []
    for ing in ai_ingredients:
        name = ing.get("name", "").upper()
        dur_item = dur_map.get(name, {})
        entry = {
            "name": name,
            "can_take": ing.get("can_take", True),
            "reason": ing.get("reason", ""),
            "dur_warning_types": ing.get("dur_warning_types", []),
            "kr_durs": dur_item.get("kr_durs", []),
            "fda_warning": dur_item.get("fda_warning", None),
            "products": products_by_ingr.get(name, []) if ing.get("can_take", False) else []
        }
        ingredients_data.append(entry)

    # 5. 최신 버전 캐시 저장
    cache_key = state.get("cache_key")
    if cache_key:
        await cache_repo.set_symptom_cache(
            query_text=cache_key,
            category="symptom_recommendation",
            fda_data=state.get("fda_data", []),
            dur_data=dur_data,
            final_answer=summary,
            recommended_ingredients=ingredients_data
        )

    return {
        "final_answer": summary,
        "dur_data": dur_data,
        "fda_data": fda_data,
        "ingredients_data": ingredients_data
    }

async def generate_product_answer_node(state: AgentState) -> AgentState:
    """Generate answer for product queries"""
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
    answer = await AIService.generate_general_answer(state["query"])
    return {"final_answer": answer}

async def generate_error_node(state: AgentState) -> AgentState:
    """Handle invalid queries"""
    return {"final_answer": "죄송합니다. 질문을 이해하지 못하거나 의약품과 관련이 없는 질문입니다."}
