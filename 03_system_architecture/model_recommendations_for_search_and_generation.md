# 모델 추천안

## 목적

현재 프로젝트의 응답 속도를 개선하기 위해 다음 역할을 분리하는 구조를 전제로 한 모델 추천안이다.

- 분류 모델: 사용자 질문 유형 판별
- 증상 해석 레이어: 증상-동의어 사전 + 임베딩 검색 + 필요 시 reranker
- 개인화 안전성 판정 엔진: DUR/상호작용/사용자 프로필 기반 룰 엔진
- 출력 모델: 최종 사용자 설명 생성

중요:

- 개인화 안전성 판정은 모델보다 룰 엔진이 우선이다.
- 모델은 분류, 검색 보조, 설명 생성에만 제한적으로 사용하는 것을 권장한다.

## 권장 구조

1. 분류 모델이 질문 유형을 빠르게 판별한다.
2. 증상 질의라면 증상-동의어 사전과 임베딩 검색으로 표준 증상 키를 찾는다.
3. 후보 성분을 검색하고 필요 시 reranker로 정렬한다.
4. 안전성 판정 엔진이 사용자 상태를 반영해 복용 가능/주의/금기를 판정한다.
5. 출력 모델이 이미 결정된 결과를 자연스럽게 설명한다.

## 역할별 추천 모델

### 1. 분류 모델

#### API 기반 추천

- `gpt-5-nano`
- 용도: 질문 유형 분류, 짧은 요약, fallback 판단
- 장점: 빠르고 비용이 낮은 편이며 분류 용도에 적합
- 링크: https://developers.openai.com/api/docs/models/gpt-5-nano

#### 로컬 기반 추천

- `FacebookAI/xlm-roberta-base`
- 용도: 한국어 포함 다국어 문장 분류 파인튜닝 베이스
- 장점: 문장 분류용으로 안정적이고 널리 사용됨
- 링크: https://huggingface.co/FacebookAI/xlm-roberta-base

### 2. 증상 검색용 임베딩 모델

#### 기본 추천

- `Alibaba-NLP/gte-multilingual-base`
- 용도: 증상 문장과 표준 증상 키 간 유사도 검색
- 장점: 다국어 검색에 적합하고 비교적 가벼움
- 링크: https://huggingface.co/Alibaba-NLP/gte-multilingual-base

#### 품질 우선 추천

- `Qwen/Qwen3-Embedding-4B`
- 용도: 증상 해석, 유사 문장 검색, 성분 후보 검색
- 장점: 품질 우선 환경에 적합
- 링크: https://huggingface.co/Qwen/Qwen3-Embedding-4B

#### 경량 로컬 추천

- `Qwen/Qwen3-Embedding-0.6B`
- 용도: 속도와 메모리 사용량이 중요한 로컬 환경
- 장점: 상대적으로 가볍고 배치 처리에 유리
- 링크: https://huggingface.co/Qwen/Qwen3-Embedding-0.6B

#### API 임베딩 추천

- `text-embedding-3-large`
- 용도: 다국어 검색, 증상-동의어 매칭, 후보 검색
- 장점: OpenAI 임베딩 라인 중 품질 우선
- 링크: https://developers.openai.com/api/docs/models/text-embedding-3-large

### 3. 재정렬 모델

- `Qwen3-Reranker-0.6B`
- 용도: 1차 검색된 증상 후보나 성분 후보를 다시 정렬
- 장점: 검색 품질 개선에 효과적이며 비교적 가벼움
- 참고 링크: https://huggingface.co/Qwen/Qwen3-Embedding-4B

### 4. 출력 모델

#### API 기반 추천

- `gpt-5-mini`
- 용도: 최종 설명 문장 생성
- 장점: 저지연, 비용 효율, 설명 생성 품질 균형이 좋음
- 링크: https://developers.openai.com/api/docs/models/gpt-5-mini

#### 로컬 기반 추천

- `google/gemma-3-4b-it`
- 용도: 최종 설명 생성
- 장점: 다국어 지원, 로컬 운용 가능
- 링크: https://huggingface.co/google/gemma-3-4b-it

#### 로컬 대안

- `Qwen/Qwen3-4B`
- 용도: 최종 설명 생성
- 장점: 다국어 지원과 로컬 운용의 균형
- 링크: https://huggingface.co/Qwen/Qwen3-4B

## 추천 조합

### 1안: 가장 현실적인 조합

- 분류: `gpt-5-nano`
- 임베딩: `gte-multilingual-base`
- reranker: `Qwen3-Reranker-0.6B`
- 출력: `gpt-5-mini`

특징:

- 구현 난이도와 성능의 균형이 좋다.
- 현재 프로젝트의 API 중심 구조와도 잘 맞는다.

### 2안: 완전 로컬 조합

- 분류: `xlm-roberta-base` 파인튜닝
- 임베딩: `Qwen3-Embedding-0.6B` 또는 `gte-multilingual-base`
- reranker: `Qwen3-Reranker-0.6B`
- 출력: `gemma-3-4b-it`

특징:

- 외부 API 의존도를 줄일 수 있다.
- 운영 난이도와 로컬 자원 요구량은 올라간다.

### 3안: 품질 우선 조합

- 분류: `gpt-5-nano`
- 임베딩: `Qwen3-Embedding-4B`
- reranker: `Qwen3-Reranker-4B`
- 출력: `gpt-5-mini`

특징:

- 검색 품질은 더 좋아질 수 있다.
- 비용과 자원 사용량이 더 크다.

## 적용 원칙

- 증상 분류와 증상 정규화는 모델 또는 임베딩 검색으로 처리한다.
- 안전성 판정은 반드시 DUR/상호작용/사용자 프로필 기반 룰 엔진으로 처리한다.
- 출력 모델은 판정 자체를 수행하지 않고, 이미 결정된 결과를 설명하는 역할로 제한한다.
- 애매한 질의에만 fallback으로 LLM 또는 sLLM을 사용한다.

## 이 프로젝트에 대한 추천 결론

현재 프로젝트에는 다음 조합이 가장 적합하다.

- 분류: `gpt-5-nano`
- 증상 검색: `gte-multilingual-base`
- 후보 재정렬: `Qwen3-Reranker-0.6B`
- 안전성 판정: 기존 DUR 기반 룰 엔진 강화
- 출력: `gpt-5-mini`

이 조합은 현재 구조를 전면 교체하지 않고도 다음 목표를 동시에 맞추기 쉽다.

- 응답 속도 개선
- 한국어 자유문장 처리 유지
- 안전성 판단의 설명 가능성 유지
- 운영 복잡도 과도한 증가 방지
