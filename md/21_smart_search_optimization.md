# 지능형 검색(smart-search) V2 최적화 방안

본 문서는 `main2.py`와 `graph_agent` 기반의 지능형 검색(smart-search)에서 발생하는 핵심 지연(Latency)의 원인을 정확히 분석하고 해결하기 위한 아키텍처 및 프롬프트 재설계 계획입니다.

## 1. 지연(Latency)의 진짜 원인 분석

코드를 분석한 결과 분류 모델 자체는 가벼운 `gpt-4o-mini`를 사용하여 큰 문제가 없었으나, 다음 구간에서 치명적인 병목이 발생하고 있습니다.

### 1.1 과도한 텍스트 생성 (LLM Generation Bottleneck)

- **현황**: `generate_symptom_answer_node`에서 FDA 및 DUR 검색으로 얻은 배열(List) 데이터를 모조리 합쳐 하나의 긴 텍스트(문자열)로 변환한 후, 이를 백그라운드 AI가 긴 단문의 글로 요약 및 나열하도록 지시하고 있습니다.
- **문제점**: 대형 언어 모델(LLM)은 구조상 출력해야 할 글자(Token)가 많을수록 정비례하여 수행 시간이 길어집니다. 3~4개의 약물 주의사항을 텍스트로 풀어쓰게 하면 최소 5초~15초 이상의 지연이 발생합니다.
- **해결 방안 (의존성 분리)**:
    - LLM(`ai_service.py`)의 역할은 환자의 질환(혹은 증상)에 따른 **"짧은 요점 및 인사말 (1~2문장)"**만 생성하도록 축약합니다. (생성 시간 1초 이내로 단축)
    - 상세한 DUR 주의사항 및 성분 데이터(`dur_data`, `fda_data`)는 JSON 객체 배열 형태 그대로 들고 가서, 프론트엔드 UI 화면(`symptom_result.html` 등)에서 템플릿 엔진(Jinja2)의 반복문(`{% for %}`)을 통해 0.1초 안에 아코디언/표 형태로 즉각 렌더링하도록 책임을 이관합니다.

### 1.2 불필요한 직렬 통신 구조

- **현황**: FDA로부터 제품/성분명을 조회한 후 조회 결과를 바탕으로 DUR(한국 식약처) 정보를 연이어 조회합니다. (`retrieve_fda_node` -> `retrieve_dur_node`)
- **문제점**: 정보 간 종속성(예: FDA에서 얻은 성분명으로 DUR을 조회해야 함)이 존재하므로 완벽한 병렬화는 불가능하지만, 일부 응답에 한해선 비동기(async) 호출 파이프라인 최적화가 가능합니다. 불필요하게 대기하는 로직을 최소화하여 노드 상태 갱신 속도를 높여야 합니다.

---

## 2. 구체적인 수정 범위 및 V2 계획

기존 파일들의 원본 유지를 위해 전부 백업 후 복사본(`_v2.py`)을 생성하여 작업합니다.

### 2.1 파일 분리 및 마이그레이션 대상

- `graph_agent/builder.py` -> `graph_agent/builder_v2.py`
- `graph_agent/nodes.py` -> `graph_agent/nodes_v2.py`
- `services/ai_service.py` -> `services/ai_service_v2.py`

### 2.2 개선 액션 플랜 (Action Plan)

1. **`ai_service_v2.py` 내의 프롬프트 축소**
    - `SYMPTOM_RESPONSE_PROMPT` 등을 수정하여 AI가 환자에게 전하는 1~2줄의 핵심 주의사항 또는 팩트만 응답하도록 변경하고 장황한 설명 목록 생성 금지 지시(Prompt Engineering) 추가.
2. **`nodes_v2.py` 응답 통합 구조 리팩토링**
    - AI 답변의 길이 축소로 인해 최종 합산되는 `final_answer` 배열은 짧아짐.
    - 대신 노드의 Raw Status Data(`fda_data`, `dur_data`)를 손실 없이 그대로 보존하여 `main2.py`를 거쳐 렌더링 화면(UI)으로 패스(Pathing)되게끔 보장.
3. **`main2.py` 연동부 V2 교체**
    - `build_graph_v2` 로드 및 라우팅 교체 작업.
