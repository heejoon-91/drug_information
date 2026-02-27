"""
application/services/map_service.py
MapService - 미국 OTC 매핑 서비스 (기존 services/map_service.py → 이동, import 경로 수정)
"""
import logging
import asyncio
from application.services.ai_service import AIService
from infrastructure.external_api.fda_client import FdaClient

logger = logging.getLogger(__name__)

_fda_client = FdaClient()


class MapService:

    @classmethod
    async def find_nearby_pharmacies(cls, lat: float, lng: float):
        return []

    @classmethod
    async def get_us_otc_products_by_ingredient(cls, ingredient: str, translate: bool = True):
        logger.info(f"[MapService] Fetching POPULAR US OTC products for ingredient: '{ingredient}'")
        # 가장 인기 있는 상위 5개 브랜드 추출
        popular_brands = await _fda_client.get_popular_products_by_ingredient(ingredient, limit=5)
        
        # UI 호환성을 위해 products 키로 반환
        return {"ingredient": ingredient, "products": popular_brands}

    @classmethod
    async def find_optimal_us_products(cls, ingredients: list) -> dict:
        result = await _fda_client.find_optimal_us_products(ingredients)
        # purpose 번역 처리
        if result.get("match_type") == "FULL_MATCH":
            products = result.get("recommendations", [])
            purposes = [p['purpose'] for p in products]
            translated = await AIService.translate_purposes(purposes)
            for i, prod in enumerate(products):
                if i < len(translated):
                    prod['purpose'] = translated[i]
        elif result.get("match_type") == "COMPONENT_MATCH":
            for ingr_result in result.get("recommendations", []):
                products = ingr_result.get("products", [])
                if products:
                    purposes = [p['purpose'] for p in products]
                    translated = await AIService.translate_purposes(purposes)
                    for i, prod in enumerate(products):
                        if i < len(translated):
                            prod['purpose'] = translated[i]
        return result

    @classmethod
    def generate_pharmacist_card(cls, ingredients: list, dosage_form: str = "Tablet/Capsule") -> dict:
        ingr_str = ", ".join(ingredients)
        return {
            "title": "Pharmacist Communication Card",
            "active_ingredients": ingredients,
            "desired_dosage_form": dosage_form,
            "english_guide": [
                f"Hello, I am looking for an OTC product containing these active ingredients: {ingr_str}.",
                f"I prefer the '{dosage_form}' form if available.",
                "Could you please recommend the closest match you have in stock?",
            ],
        }
