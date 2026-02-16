# Global Drug Safety Intelligence Chatbot

이 프로젝트는 **한국 DUR(의약품안전사용서비스)** 정보와 **미국 FDA(식품의약국)**의 최신 의약품 안전 정보를 결합하여, 사용자에게 포괄적인 약물 안전 정보를 제공하는 지능형 챗봇 서비스입니다.

## 🚀 주요 기능 (Key Features)

*   **지능형 의도 분류 (AI Intent Classification)**: 사용자 질문을 제품/증상/일반 의학 상식으로 자동 분류.
*   **하이브리드 데이터 검색 (Hybrid Data Retrieval)**: FDA 실시간 데이터와 한국 DUR DB를 결합하여 제공.
*   **실시간 안전 정보 통합**: 한/미 의약품 안전 정보를 통합하여 팝업으로 경고 제공.

## 🛠️ 기술 스택 (Tech Stack)

*   **Backend**: Django (Admin/ORM), FastAPI (AI/Service)
*   **AI**: OpenAI GPT-4o-mini
*   **Database**: MySQL
*   **External API**: OpenFDA, Korea DUR API

---

## ⚡ 설치 및 실행 가이드 (Setup Guide)

프로젝트를 실행하기 위해 아래 단계들을 순서대로 따라주세요.

### 1. 필수 요구사항 (Prerequisites)
*   Python 3.10 이상
*   MySQL 서버 (로컬 또는 원격)
*   Git

### 2. 프로젝트 클론 및 패키지 설치
```bash
# 1. 프로젝트 다운로드
git clone [repository_url]
cd drug_information

# 2. 가상환경 생성 및 활성화
python -m venv venv
# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate

# 3. 필수 패키지 설치
pip install -r requirements.txt
```

### 3. 환경 변수 설정 (.env)
프로젝트 루트 디렉토리(`drug_information/`)에 `.env` 파일을 생성하고 아래 내용을 작성하세요.

```ini
# --- [필수] API 키 설정 ---
# OpenAI API 키 (챗봇 기능용)
OPENAI_API_KEY=sk-proj-...

# 공공데이터포털 DUR API 키 (데이터 수집용, Decoding된 키 입력 권장)
KR_API_KEY=your_decoding_key_here

# --- [선택] 데이터베이스 설정 (기본값: 로컬 MySQL) ---
DB_NAME=drug_db
DB_USER=root
DB_PASSWORD=your_password
DB_HOST=127.0.0.1
DB_PORT=3306

# --- [선택] Django 시크릿 키 (배포 시 변경 필수) ---
SECRET_KEY=django-insecure-...
```

### 4. 데이터베이스 구축 (Database Setup)

**Step 1: MySQL 데이터베이스 생성**
MySQL에 접속하여 빈 데이터베이스를 생성합니다. (기본값: `drug_db`)
```sql
CREATE DATABASE drug_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

**Step 2: 테이블 생성 (Django Migration)**
Django의 마이그레이션 기능을 이용해 테이블 스키마를 생성합니다.
```bash
cd backend_django
python manage.py makemigrations
python manage.py migrate
cd ..
```

**Step 3: 초기 데이터 수집 (Data Collection)**
공공데이터포털 API를 통해 DUR 데이터를 수집하여 DB에 적재합니다.
*   주의: `KR_API_KEY`가 `.env`에 올바르게 설정되어 있어야 합니다.
*   시간이 다소 소요될 수 있습니다.

```bash
# 프로젝트 루트에서 실행
python data_pipeline/dur_unified_collector.py
```

### 5. 서버 실행 (Run Server)
모든 설정이 완료되었습니다. FastAPI 서버를 실행하세요.

```bash
# 프로젝트 루트에서 실행
python api_fastapi/main.py
```
*   **웹 접속**: `http://127.0.0.1:8000`
*   **테스트**: 검색창에 "머리 아파" 또는 "타이레놀"을 입력해보세요.

---

## � 문서 (Documentation)
더 자세한 내용은 아래 문서를 참고하세요.

*   [📂 **프로젝트 구조 (Project Structure)**](./project_structure.md): 디렉토리 및 파일 역할 설명
*   [⚙️ **설정 가이드 (Configuration Guide)**](./chatbot_config_guide.md): 챗봇 성격 및 파라미터 변경 방법
*   [🔄 **데이터 흐름 (Data Flow)**](./chatbot_data_flow.md): 사용자 입력부터 답변까지의 처리 과정