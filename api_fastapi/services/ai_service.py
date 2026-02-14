import os, json
from openai import OpenAI
from prompts.intent_classifier import INTENT_CLASS_PROMPT, SYMPTOM_RESPONSE_PROMPT

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class AIService:
    @staticmethod
    async def translate_symptom_to_eng(symptom: str):
        """한국어 증상을 FDA 검색용 영어 의학 용어 리스트로 변환"""
        prompt = f"""
        사용자의 증상: "{symptom}"
        이 증상을 완화하는 데 쓰이는 약물을 미국 FDA API에서 검색하려고 해. 
        검색에 적합한 영어 의학 용어(단어 위주)를 3개 이내로 추출해줘.
        응답은 반드시 JSON 리스트 형식으로만 해. 예: ["headache", "fever"]
        """
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={ "type": "json_object" } # 실제 구현 시 {"keywords": [...]} 구조 추천
        )
        data = json.loads(res.choices[0].message.content)
        return data.get("keywords", []) # ["headache", "pain"]

    @staticmethod
    async def generate_symptom_answer(symptom, data):
        """증상 기반 성분 안내 답변 생성"""
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "너는 성분 기반 상담사야. 제품명 언급 금지."},
                      {"role": "user", "content": SYMPTOM_RESPONSE_PROMPT.format(symptom=symptom, data=str(data))}]
        )
        return res.choices[0].message.content