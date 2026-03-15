import logging
import re
from typing import Dict, List, Tuple

from .state import AgentState
from services.ai_service_v2 import AIService
from services.drug_service import DrugService
from services.user_service import UserService
from services.supabase_service import SupabaseService
from services.ingredient_utils import canonicalize_ingredient_name

logger = logging.getLogger(__name__)

_EMPTY_PROFILE_TOKENS = {"", "none", "없음", "없어요", "n/a", "na", "x"}
_SYMPTOM_TO_FDA_TERMS = {
    "두통": ["headache", "pain"],
    "편두통": ["migraine", "headache"],
    "알레르기": ["allergy", "sneezing", "itching"],
    "기침": ["cough"],
    "감기": ["cold"],
    "발열": ["fever"],
    "소화불량": ["indigestion"],
    "복통": ["stomachache", "abdominal pain"],
    "염좌": ["sprain"],
    "찰과상": ["abrasion", "wound"],
    "상처": ["wound"],
    "화상": ["burn"],
    "곤충교상": ["insect bite", "itching"],
    "안구건조": ["dry eye"],
}

_RED_FLAG_PATTERNS = [
    (re.compile(r"호흡곤란|숨이.?차|숨쉬기.?힘들|가슴.?통증|흉통"), "호흡곤란·흉통은 일반의약품 점검보다 즉시 진료가 우선일 수 있습니다."),
    (re.compile(r"의식|실신|마비|경련|발작|심한 어지럼"), "의식 변화·마비·경련은 응급 평가가 필요한 증상일 수 있습니다."),
    (re.compile(r"피가.?멈추지|심한.?출혈|검은.?변|토혈"), "지속 출혈이나 흑변·토혈은 응급 평가가 필요할 수 있습니다."),
    (re.compile(r"39|40|고열|열이 너무 높|열이 계속"), "고열이 지속되거나 악화되면 일반의약품 복용 전 진료가 우선일 수 있습니다."),
]


def _to_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    token = str(value or "").strip().lower()
    return token in {"true", "1", "yes", "y", "on"}


def _profile_has_value(profile: dict, key: str) -> bool:
    if not isinstance(profile, dict):
        return False
    token = str(profile.get(key) or "").strip().lower()
    return bool(token and token not in _EMPTY_PROFILE_TOKENS)


def _parse_ingredient_tokens(value) -> List[str]:
    if isinstance(value, list):
        raw_items = value
    else:
        raw_items = re.split(r"[,/;|\n+]+", str(value or ""))

    tokens: List[str] = []
    seen = set()
    for raw in raw_items:
        token = str(raw or "").strip().upper()
        token = re.sub(r"\([^)]*\)", " ", token)
        token = re.sub(r"\b\d+(?:\.\d+)?\s*(MG|MCG|G|ML|%)\b", " ", token)
        token = re.sub(r"[^A-Z0-9\s\-]", " ", token)
        token = re.sub(r"\s+", " ", token).strip()
        token = canonicalize_ingredient_name(token)
        token = str(token or "").strip().upper()
        if len(token) < 2 or token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tokens


async def _load_user_profile(user_info) -> dict:
    if not user_info:
        return {}
    try:
        profile = await UserService.get_profile(user_info)
        if not profile:
            return {}
        applied_allergies = getattr(profile, "applied_allergies", None) or getattr(profile, "allergies", "")
        applied_diseases = getattr(profile, "applied_chronic_diseases", None) or getattr(profile, "chronic_diseases", "")
        food_allergy_detail = str(getattr(profile, "food_allergy_detail", "") or "").strip()
        if food_allergy_detail and "상세정보:" not in str(applied_allergies or ""):
            applied_allergies = (
                f"{applied_allergies} | 상세정보: {food_allergy_detail}"
                if applied_allergies
                else f"상세정보: {food_allergy_detail}"
            )
        return {
            "current_medications": str(getattr(profile, "current_medications", "") or "").strip(),
            "allergies": str(applied_allergies or "").strip(),
            "chronic_diseases": str(applied_diseases or "").strip(),
            "is_pregnant": bool(getattr(profile, "is_pregnant", False)),
            "main_ingr_eng": str(getattr(profile, "main_ingr_eng", "") or "").strip(),
        }
    except Exception as exc:
        logger.warning("Failed to load user profile: %s", exc)
        return {}


