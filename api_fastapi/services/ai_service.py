import os
import json
from openai import AsyncOpenAI
# 프롬프트 파일에서 필요한 텍스트들을 가져옵니다.
from prompts.system_prompts import INTENT_CLASS_PROMPT
from prompts.answer_prompts import SYMPTOM_RESPONSE_PROMPT


class AIService:
    _client = None

    @classmethod
    def get_client(cls):
        if cls._client:
            return cls._client
        try:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                cls._client = AsyncOpenAI(api_key=api_key)
            return cls._client
        except Exception as e:
            print(f"Error initializing OpenAI client: {e}")
            return None

    @classmethod
    async def classify_intent(cls, query: str):
        """질문 분류 및 영어 키워드 동시 추출 (Router)"""
        client = cls.get_client()
        if not client:
            print("OpenAI Client is None. Returning default.")
            return {"category": "product_request", "category_reason": "No Client", "keyword": query}
            
        try:
            res = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": INTENT_CLASS_PROMPT.format(user_query=query)},
                    # {"role": "user", "content": query} # Already integrated in system prompt
                ],
                temperature=0,
                response_format={ "type": "json_object" }
            )
            return json.loads(res.choices[0].message.content)
        except Exception as e:
            print(f"Error in classify_intent: {e}")
            # 에러 발생 시 기본값으로 제품 검색 처리
            return {"category": "product_request", "keyword": query}

    @classmethod
    async def generate_symptom_answer(cls, symptom, data):
        """성분 및 DUR 데이터를 기반으로 최종 AI 답변 생성 (RAG)"""
        client = cls.get_client()
        if not client:
            return "OpenAI API 키가 설정되지 않아 답변을 생성할 수 없습니다."

        try:
            res = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYMPTOM_RESPONSE_PROMPT.format(symptom=symptom, data=str(data))},
                    # {"role": "user", "content": ... } # Already integrated
                ]
            )
            return res.choices[0].message.content
        except Exception as e:
            return f"답변 생성 중 오류가 발생했습니다: {str(e)}"

    @classmethod
    async def generate_general_answer(cls, query: str):
        """일반 의학 지식 질문 처리"""
        client = cls.get_client()
        if not client:
            return "OpenAI API 키가 설정되지 않았습니다."
            
        res = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "친절한 의료 지식 가이드."},
                      {"role": "user", "content": query}]
        )
        return res.choices[0].message.content