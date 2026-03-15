import os
import logging
import json
import re
from collections import Counter
from functools import lru_cache
from typing import Any, Dict, List
from urllib.parse import quote_plus

from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse

from graph_agent.builder_v2 import build_graph
from services.ingredient_utils import canonicalize_ingredient_name

logger = logging.getLogger(__name__)

_EMPTY_PROFILE_TOKENS = {"", "none", "없음", "없어요", "n/a", "na", "x"}
_SYMPTOM_KR_TO_EN = {
    "두통": ["headache", "pain"],
    "편두통": ["migraine", "headache"],
    "알레르기": ["allergy", "itch", "sneezing"],
    "기침": ["cough"],
    "감기": ["cold"],
    "발열": ["fever"],
    "소화불량": ["indigestion"],
    "복통": ["stomachache", "abdominal pain"],
    "통증": ["pain"],
    "염좌": ["sprain", "pain"],
    "찰과상": ["abrasion", "wound"],
    "상처": ["wound"],
    "화상": ["burn"],
    "곤충교상": ["insect bite", "itch"],
}


@lru_cache(maxsize=1)
def get_graph():
    return build_graph()


def _to_profile_display(value: str, fallback: str = "입력 없음") -> str:
    token = str(value or "").strip()
    if not token:
        return fallback
    if token.lower() in _EMPTY_PROFILE_TOKENS:
        return fallback
    return token


def _contains_hangul(text: str) -> bool:
    return bool(re.search(r"[가-힣]", str(text or "")))


async def _translate_profile_fields_to_english(meds: str, allergies: str, diseases: str):
    values = {
        "meds": str(meds or "").strip(),
        "allergies": str(allergies or "").strip(),
        "diseases": str(diseases or "").strip(),
    }
    translatable = {
        key: value
        for key, value in values.items()
        if value and value != "입력 없음" and _contains_hangul(value)
    }
    if not translatable:
        return values

    try:
        from services.ai_service_v2 import AIService

        translated = await AIService.translate_profile_fields_to_english(
            meds=values["meds"],
            allergies=values["allergies"],
            diseases=values["diseases"],
        )
        if isinstance(translated, dict):
            for key in ("meds", "allergies", "diseases"):
                translated_value = str(translated.get(key) or "").strip()
                if translated_value:
                    values[key] = translated_value
    except Exception as exc:
        logger.warning("profile field translation failed: %s", exc)

    return values


def _to_english_symptom(symptom: str, symptom_term: str = "") -> str:
    candidates = [symptom_term, symptom]
    for raw in candidates:
        token = str(raw or "").strip()
        if not token:
            continue
        if re.search(r"[A-Za-z]", token) and not re.search(r"[가-힣]", token):
            return token
        exact = _SYMPTOM_KR_TO_EN.get(token)
        if exact:
            return exact[0]
        for kr_term, en_terms in _SYMPTOM_KR_TO_EN.items():
            if kr_term in token:
                return en_terms[0]
    return "unspecified symptom"


async def _build_consultation_note(symptom: str, user_profile: dict, symptom_term: str = ""):
    profile = user_profile if isinstance(user_profile, dict) else {}
    meds = _to_profile_display(profile.get("current_medications"))
    allergies = _to_profile_display(profile.get("allergies"))
    diseases = _to_profile_display(profile.get("chronic_diseases"))
    translated = await _translate_profile_fields_to_english(meds, allergies, diseases)
    meds = translated["meds"]
    allergies = translated["allergies"]
    diseases = translated["diseases"]
    pregnancy = "Yes" if bool(profile.get("is_pregnant")) else "No"
    symptom_text = _to_english_symptom(symptom=symptom, symptom_term=symptom_term)

    memo_text = (
        f"Hello, I have the symptom '{symptom_text}' and I am reviewing an OTC product before purchase.\n"
        f"- Current medications: {meds}\n"
        f"- Allergies: {allergies}\n"
        f"- Chronic conditions: {diseases}\n"
        f"- Pregnancy/Breastfeeding: {pregnancy}\n\n"
        "Please review the product or active ingredient I am considering and confirm label fit, dose, duration, and interaction risks."
    )

    return {
        "symptom": symptom_text,
        "meds": meds,
        "allergies": allergies,
        "diseases": diseases,
        "pregnancy": pregnancy,
        "memo_text": memo_text,
    }