def _build_symptom_followup(symptom_term: str, raw_query: str) -> dict:
    red_flags = []
    for pattern, message in _RED_FLAG_PATTERNS:
        if pattern.search(str(raw_query or "")):
            red_flags.append(message)

    symptom_key = str(symptom_term or "").strip()
    example_terms = _SYMPTOM_TO_FDA_TERMS.get(symptom_key, [])
    return {
        "symptom_term": symptom_key or str(raw_query or "").strip(),
        "followup_prompt": (
            "증상만으로 특정 약을 추천하지 않습니다. 지금 고려 중인 제품명 또는 주성분명을 입력하면 "
            "기저질환·복용약·임신/수유 여부 기준으로 금기·상호작용·주의사항을 점검합니다."
        ),
        "next_step_title": "다음으로 제품명 또는 주성분명을 직접 입력해 주세요",
        "generic_examples": ["Tylenol", "acetaminophen", "Advil", "ibuprofen", "Benadryl", "diphenhydramine"],
        "symptom_label_examples": example_terms,
        "red_flags": red_flags,
    }


async def classify_node(state: AgentState) -> AgentState:
    query = str(state.get("query") or "").strip()
    intent = await AIService.classify_intent(query)
    category = intent.get("category", "invalid")
    keyword = intent.get("keyword", "")

    query_l = query.lower()
    if any(token in query_l for token in ["알레르기", "allergy", "allergic"]):
        category = "symptom_recommendation"
        if not keyword or keyword == "none":
            keyword = "알레르기"

    return {
        "category": category,
        "keyword": keyword,
        "symptom": query if category == "symptom_recommendation" else None,
        "cache_key": None,
        "is_cached": False,
        "cache_source": None,
        "symptom_context": str(state.get("symptom_context") or "").strip(),
    }


async def retrieve_data_node(state: AgentState) -> AgentState:
    category = state.get("category")
    query = str(state.get("query") or "").strip()
    keyword = str(state.get("keyword") or "").strip()
    user_profile = await _load_user_profile(state.get("user_info"))

    if category == "symptom_recommendation":
        symptom_term = keyword or query
        followup = _build_symptom_followup(symptom_term=symptom_term, raw_query=query)
        return {
            "user_profile": user_profile,
            "symptom": query,
            "symptom_term": symptom_term,
            "symptom_followup": followup,
        }

    if category == "product_request":
        primary_target = keyword if keyword and keyword != "none" else query
        normalized_target = await AIService.normalize_product_keyword(query=query, hint_keyword=primary_target)

        candidates = []
        seen = set()
        for candidate in [primary_target, normalized_target, query]:
            token = str(candidate or "").strip()
            if not token:
                continue
            key = token.lower()
            if key in seen:
                continue
            seen.add(key)
            candidates.append(token)

        fda_data = await SupabaseService.get_product_profile(candidates)
        if not fda_data:
            normalized_ingredient = canonicalize_ingredient_name(primary_target or normalized_target or query)
            normalized_ingredient = str(normalized_ingredient or "").strip().upper()
            if normalized_ingredient:
                try:
                    warning_text = await DrugService.get_fda_warnings_by_ingr(normalized_ingredient)
                except Exception:
                    warning_text = None
                fda_data = {
                    "brand_name": normalized_ingredient.title(),
                    "active_ingredients": normalized_ingredient,
                    "ingredient_list": [normalized_ingredient],
                    "indications": "제품별 적응증이 다를 수 있으므로 구매 전 Drug Facts의 Uses 항목을 확인하세요.",
                    "warnings": warning_text or "제품별 경고 문구가 달라질 수 있으므로 Drug Facts의 Warnings 항목을 확인하세요.",
                    "dosage": "제품별 함량·연령 기준이 다를 수 있으므로 구매한 제품 라벨의 용법·용량을 확인하세요.",
                    "source": "ingredient_fallback",
                }
        return {
            "fda_data": fda_data,
            "user_profile": user_profile,
            "keyword": normalized_target or primary_target,
        }

    return {"user_profile": user_profile}


