
import asyncio
import os
import json
import logging
from dotenv import load_dotenv

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 경로 추가 (프로젝트 루트 및 api_fastapi)
import sys
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), 'api_fastapi'))

from infrastructure.external_api.fda_client import FdaClient
from application.services.ai_service import AIService

async def run_experiment():
    print(">>> EXPERIMENT STARTED", flush=True)
    load_dotenv()
    fda = FdaClient()
    
    query = "머리 아파"
    print(f">>> Query: {query}", flush=True)
    
    # 1. FDA 성분 추출 확인
    # classify_intent에서 키워드 추출 시뮬레이션
    intent = await AIService.classify_intent(query)
    keyword = intent.get("keyword", "HEADACHE")
    logger.info(f"추출 키워드: {keyword}")
    
    fda_ingrs = await fda.get_ingredients_by_symptoms([keyword])
    logger.info(f"FDA에서 찾은 성분 (상위 20개): {fda_ingrs[:20]}")
    
    if "ACETAMINOPHEN" in [i.upper() for i in fda_ingrs]:
        logger.info("결과: FDA 데이터에 ACETAMINOPHEN이 포함되어 있습니다.")
    else:
        logger.warning("결과: FDA 데이터에 ACETAMINOPHEN이 없습니다!")

    # 2. 온도별 AI 답변 생성 실험
    # 가상의 DUR 데이터 (DUR은 일관성 있으므로 고정)
    dummy_dur_data = []
    for ingr in fda_ingrs[:10]:
        dummy_dur_data.append({
            "ingredient": ingr,
            "kr_durs": [],
            "fda_warning": None
        })

    results = {}
    temps = [0.0, 0.5, 1.0]
    
    for t in temps:
        logger.info(f"Temperature {t} 실험 중...")
        # ai_service.py의 generate_symptom_answer는 내부적으로 0으로 고정되어 있으므로
        # 실험을 위해 직접 호출 로직을 복사하거나 임시 수정해서 호출해야 함
        # 여기서는 AIService 클래스의 메서드를 활용하되 프롬프트를 직접 넣어 실험
        
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        from prompts.answer_prompts_v2 import SYMPTOM_RESPONSE_PROMPT_V2
        
        res = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "system",
                "content": SYMPTOM_RESPONSE_PROMPT_V2.format(
                    symptom=query,
                    data=str(dummy_dur_data),
                    medications="None",
                    allergies="None",
                    chronic_diseases="None"
                )
            }],
            temperature=t,
            response_format={"type": "json_object"}
        )
        content = json.loads(res.choices[0].message.content)
        results[t] = {
            "summary": content.get("summary"),
            "ingredients": [i.get("name") for i in content.get("ingredients", [])]
        }
    
    # 리포트용 출력
    print("\n" + "="*50)
    print("실험 리포트 데이터")
    print("="*50)
    print(f"FDA Ingredients: {fda_ingrs[:10]}")
    for t, res in results.items():
        print(f"\n[Temp {t}]")
        print(f"추천 성분: {res['ingredients']}")
        print(f"요약: {res['summary'][:100]}...")
    
    return results

if __name__ == "__main__":
    asyncio.run(run_experiment())