def _profile_has_value(profile: dict, key: str) -> bool:
    if not isinstance(profile, dict):
        return False
    token = str(profile.get(key) or "").strip().lower()
    return bool(token and token not in _EMPTY_PROFILE_TOKENS)


def _to_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"true", "1", "yes", "y", "on"}


def _build_user_med_ingredient_set(profile: dict) -> set:
    sources = [
        str((profile or {}).get("main_ingr_eng") or "").strip(),
        str((profile or {}).get("current_medications") or "").strip(),
    ]
    token_set = set()
    for source in sources:
        if not source:
            continue
        pieces = re.split(r"[,/;|\n+]+", source)
        for piece in pieces:
            token = str(piece or "").strip().upper()
            token = re.sub(r"\([^)]*\)", "", token).strip()
            token = canonicalize_ingredient_name(token)
            token = str(token or "").strip().upper()
            if len(token) >= 2:
                token_set.add(token)
    return token_set


def _extract_combined_partner_tokens(warning_text: str) -> list:
    raw = str(warning_text or "")
    if not raw:
        return []

    patterns = [
        r"병용금기\s*성분\s*:\s*([^\n]+)",
        r"contraindicated\s*(?:with)?\s*:\s*([^\n]+)",
    ]
    captured = ""
    for pattern in patterns:
        matched = re.search(pattern, raw, flags=re.IGNORECASE)
        if matched:
            captured = str(matched.group(1) or "").strip()
            break
    if not captured:
        return []

    chunks = re.split(r"[,/;|+]", captured)
    tokens = []
    seen = set()
    for chunk in chunks:
        token = str(chunk or "").strip().upper()
        token = re.sub(r"\([^)]*\)", "", token).strip()
        token = canonicalize_ingredient_name(token)
        token = str(token or "").strip().upper()
        if len(token) < 2 or token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tokens


def _extract_warning_types(dur_item: dict) -> list:
    warning_types = []
    seen = set()
    for row in (dur_item or {}).get("kr_durs", []) or []:
        if not isinstance(row, dict):
            continue
        token = str(row.get("type") or "").strip()
        if not token:
            continue
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        warning_types.append(token)
    return warning_types


def _warning_excerpt(dur_item: dict, max_len: int = 160) -> str:
    for row in (dur_item or {}).get("kr_durs", []) or []:
        if not isinstance(row, dict):
            continue
        token = str(row.get("warning") or "").strip()
        if token:
            return token if len(token) <= max_len else token[: max_len - 3].rstrip() + "..."
    return ""


