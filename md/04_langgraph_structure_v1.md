# LangGraph 구조 및 워크플로우

이 문서는 의약품 정보 제공 챗봇의 LangGraph 기반 아키텍처를 설명합니다.

## 개요
사용자의 자연어 질문을 분석하여 의도를 3가지 유형(증상, 제품, 일반)으로 분류하고, 적절한 데이터 소스(FDA, DUR)를 조회하여 답변을 생성하는 에이전트 워크플로우입니다.

## 상태 정의 (State Definition)
`AgentState`는 그래프의 각 노드 간에 공유되는 데이터 구조입니다.

```python
class AgentState(TypedDict):
    query: str          # 사용자 입력 질문
    category: str       # 질문 유형 (symptom_recommendation, product_request, general_medical)
    keyword: str        # 검색 키워드 (영어 번역됨)
    symptom: Optional[str] # 증상 원문
    fda_data: Optional[Any] # FDA 검색 결과 (성분 목록 또는 제품 상세 정보)
    dur_data: Optional[List[dict]] # 국내 DUR(병용금기 등) 점검 결과
    final_answer: Optional[str] # 최종 생성된 답변
```

## 질문 유형 (Categories)
시스템은 사용자 질문을 다음 3가지 중 하나로 분류합니다:

1. **`symptom_recommendation` (1번 증상에 대한 성분 추천)**
   - 예: "머리가 아픈데 약 추천해줘", "소화불량 약 있어?"
   - 흐름: 증상 분석 -> FDA 성분 검색 -> DUR 점검 -> 종합 추천 답변

2. **`product_request` (2번 제품 설명 요구)**
   - 예: "타이레놀 효능이 뭐야?", "이지엔6 성분 알려줘"
   - 흐름: 제품명 추출 -> FDA 제품 검색 -> 성분 추출 -> DUR 점검 -> 제품 상세 정보 반환

3. **`general_medical` (3번 일반 의학적 지식 질문)**
   - 예: "약은 식후 언제 먹어야 하나요?", "항생제 내성이란?"
   - 흐름: 질문 분석 -> 일반 의학 상식 답변 생성 (외부 검색 없이 LLM 지식 활용)

## 그래프 구조 (Workflow Diagram)

```mermaid
graph TD
    Start([Start]) --> Classify[분류 (Classify Agent)]
    
    Classify -- symptom_recommendation --> FdaSymptom[증상 기반 성분 검색 (FDA)]
    Classify -- product_request --> FdaProduct[제품명 기반 검색 (FDA)]
    Classify -- general_medical --> GenAnswer[일반 의학 답변 생성]
    Classify -- error/invalid --> ErrAnswer[에러 처리]

    FdaSymptom --> DurCheck[DUR 점검]
    FdaProduct --> DurCheck

    DurCheck -->|category=symptom| SympAnswer[증상 맞춤 답변 생성]
    DurCheck -->|category=product| ProdAnswer[제품 정보 구조화]

    SympAnswer --> End([End])
    ProdAnswer --> End
    GenAnswer --> End
    ErrAnswer --> End
```

## 주요 노드 설명 (Nodes)

1. **`classify_node`**: 
   - 사용자의 질문을 분석하여 `category`와 `keyword`를 추출합니다.
   - LLM을 사용하여 한국어 증상을 영어 의학 용어로 변환하거나, 정확한 제품명을 식별합니다.

2. **`retrieve_fda_node`**:
   - `symptom_recommendation`: 증상 키워드(예: headache)와 연관된 약물 성분을 FDA 데이터베이스에서 찾습니다.
   - `product_request`: 제품명(예: Tylenol)으로 FDA의 의약품 라벨 정보를 검색합니다.

3. **`retrieve_dur_node`**:
   - 확보된 성분 리스트(영어)를 바탕으로 한국의약품안전관리원(DUR) 데이터를 조회하여 병용 금기, 임부 금기 등의 주의사항을 확인합니다.

4. **`generate_answer_node`**:
   - 수집된 FDA 효능 정보와 DUR 주의사항을 종합하여 사용자에게 최종 답변을 생성합니다.
