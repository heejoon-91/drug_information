from fastapi import APIRouter, Query, HTTPException
from services.drug_service import DrugService
from services.map_service import MapService
from typing import List, Dict

router = APIRouter(prefix="/api/drugs", tags=["drugs"])

@router.get("/search")
async def search_drugs(q: str = Query("", min_length=0)):
    """
    Search drugs by name or manufacturer from EYakInfo.
    If q is empty, returns top 100 drugs.
    """
    try:
        results = await DrugService.search_eyak_drug(q)
        return results
    except Exception as e:
        print(f"Error searching drugs: {e}")
        return []

@router.get("/us-roadmap")
async def get_us_roadmap(
    ingredients: List[str] = Query(..., description="복합제 혹은 단일제 주성분 영문명 리스트 (예: ACETAMINOPHEN)"), 
    kr_dosage_mg: float = Query(0.0, description="한국 기존 약물 기준 함량(mg) - 단일제 비교 시 활용")
):
    """
    한국 약품 주성분(들)을 기반으로 미국 가용 OTC 대체재 큐레이션 및 소통 카드 생성
    """
    try:
        # 1. & 2. 복합제 듀얼 매치 모듈 호출 (Full Match or Component Match)
        mapping_result = await MapService.find_optimal_us_products(ingredients)
        
        # 3. 약사 상담 브릿지 생성
        pharmacist_card = MapService.generate_pharmacist_card(ingredients)
        
        # 4. 용량 경고 분석
        dosage_warnings = []
        if kr_dosage_mg > 0 and mapping_result.get("recommendations"):
            match_type = mapping_result.get("match_type")
            
            if match_type == "FULL_MATCH":
                # Full Match: 복합제에서 대표 성분(또는 첫번째 비교 가능한 활성성분)을 통한 용량 비교
                for rec in mapping_result["recommendations"]:
                    active_ingr = rec.get("active_ingredient", "")
                    warn_info = DrugService.compare_dosage_and_warn(active_ingr, kr_dosage_mg)
                    if warn_info.get("us_dosage_mg") is not None:
                        dosage_warnings.append({
                            "brand_name": rec.get("brand_name"),
                            "warning_info": warn_info
                        })
            elif match_type == "COMPONENT_MATCH":
                # Component Match: 첫 번째 성분(보통 주성분)의 단일제 추천 목록을 기준으로 임의의 1개 용량 비교 예시 제공
                first_ingr_recs = mapping_result["recommendations"][0].get("products", [])
                for rec in first_ingr_recs[:3]: # 상위 3개만 비교
                    active_ingr = rec.get("active_ingredient", "")
                    warn_info = DrugService.compare_dosage_and_warn(active_ingr, kr_dosage_mg)
                    if warn_info.get("us_dosage_mg") is not None:
                        dosage_warnings.append({
                            "brand_name": rec.get("brand_name"),
                            "warning_info": warn_info
                        })

        return {
            "requested_ingredients": ingredients,
            "mapping_result": mapping_result,
            "pharmacist_card": pharmacist_card,
            "dosage_warnings": dosage_warnings
        }
    except Exception as e:
        print(f"Error generating US Roadmap: {e}")
        raise HTTPException(status_code=500, detail="오류가 발생하여 정보를 생성하지 못했습니다.")
