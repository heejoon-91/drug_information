import asyncio
import os
import sys

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.ai_service import AIService

async def test_intent_classification():
    query = "배가 너무 아파요"
    print(f"Test Query: {query}")
    
    # 1. 의도 분류 호출
    result = await AIService.classify_intent(query)
    print(f"Result: {result}")
    
    # 2. 키 확인
    if "fda_search_keywords" in result:
        print("SUCCESS: 'fda_search_keywords' key found in response.")
        print(f"Keywords: {result['fda_search_keywords']}")
    else:
        print("FAILURE: 'fda_search_keywords' key NOT found.")
        print(f"Available keys: {list(result.keys())}")

if __name__ == "__main__":
    asyncio.run(test_intent_classification())