async def retrieve_fda_products_node(state: AgentState) -> AgentState:
    return {}


async def retrieve_dur_node(state: AgentState) -> AgentState:
    category = state.get("category")
    if category == "symptom_recommendation":
        return {"dur_data": []}

    if category == "product_request":
        fda_data = state.get("fda_data")
        if not fda_data or not isinstance(fda_data, dict):
            return {"dur_data": []}

        ingredient_list = fda_data.get("ingredient_list") or []
        if not ingredient_list:
            ingredient_list = _parse_ingredient_tokens(fda_data.get("active_ingredients", ""))
        if not ingredient_list:
            return {"dur_data": []}
        dur_data = await DrugService.get_kr_dur_info(ingredient_list)
        return {"dur_data": dur_data}

    return {"dur_data": []}


async def generate_symptom_answer_node(state: AgentState) -> AgentState:
    symptom = str(state.get("symptom") or state.get("query") or "").strip()
    followup = state.get("symptom_followup") or _build_symptom_followup(state.get("symptom_term") or symptom, symptom)

    lines = [
        f"입력한 증상: {symptom}" if symptom else "입력한 증상을 확인했습니다.",
        "이 단계에서는 특정 일반의약품이나 성분을 추천하지 않습니다.",
        "사용 예정인 제품명 또는 주성분명을 직접 입력해 주시면 현재 저장된 건강정보를 기준으로 금기·상호작용·주의사항을 점검합니다.",
        "증상 악화, 고열 지속, 호흡곤란, 흉통, 의식 변화가 있으면 일반의약품 확인보다 진료가 우선입니다.",
    ]
    if followup.get("red_flags"):
        lines.append("응급·조기진료 검토 신호: " + " / ".join(followup.get("red_flags")[:3]))

    return {
        "final_answer": "\n\n".join(lines),
        "ingredients_data": [],
        "dur_data": [],
        "symptom_followup": followup,
    }


async def generate_product_answer_node(state: AgentState) -> AgentState:
    fda_data = state.get("fda_data")
    dur_data = state.get("dur_data") or []

    if not fda_data:
        query = str(state.get("query") or "").strip()
        return {
            "final_answer": (
                f"'{query}'에 대한 제품 또는 성분 정보를 찾지 못했습니다. "
                "미국 OTC 표기 그대로의 제품명이나 영문 주성분명으로 다시 입력해 주세요."
            )
        }

    brand_name = str(fda_data.get("brand_name") or state.get("query") or "제품").strip()
    ingredients = fda_data.get("ingredient_list") or _parse_ingredient_tokens(fda_data.get("active_ingredients", ""))
    if not ingredients:
        ingredients = [brand_name.upper()]

    dur_with_rows = {str(item.get("ingredient") or "").strip().upper(): item for item in dur_data if isinstance(item, dict)}
    ingredient_bits = []
    for ingredient in ingredients:
        item = dur_with_rows.get(str(ingredient or "").strip().upper())
        if item and item.get("kr_durs"):
            warning_types = [str(row.get("type") or "").strip() for row in item.get("kr_durs") if isinstance(row, dict) and str(row.get("type") or "").strip()]
            warning_types = sorted(dict.fromkeys(warning_types))
            if warning_types:
                ingredient_bits.append(f"{ingredient}({', '.join(warning_types[:3])})")
            else:
                ingredient_bits.append(str(ingredient))
        else:
            ingredient_bits.append(str(ingredient))

    final_answer = (
        f"{brand_name}의 주성분을 기준으로 금기·상호작용·주의사항 점검을 준비했습니다. "
        f"점검 대상 성분: {', '.join(ingredient_bits)}. "
        "최종 복용 판단은 제품 라벨의 Drug Facts와 약사 확인을 함께 보시는 것이 안전합니다."
    )

    return {
        "final_answer": final_answer,
        "dur_data": dur_data,
        "fda_data": fda_data,
    }


async def generate_general_answer_node(state: AgentState) -> AgentState:
    answer = await AIService.generate_general_answer(state["query"])
    return {"final_answer": answer}


async def generate_error_node(state: AgentState) -> AgentState:
    return {
        "final_answer": "제품명, 주성분명, 또는 증상을 다시 입력해 주세요."
    }
