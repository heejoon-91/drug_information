import os
import json
from openai import OpenAI
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
                cls._client = OpenAI(api_key=api_key)
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
            return {"category": "PRODUCT_SPECIFIC", "target_drug": query, "fda_search_keywords": ["pain"]}
            
        try:
            res = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "의약품 분류 및 검색 키워드 생성 전문가."},
                    {"role": "user", "content": INTENT_CLASS_PROMPT.format(user_query=query)}
                ],
                temperature=0,
                response_format={ "type": "json_object" }
            )
            return json.loads(res.choices[0].message.content)
        except Exception as e:
            print(f"Error in classify_intent: {e}")
            # 에러 발생 시 기본값으로 제품 검색 처리
            return {"category": "PRODUCT_SPECIFIC", "target_drug": query, "fda_search_keywords": ["pain"]}

    @classmethod
    async def generate_symptom_answer(cls, symptom, data):
        """성분 및 DUR 데이터를 기반으로 최종 AI 답변 생성 (RAG)"""
        client = cls.get_client()
        if not client:
            return "OpenAI API 키가 설정되지 않아 답변을 생성할 수 없습니다."

        try:
            res = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "너는 성분 기반 상담사야. 제품명 언급 금지."},
                    {"role": "user", "content": SYMPTOM_RESPONSE_PROMPT.format(symptom=symptom, data=str(data))}
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
            
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "친절한 의료 지식 가이드."},
                      {"role": "user", "content": query}]
        )
        return res.choices[0].message.content