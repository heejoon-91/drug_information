import os
import re
import json
import logging
from openai import AsyncOpenAI
# DDD 구조에서는 api_fastapi/prompts 가 PYTHONPATH 상위에 위치하므로 상대 경로 대신 절대 경로 import 사용 가능 (실행 컨텍스트에 따라 다름)
from prompts.system_prompts import INTENT_CLASS_PROMPT
from prompts.answer_prompts_v2 import SYMPTOM_RESPONSE_PROMPT_V2

logger = logging.getLogger(__name__)


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
            logger.error(f"Error initializing OpenAI client: {e}")
            return None

    @classmethod
    async def classify_intent_v2(cls, query: str):
        """질문 분류 및 영어 키워드, 캐시 키 동시 추출 (통합 라우터)"""
        client = cls.get_client()
        if not client:
            return {"category": "product_request", "keyword": query, "cache_key": query}

        try:
            res = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": INTENT_CLASS_PROMPT.format(user_query=query)},
                ],
                temperature=0,
                response_format={"type": "json_object"}
            )
            data = json.loads(res.choices[0].message.content)
            # 폴백 처리
            if "cache_key" not in data:
                data["cache_key"] = data.get("keyword") or query
            return data
        except Exception as e:
            logger.error(f"Error in classify_intent_v2: {e}")
            return {"category": "product_request", "keyword": query, "cache_key": query}

    @classmethod
    async def generate_symptom_answer(cls, symptom, data, user_profile=None):
        """성분 및 DUR 데이터를 기반으로 최종 AI 답변 생성 (RAG)"""
        client = cls.get_client()
        if not client:
            return "OpenAI API 키가 설정되지 않아 답변을 생성할 수 없습니다."

        meds = "None"
        allergies = "None"
        diseases = "None"

        if user_profile:
            meds = user_profile.get("current_medications") or "None"
            allergies = user_profile.get("allergies") or "None"
            diseases = user_profile.get("chronic_diseases") or "None"
            logger.debug(f"User Profile — Meds: {meds}, Allergies: {allergies}, Diseases: {diseases}")

        try:
            analysis_data = {
                "symptom": symptom,
                "current_medications": meds,
                "allergies": allergies,
                "chronic_diseases": diseases
            }
            
            # 성분 수 계산 (data가 리스트인 경우)
            ingredient_count = len(data) if isinstance(data, list) else 1
            
            # .format() 방식은 중괄호 {} 처리가 까다로워 안전한 .replace() 방식으로 변경합니다.
            system_prompt = SYMPTOM_RESPONSE_PROMPT_V2.replace("{analysis}", json.dumps(analysis_data, ensure_ascii=False))
            system_prompt = system_prompt.replace("{data}", str(data))
            system_prompt = system_prompt.replace("{ingredient_count}", str(ingredient_count))

            res = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    }
                ],
                temperature=0,
                response_format={"type": "json_object"}
            )
            return json.loads(res.choices[0].message.content)
        except Exception as e:
            return {"summary": f"답변 생성 중 오류가 발생했습니다: {str(e)}", "ingredients": []}

    @classmethod
    async def generate_general_answer(cls, query: str):
        """일반 의학 지식 질문 처리"""
        client = cls.get_client()
        if not client:
            return "OpenAI API 키가 설정되지 않았습니다."

        res = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "친절한 의료 지식 가이드."},
                {"role": "user", "content": query}
            ],
            temperature=0
        )
        return res.choices[0].message.content

    @classmethod
    async def recommend_ingredients_for_symptom(cls, symptom: str):
        """
        FDA 검색 실패 시, AI에게 해당 증상에 효과적인 성분(영문 성분명) 리스트를 추천받음 (Agentic Search)
        """
        client = cls.get_client()
        if not client:
            return []

        prompt = f"""
        Users asked for medicine recommendations for: "{symptom}"
        But no direct match was found in the FDA indication database.
        
        Please list 3-5 standard, over-the-counter active ingredients (generic names in English) 
        that are commonly used for this symptom.
        
        Return ONLY a JSON object like this: {{"ingredients": ["calcium carbonate", "simethicone", "loperamide"]}}
        """

        try:
            res = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a medical assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                response_format={"type": "json_object"}
            )
            data = json.loads(res.choices[0].message.content)
            # {"ingredients": [...]} 형식 또는 다른 key로 카버
            if isinstance(data, dict):
                for v in data.values():
                    if isinstance(v, list) and len(v) > 0:
                        return v  # 첫 번째 리스트 반환
                return []
            if isinstance(data, list):
                return data
            return []
        except Exception as e:
            logger.error(f"Error in recommend_ingredients_for_symptom: {e}")
            return []

    @classmethod
    async def normalize_symptom_query(cls, query: str) -> str:
        """
        사용자의 증상 입력을 분석하여 표준화된 영어 해시 키(Cache Key)로 변환합니다.
        예: "머리가 깨질듯 아파" -> "headache_severe_splitting"
        """
        client = cls.get_client()
        if not client:
            return query.strip().lower()

        prompt = f"""
        Analyze the following symptom described by a user: "{query}"
        
        Extract the core symptom, its severity, and its quality (if any).
        Normalize these into standard English medical terms used in FDA drug labels.
        
        Guidelines for "symptom":
        - If it's a stomach-related pain/ache, use terms like "heartburn", "acid indigestion", "upset stomach", or "stomach pain".
        - If it's a head pain, use "headache".
        - Avoid colloquial terms. Use terms found in OTC "indications" sections.
        
        Return a JSON object with these exactly 3 keys:
        {{"symptom": "...", "severity": "...", "quality": "..."}}
        """

        try:
            res = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a medical semantics analyzer."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                response_format={"type": "json_object"}
            )
            data = json.loads(res.choices[0].message.content)

            symptom = data.get("symptom", "").strip().lower().replace(" ", "_").replace("-", "_")
            severity = data.get("severity", "moderate").strip().lower()
            quality = data.get("quality", "none").strip().lower()

            if not symptom:
                return query.strip().lower()

            return f"{symptom}_{severity}_{quality}"
        except Exception as e:
            logger.error(f"Error in normalize_symptom_query: {e}")
            return re.sub(r'\s+', '_', re.sub(r'[^\w\s가-힣]', '', query.strip())).lower()

    @classmethod
    async def get_symptom_synonyms(cls, symptom: str):
        """
        FDA 검색 실패 시, 해당 증상과 유사한 영문 의학 용어(Synonyms)를 AI에게 조회하여
        FDA API 재검색에 사용할 키워드를 확보함
        """
        client = cls.get_client()
        if not client:
            return []

        prompt = f"""
        The user searched for the medical symptom: "{symptom}", but no direct match was found in the FDA indication database.
        Please provide 3-5 alternative standard English medical terms or related keywords commonly found in FDA OTC drug labels (Drug Facts).
        
        Examples:
        - "stomachache" -> ["heartburn", "acid indigestion", "upset stomach", "stomach pain"]
        - "headache" -> ["headache", "pain relief", "migraine"]
        - "sore throat" -> ["sore throat", "throat pain", "throat irritation"]
        
        Return ONLY a JSON list of strings. Example: ["heartburn", "acid indigestion"]
        """

        try:
            res = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a medical terminologist."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                response_format={"type": "json_object"}
            )
            data = json.loads(res.choices[0].message.content)

            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                synonyms = []
                for v in data.values():
                    if isinstance(v, list):
                        synonyms.extend(v)
                    elif isinstance(v, str):
                        synonyms.append(v)
                return synonyms
            return []
        except Exception as e:
            logger.error(f"Error in get_symptom_synonyms: {e}")
            return []

    @classmethod
    async def get_synonyms(cls, ingredient: str):
        """
        DUR 검색 실패 시, 해당 성분의 이명(Synonyms)이나 한국어 통용 명칭을 AI에게 조회
        """
        client = cls.get_client()
        if not client:
            return []

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
                messages=[
                    {"role": "system", "content": "You are a pharmaceutical terminologist."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                response_format={"type": "json_object"}
            )
            data = json.loads(res.choices[0].message.content)

            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                synonyms = []
                for v in data.values():
                    if isinstance(v, list):
                        synonyms.extend(v)
                    elif isinstance(v, str):
                        synonyms.append(v)
                return synonyms
            return []
        except Exception as e:
            logger.error(f"Error in get_synonyms: {e}")
            return []

    @classmethod
    async def bulk_summarize_fda_warnings(cls, warnings_dict: dict) -> dict:
        """여러 성분의 FDA 경고문을 한 번에 요약 (벌크 처리)"""
        client = cls.get_client()
        if not client or not warnings_dict:
            return {}

        # 요약이 필요한 항목만 필터링
        targets = {k: v for k, v in warnings_dict.items() if v and len(v) > 20}
        if not targets:
            return {k: "특이사항 없음" for k in warnings_dict.keys()}

        prompt = f"""
        Translate and summarize the following FDA drug warnings into Korean (1-2 sentences each).
        Return ONLY a JSON object where keys are the ingredient names and values are the summarized Korean text.
        
        [Warnings to Summarize]:
        {json.dumps(targets, ensure_ascii=False)}
        """

        try:
            res = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a medical translator specialized in drug safety."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                response_format={"type": "json_object"}
            )
            summaries = json.loads(res.choices[0].message.content)
            # 원본 리스트와 매핑하여 결과 구성
            result = {k: "특이사항 없음" for k in warnings_dict.keys()}
            result.update(summaries)
            return result
        except Exception as e:
            logger.error(f"Error in bulk_summarize_fda_warnings: {e}")
            return {k: "요약 오류" for k in warnings_dict.keys()}

    @classmethod
    async def translate_purposes(cls, purposes: list) -> list:
        """
        FDA 약물 purpose(효능/설명)를 한국어로 일괄 번역
        """
        client = cls.get_client()
        if not client or not purposes:
            return purposes

        prompt = f"""
        Translate the following list of medical drug purposes (indications/descriptions) into Korean concisely (1-2 sentences each).
        Return ONLY a JSON object with a key 'translated_purposes' containing the list of translated strings in the exact same order and length.
        
        Input list:
        {json.dumps(purposes, ensure_ascii=False)}
        """

        try:
            res = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a professional medical translator."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0
            )
            content = json.loads(res.choices[0].message.content)
            return content.get("translated_purposes", purposes)
        except Exception as e:
            logger.error(f"Error in translate_purposes: {e}")
            return purposes

    @classmethod
    async def filter_relevant_ingredients(cls, symptom: str, ingredients: list) -> list:
        """
        증상에 무관한 성분(예: 두통 질문에 기침약 성분)을 필터링하여 핵심 성분만 추출
        """
        client = cls.get_client()
        if not client or not ingredients:
            return ingredients[:5]

        prompt = f"""
        The user is complaining about the symptom: "{symptom}".
        Below is a list of candidate drug ingredients extracted from a database. 
        Some of these might be unrelated (e.g., antitussives like dextromethorphan for a headache)
        because they came from multi-symptom cold medicines.
        
        Candidate Ingredients: {", ".join(ingredients)}
        
        Please select the top 5-7 most relevant active ingredients for "{symptom}" ONLY.
        Include standard painkillers (like ACETAMINOPHEN, IBUPROFEN, NAPROXEN, ASPIRIN or ACETYLSALICYLIC ACID) if they are in the candidate list.
        Exclude ingredients that primarily treat unrelated conditions (like cough, congestion, or sputum) 
        unless they are directly relevant to the symptom.
        
        Return ONLY a JSON list of strings.
        Example: ["ACETAMINOPHEN", "IBUPROFEN", "ASPIRIN"]
        """

        try:
            res = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a pharmaceutical expert."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0
            )
            data = json.loads(res.choices[0].message.content)
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                for v in data.values():
                    if isinstance(v, list):
                        return v
            return ingredients[:5]
        except Exception as e:
            logger.error(f"Error in filter_relevant_ingredients: {e}")
            return ingredients[:5]
