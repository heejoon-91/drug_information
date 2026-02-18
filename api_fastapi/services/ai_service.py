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
    async def generate_symptom_answer(cls, symptom, data, user_profile=None):
        """성분 및 DUR 데이터를 기반으로 최종 AI 답변 생성 (RAG)"""
        client = cls.get_client()
        if not client:
            return "OpenAI API 키가 설정되지 않아 답변을 생성할 수 없습니다."

        # 사용자 프로필 포맷팅
        meds = "None"
        allergies = "None"
        diseases = "None"
        
        if user_profile:
            meds = user_profile.get("current_medications") or "None"
            allergies = user_profile.get("allergies") or "None"
            diseases = user_profile.get("chronic_diseases") or "None"
            print(f"[DEBUG] User Profile for AI:\n- Meds: {meds}\n- Allergies: {allergies}\n- Diseases: {diseases}")

        try:
            res = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system", 
                        "content": SYMPTOM_RESPONSE_PROMPT.format(
                            symptom=symptom, 
                            data=str(data),
                            medications=meds,
                            allergies=allergies,
                            chronic_diseases=diseases
                        )
                    },
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

    @classmethod
    async def recommend_ingredients_for_symptom(cls, symptom: str):
        """
        FDA 검색 실패 시, AI에게 해당 증상에 효과적인 성분(영문 성분명) 리스트를 추천받음 (Agentic Search)
        """
        client = cls.get_client()
        if not client: return []

        prompt = f"""
        Users asked for medicine recommendations for: "{symptom}"
        But no direct match was found in the FDA indication database.
        
        Please listed 3-5 standard, over-the-counter active ingredients (generic names in English) 
        that are commonly used for this symptom.
        
        Return ONLY a JSON list of strings. Example: ["acetaminophen", "ibuprofen"]
        """
        
        try:
            res = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": "You are a medical assistant."},
                          {"role": "user", "content": prompt}],
                response_format={ "type": "json_object" }
            )
            content = res.choices[0].message.content
            data = json.loads(content)
            # Handle various JSON structures (list or dict with key)
            if isinstance(data, list): return data
            if isinstance(data, dict):
                return list(data.values())[0] if data else []
            return []
        except Exception as e:
            print(f"Error in recommend_ingredients_for_symptom: {e}")
            return []

    @classmethod
    async def get_synonyms(cls, ingredient: str):
        """
        DUR 검색 실패 시, 해당 성분의 이명(Synonyms)이나 한국어 통용 명칭을 AI에게 조회
        """
        client = cls.get_client()
        if not client: return []

        prompt = f"""
        Provide 3-5 common synonyms or alternate names for the drug ingredient: "{ingredient}".
        Include:
        1. Official synonyms (e.g., Acetaminophen <-> Paracetamol)
        2. Common brand names treated as generics in some contexts (if applicable)
        3. Korean standard name if known (written in English or Korean)
        
        Return ONLY a JSON list of strings. Example: ["Paracetamol", "APAP", "N-acetyl-p-aminophenol"]
        """
        
        try:
            res = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": "You are a pharmaceutical terminologist."},
                          {"role": "user", "content": prompt}],
                response_format={ "type": "json_object" }
            )
            content = res.choices[0].message.content
            data = json.loads(content)
            
            if isinstance(data, list): return data
            if isinstance(data, dict):
                # Flatten all values if dict
                synonyms = []
                for v in data.values():
                    if isinstance(v, list): synonyms.extend(v)
                    elif isinstance(v, str): synonyms.append(v)
                return synonyms
            return []
        except Exception as e:
            print(f"Error in get_synonyms: {e}")
            return []

    @classmethod
    async def summarize_fda_warning(cls, text: str):
        """
        FDA 경고문(영문)을 한국어로 핵심만 요약
        """
        client = cls.get_client()
        if not client or not text: return None

        prompt = f"""
        Summarize the following FDA warning text into **Korean** in 1-2 concis sentences.
        Focus on the most critical safety information (contraindications, serious side effects).
        If the text is generic (e.g., "See full prescribing information"), return "특이사항 없음".
        
        [FDA Warning Text]:
        {text[:1000]}
        """
        
        try:
            res = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": "You are a medical translator."},
                          {"role": "user", "content": prompt}]
            )
            return res.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error in summarize_fda_warning: {e}")
            return None