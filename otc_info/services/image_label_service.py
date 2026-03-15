import base64
import json
import logging
import mimetypes
import os
from typing import Dict, List

from services.ai_service_v2 import AIService
from services.ingredient_utils import canonicalize_ingredient_name

logger = logging.getLogger(__name__)


class ImageLabelService:
    ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
    MAX_UPLOAD_BYTES = int(os.getenv("LABEL_IMAGE_MAX_BYTES", str(8 * 1024 * 1024)))

    @classmethod
    def _guess_content_type(cls, uploaded_file) -> str:
        content_type = str(getattr(uploaded_file, "content_type", "") or "").strip().lower()
        if content_type:
            return content_type
        filename = str(getattr(uploaded_file, "name", "") or "")
        guessed, _ = mimetypes.guess_type(filename)
        return str(guessed or "application/octet-stream").lower()

    @classmethod
    def _validate_upload(cls, uploaded_file) -> str:
        if uploaded_file is None:
            raise ValueError("이미지 파일이 필요합니다.")
        size = int(getattr(uploaded_file, "size", 0) or 0)
        if size <= 0:
            raise ValueError("빈 파일은 업로드할 수 없습니다.")
        if size > cls.MAX_UPLOAD_BYTES:
            raise ValueError("이미지 크기가 너무 큽니다. 8MB 이하 파일을 사용해 주세요.")
        content_type = cls._guess_content_type(uploaded_file)
        if content_type not in cls.ALLOWED_CONTENT_TYPES:
            raise ValueError("JPEG, PNG, WEBP 이미지 파일만 지원합니다.")
        return content_type

    @classmethod
    def _to_data_url(cls, uploaded_file) -> str:
        content_type = cls._validate_upload(uploaded_file)
        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(0)
        content = uploaded_file.read()
        if not content:
            raise ValueError("이미지 내용을 읽지 못했습니다.")
        encoded = base64.b64encode(content).decode("ascii")
        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(0)
        return f"data:{content_type};base64,{encoded}"

    @staticmethod
    def _clean_string_list(values, limit: int = 8) -> List[str]:
        if not isinstance(values, list):
            return []
        cleaned = []
        seen = set()
        for item in values:
            token = str(item or "").strip()
            if not token:
                continue
            key = token.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(token)
            if len(cleaned) >= limit:
                break
        return cleaned

    @staticmethod
    def _truncate_text(value: str, max_len: int = 1200) -> str:
        text = str(value or "").strip()
        if len(text) <= max_len:
            return text
        return text[: max_len - 3].rstrip() + "..."

    @classmethod
    def _normalize_active_ingredients(cls, values) -> List[str]:
        normalized = []
        seen = set()
        for token in cls._clean_string_list(values, limit=8):
            canonical = canonicalize_ingredient_name(token) or token
            canonical = str(canonical or "").strip()
            if not canonical:
                continue
            key = canonical.lower()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(canonical)
        return normalized

    @classmethod
    async def analyze_label_image(cls, uploaded_file) -> Dict:
        data_url = cls._to_data_url(uploaded_file)
        client = AIService.get_client()
        if not client:
            raise RuntimeError("OpenAI API 키가 설정되지 않아 이미지 분석을 수행할 수 없습니다.")

        system_prompt = (
            "You analyze photos of U.S. OTC medicine packaging, Drug Facts panels, or warning labels.\n"
            "Allowed tasks:\n"
            "1) Read visible text as accurately as possible.\n"
            "2) Translate visible text into Korean.\n"
            "3) Explain what the visible warning, dosage, age, and ingredient text means in plain Korean.\n"
            "4) Identify product name, active ingredients, and warning headings ONLY if visible.\n"
            "5) Clearly mark uncertain or unreadable parts.\n"
            "Strict prohibitions:\n"
            "- Do not recommend a medicine.\n"
            "- Do not say whether a specific person can safely take it.\n"
            "- Do not diagnose symptoms.\n"
            "- Do not personalize based on medical history.\n"
            "Return neutral label interpretation only."
        )
        user_text = (
            "Read the uploaded medicine photo. It may show the front package, Drug Facts, or a warnings panel. "
            "Return structured JSON. If the image is blurry, partial, or non-medication-related, say so clearly."
        )

        schema = {
            "name": "otc_label_image_analysis",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "label_type": {
                        "type": "string",
                        "enum": ["product_front", "drug_facts", "warning_panel", "unknown"],
                    },
                    "product_name": {"type": "string"},
                    "active_ingredients": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 0,
                        "maxItems": 8,
                    },
                    "warning_headings": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 0,
                        "maxItems": 8,
                    },
                    "raw_visible_text": {"type": "string"},
                    "korean_translation": {"type": "string"},
                    "plain_explanation": {"type": "string"},
                    "caution_points": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 0,
                        "maxItems": 8,
                    },
                    "uncertain_points": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 0,
                        "maxItems": 6,
                    },
                    "detected_query_term": {"type": "string"},
                },
                "required": [
                    "label_type",
                    "product_name",
                    "active_ingredients",
                    "warning_headings",
                    "raw_visible_text",
                    "korean_translation",
                    "plain_explanation",
                    "caution_points",
                    "uncertain_points",
                    "detected_query_term",
                ],
                "additionalProperties": False,
            },
        }

        try:
            response = await client.chat.completions.create(
                model=os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_text},
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ],
                    },
                ],
                temperature=0,
                response_format={"type": "json_schema", "json_schema": schema},
            )
            raw = response.choices[0].message.content or "{}"
            data = json.loads(raw)
        except Exception as exc:
            logger.error("image label analysis failed: %s", exc)
            raise RuntimeError("이미지 분석 모델 호출에 실패했습니다.") from exc

        product_name = str((data or {}).get("product_name") or "").strip()
        active_ingredients = cls._normalize_active_ingredients((data or {}).get("active_ingredients", []))
        warning_headings = cls._clean_string_list((data or {}).get("warning_headings", []), limit=8)
        raw_visible_text = cls._truncate_text((data or {}).get("raw_visible_text") or "")
        korean_translation = cls._truncate_text((data or {}).get("korean_translation") or "", max_len=1600)
        plain_explanation = cls._truncate_text((data or {}).get("plain_explanation") or "", max_len=1200)
        caution_points = cls._clean_string_list((data or {}).get("caution_points", []), limit=8)
        uncertain_points = cls._clean_string_list((data or {}).get("uncertain_points", []), limit=6)
        detected_query_term = str((data or {}).get("detected_query_term") or "").strip()

        if not detected_query_term:
            detected_query_term = product_name or (active_ingredients[0] if active_ingredients else "")

        return {
            "label_type": str((data or {}).get("label_type") or "unknown").strip() or "unknown",
            "product_name": product_name,
            "active_ingredients": active_ingredients,
            "warning_headings": warning_headings,
            "raw_visible_text": raw_visible_text,
            "korean_translation": korean_translation,
            "plain_explanation": plain_explanation,
            "caution_points": caution_points,
            "uncertain_points": uncertain_points,
            "detected_query_term": detected_query_term,
            "source_filename": str(getattr(uploaded_file, "name", "") or "").strip(),
        }
