"""
application/use_cases/dur_inquiry.py
DUR 금기 조회 유스케이스
"""
import logging
from domain.drug.repositories import DurRepository
from domain.drug.services import DurAnalysisService

logger = logging.getLogger(__name__)


class DurInquiryUseCase:
    """
    DUR 금기 정보 조회 유스케이스
    - 성분명으로 DUR 조회 + 그룹화/번역
    - AI 동의어 확장 지원
    """

    def __init__(self, dur_repo: DurRepository):
        self._dur_repo = dur_repo
        self._domain_svc = DurAnalysisService()

    async def get_by_ingredient_text(self, ingr_text: str) -> list[dict]:
        """
        성분 텍스트(콤마/슬래시 구분)로 DUR 조회 → 검색 결과 형식 반환
        (기존 DrugService.get_dur_by_ingr 역할)
        """
        if not ingr_text:
            return []

        ingr_list = [i.strip() for i in ingr_text.replace(',', '/').split('/') if len(i.strip()) > 1]
        all_durs = await self._dur_repo.find_by_ingredient_names(ingr_list)

        return [
            {
                "type": d.dur_type,
                "ingr_name": d.ingr_kor_name,
                "warning_msg": d.warning_text,
                "severity": d.critical_value,
            }
            for d in all_durs
        ]

    async def get_enriched_by_ingredient(self, ingr_name: str, ai_service=None) -> list[dict]:
        """
        단일 성분으로 DUR 조회 + AI 동의어 확장(타임아웃 1초 제한) + 그룹화/번역
        """
        import asyncio
        if not ingr_name:
            return []

        # 1차 조회
        dur_list = await self._dur_repo.find_by_ingredient_name(ingr_name)

        # AI 동의어 확장 (결과 없을 때만, 최대 1초 제한)
        if not dur_list and ai_service and len(ingr_name.strip()) > 2:
            try:
                logger.debug(f"DUR 직접 매칭 없음 '{ingr_name}'. AI 동의어 요청 중 (timeout=1s)...")
                ai_synonyms = await asyncio.wait_for(
                    ai_service.get_synonyms(ingr_name),
                    timeout=1.0  # 🔑 최대 1초 — 초과하면 동의어 없이 진행
                )
                logger.debug(f"AI 동의어: {ai_synonyms}")
                if ai_synonyms:
                    dur_list = await self._dur_repo.find_by_ingredient_names(ai_synonyms)
            except asyncio.TimeoutError:
                logger.warning(f"AI 동의어 조회 타임아웃 ('{ingr_name}'). 건너뜁니다.")

        return self._domain_svc.group_and_translate(dur_list)
