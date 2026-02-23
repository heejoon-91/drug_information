# 보류된 외부 연동 API 목록 및 명세

이 문서는 사용자의 요청 또는 정책에 의해 일시적으로 주석 처리되거나 보류된 외부 연동 API의 명세를 기록합니다.

## 1. Google Maps Nearby Search API (약국 검색)

*   **관련 파일**: [api_fastapi/services/map_service.py](file:///c:/Workspaces/drug_information/api_fastapi/services/map_service.py) 
*   **메서드**: [find_nearby_pharmacies(lat, lng)](file:///c:/Workspaces/drug_information/api_fastapi/services/map_service.py#7-25)
*   **상태**: 주석 처리됨 (사용자 요청)

### 기능 설명
주어진 위경도(Latitude, Longitude) 좌표를 기준으로 반경 1.5km 이내의 약국(`type="pharmacy"`) 목록을 검색하여 반환합니다. DUR 매핑 후 사용자가 근처 약국을 찾고 싶을 때 활용할 목적이었습니다.

### 기존 코드 구조
```python
@classmethod
async def find_nearby_pharmacies(cls, lat: float, lng: float):
    # Google Maps Nearby Search API 활용
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        "location": f"{lat},{lng}",
        "radius": 1500, # 1.5km
        "type": "pharmacy",
        "key": api_key,
        "language": "ko"
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params)
        return resp.json().get("results", [])
```

### 사유
비용 또는 API 키 의존성 문제로 판단되어 일단 제외되었습니다. 이후 약국 검색 기능 부활 시 위 로직을 바탕으로 쉽게 연동을 재개할 수 있습니다.
