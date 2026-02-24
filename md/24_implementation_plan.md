# 응답 속도 혁신 및 캐시 지능형 갱신 계획 (v5)

"모든 제품을 보여주되 속도는 획기적으로 빠르게" 하고, "프롬프트 수정이 즉시 반영"되도록 하는 고도화 전략입니다.

## 핵심 개선 전략

### 1. 벌크 번역 (Bulk Translation) '편법' 적용
- **문제**: 성분이 10개면 10번의 AI 번역 호출이 발생하여 지연 심화.
- **해결**: 
  1. 모든 성분에 대한 제품 정보를 번역 없이 고속으로 먼저 수집.
  2. 수집된 모든 제품의 [purpose](file:///c:/codes/SKN22-4th-drug/api_fastapi/application/services/ai_service.py#317-349)(효능) 문구들을 하나의 리스트로 통합.
  3. **단 한 번의 AI 호출**로 모든 문구를 번역.
  4. 번역된 결과를 다시 각 제품에 매핑.
- **효과**: AI 호출 횟수가 1/N로 줄어들어 응답 시간이 비약적으로 단축됨.

### 2. 스마트 캐시 버전 관리 (Auto Refresh)
- **문제**: 캐시에 이전 답변이 있으면 프롬프트를 고쳐도 수정되지 않음.
- **해결**: [classify_node](file:///c:/codes/SKN22-4th-drug/api_fastapi/interfaces/agent/nodes_v2.py#31-63)에서 캐시 데이터를 가져올 때, `final_answer`에 새로운 세션 구분자인 `### 1. 상황별`이 포함되어 있는지 검사.
- **효과**: 프롬프트 수정 후 첫 질문 시 자동으로 구버전 캐시를 무시하고 새 버전으로 갱신함.

## 변경 대상 파일

#### [MODIFY] [map_service.py](file:///c:/codes/SKN22-4th-drug/api_fastapi/application/services/map_service.py)
- [get_us_otc_products_by_ingredient](file:///c:/codes/SKN22-4th-drug/api_fastapi/services/map_service.py#30-89): 번역 로직을 선택적으로 건너뛸 수 있는 파라미터 추가 또는 분리.

#### [MODIFY] [nodes_v2.py](file:///c:/codes/SKN22-4th-drug/api_fastapi/interfaces/agent/nodes_v2.py)
- [classify_node](file:///c:/codes/SKN22-4th-drug/api_fastapi/interfaces/agent/nodes_v2.py#31-63): `final_answer` 형식 체크 및 강제 갱신 로직 추가.
- [generate_symptom_answer_node](file:///c:/codes/SKN22-4th-drug/api_fastapi/interfaces/agent/nodes_v2.py#92-169): 제품 수집 -> 벌크 번역 -> 매핑 순으로 워크플로우 재설계.

## 검증 계획
- 성분이 10개 이상인 질문 시 응답 시간이 획기적으로 줄어드는지 확인.
- 수정된 상황별/증상별 답변 형식이 모든 질문에 대해 즉시 적용되는지 확인.
