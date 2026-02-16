# 출력결과 변경하고 싶을떄 참고

# 챗봇 설정 및 파라미터 가이드 (Chatbot Configuration Guide)

이 문서는 프로젝트 내에서 챗봇의 동작, 응답 스타일, 검색 범위를 조정할 수 있는 핵심 설정 파일들과 파라미터를 설명합니다.

## 1. 프롬프트 및 의도 분류 (Prompts & Intent Logic)

AI가 사용자의 질문을 어떻게 이해하고 답변의 방향성을 잡는지 결정하는 설정입니다.

### `api_fastapi/prompts/system_prompts.py`
*   **핵심 변수**: `INTENT_CLASS_PROMPT`
*   **역할**:
    *   사용자 질문을 **3가지 카테고리**(제품별, 증상별, 일반의학)로 분류하는 기준을 정의합니다.
    *   **검색 키워드 추출 규칙**: 
        *   "핵심 용어만 추출하라", "상위 개념(Pain)도 포함하라" 등의 지침이 여기에 포함됩니다.
        *   검색 품질(Recall vs Precision)을 조절하려면 이 프롬프트를 수정하세요.

### `api_fastapi/prompts/answer_prompts.py`
*   **핵심 변수**: `SYMPTOM_RESPONSE_PROMPT`
*   **역할**:
    *   검색된 데이터(FDA/DUR)를 바탕으로 **최종 답변을 생성하는 스타일**을 지정합니다.
    *   "성분명 위주로 답변하라", "제품명 언급 금지", "친절한 어조를 사용하라" 등의 제약 조건이 명시되어 있습니다.

---

## 2. AI 모델 및 생성 설정 (Model & Generation Config)

AI 모델의 종류와 답변의 창의성/일관성을 조절하는 설정입니다.

### `api_fastapi/services/ai_service.py`
*   **핵심 메서드**: `classify_intent`, `generate_symptom_answer`
*   **주요 파라미터**:
    *   `model="gpt-4o-mini"`: 사용할 OpenAI 모델을 변경할 수 있습니다. (비용/성능 트레이드오프 고려)
    *   `temperature=0`: 
        *   `0`: **일관성 중시**. 같은 질문에 항상 같은 답변/키워드를 생성합니다. (현재 설정)
        *   `0.7` 이상: **창의성 중시**. 답변이 다양해지지만 환각(Hallucination) 위험이 증가할 수 있습니다.
    *   `messages`: 프롬프트를 AI에게 전달하는 구조(System/User 역할 분담)를 정의합니다.

---

## 3. 데이터 검색 범위 및 로직 (Search Logic & Scope)

FDA 및 DUR 데이터베이스에서 정보를 가져오는 방식과 양을 조절하는 설정입니다.

### `api_fastapi/services/drug_service.py`
*   **핵심 메서드**: `search_fda`, `get_ingrs_from_fda_by_symptoms`
*   **주요 파라미터**:
    *   `limit`: 
        *   FDA API 요청 시 가져올 결과의 개수입니다.
        *   현재 증상 검색 시 `limit=3`으로 설정되어 있어, 상위 3개 약물군을 분석합니다.
    *   `search` 쿼리 파라미터:
        *   FDA 데이터의 어떤 필드(`generic_name`, `indications_and_usage` 등)를 검색할지 결정합니다.