def _assess_ingredient_for_profile(dur_item: dict, user_profile: dict) -> Dict[str, Any]:
    ingredient = str((dur_item or {}).get("ingredient") or "").strip().upper()
    warning_types = _extract_warning_types(dur_item)
    rows = (dur_item or {}).get("kr_durs", []) or []
    has_profile = any(
        [
            _profile_has_value(user_profile, "current_medications"),
            _profile_has_value(user_profile, "allergies"),
            _profile_has_value(user_profile, "chronic_diseases"),
            _to_bool((user_profile or {}).get("is_pregnant")),
        ]
    )
    user_med_ingredients = _build_user_med_ingredient_set(user_profile)
    is_pregnant = _to_bool((user_profile or {}).get("is_pregnant"))

    blocked_reasons = []
    caution_notes = []
    matched_profile_fields = []

    for row in rows:
        if not isinstance(row, dict):
            continue
        type_text = str(row.get("type") or "").strip()
        warning_text = str(row.get("warning") or "").strip()
        merged = f"{type_text} {warning_text}".lower()

        if any(token in merged for token in ("임부", "임신", "수유", "pregnan", "lactat", "breastfeeding")):
            if is_pregnant:
                blocked_reasons.append("임신/수유 정보와 연결된 금기·주의 항목이 확인되었습니다.")
                matched_profile_fields.append("임신/수유")
            else:
                caution_notes.append("임신/수유 중에는 별도 금기·주의가 있을 수 있는 성분입니다.")
            continue

        if any(token in merged for token in ("병용금기", "contra", "combined")):
            if user_med_ingredients:
                partner_tokens = _extract_combined_partner_tokens(warning_text)
                matched = [token for token in partner_tokens if token in user_med_ingredients]
                if matched:
                    blocked_reasons.append(
                        f"현재 복용 중인 약과 병용금기 가능성이 확인되었습니다: {', '.join(matched[:3])}"
                    )
                    matched_profile_fields.append("복용 중인 약")
                else:
                    caution_notes.append("병용금기 항목이 있어 현재 복용 중인 약과의 직접 비교가 필요합니다.")
            else:
                caution_notes.append("병용금기 항목이 있으나 복용 중인 약 정보가 없어 주의 확인이 필요합니다.")
            continue

        if type_text:
            caution_notes.append(f"DUR '{type_text}' 항목이 확인되었습니다.")

    excerpt = _warning_excerpt(dur_item)
    if blocked_reasons:
        reason = " ".join(dict.fromkeys(blocked_reasons))
        if warning_types:
            reason += f" (DUR 유형: {', '.join(warning_types[:3])})"
        if excerpt:
            reason += f" 근거 문구: {excerpt}"
        return {
            "name": ingredient,
            "status_key": "blocked",
            "status_label": "복용 제한 검토 필요",
            "can_take": False,
            "reason": reason,
            "warning_types": warning_types,
            "matched_profile_fields": sorted(set(matched_profile_fields)),
            "kr_durs": rows,
        }

    if warning_types:
        reason = " ".join(dict.fromkeys(caution_notes)) if caution_notes else "DUR 주의 항목이 확인되었습니다."
        if excerpt:
            reason += f" 근거 문구: {excerpt}"
        return {
            "name": ingredient,
            "status_key": "caution",
            "status_label": "주의 확인 필요",
            "can_take": True,
            "reason": reason,
            "warning_types": warning_types,
            "matched_profile_fields": sorted(set(matched_profile_fields)),
            "kr_durs": rows,
        }

    if has_profile:
        reason = "현재 입력된 건강정보 기준에서 직접 연결된 금기·상호작용 항목은 확인되지 않았습니다. 다만 복용 적합성 판단은 아니므로 제품 라벨의 용량·연령·투여기간을 별도로 확인하세요."
    else:
        reason = "회원 건강정보가 없어서 일반 라벨·DUR 기준만 점검했습니다. 로그인 후 더 구체적으로 확인할 수 있습니다."

    return {
        "name": ingredient,
        "status_key": "clear",
        "status_label": "현재 입력 기준 직접 경고 없음",
        "can_take": True,
        "reason": reason,
        "warning_types": warning_types,
        "matched_profile_fields": [],
        "kr_durs": rows,
    }


def _build_product_assessments(dur_data: List[dict], user_profile: dict) -> List[dict]:
    items = []
    for item in dur_data or []:
        if not isinstance(item, dict):
            continue
        ingredient = str(item.get("ingredient") or "").strip().upper()
        if not ingredient:
            continue
        items.append(_assess_ingredient_for_profile(item, user_profile or {}))
    return items


def _summarize_assessments(assessments: List[dict]) -> Dict[str, str]:
    blocked = [item for item in assessments if item.get("status_key") == "blocked"]
    caution = [item for item in assessments if item.get("status_key") == "caution"]

    if blocked:
        return {
            "key": "blocked",
            "label": "복용 전 전문가 확인 우선",
            "description": "개인 건강정보와 직접 연결된 금기·상호작용 가능성이 확인되었습니다.",
        }
    if caution:
        return {
            "key": "caution",
            "label": "주의사항 확인 필요",
            "description": "즉시 금기로 단정되지는 않지만 DUR 주의 항목 또는 라벨 확인 포인트가 있습니다.",
        }
    return {
        "key": "clear",
        "label": "현재 입력 기준 직접 경고 없음",
        "description": "현재 입력된 건강정보 기준에서 직접 연결된 금기·상호작용 항목은 확인되지 않았습니다. 다만 복용 가능 여부를 판단한 것은 아니므로 제품 라벨과 약사 상담을 함께 확인해 주세요.",
    }


