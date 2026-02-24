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
        증상 키워드 → FDA 성분 추출 (AI 폴백 포함)
        """
        fda_ingrs = await self._fda_client.get_ingredients_by_symptoms([keyword])

        if not fda_ingrs and self._ai_service:
            logger.info(f"FDA 검색 실패 '{keyword}'. AI 동의어 시도 중...")
            synonyms = await self._ai_service.get_symptom_synonyms(keyword)
            if synonyms:
                fda_ingrs = await self._fda_client.get_ingredients_by_symptoms(synonyms)

            if not fda_ingrs:
                logger.info("FDA + 동의어 검색 실패. AI 성분 추천 중...")
                fda_ingrs = await self._ai_service.recommend_ingredients_for_symptom(keyword)

        return fda_ingrs

    async def get_enriched_dur_for_ingredients(self, ingr_list: list[str]) -> list[dict]:
        """
        성분 리스트 → DUR 금기 + FDA Warning 병합 조회
        (기존 DrugService.get_enriched_dur_info 역할)
        """
        from domain.drug.services import DurAnalysisService
        from application.use_cases.dur_inquiry import DurInquiryUseCase

        dur_inquiry = DurInquiryUseCase(self._dur_repo)
        domain_svc = DurAnalysisService()
        enriched_data = []

        unique_ingrs = sorted(set(i.upper() for i in ingr_list))

        for ingr in unique_ingrs:
            kr_durs = await dur_inquiry.get_enriched_by_ingredient(ingr, self._ai_service)
            fda_warn = await self._fda_client.get_warnings_by_ingredient(ingr)

            if fda_warn and self._ai_service:
                summary = await self._ai_service.summarize_fda_warning(fda_warn)
                if summary:
                    fda_warn = summary

            enriched_data.append({
                "ingredient": ingr,
                "kr_durs": kr_durs,
                "fda_warning": fda_warn,
            })

        return enriched_data
