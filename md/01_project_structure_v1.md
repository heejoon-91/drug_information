# 프로젝트 구조 설명 (Project Structure Overview) - V1

이 프로젝트는 **Django(ORM/Admin)**와 **FastAPI(Service/API)**가 결합된 하이브리드 구조를 가지고 있습니다.
각 디렉토리와 핵심 파일의 역할을 상세 설명합니다.

---

## 📂 api_fastapi/
**핵심 서비스 로직 및 API 서버 (Microservice Layer)**
FastAPI를 사용하여 사용자의 요청을 처리하고, AI 및 외부 API(FDA)와 통신하는 실질적인 '두뇌' 역할을 합니다.

*   **`main.py`**:
    *   FastAPI 앱의 진입점(Entry Point)입니다.
    *   API 엔드포인트(`smart-search` 등)가 정의되어 있으며, 요청을 받아 적절한 서비스(`Service`)로 연결합니다.
    *   환경 변수 로딩, 로깅 설정, 템플릿 렌더링을 담당합니다.
*   **`services/`**: 비즈니스 로직이 모여 있는 곳입니다.
    *   `ai_service.py`: OpenAI API와 통신하며 의도 분류, 답변 생성을 담당합니다. (싱글톤 패턴, Lazy Init 적용)
    *   `drug_service.py`: FDA API 조회, DUR DB 조회, 데이터 병합 등 데이터 처리 로직을 담당합니다.
*   **`prompts/`**: AI에게 보낼 프롬프트 템플릿을 관리합니다.
    *   `system_prompts.py`: AI의 페르소나 및 의도 분류 가이드.
    *   `answer_prompts.py`: 최종 답변 생성 가이드.
*   **`templates/`**:
    *   `symptom_result.html`, `search_result.html` 등 사용자에게 보여질 HTML 파일들이 있습니다. (Jinja2 템플릿)

---

## 📂 backend_django/
**데이터 모델 및 관리자 페이지 (Data Layer)**
Django의 강력한 ORM 기능을 사용하여 DB 스키마를 정의하고 데이터를 관리합니다.

*   **`drugs/models.py`**:
    *   `DurMaster`: 한국 DUR(병용금기 등) 정보를 담는 테이블 스키마.
    *   `EYakInfo`: 국내 의약품 상세 정보를 담는 테이블 스키마.
*   **`core/settings.py`**:
    *   데이터베이스 연결 설정, 앱 등록 등 Django 설정 파일입니다.
*   **`manage.py`**:
    *   DB 마이그레이션, 관리자 계정 생성 등 Django 명령어를 실행하는 도구입니다.

---

## 📂 data_pipeline/
**데이터 수집 및 동기화 (ETL Layer)**
공공데이터포털 등 외부에서 데이터를 가져와 DB에 적재하는 스크립트입니다.

*   `dur_unified_collector.py`: DUR 정보를 통합 수집하는 스크립트.

---

## 📄 Documentation (문서)
프로젝트 이해를 돕기 위해 생성된 가이드 문서들입니다.

*   **`chatbot_config_guide.md`**: 챗봇의 성격, 답변 스타일, 검색 범위를 수정하는 방법 가이드.
*   **`chatbot_data_flow.md`**: 사용자 질문부터 답변 출력까지의 데이터 흐름 설명.
*   **`project_structure.md`**: (본 문서) 프로젝트 디렉토리 구조 설명.

---

## ⚙️ 설정 파일
*   **`.env`**: OpenAI API Key, DB 접속 정보 등 민감한 환경 변수를 저장하는 파일. (Git에 포함되지 않음)
*   **`requirements.txt`**: 프로젝트 실행에 필요한 Python 패키지 목록.
