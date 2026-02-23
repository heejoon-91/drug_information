# 의약품 원료성분 수집 파이프라인 및 DB 구조 개편 (v1.0)

## 개요

기존 의약품 허가 정보(`getDrugPrdtPrmsnInq07`) API에서는 원료성분(`MTRAL_NM`) 정보가 제공되지 않는 문제를 해결하기 위해, 상세조회 통합 API(`getDrugPrdtPrmsnDtlInq06`)로 파이프라인을 전면 교체하여 원료성분을 포함한 1-Step 데이터 수집 아키텍처를 구축하고 DB 모델을 개편했습니다.

## 1. Database Model (스키마) 변경 사항

Django `models.py` 내의 의약품 정보 테이블 구조를 명확히 분리하고 영문/한글 데이터를 적절히 담기 위해 컬럼명을 변경했습니다.
(대상 모델: `DrugPermitInfo`, `UnifiedDrugInfo`)

- **`main_ingr_name` (변경 전) -> `main_ingr_eng` (변경 후)**
    - 목적: 기존 주성분 데이터를 영문 전용 컬럼으로 분리
    - API 매핑 키: `MAIN_INGR_ENG`
- **`material_name` (변경 전) -> `main_ingr_kor` (변경 후)**
    - 목적: 텍스트 형태로 길게(파이프 형태) 붙어 들어오는 신규 원료성분 데이터를 한글 전용 컬럼으로 분리
    - API 매핑 키: `MAIN_ITEM_INGR`

## 2. 데이터 파이프라인 스크립트 수정 사항

### 2.1. `drug_enrichment_collector.py` (수집기)

- **API 엔드포인트 단일화:**
    - 기존 API (`/getDrugPrdtPrmsnInq07`) -> **상세 통합조회 API (`/getDrugPrdtPrmsnDtlInq06`)** 로 교체
    - 기능 분리를 위한 2-Step 호출 구조를 폐기하고 한 번의 네트워크 호출로 모든 정보 수집 (효율성 극대화)
- **데이터 파싱 필드명(Key) 수정:**
    - `item_eng_name` : `ITEM_ENG_NAME` (없을 시 `''` 보장)
    - `etc_otcc_name` : `MAKE_MATERIAL_FLAG` (전문/일반 구분)
    - `main_ingr_eng` : `MAIN_INGR_ENG`
    - `main_ingr_kor` : `MAIN_ITEM_INGR` (정규화된 `[코드]성분명|...` 문자열)

### 2.2. `unified_loader.py` (통합 로더)

- 변경된 DB 모델 컬럼명(`main_ingr_eng`, `main_ingr_kor`)에 맞춰 `defaults` 딕셔너리 매핑 로직 수정
- `DrugPermitInfo`의 데이터를 읽어와 `UnifiedDrugInfo` 테이블로 병합(Upsert) 시 동일하게 반영되도록 파이프라인 연계 완료

### 2.3. `sync_to_supabase.py` (클라우드 동기화 로직)

- **컬럼명 변경 반영:** `unified_drug_info` 동기화 로직 내 payload 필드명 업데이트
- **Upsert(덮어쓰기) 적용:**
    - 기존 `insert()` 방식에서 PK(`item_seq`, `dur_seq`) 충돌 에러방지를 위해 전 구간 **`.upsert()`** 메서드로 교체. 중복 데이터도 안정적으로 최신화 가능
- **`drug_permit_info` 테이블 전송 로직 신설:**
    - 원본 데이터인 `DrugPermitInfo` 테이블의 데이터 역시 Supabase로 백업될 수 있도록 500건 단위의 배치 처리(Upsert) 전송 로직 새로 추가

## 3. 원료성분(`main_ingr_kor`) 데이터 포맷 안내 및 활용

수집된 원료성분 데이터는 다음과 같은 형태의 정형 문자열로 저장됩니다.

> `[M040702]포도당|[M040426]염화나트륨`

- 개별 성분은 파이프(`|`) 기호로 구분됩니다.
- 각 성분명 앞에는 대괄호(`[]`)로 둘러싸인 고유 성분코드 7자리가 명시됩니다.
- **활용 방안:** 프론트엔드/백엔드 서버 또는 대형 언어 모델(LLM) 프롬프트 연동 시 해당 분리자(`|`) 규칙과 대괄호 코드를 파싱(제거/분리)하여 쉽게 성분 배열 정보만 추출할 수 있어 응용성이 매우 뛰어납니다.

## 4. 인프라 적용 방법

본 개편 사항을 반영하기 위해 다음 3단계가 수행되어야 합니다.

1. Supabase 원격 테이블(`drug_permit_info`, `unified_drug_info`) 컬럼 구조 변경
   (`main_ingr_name` -> `main_ingr_eng` / `main_ingr_kor` 새로 추가)
2. 로컬 Django 마이그레이션 적용 (`makemigrations`, `migrate`)
3. 전체 파이프라인 재실행 (Collector -> Loader -> Supabase Sync)
