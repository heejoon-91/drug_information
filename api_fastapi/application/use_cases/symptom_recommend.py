"""
application/use_cases/symptom_recommend.py
증상 기반 약품 추천 유스케이스
"""
import logging
import asyncio
import re
from collections import Counter
from domain.drug.repositories import DurRepository, DrugRepository
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
        drug_repo: DrugRepository = None,
        ai_service=None,
        cache=None,
    ):
        self._dur_repo = dur_repo
        self._fda_client = fda_client
        self._drug_repo = drug_repo
        self._ai_service = ai_service
        self._cache = cache

    async def get_best_ingredients_for_symptom(self, keyword: str, symptom: str = None) -> list[str]:
        """
        [DB-First 설계]
        증상 키워드 → 1. 국내 DB 효능 검색 → 2. FDA 검색 → 3. AI 추천 순으로 성분 추출
        """
        candidate_ingrs = []
        db_search_key = symptom if symptom and any('\uac00' <= c <= '\ud7a3' for c in symptom) else keyword
        
        # 1. 국내 DB 효능(efficacy) 검색 (우선순위 1)
        if self._drug_repo:
            logger.info(f"1단계: 국내 DB 효능 검색 시도 ('{db_search_key}')")
            drugs = await self._drug_repo.find_by_efficacy(db_search_key, limit=20)
            db_ingrs = []
            for d in drugs:
                if d.main_ingr_eng:
                    parts = [p.strip().upper() for p in re.split(r'[/,]', d.main_ingr_eng)]
                    db_ingrs.extend(parts)
            
            if db_ingrs:
                counts = Counter(db_ingrs)
                candidate_ingrs = [item for item, count in counts.most_common(15)]
                logger.info(f"국내 DB에서 {len(candidate_ingrs)}개 성분 후보 추출 완료")

        # 2. 국내 DB 결과가 없으면 기존 FDA 검색 수행 (우선순위 2)
        if not candidate_ingrs:
            logger.info(f"2단계: FDA 성분 추출 시도 ('{keyword}')")
            candidate_ingrs = await self._fda_client.get_ingredients_by_symptoms([keyword])

            # 3. 결과가 부족하면 동의어 검색
            if len(candidate_ingrs) <= 1 and self._ai_service:
                logger.info(f"FDA 검색 결과 부족. AI 동의어 병합 검색 시도 중...")
                synonyms = await self._ai_service.get_symptom_synonyms(keyword)
                if synonyms:
                    all_keywords = [keyword] + synonyms[:4]
                    candidate_ingrs = await self._fda_client.get_ingredients_by_symptoms(all_keywords)

        # 4. 그래도 없으면 AI 직접 추천 (우선순위 3)
        if not candidate_ingrs and self._ai_service:
            logger.info("모든 검색 실패. AI 성분 직접 추천 중...")
            candidate_ingrs = await self._ai_service.recommend_ingredients_for_symptom(keyword)
            logger.info(f"AI 직접 추천 결과: {candidate_ingrs}")

        # [핵심] 모든 경로에서 추출된 성분에 대해 AI 필터링 적용 (증상 적합성 검증)
        if candidate_ingrs and self._ai_service:
            logger.info(f"최종 AI 필터링 시작 (대상: {len(candidate_ingrs)}개 성분)")
            # 필터링용 증상은 사용자의 원래 질문(symptom)을 우선 사용
            filter_key = symptom or keyword
            filtered_ingrs = await self._ai_service.filter_relevant_ingredients(filter_key, candidate_ingrs)
            # 엄격하게 상위 5개만 반환
            final_5 = filtered_ingrs[:5]
            logger.info(f"최종 AI 필터링 결과 (상위 5): {final_5}")
            return final_5

        return candidate_ingrs[:5]

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
