"""
infrastructure/external_api/fda_client.py
FDA Open API 호출 클라이언트 (기존 DrugService의 FDA 관련 메서드 이동)
"""
import re
import asyncio
import logging
import httpx

logger = logging.getLogger(__name__)

FDA_BASE_URL = "https://api.fda.gov/drug/label.json"
FDA_OTC_FILTER = 'openfda.product_type:"HUMAN OTC DRUG" AND _exists_:openfda.application_number'


class FdaClient:
    """FDA Open API 클라이언트"""

    def _get_base_ingredient_name(self, name: str) -> str:
        """성분명에서 염기(Salt) 등 접미사 제거하여 기본 성분명 추출"""
        # 대문자로 변환하여 처리
        name = name.upper().strip()
        # 흔히 쓰이는 염기/접미사 패턴
        salts = [
            ' SODIUM', ' POTASSIUM', ' HYDROCHLORIDE', ' HCL', ' MALEATE', 
            ' CALCIUM', ' PHOSPHATE', ' SULFATE', ' TARTRATE', ' BROMIDE',
            ' CITRATE', ' ACETATE', ' FUMARATE', ' HYDROBROMIDE', ' HBR', ' MONOHYDRATE'
        ]
        base_name = name
        for salt in salts:
            if base_name.endswith(salt):
                base_name = base_name.replace(salt, '').strip()
                break
        return base_name

    async def _fetch_from_fda(self, params: dict) -> dict | None:
        """공통 FDA API 요청 래퍼"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                # params['search']에 이미 특수문자가 포함된 경우 httpx가 안전하게 인코딩하도록 함
                res = await client.get(FDA_BASE_URL, params=params)
                if res.status_code == 200:
                    return res.json()
                elif res.status_code == 404:
                    return None
                else:
                    logger.warning(f"[FdaClient] API Error: {res.status_code} for params: {params}")
                    return None
            except Exception as e:
                logger.error(f"[FdaClient] Network Error: {e}")
                return None

    async def search_by_name(self, name: str) -> dict | None:
        """
        제품명/성분명으로 FDA OTC 의약품 정보 검색
        """
        name_up = name.upper()
        # 쿼리 내에서 AND/OR는 대문자로 사용하며, + 대신 공백 사용 (httpx가 +로 변환함)
        params = {
            'search': f'(openfda.brand_name:"{name_up}" OR openfda.generic_name:"{name_up}") AND {FDA_OTC_FILTER}',
        }
        
        data = await self._fetch_from_fda(params)
        if not data or not data.get('results'):
            # 2단계: 기본 이름으로 재시도
            base_name = self._get_base_ingredient_name(name)
            if base_name != name_up:
                logger.info(f"[FdaClient] Retrying search with base name: {base_name}")
                params['search'] = f'(openfda.brand_name:"{base_name}" OR openfda.generic_name:"{base_name}") AND {FDA_OTC_FILTER}'
                data = await self._fetch_from_fda(params)

        if data and data.get('results'):
            result = data['results'][0]
            openfda = result.get('openfda', {})

            generic_names = openfda.get('generic_name', [])
            substance_names = openfda.get('substance_name', [])
            combined_ingrs = list(set(generic_names + substance_names))
            if not combined_ingrs:
                combined_ingrs = result.get('active_ingredient', [])

            ingr_text = ", ".join(combined_ingrs) if isinstance(combined_ingrs, list) else str(combined_ingrs)

            return {
                "brand_name": name,
                "active_ingredients": ingr_text or "Ingredient Not Found",
                "ingredients": ingr_text,
                "indications": result.get('indications_and_usage', ["Indications not provided"])[0],
                "warnings": result.get('warnings', ["Warnings not provided"])[0],
                "dosage": result.get('dosage_and_administration', ["Dosage info not provided"])[0],
            }
        return None

    async def get_ingredients_by_symptoms(self, keywords: list[str]) -> list[str]:
        """
        증상 키워드로 FDA에서 관련 성분명 집계 (결정적 정렬 및 가중치 적용)
        """
        from collections import Counter
        ingr_counts = Counter()

        async with httpx.AsyncClient(timeout=10.0) as client:
            tasks = []
            for kw in keywords:
                # 검색어도 대문자화 (FDA 데이터와 매칭 확률 높임)
                kw_up = kw.upper()
                params = {
                    'search': f'indications_and_usage:"{kw_up}" AND {FDA_OTC_FILTER}',
                    'count': 'openfda.generic_name.exact',
                    'limit': 100  # 통계적 유의성을 위해 분석 범위 확대
                }
                tasks.append(client.get(FDA_BASE_URL, params=params))

            responses = await asyncio.gather(*tasks, return_exceptions=True)

            for res in responses:
                if isinstance(res, httpx.Response) and res.status_code == 200:
                    try:
                        results = res.json().get('results', [])
                        for item in results:
                            term = item.get('term', '').upper()
                            count = item.get('count', 0)
                            if not term:
                                continue
                            
                            parts = [p.strip() for p in re.split(r',\s*| AND ', term)]
                            
                            # 단일 성분 제품인 경우 가중치(x2) 부여 - 해당 증상의 전용 약물일 확률이 높음
                            is_single = (len(parts) == 1)
                            weight = 2 if is_single else 1
                            
                            for part in parts:
                                # 1. 숫자로 시작하는 함량 정보 등 제거
                                part_clean = re.sub(r'\s+\d+.*$', '', part).strip()
                                # 2. 접미사 제거하여 베이스 성분명 추출
                                base_name = self._get_base_ingredient_name(part_clean)
                                
                                if base_name and len(base_name) > 2:
                                    ingr_counts[base_name] += (count * weight)
                    except Exception as e:
                        logger.warning(f"[FdaClient] count 파싱 오류: {e}")

        # 빈도(가중치 합산) 순으로 정렬
        sorted_ingrs = sorted(
            ingr_counts.keys(), 
            key=lambda x: (-ingr_counts[x], x)
        )
        
        return sorted_ingrs[:20]

    async def get_warnings_by_ingredient(self, ingr_name: str) -> str | None:
        """성분명으로 FDA 경고(Warnings) 정보 조회"""
        ingr_up = ingr_name.upper()
        params = {
            'search': f'(openfda.generic_name:"{ingr_up}" OR openfda.substance_name:"{ingr_up}") AND {FDA_OTC_FILTER}',
        }
        
        data = await self._fetch_from_fda(params)
        if not data or not data.get('results'):
            # Fallback to base name
            base_name = self._get_base_ingredient_name(ingr_name)
            if base_name != ingr_up:
                params['search'] = f'(openfda.generic_name:"{base_name}" OR openfda.substance_name:"{base_name}") AND {FDA_OTC_FILTER}'
                data = await self._fetch_from_fda(params)

        if data and data.get('results'):
            return data['results'][0].get('warnings', ["No FDA warning found."])[0]
        return None

    async def get_otc_products_by_ingredient(self, ingredient: str) -> dict:
        """특정 성분이 포함된 미국 OTC 제품 리스트 조회"""
        ingr_up = ingredient.upper()
        params = {
            'search': f'(openfda.substance_name:"{ingr_up}" OR openfda.generic_name:"{ingr_up}") AND {FDA_OTC_FILTER}',
            'limit': 10  # 최대 10개만 조회 (번역 비용 방지)
        }

        data = await self._fetch_from_fda(params)
        if not data or not data.get('results'):
            # Fallback
            base_name = self._get_base_ingredient_name(ingredient)
            if base_name != ingr_up:
                params['search'] = f'(openfda.substance_name:"{base_name}" OR openfda.generic_name:"{base_name}") AND {FDA_OTC_FILTER}'
                data = await self._fetch_from_fda(params)

        if data and data.get('results'):
            results = data['results']
            products_info = []
            for item in results:
                openfda = item.get('openfda', {})
                brand_names = openfda.get('brand_name', [])
                if not brand_names:
                    continue
                products_info.append({
                    "brand_name": brand_names[0], # 서버 반환값 그대로 유지 (보통 대문자)
                    "purpose": item.get('purpose', ["Description not available."])[0],
                    "active_ingredient": item.get('active_ingredient', ["Unknown"])[0],
                })

            # 중복 제거 (brand_name 기준) 후 상위 5개만 반환
            unique = {p['brand_name'].upper(): p for p in products_info}
            sorted_products = sorted(unique.values(), key=lambda x: x['brand_name'])[:5]  # 🔑 최대 5개

            return {
                "ingredient": ingredient,
                "products": sorted_products,
                "count": len(sorted_products),
            }
        
        return {"ingredient": ingredient, "products": [], "count": 0}

    async def get_popular_products_by_ingredient(self, ingredient: str, limit: int = 5) -> list[dict]:
        """
        특정 성분이 포함된 미국 제품 중 가장 대중적인(빈도가 높은) 브랜드 상위 5개 추출
        FDA count API (openfda.brand_name.exact) 활용
        """
        ingr_up = ingredient.upper()
        # 성분명 접미사 제거하여 더 넓은 매칭 시도
        base_name = self._get_base_ingredient_name(ingr_up)
        
        params = {
            'search': f'(openfda.substance_name:"{base_name}" OR openfda.generic_name:"{base_name}") AND {FDA_OTC_FILTER}',
            'count': 'openfda.brand_name.exact',
            'limit': 50 # 상위 50개 중 유효한 브랜드명 선별
        }

        data = await self._fetch_from_fda(params)
        popular_products = []
        
        if data and data.get('results'):
            results = data['results']
            # 유효한 브랜드명 필터링 및 상위 n개 추출
            for item in results:
                brand = item.get('term', '').upper()
                count = item.get('count', 0)
                
                # 너무 짧거나 숫자로 시작하거나 일반명과 동일한 브랜드는 제외 시도
                if not brand or len(brand) < 2:
                    continue
                if brand == base_name:
                    continue
                
                popular_products.append({
                    "brand_name": brand,
                    "popularity_score": count
                })
                
                if len(popular_products) >= limit:
                    break
                    
        return popular_products

    async def find_optimal_us_products(self, ingredients: list[str]) -> dict:
        """복합 성분 기반 미국 OTC 제품 최적 매칭"""
        if not ingredients:
            return {"match_type": "NONE", "recommendations": []}

        # 모든 성분을 대문자로 변환
        search_query = " AND ".join(
            [f'(openfda.substance_name:"{ingr.upper()}" OR openfda.generic_name:"{ingr.upper()}")' for ingr in ingredients]
        )
        params = {
            'search': f'{search_query} AND {FDA_OTC_FILTER}',
            'limit': 10
        }

        data = await self._fetch_from_fda(params)
        if data and data.get('results'):
            results = data['results']
            products = [
                {
                    "brand_name": item.get('openfda', {}).get('brand_name', ['UNKNOWN'])[0],
                    "purpose": item.get('purpose', ['No purpose specified.'])[0],
                    "active_ingredient": item.get('active_ingredient', ['Unknown'])[0],
                }
                for item in results
            ]
            return {
                "match_type": "FULL_MATCH",
                "description": "모든 성분이 일치하는 미국 복합제 우선 추천",
                "recommendations": products,
            }

        # Component Match
        component_recommendations = []
        for ingr in ingredients:
            result = await self.get_otc_products_by_ingredient(ingr)
            component_recommendations.append(result)

        return {
            "match_type": "COMPONENT_MATCH",
            "description": "완전 일치 복합제가 없어 각 성분별 단일제 그룹을 큐레이션하여 추천합니다.",
            "recommendations": component_recommendations,
        }


