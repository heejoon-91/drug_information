# API 호출 구조 최적화 비교

## 목적

현재 `skn22_4th_prj` 구조보다 더 빠르게 응답할 수 있는 구조가 있는지 검토하고, 어떤 변경이 실제 체감 속도에 가장 큰 영향을 주는지 정리한다.

---

## 현재 구조 요약

- 진입점은 Django ASGI + Uvicorn
- 메인 검색은 `chat/views.py`의 `smart_search()`에서 LangGraph를 직접 호출
- 증상 검색 시 내부적으로 다음 작업이 순차 또는 조건부로 실행됨
  - 질문 분류
  - 사용자 프로필 조회
  - Supabase 기반 성분 검색
  - FDA 후보 조회
  - LLM 기반 성분 선택
  - DUR 조회
  - HTML 렌더링
- 후속 상세 정보는 별도 API로 분리
  - `/api/symptom-products/`
  - `/api/pharmacies/`

관련 코드:

- [chat/views.py](c:/Users/OWNER/Desktop/drug_info/skn22_4th_prj/chat/views.py#L317)
- [graph_agent/nodes_v2.py](c:/Users/OWNER/Desktop/drug_info/skn22_4th_prj/graph_agent/nodes_v2.py#L505)
- [services/ai_service_v2.py](c:/Users/OWNER/Desktop/drug_info/skn22_4th_prj/services/ai_service_v2.py#L47)
- [services/supabase_service.py](c:/Users/OWNER/Desktop/drug_info/skn22_4th_prj/services/supabase_service.py#L22)

---

## 핵심 병목

프레임워크 자체보다 아래 항목들이 더 큰 병목이다.

### 1. 요청당 LLM 호출 수가 많음

증상 검색 경로는 상황에 따라 LLM을 여러 번 호출한다.

- 질문 분류: `classify_intent_v2()`
- 증상 표준화: `canonicalize_symptom_term()`
- 직접 성분 선택: `select_direct_symptom_ingredients()`
- 프로필 번역: `_translate_profile_fields_to_english()` 조건부 추가
- FDA 후보가 부족하면 동의어 생성 또는 대체 성분 추천까지 추가 호출 가능

즉 일반적인 증상 검색도 `3~4회` LLM 왕복이 발생할 수 있다.

### 2. Supabase 호출이 async native가 아님

현재 Supabase Python SDK 호출은 `asyncio.to_thread()`로 감싸서 사용 중이다.

- [supabase_service.py](c:/Users/OWNER/Desktop/drug_info/skn22_4th_prj/services/supabase_service.py#L22)

이 구조는 동작은 하지만, 고동시성에서 thread offload 비용과 순차 쿼리 비용이 남는다.

### 3. 캐시 구조는 있으나 메인 증상 흐름에 실질적으로 연결되지 않음

- `builder_v2.py`에는 `is_cached` 분기가 있음
- 하지만 `nodes_v2.py`의 분류 노드는 항상 `is_cached=False`를 반환
- `get_symptom_cache()` / `set_symptom_cache()`는 존재하지만 메인 증상 검색 흐름과 연결되어 있지 않음

관련 코드:

- [builder_v2.py](c:/Users/OWNER/Desktop/drug_info/skn22_4th_prj/graph_agent/builder_v2.py#L40)
- [nodes_v2.py](c:/Users/OWNER/Desktop/drug_info/skn22_4th_prj/graph_agent/nodes_v2.py#L520)
- [supabase_service.py](c:/Users/OWNER/Desktop/drug_info/skn22_4th_prj/services/supabase_service.py#L397)

### 4. 후속 상품 추천 API도 꽤 무거움

`/api/symptom-products/`는 성분별 openFDA 조회, FDA warning 조회, 목적 문장 번역, Amazon 랭킹 보강까지 수행할 수 있다.

관련 코드:

- [chat/views.py](c:/Users/OWNER/Desktop/drug_info/skn22_4th_prj/chat/views.py#L447)
- [map_service.py](c:/Users/OWNER/Desktop/drug_info/skn22_4th_prj/services/map_service.py#L719)
- [map_service.py](c:/Users/OWNER/Desktop/drug_info/skn22_4th_prj/services/map_service.py#L613)
- [amazon_rank_service.py](c:/Users/OWNER/Desktop/drug_info/skn22_4th_prj/services/amazon_rank_service.py#L294)

---

## 비교 대상 구조

### A. 현재 구조 유지

- Django가 HTML까지 렌더
- 일부 상세 정보는 후속 API로 로드
- 장점: 변경 비용이 가장 적음
- 단점: 메인 요청 안에 LLM/DB/API 작업이 많이 묶여 있음

### B. Django -> 내부 HTTP -> FastAPI 분리

- Django는 UI만 담당
- 실제 검색/추천은 별도 FastAPI 서버로 HTTP 호출
- 장점: 서비스 분리, 독립 배포, 역할 분리
- 단점: 같은 작업을 하더라도 내부 네트워크 hop이 추가됨
- 단일 요청 속도만 보면 대체로 큰 이득이 없음

### C. Django BFF + JSON/SSE API + 캐시 + DB RPC

- Django는 UI/BFF 역할만 담당
- 검색 본문은 API로 먼저 반환
- 상품/약국/보강 정보는 후속 API 또는 SSE로 점진 로딩
- 캐시를 메인 경로에 실제 연결
- Supabase 쿼리는 DB 함수 또는 batch RPC로 통합
- 장점: 현재 코드와 가장 잘 맞고, 체감 속도 개선 폭이 큼

### D. FastAPI 전면 전환

- UI를 API 기반으로 재구성
- Django 템플릿 렌더 의존도를 낮춤
- 장점: API 중심 구조에는 잘 맞음
- 단점: 현재 병목의 본질은 Django 자체가 아니라서, 투자 대비 속도 이득이 제한적일 수 있음

---

## 실제로 얼마나 빨라질 가능성이 있는가

### 1. HTML 렌더를 JSON API로 바꾸는 효과

로컬 서버에서 간단히 측정한 값:

- `/` 평균 응답: 약 `9.08ms`
- `/healthz/` 평균 응답: 약 `7.29ms`

차이는 약 `1.79ms` 정도다.

의미:

- 단순 페이지에서는 JSON 응답이 약간 더 빠르다
- 하지만 `smart_search`처럼 LLM과 외부 API가 들어가는 요청에서는 이 차이가 전체 시간에서 차지하는 비중이 매우 작다
- 따라서 "Django 템플릿을 버리고 API만 쓰면 엄청 빨라진다"는 기대는 현재 프로젝트에는 맞지 않는다

### 2. 내부 HTTP로 FastAPI를 하나 더 두는 효과

예상 결과:

- 순수 연산은 동일
- Django -> FastAPI 내부 호출 비용이 추가
- 체감상 `0ms ~ 수십 ms` 수준의 오버헤드가 생길 가능성이 큼
- 단일 요청 latency 관점에서는 대체로 `동일하거나 소폭 악화`

의미:

- 운영 분리나 팀 분업 목적이라면 가치가 있음
- 속도만 목표라면 우선순위가 낮음

### 3. 캐시 연결 효과

반복 질문 기준 예상:

- 현재: 보통 `2~6초` 이상 걸릴 수 있음
- 캐시 적중 시: 대략 `50~200ms` 수준까지 줄 가능성

예상 개선 폭:

- 약 `10x ~ 30x`

주의:

- 이 수치는 현재 코드 구조와 일반적인 LLM/API 지연을 바탕으로 한 추정치다
- 실제 값은 질문 종류, OpenAI 응답 시간, Supabase 응답 시간에 따라 달라진다

### 4. LLM 호출 수 축소 효과

현재 증상 검색은 보통 `3~4회` LLM 호출이 발생할 수 있다.
이를 `1~2회`로 줄이면:

- 대략 `0.6 ~ 2.4초` 절감 가능성
- 엔드투엔드 기준 약 `25% ~ 50%` 단축 가능성

이 역시 추정치지만, 프레임워크 교체보다 훨씬 영향이 크다.

### 5. Supabase batch/RPC화 효과

현재는 thread offload + 순차 fallback 쿼리가 섞여 있다.
이를 DB 함수나 batch RPC로 통합하면:

- 요청당 `50 ~ 300ms` 정도 절감 가능성
- 동시 요청이 많을 때 안정성도 좋아질 가능성이 큼

---

## 추천 구조

현재 프로젝트에 가장 현실적인 추천안은 다음 구조다.

### 추천안: Django BFF + API-first 보강 구조

1. 첫 응답은 가볍게 반환

- 질문 분류
- 핵심 성분 후보
- KR DUR 결과
- 짧은 요약

2. 무거운 작업은 후속 로딩

- 미국 OTC 상품 추천
- FDA warning 원문/요약
- 약국 지도
- Amazon 랭킹
- 추가 번역

3. 증상 캐시를 실제 메인 경로에 연결

- 캐시 키: `symptom + user_profile_hash`
- 반복 질의는 그래프 전체를 다시 돌리지 않도록 처리

4. Supabase 조회는 RPC 또는 DB function으로 통합

- symptom -> ranked ingredients
- ingredient list -> DUR batch lookup

5. 필요하면 그 다음 단계로 FastAPI worker 분리

- 목적이 독립 배포, 독립 확장, API 제품화라면 유효
- 목적이 단순 속도 개선이면 1순위는 아님

---

## 우선순위별 개선 효과

### 1순위

메인 증상 검색 캐시 연결

- 기대 효과: 가장 큼
- 반복 질의에서 `10x` 이상 가능

### 2순위

LLM 홉 수 줄이기

- 질문 분류 + 성분 선택을 더 단순화
- 불필요한 표준화/동의어 생성 경로 축소

### 3순위

Supabase batch/RPC화

- thread offload 감소
- batch lookup으로 round trip 수 감소

### 4순위

응답 스트리밍 또는 후속 API 분리 강화

- 총 처리 시간이 줄지 않아도 체감 속도는 좋아짐
- 사용자는 먼저 핵심 답을 보고 나머지를 뒤에서 받게 됨

### 5순위

FastAPI 서비스 분리

- 확장성과 유지보수성 측면에서는 의미 있음
- 속도만 보면 앞선 작업보다 ROI가 낮음

---

## 최종 결론

이 프로젝트에서 더 빨라지는 구조는 `Django -> FastAPI 내부 호출` 구조가 아니다.

가장 효과적인 방향은 아래 조합이다.

- 메인 검색 경량화
- 캐시 실연결
- LLM 호출 수 축소
- Supabase batch/RPC화
- 무거운 보강 정보는 후속 API 또는 스트리밍 처리

정리하면:

- 프레임워크 교체 효과: 작음
- API-first + 캐시 + RPC 효과: 큼
- 가장 추천하는 구조: `Django BFF + 가벼운 첫 응답 + 후속 API/SSE + 캐시 + DB 함수`

---

## 참고 자료

- Django async docs: https://docs.djangoproject.com/en/5.1/topics/async/
- FastAPI benchmarks: https://fastapi.tiangolo.com/benchmarks/
- Uvicorn settings: https://www.uvicorn.org/settings/
- Supabase Edge Functions: https://supabase.com/docs/guides/functions
- Supabase Database Functions: https://supabase.com/docs/guides/database/functions
- OpenAI Streaming guide: https://platform.openai.com/docs/guides/streaming
