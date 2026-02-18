from fastapi import APIRouter, Query, HTTPException
from services.drug_service import DrugService
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
