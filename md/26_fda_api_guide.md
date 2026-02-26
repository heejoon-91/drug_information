# FDA query를 어떻게 보내는지 확인

# FDA API 요청 형식 가이드

이 문서는 openFDA Drug Label API를 사용하는 방법과 요청 형식을 설명합니다.

## 1. 기본 정보
*   **Base URL:** `https://api.fda.gov/drug/label.json`
*   **Method:** `GET`
*   **응답 형식:** `application/json`

## 2. 주요 쿼리 파라미터

| 파라미터 | 설명 | 비고 |
| :--- | :--- | :--- |
| `search` | 검색 조건을 지정합니다. Lucene 문법을 사용합니다. | 필수급 |
| `limit` | 반환할 결과의 개수를 지정합니다. (기본 1) | 최대 100/1000 |
| `count` | 특정 필드 기준의 통계 데이터를 가져옵니다. | 분석용 |
| `api_key` | API 요청 제한을 늘리기 위한 인증 키입니다. | `.env` 참조 |

## 3. 검색 쿼리 작성 (search 파라미터)

`search=필드명:"검색어"` 형식으로 사용합니다.

### 자주 사용하는 필드
*   `openfda.brand_name`: 제품명 (예: TYLENOL)
*   `openfda.generic_name`: 성분명 (예: acetaminophen)
*   `openfda.product_type`: 의약품 타입 (예: "HUMAN OTC DRUG")
*   `indications_and_usage`: 효능 및 효과
*   `warnings`: 경고 사항

### 논리 연산자
연산자는 반드시 **대문자**로 작성해야 합니다.
*   **AND**: 두 조건 모두 만족
*   **OR**: 한 조건이라도 만족
*   **연산 예시**: `(openfda.brand_name:"TYLENOL" OR openfda.generic_name:"acetaminophen") AND openfda.product_type:"HUMAN OTC DRUG"`

## 4. 요청 예시

### 일반의약품(OTC) 제품명 검색
```http
GET https://api.fda.gov/drug/label.json?search=openfda.brand_name:"TYLENOL" AND openfda.product_type:"HUMAN OTC DRUG"&limit=1
```

### 특정 성분이 포함된 제품 통계
```http
GET https://api.fda.gov/drug/label.json?search=openfda.product_type:"HUMAN OTC DRUG"&count=openfda.brand_name.exact
```

## 5. 프로젝트 내 설정 안내 (`.env`)
현재 프로젝트에서는 다음 환경 변수를 통해 API 키를 관리합니다.

```env
OPENFDA_API_KEY=LtTHUuHcAPFQIb7bzXZItV3Po6d1AgozGZP0TduN
```

API 호출 시 `api_key` 파라미터에 이 값을 포함하여 요청하시기 바랍니다.
