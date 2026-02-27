import logging
import asyncio
import time
from .state import AgentState
from application.services.ai_service import AIService
from application.use_cases.symptom_recommend import SymptomRecommendUseCase
from application.use_cases.dur_inquiry import DurInquiryUseCase
from infrastructure.supabase_db.drug_repository import SupabaseDrugRepository
from infrastructure.supabase_db.dur_repository import SupabaseDurRepository
from infrastructure.external_api.fda_client import FdaClient
from infrastructure.cache.supabase_cache import SupabaseCacheRepository

logger = logging.getLogger(__name__)

# --- 시스템 로직 버전 ---
LOGIC_VERSION = "2026.02.26.v6" 

drug_repo = SupabaseDrugRepository()
dur_repo = SupabaseDurRepository()
fda_client = FdaClient()
cache_repo = SupabaseCacheRepository()

symptom_recommend_use_case = SymptomRecommendUseCase(
    dur_repo=dur_repo,
    fda_client=fda_client,
    drug_repo=drug_repo,
    ai_service=AIService,
    cache=cache_repo
)
dur_inquiry_use_case = DurInquiryUseCase(dur_repo)


async def classify_node(state: AgentState) -> AgentState:
    """Classify user query and extract keywords (Integrated v2)"""
    query = state["query"]
    t0 = time.time()

    # 의도 분류 및 키워드 추출 (한국어/영어 모두)
    intent = await AIService.classify_intent_v2(query)
    logger.info(f"[⏱ TIMING] classify_intent_v2: {time.time()-t0:.2f}s")

    category = intent.get("category", "invalid")
    keyword = intent.get("keyword", "")
    keyword_kr = intent.get("keyword_kr", "")
    cache_key = intent.get("cache_key", query)
    logger.info(f"Classified query: {category} (keyword_kr: {keyword_kr}, cache_key: {cache_key})")

    # 캐시 확인
    cached_data = await cache_repo.get_symptom_cache(cache_key)
    if cached_data and cached_data.get("logic_version") == LOGIC_VERSION:
        logger.info(f"Cache Hit: {cache_key}")
        return {
            "category": category,
            "keyword": "",
            "keyword_kr": "",
            "symptom": query,
            "cache_key": cache_key,
            "is_cached": True,
            "cached_data": cached_data
        }

    return {
        "category": category,
        "keyword": keyword,
        "keyword_kr": keyword_kr,
        "symptom": query if category == "symptom_recommendation" else None,
        "cache_key": cache_key if category == "symptom_recommendation" else None,
        "is_cached": False
    }


async def retrieve_fda_node(state: AgentState) -> AgentState:
    """Retrieve FDA data based on category"""
    category = state["category"]
    keyword = state["keyword"]
    keyword_kr = state.get("keyword_kr")
    query = state["query"]
    fda_data = None
    t0 = time.time()

    if category == "symptom_recommendation":
        # DB-First 로직 실행 (상태에 저장된 한국어 키워드 우선 사용)
        symptom_context = keyword_kr or query
        fda_data = await symptom_recommend_use_case.get_best_ingredients_for_symptom(keyword, symptom_context)
        logger.info(f"[⏱ TIMING] retrieve_fda (symptom, ingredients={len(fda_data) if fda_data else 0}): {time.time()-t0:.2f}s")
    elif category == "product_request":
        target = keyword if keyword and keyword != "none" else query
        fda_data = await fda_client.search_by_name(target)
        logger.info(f"[⏱ TIMING] retrieve_fda (product): {time.time()-t0:.2f}s")

    return {"fda_data": fda_data}


async def retrieve_dur_node(state: AgentState) -> AgentState:
    """Retrieve DUR data based on FDA ingredients"""
    category = state["category"]
    fda_data = state["fda_data"]
    is_cached = state.get("is_cached", False)
    cached_data = state.get("cached_data")

    if not fda_data:
        return {"dur_data": []}

    dur_data = []
    t0 = time.time()
    if category == "symptom_recommendation" and isinstance(fda_data, list):
        dur_data = await symptom_recommend_use_case.get_enriched_dur_for_ingredients(fda_data)
        logger.info(f"[⏱ TIMING] retrieve_dur (symptom, ingrs={len(fda_data)}): {time.time()-t0:.2f}s")

        # 캐시 매칭 로직 (데이터가 동일하면 캐시된 답변 사용)
        if is_cached and cached_data:
            return {
                "dur_data": dur_data,
                "fda_data": cached_data.get("fda_data"),
                "final_answer": cached_data.get("final_answer"),
                "ingredients_data": cached_data.get("recommended_ingredients")
            }
        
        return {"dur_data": dur_data}

    elif category == "product_request" and isinstance(fda_data, dict):
        ingrs = fda_data.get('active_ingredients', '')
        dur_data = await dur_inquiry_use_case.get_by_ingredient_text(ingrs)
        logger.info(f"[⏱ TIMING] retrieve_dur (product): {time.time()-t0:.2f}s")
    
    return {"dur_data": dur_data}


async def generate_symptom_answer_node(state: AgentState) -> AgentState:
    """Generate per-ingredient safety guidance and fetch OTC product names"""
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

    # DUR 데이터가 없으면 일반 AI 답변으로 폴백
    if not dur_data:
        fallback_query = (
            f"The user asked about '{symptom}' but I couldn't find specific drugs in the FDA/DUR database. "
            f"Please provide general medical advice or common over-the-counter ingredients for this symptom. "
            f"(User query: {state['query']})"
        )
        answer = await AIService.generate_general_answer(fallback_query)
        prefix = "해당 증상에 대한 FDA/DUR 기반의 정확한 의약품 정보는 찾을 수 없었지만, 일반적인 정보를 안내해 드립니다.\n\n"
        return {"final_answer": prefix + answer, "ingredients_data": []}

    # AI에게 성분별 안전 여부 판단 요청
    ai_result = await AIService.generate_symptom_answer(symptom, dur_data, state.get("user_profile"))

    if not isinstance(ai_result, dict):
        # 예외적 폴백
        return {"final_answer": str(ai_result), "dur_data": dur_data, "ingredients_data": []}

    summary = ai_result.get("summary", "")
    ai_ingredients = ai_result.get("ingredients", [])

    logger.info(f"AI classified {len(ai_ingredients)} ingredients for symptom '{symptom}'")

    # DUR 상세 데이터를 성분명 기준으로 인덱싱
    dur_map = {item["ingredient"].upper(): item for item in dur_data}

    # 안전 성분의 제품명을 병렬로 조회
    safe_names = [
        ing["name"].upper()
        for ing in ai_ingredients
        if ing.get("can_take", False)
    ]

    async def fetch_products(ingr_name: str):
        from application.services.map_service import MapService
        try:
            result = await MapService.get_us_otc_products_by_ingredient(ingr_name)
            return ingr_name, result.get("products", [])
        except Exception as e:
            logger.warning(f"Failed to fetch products for '{ingr_name}': {e}")
            return ingr_name, []

    product_results = await asyncio.gather(*[fetch_products(n) for n in safe_names])
    products_map = dict(product_results)

    # 최종 ingredients_data 조립
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
            "products": products_map.get(name, []) if ing.get("can_take", False) else []
        }
        ingredients_data.append(entry)

    # 4. 캐시 저장
    cache_key = state.get("cache_key")
    if cache_key:
        await cache_repo.set_symptom_cache(
            query_text=cache_key,
            category="symptom_recommendation",
            fda_data=fda_data,
            dur_data=dur_data,
            final_answer=summary,
            recommended_ingredients=ingredients_data,
            logic_version=LOGIC_VERSION
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
