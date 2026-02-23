# 의약품 정보 관련 데이터베이스 스키마 명세서

현재 프로젝트에서 관리하는 의약품 및 DUR(의약품안전사용서비스) 관련 데이터베이스 테이블의 구조와 목적을 설명합니다.
모든 모델은 Django의 `drugs` 앱 내부 `models.py`에 정의되어 있습니다.

## 1. UnifiedDrugInfo (통합 의약품 정보)

`e약은요` API 데이터와 `제품허가정보` API 데이터를 결합하여 서비스에서 실제로 사용자에게 보여줄 통합 의약품 정보를 저장하는 메인 테이블입니다.

- **테이블 명:** `unified_drug_info`
- **주요 목적:** 사용자가 약품을 검색하고 상세 정보를 확인할 때 기본적으로 조회되는 마스터 테이블
- **스키마 구성:**
    - `item_seq` (PK, CharField): 품목기준코드 (고유 식별자)
    - `item_name` (TextField, Index): 제품명
    - `entp_name` (CharField): 업체명
    - `etc_otcc_name` (CharField): 전문/일반 구분 (제품허가정보 유래)
    - `main_ingr_name` (TextField): 주성분 (제품허가정보 유래)
    - `efficacy` (TextField): 효능 (e약은요 유래)
    - `use_method` (TextField): 사용법 (e약은요 유래)
    - `precautions` (TextField): 주의사항 (e약은요 유래)
    - `interaction` (TextField): 상호작용 (e약은요 유래)
    - `side_effects` (TextField): 부작용 (e약은요 유래)
    - `item_image` (URLField): 제품 이미지 URL
    - `source_updated_at` (DateField): 식약처 허가/수정일자
    - `last_synced_at` (DateTimeField): 시스템 동기화 시각

## 2. EYakInfo (e약은요 상세 정보)

식약처의 "e약은요" API에서 수집된 원본 상세 가이드 데이터를 보관하는 서브 테이블입니다. 통합 테이블(`UnifiedDrugInfo`)을 구성하는 주요 출처 중 하나입니다.

- **테이블 명:** `eyak_info`
- **주요 목적:** 소비자 친화적인 쉬운 용어로 작성된 약품 상세 가이드(효능, 주의사항 등) 원본 데이터 보관
- **스키마 구성:**
    - `item_seq` (PK, CharField): 품목기준코드
    - `item_name` (TextField): 제품명
    - `entp_name` (CharField): 업체명
    - `efficacy` (TextField): 효능
    - `use_method` (TextField): 사용법
    - `precautions` (TextField): 주의사항
    - `interaction` (TextField): 상호작용
    - `side_effects` (TextField): 부작용
    - `item_image` (URLField): 제품 이미지 URL
    - `source_updated_at` (DateField): 식약처 수정일
    - `last_synced_at` (DateTimeField): 시스템 동기화 시각

## 3. DrugPermitInfo (의약품 제품 허가 정보)

식약처 "의약품 제품 허가 정보" API에서 수집된 전문적인 원본 데이터를 보관하는 테이블입니다. '주성분'과 '전문/일반의약품 구분' 등 식별 위주의 데이터를 제공합니다.

- **테이블 명:** `drug_permit_info`
- **주요 목적:** 의약품의 허가 기초 정보(주성분명, 업체 정보 등) 원본 보관 및 검색 보조
- **스키마 구성:**
    - `item_seq` (PK, CharField): 품목기준코드
    - `item_name` (TextField): 제품명
    - `item_eng_name` (TextField): 제품명(영문)
    - `entp_name` (CharField): 업체명
    - `main_ingr_name` (TextField): 주성분명
    - `etc_otcc_name` (CharField): 전문/일반의약품 구분
    - `source_updated_at` (DateField): 허가일자
    - `last_synced_at` (DateTimeField): 시스템 동기화 시각

## 4. DurMaster (DUR 통합 마스터 테이블)

건강보험심사평가원의 7가지 DUR(의약품안전사용서비스) 주의 정보를 하나의 테이블로 통합하여 관리합니다. 약품의 성분코드(`ingr_code`)를 기준으로 금기 및 주의사항을 매핑할 때 사용됩니다.

- **테이블 명:** `dur_master`
- **주요 목적:** 병용금기, 임부금기, 노인주의, 용량/기간 주의 등의 성분별 안전 기준 데이터를 통합 제공
- **스키마 구성:** (7개 API의 모든 데이터를 포괄할 수 있도록 설계됨)
    - **[식별자/분류]** `dur_seq` (DUR 일련번호), `dur_type` (금기유형: COMBINED, PREGNANCY 등), `type_name` (유형 한글명)
        - _Index:_ `[dur_type, ingr_code]` 복합 인덱스 적용
    - **[기준 성분]** `ingr_code` (성분코드), `ingr_kor_name`, `ingr_eng_name`
    - **[정보 수식어]** `form_name` (제형), `mix_type` (단일/복합여부), `mix_ingr` (복합성분정보), `ori_ingr` (원문정보)
    - **[병용금기 전용]** `mixture_ingr_code`, `mixture_ingr_kor_name`, `mixture_ingr_eng_name`, `mixture_mix_type`, `mixture_class`, `mixture_ori`
    - **[특정 주의 전용 값]**
        - `grade` (임부금기 등급)
        - `max_qty` (용량주의 최대투여량)
        - `max_dosage_term` (투여기간주의 최대기간)
        - `age_base` (연령금기 기준연령)
        - `effect_code`, `sers_name` (효능군중복 코드 및 이름)
    - **[공통 메타 정보]**
        - `critical_value` (핵심주의값 - 통합 편의를 위한 추출 값)
        - `prohbt_content` (금기/주의 상세 내용)
        - `remark` (비고 사항)
        - `class_name` (효능군/계열)
        - `notification_date` (고시/공고 일자)
        - `del_yn` (유효 데이터 여부)
        - `last_synced_at` (동기화 시각)

## 5. UserProfile (사용자 건강 정보 프로필)

장기적으로 사용자 개인화 서비스를 위해 마련된 Django 기본 User 모델의 확장(1:1 OneToOne) 테이블입니다.

- **테이블 명:** `user_profile`
- **주요 목적:** 사용자의 기저 건강 상태(복용약, 알러지 등)를 저장하여 맞춤형 의약품 안전 정보(DUR 매칭 등) 제공
- **스키마 구성:**
    - `user_id` (PK/FK, OneToOne): Django 내장 사용자 테이블(User) ID
    - `current_medications` (TextField): 복용 중인 약품 목록 (텍스트)
    - `allergies` (TextField): 앓고 있는 알러지 내용
    - `chronic_diseases` (TextField): 기저 질환 내역
    - `updated_at` (DateTimeField): 최근 프로필 수정 시각
