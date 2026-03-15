import asyncio
import logging
import math
import os
import re
from functools import lru_cache

from services.ingredient_utils import canonicalize_ingredient_name

logger = logging.getLogger(__name__)


class LocalModelService:
    _classifier = None
    _generator = None
    _embedder = None
    _symptom_index = None

    _CATEGORY_LABELS = {
        "symptom_recommendation": "symptom recommendation",
        "product_request": "specific product request",
        "general_medical": "general medical question",
    }

    _SYMPTOM_ALIASES = {
        "두통": [
            "두통",
            "머리 아픔",
            "머리가 아파",
            "머리 아파",
            "headache",
            "head pain",
            "pain relief",
        ],
        "편두통": ["편두통", "migraine", "편측 두통", "지끈거림"],
        "알레르기": ["알레르기", "allergy", "알러지", "재채기", "콧물", "itch"],
        "기침": ["기침", "cough", "콜록", "가래", "목이 칼칼"],
        "감기": ["감기", "cold", "몸살", "오한"],
        "발열": ["발열", "fever", "열남", "열이 나", "고열"],
        "소화불량": ["소화불량", "indigestion", "체함", "속이 더부룩", "더부룩"],
        "복통": ["복통", "배 아픔", "배가 아파", "stomachache", "abdominal pain"],
        "염좌": ["염좌", "sprain", "삐었", "접질렀"],
        "찰과상": ["찰과상", "wound", "skin abrasion", "까졌", "긁힘"],
        "화상": ["화상", "burn", "데였", "화끈"],
        "곤충교상": ["곤충교상", "insect bite", "벌레 물림", "모기 물림", "가려움"],
    }

    _SYMPTOM_SEARCH_TERMS = {
        "두통": ["headache", "pain relief"],
        "편두통": ["migraine", "headache"],
        "알레르기": ["allergy", "antihistamine", "itch relief"],
        "기침": ["cough", "cold", "nasal congestion"],
        "감기": ["cold", "flu symptoms"],
        "발열": ["fever", "pain relief"],
        "소화불량": ["indigestion", "heartburn"],
        "복통": ["stomachache", "abdominal pain"],
        "염좌": ["sprain", "muscle pain"],
        "찰과상": ["wound", "skin abrasion"],
        "화상": ["burn", "burn relief"],
        "곤충교상": ["insect bite", "itch relief"],
    }

    _SYMPTOM_INGREDIENTS = {
        "두통": ["ACETAMINOPHEN", "IBUPROFEN", "NAPROXEN", "ASPIRIN"],
        "편두통": ["IBUPROFEN", "NAPROXEN", "ACETAMINOPHEN", "ASPIRIN"],
        "알레르기": ["LORATADINE", "CETIRIZINE", "DIPHENHYDRAMINE"],
        "기침": ["DEXTROMETHORPHAN", "GUAIFENESIN", "DIPHENHYDRAMINE"],
        "감기": ["ACETAMINOPHEN", "DEXTROMETHORPHAN", "GUAIFENESIN", "PHENYLEPHRINE"],
        "발열": ["ACETAMINOPHEN", "IBUPROFEN", "ASPIRIN"],
        "소화불량": ["BISMUTH SUBSALICYLATE", "FAMOTIDINE", "OMEPRAZOLE"],
        "복통": ["BISMUTH SUBSALICYLATE", "LOPERAMIDE", "FAMOTIDINE"],
        "염좌": ["IBUPROFEN", "NAPROXEN", "ACETAMINOPHEN"],
        "찰과상": ["BACITRACIN", "NEOMYCIN", "POLYMYXIN B"],
        "화상": ["LIDOCAINE", "ALOE VERA"],
        "곤충교상": ["DIPHENHYDRAMINE", "HYDROCORTISONE"],
    }

    _PRODUCT_ALIASES = {
        "타이레놀": "Tylenol",
        "tylenol": "Tylenol",
        "애드빌": "Advil",
        "advil": "Advil",
        "부루펜": "ibuprofen",
        "이부프로펜": "ibuprofen",
        "아세트아미노펜": "acetaminophen",
        "acetaminophen": "acetaminophen",
        "ibuprofen": "ibuprofen",
        "naproxen": "naproxen",
        "aspirin": "aspirin",
    }

    _KNOWN_PRODUCT_TOKENS = {
        "tylenol",
        "advil",
        "acetaminophen",
        "ibuprofen",
        "naproxen",
        "aspirin",
        "loratadine",
        "cetirizine",
        "diphenhydramine",
        "guaifenesin",
        "dextromethorphan",
        "famotidine",
        "omeprazole",
    }

    _GENERAL_HINTS = (
        "항생제",
        "내성",
        "복용법",
        "부작용",
        "상호작용",
        "주의사항",
        "건강정보",
    )

    @classmethod
    def is_enabled(cls) -> bool:
        token = str(
            os.getenv("AI_PROVIDER")
            or os.getenv("LOCAL_MODEL_ENABLED")
            or ""
        ).strip().lower()
        return token in {"local", "1", "true", "yes", "on"}

    @staticmethod
    def _normalize_text(text: str) -> str:
        value = str(text or "").strip().lower()
        value = re.sub(r"\s+", " ", value)
        return value

    @staticmethod
    def _safe_cache_key(value: str) -> str:
        token = re.sub(r"[^a-z0-9_가-힣\-]", "_", str(value or "").strip().lower())
        token = re.sub(r"_+", "_", token).strip("_")
        return token or "unknown"

    @staticmethod
    def _extract_english_tokens(text: str):
        return re.findall(r"[a-zA-Z][a-zA-Z0-9\-]+", str(text or ""))

    @classmethod
    def _severity_from_query(cls, query: str) -> str:
        text = cls._normalize_text(query)
        if any(token in text for token in ("심한", "심하게", "극심", "아주 아픈", "severe", "terrible")):
            return "severe"
        if any(token in text for token in ("약한", "가벼운", "mild", "살짝")):
            return "mild"
        return "moderate"

    @classmethod
    def _quality_from_query(cls, query: str) -> str:
        text = cls._normalize_text(query)
        mapping = {
            "splitting": ("지끈", "욱신", "깨질", "splitting"),
            "sharp": ("찌르", "sharp"),
            "burning": ("화끈", "burning"),
            "stuffy": ("막힘", "답답", "stuffy"),
        }
        for label, tokens in mapping.items():
            if any(token in text for token in tokens):
                return label
        return "none"

    @classmethod
    def _heuristic_category(cls, query: str):
        text = cls._normalize_text(query)
        if not text or len(text) < 2:
            return "invalid"

        if cls._lookup_product_term(text):
            return "product_request"
        if cls._lookup_symptom_term(text):
            return "symptom_recommendation"
        if any(token in text for token in ("추천", "약", "먹", "바를", "증상", "아픈", "가려")):
            return "symptom_recommendation"
        if any(token in text for token in cls._GENERAL_HINTS):
            return "general_medical"
        return "general_medical"

    @classmethod
    def _lookup_product_term(cls, text: str) -> str:
        normalized = cls._normalize_text(text)
        if normalized in cls._PRODUCT_ALIASES:
            return cls._PRODUCT_ALIASES[normalized]
        for alias, target in cls._PRODUCT_ALIASES.items():
            if alias in normalized:
                return target
        english_tokens = cls._extract_english_tokens(normalized)
        if english_tokens and english_tokens[0].lower() in cls._KNOWN_PRODUCT_TOKENS:
            return english_tokens[0]
        return ""

    @classmethod
    def _lookup_symptom_term(cls, text: str) -> str:
        normalized = cls._normalize_text(text)
        for canonical, aliases in cls._SYMPTOM_ALIASES.items():
            if canonical in normalized:
                return canonical
            for alias in aliases:
                if cls._normalize_text(alias) in normalized:
                    return canonical
        return ""

    @classmethod
    def _score_overlap(cls, query: str, alias: str) -> float:
        query_terms = set(re.findall(r"[a-z0-9가-힣]+", cls._normalize_text(query)))
        alias_terms = set(re.findall(r"[a-z0-9가-힣]+", cls._normalize_text(alias)))
        if not query_terms or not alias_terms:
            return 0.0
        intersection = len(query_terms & alias_terms)
        union = len(query_terms | alias_terms)
        return intersection / union if union else 0.0

    @classmethod
    def _load_embedder(cls):
        if cls._embedder is not None:
            return cls._embedder
        model_id = str(os.getenv("LOCAL_EMBED_MODEL_ID") or "").strip()
        if not model_id:
            return None
        try:
            from sentence_transformers import SentenceTransformer

            cls._embedder = SentenceTransformer(model_id)
        except Exception as exc:
            logger.warning("Local embedding model unavailable: %s", exc)
            cls._embedder = False
        return cls._embedder or None

    @classmethod
    def _load_classifier(cls):
        if cls._classifier is not None:
            return cls._classifier
        model_id = str(os.getenv("LOCAL_CLASSIFIER_MODEL_ID") or "").strip()
        if not model_id:
            return None
        try:
            from transformers import pipeline

            cls._classifier = pipeline(
                "zero-shot-classification",
                model=model_id,
            )
        except Exception as exc:
            logger.warning("Local classifier model unavailable: %s", exc)
            cls._classifier = False
        return cls._classifier or None

    @classmethod
    def _load_generator(cls):
        if cls._generator is not None:
            return cls._generator
        model_id = str(os.getenv("LOCAL_OUTPUT_MODEL_ID") or "").strip()
        if not model_id:
            return None
        try:
            from transformers import pipeline

            cls._generator = pipeline(
                "text-generation",
                model=model_id,
                device_map="auto",
            )
        except Exception as exc:
            logger.warning("Local generation model unavailable: %s", exc)
            cls._generator = False
        return cls._generator or None

    @classmethod
    @lru_cache(maxsize=1)
    def _build_symptom_index(cls):
        index = []
        for canonical, aliases in cls._SYMPTOM_ALIASES.items():
            for alias in aliases:
                index.append((canonical, alias))
        return index

    @classmethod
    def _embed_lookup(cls, query: str):
        model = cls._load_embedder()
        if not model:
            return ""
        index = cls._build_symptom_index()
        try:
            corpus = [alias for _, alias in index]
            query_vec = model.encode([query], normalize_embeddings=True)[0]
            alias_vecs = model.encode(corpus, normalize_embeddings=True)
            best_canonical = ""
            best_score = -1.0
            for idx, (canonical, _) in enumerate(index):
                score = float(sum(a * b for a, b in zip(query_vec, alias_vecs[idx])))
                if score > best_score:
                    best_score = score
                    best_canonical = canonical
            return best_canonical if best_score >= 0.42 else ""
        except Exception as exc:
            logger.warning("Embedding lookup failed: %s", exc)
            return ""

    @classmethod
    async def classify_intent(cls, query: str):
        query = str(query or "").strip()
        category = cls._heuristic_category(query)
        keyword = "none"

        if category == "product_request":
            keyword = await cls.normalize_product_keyword(query)
            cache_key = f"product_{cls._safe_cache_key(keyword)}"
        elif category == "symptom_recommendation":
            keyword = await cls.canonicalize_symptom_term(query)
            cache_key = await cls.normalize_symptom_query(query)
        elif category == "invalid":
            return {"category": "invalid", "keyword": "none", "cache_key": "invalid"}
        else:
            cache_key = f"general_{cls._safe_cache_key(query[:48])}"

        if category == "general_medical":
            classifier = cls._load_classifier()
            if classifier:
                try:
                    result = await asyncio.to_thread(
                        classifier,
                        query,
                        list(cls._CATEGORY_LABELS.values()),
                        hypothesis_template="This query is about {}.",
                    )
                    label = str((result.get("labels") or [""])[0] or "").strip().lower()
                    reverse = {v: k for k, v in cls._CATEGORY_LABELS.items()}
                    category = reverse.get(label, category)
                    if category == "symptom_recommendation":
                        keyword = await cls.canonicalize_symptom_term(query)
                        cache_key = await cls.normalize_symptom_query(query)
                    elif category == "product_request":
                        keyword = await cls.normalize_product_keyword(query)
                        cache_key = f"product_{cls._safe_cache_key(keyword)}"
                except Exception as exc:
                    logger.warning("Local zero-shot classifier failed: %s", exc)

        return {"category": category, "keyword": keyword, "cache_key": cache_key}

    @classmethod
    async def canonicalize_symptom_term(cls, query: str, hint_keyword: str = "") -> str:
        hint = str(hint_keyword or "").strip()
        if hint and hint in cls._SYMPTOM_ALIASES:
            return hint

        lexical = cls._lookup_symptom_term(query)
        if lexical:
            return lexical

        best_term = ""
        best_score = 0.0
        for canonical, alias in cls._build_symptom_index():
            score = cls._score_overlap(query, alias)
            if score > best_score:
                best_score = score
                best_term = canonical
        if best_term and best_score >= 0.18:
            return best_term

        embedded = cls._embed_lookup(query)
        if embedded:
            return embedded

        return hint or str(query or "").strip()

    @classmethod
    async def normalize_product_keyword(cls, query: str, hint_keyword: str = "") -> str:
        hint = str(hint_keyword or "").strip()
        product = cls._lookup_product_term(hint or query)
        return product or hint or str(query or "").strip()

    @classmethod
    async def normalize_symptom_query(cls, query: str) -> str:
        canonical = await cls.canonicalize_symptom_term(query)
        severity = cls._severity_from_query(query)
        quality = cls._quality_from_query(query)
        canonical_token = cls._safe_cache_key(canonical)
        return f"{canonical_token}_{severity}_{quality}"

    @classmethod
    async def select_direct_symptom_ingredients(cls, symptom: str, candidates, top_n: int = 5):
        normalized = []
        seen = set()
        if isinstance(candidates, list):
            for item in candidates:
                if isinstance(item, dict):
                    name = canonicalize_ingredient_name(item.get("ingredient"))
                    score = int(item.get("score", 0) or 0)
                else:
                    name = canonicalize_ingredient_name(item)
                    score = 0
                if not name or name in seen:
                    continue
                seen.add(name)
                normalized.append({"ingredient": name, "score": score})

        if not normalized:
            return []

        symptom_term = await cls.canonicalize_symptom_term(symptom)
        preferred = cls._SYMPTOM_INGREDIENTS.get(symptom_term, [])
        preferred_rank = {name: idx for idx, name in enumerate(preferred)}

        def _rank(item):
            name = item["ingredient"]
            preferred_score = preferred_rank.get(name, math.inf)
            return (preferred_score, -item["score"], name)

        normalized.sort(key=_rank)
        return [item["ingredient"] for item in normalized[: max(top_n, 1)]]

    @classmethod
    async def recommend_ingredients_for_symptom(cls, symptom: str):
        symptom_term = await cls.canonicalize_symptom_term(symptom)
        return list(cls._SYMPTOM_INGREDIENTS.get(symptom_term, []))

    @classmethod
    async def get_symptom_synonyms(cls, symptom: str):
        symptom_term = await cls.canonicalize_symptom_term(symptom)
        return list(cls._SYMPTOM_SEARCH_TERMS.get(symptom_term, []))

    @classmethod
    async def get_synonyms(cls, ingredient: str):
        name = canonicalize_ingredient_name(ingredient or "")
        if not name:
            return []
        mappings = {
            "ACETAMINOPHEN": ["acetaminophen", "paracetamol", "APAP"],
            "IBUPROFEN": ["ibuprofen", "advil", "motrin"],
            "NAPROXEN": ["naproxen", "aleve"],
            "ASPIRIN": ["aspirin", "acetylsalicylic acid"],
        }
        return mappings.get(name, [name])

    @classmethod
    async def translate_profile_fields_to_english(cls, meds: str, allergies: str, diseases: str):
        return {
            "meds": str(meds or "").strip(),
            "allergies": str(allergies or "").strip(),
            "diseases": str(diseases or "").strip(),
        }

    @classmethod
    async def _generate_text(cls, system_prompt: str, user_prompt: str, max_new_tokens: int = 256):
        generator = cls._load_generator()
        if not generator:
            return ""
        prompt = f"{system_prompt.strip()}\n\n{user_prompt.strip()}".strip()
        try:
            outputs = await asyncio.to_thread(
                generator,
                prompt,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                return_full_text=False,
            )
            if isinstance(outputs, list) and outputs:
                generated = outputs[0].get("generated_text")
                if isinstance(generated, str):
                    return generated.strip()
        except Exception as exc:
            logger.warning("Local generation failed: %s", exc)
        return ""

    @classmethod
    async def generate_general_answer(cls, query: str):
        generated = await cls._generate_text(
            "You are a concise OTC medical guidance assistant. Answer in Korean.",
            str(query or "").strip(),
            max_new_tokens=220,
        )
        if generated:
            return generated
        return (
            "현재 로컬 모드로 동작 중입니다. 증상이 지속되거나 악화되면 의사 또는 약사와 상담하고, "
            "복용 전에는 용법, 용량, 상호작용 여부를 함께 확인하세요."
        )

    @classmethod
    async def generate_web_search_answer(cls, query: str):
        return await cls.generate_general_answer(query)

    @classmethod
    async def generate_symptom_answer(cls, symptom, data, user_profile=None):
        items = []
        for item in data or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("ingredient") or item.get("name") or "").strip()
            if not name:
                continue
            warning_count = len(item.get("kr_durs") or [])
            items.append(
                {
                    "name": name,
                    "warning_count": warning_count,
                    "has_fda_warning": bool(item.get("fda_warning")),
                }
            )
        summary = await cls.generate_general_answer(
            f"{symptom} 증상에 대해 확인된 성분 수는 {len(items)}개입니다."
        )
        return {"summary": summary, "ingredients": items}

    @classmethod
    async def bulk_summarize_fda_warnings(cls, warnings_dict: dict) -> dict:
        result = {}
        for ingredient, warning in (warnings_dict or {}).items():
            text = re.sub(r"\s+", " ", str(warning or "").strip())
            if not text:
                result[ingredient] = "특이사항 없음"
            elif len(text) > 180:
                result[ingredient] = text[:177].rstrip() + "..."
            else:
                result[ingredient] = text
        return result

    @classmethod
    async def translate_purposes(cls, purposes: list) -> list:
        return [str(item or "").strip() for item in (purposes or [])]
