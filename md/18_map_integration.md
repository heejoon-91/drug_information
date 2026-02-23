# 구글 맵 API 기반 동적 약국 지도 (근처 약국 추천) 기능 추가

## 개요
사용자의 현재 위치를 기반으로 반경 1.5km 이내의 약국(Pharmacy) 정보를 동적으로 검색하고, 지도(Google Maps) 상에 표시하는 통합 기능이 성공적으로 적용되었습니다. 프론트엔드에서는 브라우저의 Geolocation API를, 백엔드에서는 Google Maps Places API(Nearby Search)를 사용합니다.

## 세부 변경 및 추가 사항

### 1. 백엔드 (FastAPI)
*   **새로운 서비스 모듈: `api_fastapi/services/map_service.py`**
    *   `MapService.find_nearby_pharmacies` `@classmethod` 구현. `httpx` 비동기 통신을 활용하여 구글 서버로 직접 API 콜을 수행합니다.
*   **라우터 엔드포인트: `/api/pharmacies` (`main.py`, `main2.py`)**
    *   사용자의 위도(`lat`)와 경도(`lng`)를 전달받아 `MapService`를 호출하고 그 결과 배열을 프론트엔드로 반환하는 브릿지 API 개통.
    *   백엔드 오류 및 API Key 누락과 연관된 예외 처리(`try..except`)를 통해 에러 상세 데이터(Traceback 포함)를 프론트엔드로 안전하게 전달하도록 구현.
*   **템플릿 렌더링 (`maps_key` 주입)**
    *   `web-search` 및 `smart-search` (Product/Symptom/Medical) 응답 시, 프론트엔드 HTML 상에서 `<script>` 태그를 이용해 구글 맵 JS 라이브러리를 동적 로딩할 수 있도록 `.env` 의 `GOOGLE_MAPS_API_KEY` 값을 꺼내 템플릿에 전달.

### 2. 프론트엔드 (HTML/JS)
*   **지원 템플릿: `search_result.html`, `symptom_result.html`**
    *   **섹션 UI 구조화**: Tailwind CSS 기반으로 증상 또는 검색 결과 아래에 "[내 근처 추천 약국]" 구역을 구성.
    *   **위치 권한 획득**: 페이지 렌더링 직후 `navigator.geolocation`을 통해 사용자 브라우저 위치 정보 권한 요청 및 좌표 획득.
    *   **지도 렌더링 (Google Maps SDK)**:
        *   얻어온 좌표를 중앙으로 구글 맵 캔버스 초기화.
        *   현재 사용자 위치를 "파란색 원형 마커"로 표기.
    *   **약국 리스트 렌더링**:
        *   백엔드(`/api/pharmacies`)로부터 받아온 JSON 약국 결과 배열을 순회.
        *   각 약국 위치마다 붉은 마커 표시 (클릭 시 이름과 평점이 담긴 InfoWindow 팝업 표출).
        *   지도 하단에 스크롤 가능한 리스트 형태로 약국 상호명, 주소, 평점 목록 출력.
        *   리스트 아이템 클릭 시, 지도가 해당 약국 마커 위치로 자동 이동(`panTo`) 및 17레벨 `zoom` 기능 구현.
    *   **강화된 에러 핸들링**: 
        *   약국 결과가 없거나 구글 계정 관련 제약(Billing 권한 없음, KEY 거부 등)이 있을 때 `Not Found` 오류를 표출하는 대신 반환된 JSON 원본을 회색 박스 내에 표시하여 쉽게 원인을 파악할 수 있도록 수정.

### 3. 환경 변수
*   **`.env` 설정**:
    *   `GOOGLE_MAPS_API_KEY` 환경 변수 구조에 통합하여 API 무단 탈취 방지.
