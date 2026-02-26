"""
domain/drug/services.py
도메인 서비스 - 비즈니스 규칙 (DUR 분석, 성분 동의어 해석 등)
외부 의존성(DB, API) 없음
"""
import re
from domain.drug.entities import DurInfoEntity
from domain.drug.value_objects import DurType


class DurAnalysisService:
    """DUR 데이터 분석 도메인 서비스"""

    # 성분 동의어 사전 (FDA generic_name → DUR ingr_eng_name 매핑)
    SYNONYMS: dict[str, list[str]] = {
        "acetaminophen": ["acetaminophen", "paracetamol"],
        "paracetamol": ["acetaminophen", "paracetamol"],
        "aspirin": ["aspirin", "acetylsalicylic acid"],
        "ibuprofen": ["ibuprofen"],
        "naproxen": ["naproxen"],
        "diphenhydramine": ["diphenhydramine"],
    }

    # FDA 성분명 → DUR DB 성분명 수동 매핑
    MANUAL_INGR_MAPPING: dict[str, str] = {
        "DIVALPROEX SODIUM": "VALPROIC ACID",
        "DIVALPROEX": "VALPROIC ACID",
    }

    def resolve_synonyms(self, ingr_name: str) -> set[str]:
        """성분명에 대한 동의어 및 첫 단어를 포함한 검색 후보 반환"""
        target = ingr_name.strip().lower()
        candidates: set[str] = {target}

        # 수동 매핑 적용
        mapped = self.MANUAL_INGR_MAPPING.get(target.upper())
        if mapped:
            candidates.add(mapped.lower())

        # 동의어 사전 적용
        if target in self.SYNONYMS:
            candidates.update(self.SYNONYMS[target])

        # 첫 단어 추가 (긴 성분명 처리)
        first_word = target.split()[0]
        if len(first_word) > 3:
            candidates.add(first_word)

        return candidates

    def group_and_translate(self, dur_list: list[DurInfoEntity]) -> list[dict]:
        """
        DUR 목록을 유형별로 그룹화하고 한국어로 변환
        중복 경고 내용 제거 후 결합
        """
        grouped: dict[str, dict] = {}

        for d in dur_list:
            dur_type = DurType(d.dur_type)
            kor_type = dur_type.kor_name
            content = d.warning_text.strip()

            if not content:
                continue

            if kor_type not in grouped:
                grouped[kor_type] = {
                    "type": kor_type,
                    "original_type": d.dur_type,
                    "kor_name": d.ingr_kor_name,
                    "warnings": set(),
                }
            grouped[kor_type]["warnings"].add(content)

        results = []
        for val in grouped.values():
            combined = "\n".join(sorted(val["warnings"]))
            results.append({
                "type": val["type"],
                "kor_name": val["kor_name"],
                "warning": combined,
            })

        return results

    def extract_dosage_mg(self, active_ingredient_text: str) -> float | None:
        """FDA active_ingredient 텍스트에서 mg 수치 추출"""
        match = re.search(r'(\d+(?:\.\d+)?)\s*mg', active_ingredient_text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
        return None

    def compare_dosage(self, fda_text: str, kr_dosage_mg: float) -> dict:
        """FDA 함량과 한국 기준 함량 비교 후 경고 메시지 반환"""
        us_mg = self.extract_dosage_mg(fda_text)

        if us_mg is not None and kr_dosage_mg > 0:
            ratio = us_mg / kr_dosage_mg
            if ratio >= 1.5:
                msg = f"주의: 미국 제품의 함량({us_mg}mg)이 한국 기준({kr_dosage_mg}mg)보다 1.5배 이상 높습니다."
            elif ratio <= 0.5:
                msg = f"주의: 미국 제품의 함량({us_mg}mg)이 한국 기준({kr_dosage_mg}mg)보다 0.5배 이하로 낮습니다."
            else:
                msg = f"미국 제품의 함량({us_mg}mg)은 한국 처방 기준({kr_dosage_mg}mg)과 유사합니다."
        else:
            msg = "함량(mg) 정보를 추출하지 못하거나 기준량이 없어 비교할 수 없습니다."

        return {
            "us_dosage_mg": us_mg,
            "kr_dosage_mg": kr_dosage_mg,
            "warning": msg,
        }
