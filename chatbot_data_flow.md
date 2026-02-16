# 사용자 input에서 출력까지의 과정

# 챗봇 데이터 처리 흐름 (Chatbot Data Flow)

사용자가 질문을 입력했을 때부터 최종 답변이 화면에 출력되기까지의 과정을 단계별로 상세히 설명합니다.

---

## 1. 사용자 입력 수신 (User Input)
사용자가 웹 인터페이스의 검색창에 질문을 입력하고 엔터를 치면, 브라우저는 다음 주소로 요청을 보냅니다.
- **Endpoint**: `GET /smart-search?q={사용자 질문}`
- **Handler**: `api_fastapi/main.py`의 `smart_search` 함수

## 2. 의도 분류 (Intent Classification)
서버는 가장 먼저 AI를 통해 사용자의 의도를 파악합니다.
- **담당 모듈**: `services/ai_service.py` -> `classify_intent()`
- **동작**:
    1. `system_prompts.py`의 `INTENT_CLASS_PROMPT`와 사용자 질문을 조합하여 OpenAI에 전송합니다.
    2. AI는 질문을 분석하여 다음 3가지 중 하나로 분류하고 JSON으로 반환합니다.
        - `PRODUCT_SPECIFIC` (제품명 검색)
        - `SYMPTOM_RELIEF` (증상 완화 약물 찾기)
        - `GENERAL_MEDICAL` (일반 의학 지식)
    3. 동시에 FDA 검색을 위한 영어 키워드(예: 'Headache', 'Pain')를 추출합니다.

---

## 3. 분기 처리 (Branching Logic)
분류된 결과(`category`)에 따라 서로 다른 로직이 실행됩니다.

### Case A: 증상 해결 (SYMPTOM_RELIEF) - 가장 복잡한 흐름
사용자가 "머리 아파"라고 했을 때의 흐름입니다.

1.  **FDA 성분 검색 (`drug_service.py`)**:
    - 추출된 영어 키워드(예: `Headache`)로 FDA API를 호출합니다.
    - 해당 적응증(`indications_and_usage`)을 가진 약물들의 **성분명(Generic Name, Substance Name)**을 수집합니다.
    
2.  **DUR 정보 병합 (`get_enriched_dur_info`)**:
    - 수집된 각 성분에 대해 두 가지 조회를 병렬로 수행합니다.
        - **한국 DUR DB**: 해당 성분의 병용금기/임부금기 정보가 있는지 DB에서 조회합니다.
        - **FDA Warning**: 해당 성분에 대한 FDA의 경고 문구(Boxed Warning)를 조회합니다.
    - 이 정보들을 하나로 합쳐 `purified_data`를 만듭니다.

3.  **최종 답변 생성 (`ai_service.py`)**:
    - 수집된 DUR/FDA 정보를 요약 텍스트로 변환합니다.
    - `answer_prompts.py`의 `SYMPTOM_RESPONSE_PROMPT`에 **사용자 증상**과 **요약된 약물 정보**를 넣어 OpenAI에 보냅니다.
    - AI는 이 정보를 바탕으로 사용자에게 친절한 답변을 작성합니다.

4.  **화면 출력**:
    - `symptom_result.html` 템플릿에 `AI 답변`과 `상세 DUR 데이터(JSON)`를 전달합니다.
    - 화면이 로딩되면 자동으로 팝업이 뜨며 상세 DUR 정보를 보여줍니다.


### Case B: 제품 검색 (PRODUCT_SPECIFIC)
사용자가 "타이레놀 효능"이라고 했을 때의 흐름입니다.

1.  **FDA 제품 검색**:
    - 제품명(브랜드명)으로 FDA API를 직접 조회합니다.
    - 효능, 용법, 주의사항을 가져옵니다.

2.  **성분 기반 DUR 조회**:
    - 검색된 제품의 성분명을 추출하여 한국 DUR DB에 해당 성분이 있는지 확인합니다.

3.  **화면 출력**:
    - `search_result.html` 템플릿에 제품 상세 정보를 보여줍니다.


### Case C: 일반 의학 상식 (GENERAL_MEDICAL)
사용자가 "내성이란 뭐야?"라고 했을 때의 흐름입니다.

1.  **AI 답변 생성**:
    - 별도의 DB/API 조회 없이, AI가 자신의 지식을 바탕으로 답변을 작성합니다. (`generate_general_answer`)
2.  **화면 출력**:
    - 결과 화면에 텍스트 답변만 출력됩니다.

---

## 4. 최종 응답 (Response)
처리된 결과는 **FastAPI의 Jinja2 템플릿 엔진**을 통해 HTML로 렌더링되어 사용자의 브라우저로 전송됩니다.
- 사용자는 AI가 요약해준 텍스트 답변을 먼저 보고, 필요 시 "상세 정보 보기" 버튼을 통해 원본 데이터를 확인할 수 있습니다.