def _build_structured_dur_summary(dur_items: List[dict], limit: int = 6) -> Dict[str, Any]:
    flat_entries = []
    for item in dur_items or []:
        ingredient = str(item.get("ingredient") or "").strip().upper()
        for row in item.get("kr_durs", []) or []:
            if not isinstance(row, dict):
                continue
            flat_entries.append(
                {
                    "type": str(row.get("type") or "주의").strip() or "주의",
                    "ingredient": ingredient,
                    "warning": str(row.get("warning") or "").strip(),
                }
            )

    if not flat_entries:
        return {
            "count": 0,
            "headline": "",
            "type_summary": "",
            "lines": [],
            "has_more": False,
        }

    type_counter = Counter(entry["type"] for entry in flat_entries if entry["type"])
    top_types = ", ".join(
        [f"{dur_type} {count}건" for dur_type, count in type_counter.most_common(3)]
    )
    lines = []
    for entry in flat_entries[:limit]:
        warning = entry["warning"]
        if len(warning) > 120:
            warning = warning[:117].rstrip() + "..."
        line = f"{entry['ingredient']}: {entry['type']}"
        if warning:
            line += f" - {warning}"
        lines.append(line)

    return {
        "count": len(flat_entries),
        "headline": f"DUR 안내 항목 {len(flat_entries)}건이 확인되었습니다.",
        "type_summary": top_types,
        "lines": lines,
        "has_more": len(flat_entries) > limit,
    }


def _build_symptom_fit_note(symptom_context: str, fda_data: dict) -> Dict[str, str]:
    symptom = str(symptom_context or "").strip()
    if not symptom:
        return {}

    indications = str((fda_data or {}).get("indications") or "").lower()
    if not indications:
        return {
            "key": "unknown",
            "label": "적응증 비교 불가",
            "description": "라벨 적응증 정보가 충분하지 않아 증상과의 일치 여부를 자동 비교하지 못했습니다.",
        }

    search_terms = []
    for kr_term, en_terms in _SYMPTOM_KR_TO_EN.items():
        if kr_term in symptom:
            search_terms.extend(en_terms)
    if not search_terms:
        search_terms = [symptom.lower()]

    matched = [term for term in search_terms if term and term.lower() in indications]
    if matched:
        return {
            "key": "matched",
            "label": "라벨 적응증 표현 확인",
            "description": "입력한 증상과 관련된 표현이 FDA 라벨의 Uses/Indications 문구에서 확인되었습니다. 그래도 개인 적합성은 별도로 확인하세요.",
        }
    return {
        "key": "unmatched",
        "label": "라벨 적응증 직접 확인 필요",
        "description": "입력한 증상 표현이 라벨 적응증에서 명확히 확인되지 않았습니다. 구매 전 Uses/Indications를 다시 확인하세요.",
    }


def _build_profile_snapshot(user_profile: dict) -> Dict[str, str]:
    profile = user_profile if isinstance(user_profile, dict) else {}
    return {
        "current_medications": _to_profile_display(profile.get("current_medications")),
        "allergies": _to_profile_display(profile.get("allergies")),
        "chronic_diseases": _to_profile_display(profile.get("chronic_diseases")),
        "pregnancy": "예" if bool(profile.get("is_pregnant")) else "아니오",
    }


def _build_general_use_panel(fda_data: dict, fallback_name: str = "") -> Dict[str, Any]:
    data = fda_data if isinstance(fda_data, dict) else {}
    product_name = str(data.get("brand_name") or fallback_name or "이 제품").strip()
    indications = str(data.get("indications") or "").strip()
    warnings = str(data.get("warnings") or "").strip()

    bullets = []
    for piece in re.split(r"\n+|•|;|\.\s+", indications):
        token = str(piece or "").strip(" -•\t")
        if len(token) < 2 or token in bullets:
            continue
        bullets.append(token)
        if len(bullets) >= 6:
            break

    if indications:
        summary = f"{product_name}의 라벨상 일반 효능/용도는 아래 Uses·Indications 문구를 기준으로 확인할 수 있습니다."
    else:
        summary = f"{product_name}의 일반 효능/용도 문구를 충분히 찾지 못했습니다. 구매 전 Drug Facts의 Uses 항목을 직접 확인해 주세요."

    caution = "이 정보는 라벨의 일반 효능 안내이며, 현재 증상에 맞는지 또는 복용 가능한지는 별도로 판단하지 않습니다."
    if warnings and not indications:
        caution += " 경고 문구는 확인되었지만 효능 문구는 부족할 수 있습니다."

    return {
        "title": "일반 효능 / 용도",
        "summary": summary,
        "raw_text": indications or "정보 없음",
        "bullets": bullets,
        "caution": caution,
    }


