# DUR API 응답 스키마 (Korean Version)

이 문서는 DUR(의약품안전사용서비스) API (`dur_unified_collector.py`)가 실제로 수집하는 데이터 필드를 정리한 문서입니다.
`dur_table.md`의 내용을 바탕으로 작성되었습니다.

## 공통 응답 구조

- **기본 URL**: `https://apis.data.go.kr/1471000/DURIrdntInfoService03`
- **형식**: JSON (`body` -> `items` -> `item`)

## 공통 필드 (모든 엔드포인트)

모든 엔드포인트 응답에 공통으로 포함되는 필드입니다.

| 필드명 (Case 1)     | 필드명 (Case 2) | 설명                | DB 매핑 (`DurMaster`) |
| :------------------ | :-------------- | :------------------ | :-------------------- |
| `INGR_CODE`         | -               | 성분코드            | `ingr_code`           |
| `INGR_NAME`         | `INGR_KOR_NAME` | 성분명 (한글)       | `ingr_kor_name`       |
| `INGR_ENG_NAME`     | -               | 성분명 (영문)       | `ingr_eng_name`       |
| `PROHBT_CONTENT`    | -               | 금기 내용           | `prohbt_content`      |
| `REMARK`            | -               | 비고                | `remark`              |
| `CLASS_NAME`        | -               | 약효 분류명         | `class_name`          |
| `NOTIFICATION_DATE` | -               | 고시일자 (YYYYMMDD) | `notification_date`   |

> **주의**: `INGR_KOR_NAME`은 주로 **병용금기** API에서 사용되며, 나머지 대부분의 API는 `INGR_NAME`을 사용합니다. 수집기에서 두 가지 경우를 모두 처리해야 합니다.

## 엔드포인트별 핵심 데이터

각 API 엔드포인트별로 `critical_value` (핵심 주의 값)에 매핑되는 필드입니다.

### 1. 병용금기 (`getUsjntTabooInfoList02`)

- **유형**: `COMBINED`
- **핵심 필드**: `MIXTURE_INGR_KOR_NAME` (병용 금기 성분명)
- **특이사항**: 본래 성분명 필드로 `INGR_KOR_NAME` 사용.

### 2. 임부금기 (`getPwnmTabooInfoList02`)

- **유형**: `PREGNANCY`
- **핵심 필드**: `GRADE` (금기 등급)
- **특이사항**: 성분명 필드로 `INGR_NAME` 사용.

### 3. 용량주의 (`getCpctyAtentInfoList02`)

- **유형**: `MAX_CAPACITY`
- **핵심 필드**: `MAX_QTY` (1일 최대 투여량)
- **특이사항**: 성분명 필드로 `INGR_NAME` 사용.

### 4. 투여기간주의 (`getMdctnPdAtentInfoList02`)

- **유형**: `DURATION`
- **핵심 필드**: `MAX_DOSAGE_TERM` (최대 투여 기간)
- **특이사항**: 성분명 필드로 `INGR_NAME` 사용.

### 5. 노인주의 (`getOdsnAtentInfoList02`)

- **유형**: `ELDERLY`
- **핵심 필드**: _없음_ (목록에 존재하면 주의)
- **기본값**: "주의"
- **특이사항**: `PROHBT_CONTENT`에 주의 내용이 포함됨.

### 6. 특정연령대금기 (`getSpcifyAgrdeTabooInfoList02`)

- **유형**: `AGE_LIMIT`
- **핵심 필드**: `AGE_BASE` (기준 연령)
- **특이사항**: 성분명 필드로 `INGR_NAME` 사용.

### 7. 효능군중복 (`getEfcyDplctInfoList02`)

- **유형**: `EFFICACY_DUPLICATE`
- **핵심 필드**: `SERS_NAME` (효능군 이름)
- **특이사항**: 성분명 필드로 `INGR_NAME` 사용.
