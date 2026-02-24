from fastapi import APIRouter, Query, HTTPException
from typing import List

from infrastructure.django_db.drug_repository import DjangoDrugRepository
from infrastructure.django_db.dur_repository import DjangoDurRepository
from infrastructure.external_api.fda_client import FdaClient
from infrastructure.cache.supabase_cache import SupabaseCacheRepository
from application.use_cases.drug_search import DrugSearchUseCase
from application.services.map_service import MapService
from domain.drug.services import DurAnalysisService

router = APIRouter(prefix="/api/drugs", tags=["drugs"])

# DI (인터페이스 계층에서 인프라와 애플리케이션 계층을 조립)
drug_repo = DjangoDrugRepository()
dur_repo = DjangoDurRepository()
fda_client = FdaClient()
supabase_cache = SupabaseCacheRepository()
dur_analysis_svc = DurAnalysisService()

drug_search_use_case = DrugSearchUseCase(drug_repo)

@router.get("/search")
async def search_drugs(q: str = Query("", min_length=0)):
    """
    제품명 또는 업체명으로 약품 검색
    """
    return await drug_search_use_case.execute(q)

@router.get("/us-roadmap")
async def get_us_roadmap(
    ingredients: List[str] = Query(..., description="주성분 영문명 리스트"), 
    kr_dosage_mg: float = Query(0.0, description="한국 기준 함량(mg)")
):
    """
    한국 약품 주성분 기반 미국 OTC 대체재 로드맵 생성 (캐시 활용)
    """
    # 1. 캐시 키 생성
    sorted_ingrs = sorted([ingr.strip().upper() for ingr in ingredients if ingr.strip()])
    ingrs_str = "_".join(sorted_ingrs)
    cache_key = f"roadmap_{kr_dosage_mg}_{ingrs_str}"
    
    # 2. 캐시 확인
    try:
        cached_data = await supabase_cache.get_roadmap_cache(cache_key)
        if cached_data:
            return {
                "requested_ingredients": ingredients,
                "mapping_result": cached_data.get("mapping_result", {}),
                "pharmacist_card": cached_data.get("pharmacist_card", {}),
                "dosage_warnings": cached_data.get("dosage_warnings", [])
            }
    except Exception as e:
        print(f"[Roadmap Cache Read Error]: {e}")

    # 3. 신규 로드맵 생성
    try:
        mapping_result = await MapService.find_optimal_us_products(ingredients)
        pharmacist_card = MapService.generate_pharmacist_card(ingredients)
        
        # 용량 경고 분석 (도메인 서비스 활용)
        dosage_warnings = []
        recommendations = []
        if mapping_result.get("match_type") == "FULL_MATCH":
            recommendations = mapping_result.get("recommendations", [])
        elif mapping_result.get("match_type") == "COMPONENT_MATCH":
            recs = mapping_result.get("recommendations", [])
            if recs:
                recommendations = recs[0].get("products", [])[:3]

        if kr_dosage_mg > 0:
            for rec in recommendations:
                active_ingr = rec.get("active_ingredient", "")
                warn_info = dur_analysis_svc.compare_dosage(active_ingr, kr_dosage_mg)
                if warn_info.get("us_dosage_mg") is not None:
                    dosage_warnings.append({
                        "brand_name": rec.get("brand_name"),
                        "warning_info": warn_info
                    })

        # 4. 캐시 저장
        import asyncio
        asyncio.create_task(
            supabase_cache.set_roadmap_cache(
                query_text=cache_key,
                mapping_result=mapping_result,
                pharmacist_card=pharmacist_card,
                dosage_warnings=dosage_warnings
            )
        )

        return {
            "requested_ingredients": ingredients,
            "mapping_result": mapping_result,
            "pharmacist_card": pharmacist_card,
            "dosage_warnings": dosage_warnings
        }
    except Exception as e:
        print(f"Error generating US Roadmap: {e}")
        raise HTTPException(status_code=500, detail="오류가 발생하여 정보를 생성하지 못했습니다.")
