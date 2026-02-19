# 🗄️ 데이터베이스 스키마 및 테이블 명세 (Database Schema & Table Description)

이 문서는 프로젝트에서 사용하는 주요 데이터베이스 테이블과 각 컬럼에 대한 상세 설명을 제공합니다.

---

## 1. 📜 의약품 허가 정보 (`drug_permit_info`)
식약처의 의약품 제품 허가 정보를 저장하는 기본 테이블입니다.

| 컬럼명 (Column) | 타입 (Type) | 설명 (Description) | 비고 |
| :--- | :--- | :--- | :--- |
| **`item_seq`** | `VARCHAR(50)` | **품목기준코드 (Primary Key)** | 의약품 고유 식별 코드 |
| `item_name` | `TEXT` | 제품명 | 한글 제품명 |
| `item_eng_name` | `TEXT` | 제품명(영문) | 영문 제품명 (NULL 허용) |
| `entp_name` | `VARCHAR(255)` | 업체명 | 제조/수입 업체명 |
| `main_ingr_name` | `TEXT` | 주성분 | 주요 성분 명칭 |
| `etc_otcc_name` | `VARCHAR(50)` | 전문/일반 구분 | 전문의약품 또는 일반의약품 |
| `source_updated_at` | `DATE` | 허가일자 | 식약처 허가 일자 |
| `last_synced_at` | `DATETIME` | 시스템 동기화 일시 | 데이터 시스템 반영 시간 |

---

## 2. 💊 e약은요 상세 정보 (`eyak_info`)
'e약은요' 서비스에서 제공하는 의약품의 상세 효능, 복용법, 주의사항 등을 저장합니다.

| 컬럼명 (Column) | 타입 (Type) | 설명 (Description) | 비고 |
| :--- | :--- | :--- | :--- |
| **`item_seq`** | `VARCHAR(20)` | **품목기준코드 (Primary Key)** | 의약품 고유 식별 코드 |
| `item_name` | `TEXT` | 제품명 | 한글 제품명 |
| `entp_name` | `VARCHAR(255)` | 업체명 | 제조/수입 업체명 |
| `efficacy` | `TEXT` | 효능 | 약의 효능 및 효과 |
| `use_method` | `TEXT` | 사용법 | 올바른 복용/사용 방법 |
| `precautions` | `TEXT` | 주의사항 | 복용 시 주의해야 할 점 |
| `interaction` | `TEXT` | 상호작용 | 다른 약물이나 음식과의 상호작용 |
| `side_effects` | `TEXT` | 부작용 | 예상되는 부작용 정보 |
| `item_image` | `VARCHAR(500)` | 제품 이미지 URL | 의약품 낱알 식별 이미지 주소 |
| `source_updated_at` | `DATE` | 식약처 수정일 | 원천 데이터의 수정 일자 |
| `last_synced_at` | `DATETIME` | 시스템 동기화 일시 | 데이터 시스템 반영 시간 |

---

## 3. 🔗 통합 의약품 정보 (`unified_drug_info`)
`drug_permit_info`와 `eyak_info`의 데이터를 통합하여, 검색 및 AI 응답 생성 효율을 높이기 위한 단일 테이블입니다.

| 컬럼명 (Column) | 타입 (Type) | 설명 (Description) | 비고 |
| :--- | :--- | :--- | :--- |
| **`item_seq`** | `VARCHAR(20)` | **품목기준코드 (Primary Key)** | 의약품 고유 식별 코드 |
| `item_name` | `TEXT` | 제품명 | 한글 제품명 (인덱스) |
| `entp_name` | `VARCHAR(255)` | 업체명 | 제조/수입 업체명 |
| `etc_otcc_name` | `VARCHAR(50)` | 전문/일반 구분 | 전문/일반 의약품 구분 |
| `main_ingr_name` | `TEXT` | 주성분 | 주요 성분 명칭 |
| `efficacy` | `TEXT` | 효능 | 약의 효능 및 효과 |
| `use_method` | `TEXT` | 사용법 | 올바른 복용/사용 방법 |
| `precautions` | `TEXT` | 주의사항 | 복용 시 주의해야 할 점 |
| `interaction` | `TEXT` | 상호작용 | 상호작용 정보 |
| `side_effects` | `TEXT` | 부작용 | 부작용 정보 |
| `item_image` | `VARCHAR(500)` | 제품 이미지 URL | - |
| `source_updated_at` | `DATE` | 허가일/수정일 | 데이터 최신화 기준일 |
| `last_synced_at` | `DATETIME` | 시스템 동기화 일시 | - |

---

## 4. 🚫 DUR 통합 마스터 (`dur_master`)
의약품 안전 사용 서비스(DUR)의 병용금기, 연령금기, 임부금기 등의 규칙 정보를 저장합니다.

| 컬럼명 (Column) | 타입 (Type) | 설명 (Description) | 비고 |
| :--- | :--- | :--- | :--- |
| **`id`** | `BIGINT` | **ID (Primary Key)** | 자동 증가 PK |
| `dur_type` | `VARCHAR(50)` | 금기 유형 | 예: 병용금기, 연령금기, 임부금기 |
| `ingr_code` | `VARCHAR(20)` | 성분 코드 | 금기 대상 성분 코드 |
| `ingr_eng_name` | `VARCHAR(255)` | 성분명 (영문) | 영문 성분명 |
| `ingr_kor_name` | `VARCHAR(255)` | 성분명 (국문) | 한글 성분명 |
| `critical_value` | `VARCHAR(255)` | 핵심 주의값 | 금기 기준 (예: 특정 연령, 기간 등) |
| `prohbt_content` | `TEXT` | 금기 내용 | 상세 금기 사유 |
| `remark` | `TEXT` | 비고 | 추가 참고 사항 |
| `class_name` | `VARCHAR(255)` | 효능군/계열 | 약물의 효능군 분류 |
| `notification_date` | `DATE` | 공고 일자 | 식약처 공고일 |
| `last_synced_at` | `DATETIME` | 시스템 동기화 일시 | - |