async def _build_product_consultation_note(query: str, fda_data: dict, user_profile: dict, symptom_context: str = ""):
    profile = user_profile if isinstance(user_profile, dict) else {}
    product_name = str((fda_data or {}).get("brand_name") or query or "제품").strip()
    active_ingredients = str((fda_data or {}).get("active_ingredients") or "").strip()
    indications = str((fda_data or {}).get("indications") or "").strip()

    meds = _to_profile_display(profile.get("current_medications"))
    allergies = _to_profile_display(profile.get("allergies"))
    diseases = _to_profile_display(profile.get("chronic_diseases"))
    translated = await _translate_profile_fields_to_english(meds, allergies, diseases)
    meds = translated["meds"]
    allergies = translated["allergies"]
    diseases = translated["diseases"]
    pregnancy = "Yes" if bool(profile.get("is_pregnant")) else "No"

    lines = [
        "Hello, I am checking an OTC product before purchase.",
        f"- Product or ingredient: {product_name}",
    ]
    if active_ingredients:
        lines.append(f"- Active ingredient(s): {active_ingredients}")
    if symptom_context:
        lines.append(f"- Symptom note (optional): {_to_english_symptom(symptom_context, symptom_context)}")
    if indications:
        short_use = indications if len(indications) <= 220 else indications[:217].rstrip() + "..."
        lines.append(f"- Label uses shown: {short_use}")
    lines.extend([
        f"- Current medications: {meds}",
        f"- Allergies: {allergies}",
        f"- Chronic conditions: {diseases}",
        f"- Pregnancy/Breastfeeding: {pregnancy}",
        "",
        "Please review the label warnings, interactions, dose, age limits, and whether I should avoid this OTC product.",
    ])

    return {
        "product_name": product_name,
        "active_ingredients": active_ingredients,
        "memo_text": "\n".join(lines).strip(),
    }


def _build_manual_check_url(query: str, symptom_context: str = "") -> str:
    token = str(query or "").strip()
    if not token:
        return ""
    url = f"/smart-search/?q={quote_plus(token)}"
    if symptom_context:
        url += f"&symptom_context={quote_plus(str(symptom_context).strip())}"
    return url


def home(request):
    user = request.session.get("supabase_user")
    return render(request, "index.html", {"user": user})


def healthz(request):
    return JsonResponse({"status": "ok"})


def symptom_products_page(request):
    payload = request.session.get("last_symptom_result")
    if not isinstance(payload, dict):
        return redirect("chat:home")

    return render(
        request,
        "symptom_products_page.html",
        {
            "symptom": str(payload.get("symptom") or "").strip(),
            "consultation_note": payload.get("consultation_note"),
            "followup": payload.get("followup") or {},
        },
    )


