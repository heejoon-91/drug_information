import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from routers.drug_router import get_us_roadmap

async def test_roadmap():
    print("=== Test 1: Single Ingredient (ACETAMINOPHEN 500mg) ===")
    res1 = await get_us_roadmap(ingredients=["ACETAMINOPHEN"], kr_dosage_mg=500.0)
    print(f"Match Type: {res1['mapping_result']['match_type']}")
    print(f"Warnings: {res1['dosage_warnings'][:2]}")
    print(f"Card Title: {res1['pharmacist_card']['title']}")

    print("\n=== Test 2: Combo Ingredients (ACETAMINOPHEN + CHLORPHENIRAMINE) ===")
    res2 = await get_us_roadmap(ingredients=["ACETAMINOPHEN", "CHLORPHENIRAMINE"], kr_dosage_mg=0.0)
    print(f"Match Type: {res2['mapping_result']['match_type']}")
    recs = res2['mapping_result']['recommendations']
    if res2['mapping_result']['match_type'] == 'FULL_MATCH':
        print(f"Found {len(recs)} Full Match products.")
        if recs:
            print(f"Example: {recs[0]['brand_name']}")
    elif res2['mapping_result']['match_type'] == 'COMPONENT_MATCH':
        print(f"Fallback to Component Match. Found {len(recs)} individual ingredient groups.")

if __name__ == "__main__":
    asyncio.run(test_roadmap())
