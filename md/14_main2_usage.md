# main2.py (웹 서비스 - Supabase 버전) 사용 가이드

이 서버는 `main.py`의 완전한 복제본이지만, **DUR(의약품 금기) 정보를 로컬 SQL DB 대신 Supabase에서 직접 조회**하도록 수정된 버전입니다.

## 1. 사전 준비

### 환경 변수 설정 (.env)
- `OPENAI_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_KEY`
- `DJANGO_SETTINGS_MODULE` (Django 모델 임포트를 위해 필요)

### 라이브러리 설치
```bash
pip install httpx asyncio supabase openai python-dotenv fastapi uvicorn jinja2
```

## 2. 서버 실행 방법

터미널에서 프로젝트 루트(`drug_information`)로 이동 후 실행하세요.

```bash
# 중요: 루트 디렉토리에서 실행
python api_fastapi/main2.py
```

또는:
```bash
uvicorn api_fastapi.main2:app --reload --port 8001
```

## 3. 기능 안내 (main.py와 동일)

1. **제품 검색 (Web Search)**:
   - 주소: `http://127.0.0.1:8001`
   - 약물 입력 시 FDA 정보와 함께 **Supabase**에서 조회한 한국 DUR 정보를 표시합니다.

2. **지능형 검색 (Smart Search)**:
   - LangGraph 에이전트가 작동하며, 내부적으로 DUR 정보를 조회할 때도 **Supabase**를 사용합니다.

## 4. 구조적 차이

- `main.py`: `DrugService`가 로컬 Django ORM(`DurMaster.objects.filter`)을 사용
- `main2.py`: `DrugService`를 몽키패치하여 `SupabaseService`가 대신 작동 (API 호출)