async def _run_search_pipeline(request, query: str, symptom_context: str = ""):
    logger.info("LangGraph User Query: %s", query)

    user_info = request.session.get("supabase_user")
    inputs = {"query": query, "user_info": user_info, "symptom_context": symptom_context}

    try:
        result = await get_graph().ainvoke(inputs)
    except Exception as exc:
        logger.error("Graph Execution Error: %s", exc)
        return {
            "status": "error",
            "query": query,
            "message": f"처리 중 오류가 발생했습니다: {str(exc)}",
        }

    category = result.get("category")
    final_answer = result.get("final_answer", "")
    cache_source = result.get("cache_source")

    if category == "symptom_recommendation":
        followup = result.get("symptom_followup") or {}
        consultation_note = await _build_consultation_note(
            symptom=query,
            user_profile=result.get("user_profile") or {},
            symptom_term=result.get("symptom_term") or "",
        )
        request.session["last_symptom_result"] = {
            "symptom": query,
            "answer": final_answer,
            "consultation_note": consultation_note,
            "followup": followup,
        }
        return {
            "status": "ok",
            "query": query,
            "category": category,
            "cache_source": cache_source,
            "template": "symptom_result.html",
            "context": {
                "symptom": query,
                "answer": final_answer,
                "consultation_note": consultation_note,
                "followup": followup,
            },
            "data": {
                "answer": final_answer,
                "consultation_note": consultation_note,
                "followup": followup,
            },
        }

    if category == "product_request":
        fda = result.get("fda_data")
        structured_dur = result.get("dur_data", []) or []
        user_profile = result.get("user_profile") or {}

        if not fda:
            answer_text = final_answer or f"'{query}' 제품 또는 성분 정보를 찾지 못했습니다."
            return {
                "status": "ok",
                "query": query,
                "category": "general_medical",
                "cache_source": cache_source,
                "template": "general_result.html",
                "context": {
                    "query": query,
                    "answer": answer_text,
                    "symptom_context": symptom_context,
                },
                "data": {
                    "answer": answer_text,
                },
            }

        assessments = _build_product_assessments(structured_dur, user_profile)
        overall_status = _summarize_assessments(assessments)
        dur_summary = _build_structured_dur_summary(structured_dur)
        symptom_fit_note = _build_symptom_fit_note(symptom_context, fda)
        profile_snapshot = _build_profile_snapshot(user_profile)
        general_use_panel = _build_general_use_panel(fda, fallback_name=query)
        consultation_note = await _build_product_consultation_note(
            query=query,
            fda_data=fda,
            user_profile=user_profile,
            symptom_context=symptom_context,
        )

        return {
            "status": "ok",
            "query": query,
            "category": category,
            "cache_source": cache_source,
            "template": "search_result.html",
            "context": {
                "drug_name": fda.get("brand_name", query),
                "ingredients": fda.get("active_ingredients"),
                "ingredient_list": fda.get("ingredient_list") or [],
                "search_query": query,
                "matched_query": result.get("keyword") or fda.get("brand_name", ""),
                "us_guideline": fda,
                "ingredient_assessments": assessments,
                "overall_status": overall_status,
                "dur_summary": dur_summary,
                "profile_snapshot": profile_snapshot,
                "symptom_context": symptom_context,
                "symptom_fit_note": symptom_fit_note,
                "general_use_panel": general_use_panel,
                "consultation_note": consultation_note,
                "answer": final_answer,
            },
            "data": {
                "fda_data": fda,
                "dur_data": structured_dur,
                "ingredient_assessments": assessments,
                "overall_status": overall_status,
                "dur_summary": dur_summary,
                "profile_snapshot": profile_snapshot,
                "symptom_context": symptom_context,
                "symptom_fit_note": symptom_fit_note,
                "general_use_panel": general_use_panel,
                "consultation_note": consultation_note,
            },
        }

    if category == "general_medical":
        return {
            "status": "ok",
            "query": query,
            "category": category,
            "cache_source": cache_source,
            "template": "general_result.html",
            "context": {
                "query": query,
                "answer": final_answer,
                "symptom_context": symptom_context,
            },
            "data": {
                "answer": final_answer,
            },
        }

    return {
        "status": "error",
        "query": query,
        "category": category,
        "cache_source": cache_source,
        "message": final_answer or "요청을 처리할 수 없습니다.",
    }


async def smart_search(request):
    query = request.GET.get("q") or request.POST.get("q")
    if not query:
        return HttpResponse("<script>alert('검색어를 입력하세요.'); history.back();</script>")

    symptom_context = request.GET.get("symptom_context") or request.POST.get("symptom_context") or ""
    payload = await _run_search_pipeline(request, query, symptom_context=symptom_context)
    if payload.get("status") != "ok":
        return render(request, "error.html", {"message": payload.get("message", "요청을 처리할 수 없습니다.")})

    return render(request, payload["template"], payload["context"])


async def smart_search_api(request):
    query = request.GET.get("q") or request.POST.get("q")
    if not query:
        return JsonResponse({"status": "error", "message": "q is required"}, status=400)

    symptom_context = request.GET.get("symptom_context") or request.POST.get("symptom_context") or ""
    payload = await _run_search_pipeline(request, query, symptom_context=symptom_context)
    if payload.get("status") != "ok":
        return JsonResponse(
            {
                "status": "error",
                "query": query,
                "category": payload.get("category"),
                "cache_source": payload.get("cache_source"),
                "message": payload.get("message", "요청을 처리할 수 없습니다."),
            },
            status=500,
        )

    return JsonResponse(
        {
            "status": "success",
            "query": payload.get("query", query),
            "category": payload.get("category"),
            "cache_source": payload.get("cache_source"),
            "data": payload.get("data", {}),
        }
    )


