"""
application/use_cases/symptom_recommend.py
증상 기반 약품 추천 유스케이스
"""
import logging
import asyncio
from domain.drug.repositories import DurRepository
from infrastructure.external_api.fda_client import FdaClient

logger = logging.getLogger(__name__)


class SymptomRecommendUseCase:
    """
    증상 기반 약품 추천 유스케이스
    - FDA에서 증상 관련 성분 추출
    - DUR 금기 정보 결합
    - AI를 통한 최종 답변 생성
    (기존 LangGraph nodes_v2.py retrieve_fda_node + retrieve_dur_node 오케스트레이션)
    """

    def __init__(
        self,
        dur_repo: DurRepository,
        fda_client: FdaClient,
        ai_service=None,
        cache=None,
    ):
        self._dur_repo = dur_repo
        self._fda_client = fda_client
        self._ai_service = ai_service
        self._cache = cache

    async def get_fda_ingredients_for_symptom(self, keyword: str) -> list[str]:
        """
        증상 키워드 → FDA 성분 추출 (동의어 즉시 병합 검색으로 결과 확대)
        """
        import asyncio

        # 1차: 단일 키워드 검색
        fda_ingrs = await self._fda_client.get_ingredients_by_symptoms([keyword])

        # 결과가 없거나 너무 적으면(<=1개) 동의어도 병렬로 검색해서 합산
        if len(fda_ingrs) <= 1 and self._ai_service:
            logger.info(f"FDA 검색 결과 부족({len(fda_ingrs)}개). AI 동의어 병합 검색 시도 중...")
            synonyms = await self._ai_service.get_symptom_synonyms(keyword)
            if synonyms:
                # 원본 키워드 + 동의어를 한 번에 묶어서 재검색
                all_keywords = [keyword] + synonyms[:4]  # 최대 5개 키워드
                fda_ingrs = await self._fda_client.get_ingredients_by_symptoms(all_keywords)
                logger.info(f"동의어 병합 검색 결과: {len(fda_ingrs)}개 성분")

        # 그래도 없으면 AI 직접 추천
        if not fda_ingrs and self._ai_service:
            logger.info("FDA + 동의어 검색 실패. AI 성분 직접 추천 중...")
            fda_ingrs = await self._ai_service.recommend_ingredients_for_symptom(keyword)
            logger.info(f"AI 직접 추천 결과: {fda_ingrs}")

        return fda_ingrs

    async def get_enriched_dur_for_ingredients(self, ingr_list: list[str]) -> list[dict]:
        """
        성분 리스트 → DUR 금기 + FDA Warning 병합 조회 (병렬 처리 고속화)
        """
        from domain.drug.services import DurAnalysisService
        from application.use_cases.dur_inquiry import DurInquiryUseCase

        dur_inquiry = DurInquiryUseCase(self._dur_repo)
        # 중복 성분 제거 (염기/수화물 접미사 제거하여 통합)
        raw_unique = set(i.upper() for i in ingr_list)
        normalized_unique = set()
        for ingr in raw_unique:
            base = self._fda_client._get_base_ingredient_name(ingr)
            normalized_unique.add(base)
            
        unique_ingrs = sorted(normalized_unique)

        # 모든 성분에 대해 병렬로 조회 실행 (FDA 데이터 수집)
        raw_items = await asyncio.gather(*[
            asyncio.gather(
                dur_inquiry.get_enriched_by_ingredient(ing, self._ai_service),
                self._fda_client.get_warnings_by_ingredient(ing)
            ) for ing in unique_ingrs
        ])

        # 2. 벌크 요약 처리 (AI 호출 횟수 감소)
        warnings_to_summarize = {unique_ingrs[i]: items[1] for i, items in enumerate(raw_items) if items[1]}
        summaries = {}
        if warnings_to_summarize:
            summaries = await self._ai_service.bulk_summarize_fda_warnings(warnings_to_summarize)

        # 3. 결과 조합
        enriched_data = []
        for i, ing in enumerate(unique_ingrs):
            kr_durs, raw_warn = raw_items[i]
            enriched_data.append({
                "ingredient": ing,
                "kr_durs": kr_durs,
                "fda_warning": summaries.get(ing, "특이사항 없음") if raw_warn else None
            })
        
        return enriched_data
