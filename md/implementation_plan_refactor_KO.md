# 구현 계획 - DUR 데이터 완전 통합 (Refactoring)

사용자 요청에 따라, DUR API에서 제공하는 **모든 필드**를 누락 없이 저장, 조회할 수 있도록 `DurMaster` 테이블과 수집기를 전면 개편합니다.

## 목표

- `DurMaster` 단일 테이블에 모든 유형(병용금기, 임부금기 등)을 통합 저장.
- API 응답에 존재하는 모든 컬럼을 DB 필드로 생성 (Flatten Strategy).

## 변경 사항

### 1. 데이터베이스 모델 (`backend_django/drugs/models.py`)

`DurMaster` 모델에 다음 필드들을 추가합니다. (약 20개 컬럼 추가)

| 구분              | 필드명                  | 설명                                   |
| :---------------- | :---------------------- | :------------------------------------- |
| **기본정보**      | `dur_seq`               | DUR 일련번호                           |
|                   | `type_name`             | 금기 유형명                            |
|                   | `mix_type`              | 단일/복합 구분                         |
|                   | `form_name`             | 제형                                   |
|                   | `del_yn`                | 삭제 여부 (정상/삭제)                  |
| **원문정보**      | `ori_ingr`              | 처방명/제품명 원문 (`ORI`, `ORI_INGR`) |
|                   | `mix_ingr`              | 복합 성분 정보 (`MIX`, `MIX_INGR`)     |
| **병용금기 상세** | `mixture_ingr_code`     | 병용금기 성분코드                      |
|                   | `mixture_ingr_kor_name` | 병용금기 성분명(한글)                  |
|                   | `mixture_ingr_eng_name` | 병용금기 성분명(영문)                  |
|                   | `mixture_mix_type`      | 병용금기 단일/복합 구분                |
|                   | `mixture_class`         | 병용금기 약효분류                      |
|                   | `mixture_ori`           | 병용금기 원문 (`MIXTURE_ORI`)          |
| **유형별 상세**   | `grade`                 | 금기 등급 (임부)                       |
|                   | `max_qty`               | 최대 투여량 (용량)                     |
|                   | `max_dosage_term`       | 최대 투여기간 (기간)                   |
|                   | `age_base`              | 기준 연령 (연령)                       |
|                   | `effect_code`           | 효능 코드 (효능군)                     |
|                   | `sers_name`             | 효능군 명칭 (효능군)                   |

### 2. 데이터 수집기 (`data_pipeline/dur_unified_collector.py`)

- API 응답(`dur_table.md` 참조)의 키 값을 모델 필드에 1:1로 매핑하여 저장하도록 로직 수정.
- 필드명 변형 처리 (예: `INGR_KOR_NAME` vs `INGR_NAME`, `ORI` vs `ORI_INGR`) 로직 강화.

## 검증 계획

1. 모델 변경 후 `makemigrations` (가능한 경우) 또는 코드 리뷰.
2. 수집기 실행 시, 각 유형별 데이터가 해당 컬럼에 올바르게 들어가는지 확인.