async def pharmacy_api(request):
    try:
        lat = float(request.GET.get("lat", 0))
        lng = float(request.GET.get("lng", 0))
        radius_m = int(request.GET.get("radius", 3000) or 3000)
        limit = int(request.GET.get("limit", 10) or 10)
    except (TypeError, ValueError):
        return JsonResponse({"status": "error", "message": "Invalid coordinates or query params"}, status=400)

    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return JsonResponse({"status": "error", "message": "Coordinates out of range"}, status=400)

    from services.map_service import MapService

    try:
        results = await MapService.find_nearby_pharmacies(lat=lat, lng=lng, radius_m=radius_m, limit=limit)
        return JsonResponse({"status": "success", "results": results})
    except Exception as exc:
        logger.error("Error fetching pharmacies: %s", exc)
        return JsonResponse({"status": "error", "message": str(exc)})


async def symptom_products_api(request):
    query = request.GET.get("q") or request.POST.get("q")
    symptom_context = request.GET.get("symptom_context") or request.POST.get("symptom_context") or ""
    if query:
        payload = await _run_search_pipeline(request, query, symptom_context=symptom_context)
        if payload.get("status") != "ok":
            return JsonResponse({"status": "error", "message": payload.get("message", "요청을 처리할 수 없습니다.")}, status=500)
        return JsonResponse({"status": "success", "query": query, "category": payload.get("category"), "data": payload.get("data", {})})

    raw = request.GET.get("ingredients", "").strip()
    ingredients = []
    seen = set()
    for token in re.split(r"[,/;|\n+]+", raw):
        ingredient = str(token or "").strip().upper()
        ingredient = canonicalize_ingredient_name(ingredient)
        ingredient = str(ingredient or "").strip().upper()
        if not ingredient or ingredient in seen:
            continue
        seen.add(ingredient)
        ingredients.append(ingredient)
    if not ingredients:
        return JsonResponse({"status": "error", "message": "q or ingredients is required"}, status=400)

    from services.drug_service import DrugService
    from services.user_service import UserService

    user_profile = {}
    try:
        user_info = request.session.get("supabase_user")
        if isinstance(user_info, dict) and user_info.get("id"):
            profile = await UserService.get_profile(user_info)
            if profile:
                user_profile = {
                    "current_medications": str(getattr(profile, "current_medications", "") or "").strip(),
                    "allergies": str(getattr(profile, "allergies", "") or "").strip(),
                    "chronic_diseases": str(getattr(profile, "chronic_diseases", "") or "").strip(),
                    "is_pregnant": bool(getattr(profile, "is_pregnant", False)),
                    "main_ingr_eng": str(getattr(profile, "main_ingr_eng", "") or "").strip(),
                }
    except Exception as exc:
        logger.warning("failed to load user profile in symptom_products_api: %s", exc)

    dur_data = await DrugService.get_kr_dur_info(ingredients)
    assessments = _build_product_assessments(dur_data, user_profile)
    return JsonResponse(
        {
            "status": "success",
            "ingredients": ingredients,
            "overall_status": _summarize_assessments(assessments),
            "assessments": assessments,
            "profile_snapshot": _build_profile_snapshot(user_profile),
        }
    )


async def label_image_api(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "POST only"}, status=405)

    uploaded_file = request.FILES.get("image")
    if not uploaded_file:
        return JsonResponse({"status": "error", "message": "image file is required"}, status=400)

    symptom_context = str(request.POST.get("symptom_context") or "").strip()

    try:
        from services.image_label_service import ImageLabelService

        data = await ImageLabelService.analyze_label_image(uploaded_file)
    except ValueError as exc:
        return JsonResponse({"status": "error", "message": str(exc)}, status=400)
    except RuntimeError as exc:
        return JsonResponse({"status": "error", "message": str(exc)}, status=503)
    except Exception as exc:
        logger.exception("label image analysis failed: %s", exc)
        return JsonResponse({"status": "error", "message": "이미지 분석 중 오류가 발생했습니다."}, status=500)

    detected_query_term = str(data.get("detected_query_term") or "").strip()
    if detected_query_term:
        data["search_url"] = _build_manual_check_url(detected_query_term, symptom_context=symptom_context)
    data["symptom_context"] = symptom_context
    return JsonResponse({"status": "success", "data": data})
