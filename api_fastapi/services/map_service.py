import os
import httpx

class MapService:
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