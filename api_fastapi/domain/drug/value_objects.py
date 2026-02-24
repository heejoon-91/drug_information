"""
domain/drug/value_objects.py
값 객체(Value Objects) - 불변, 동등성은 값으로 판단
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class DurType:
    """DUR 금기 유형 값 객체"""
    code: str  # 예: "PREGNANCY", "COMBINED"

    # 유효한 DUR 유형 목록
    VALID_TYPES = {
        "PREGNANCY", "COMBINED", "AGE_SPECIFIC", "ELDERLY",
        "MAX_CAPACITY", "MAX_DURATION", "EFFICACY_DUPLICATE",
        "DOSAGE_DUPLICATE", "ADMINISTRATION_DUPLICATE",
        "LACTATION", "WEIGHT", "KIDNEY", "LIVER", "G6PD", "PEDIATRIC",
    }

    # DUR 유형 → 한국어 이름 매핑
    KOR_MAP = {
        "PREGNANCY": "임부 금기/주의",
        "COMBINED": "병용 금기",
        "AGE_SPECIFIC": "연령 금기",
        "ELDERLY": "노인 주의",
        "MAX_CAPACITY": "용량 주의",
        "MAX_DURATION": "투여 기간 주의",
        "EFFICACY_DUPLICATE": "효능 중복 주의",
        "DOSAGE_DUPLICATE": "용법 주의",
        "ADMINISTRATION_DUPLICATE": "투여 경로 주의",
        "LACTATION": "수유부 주의",
        "WEIGHT": "체중 주의",
        "KIDNEY": "신장 질환 주의",
        "LIVER": "간 질환 주의",
        "G6PD": "특정 효소 결핍 주의",
        "PEDIATRIC": "소아 주의",
    }

    @property
    def kor_name(self) -> str:
        return self.KOR_MAP.get(self.code, self.code)


@dataclass(frozen=True)
class IngrCode:
    """성분 코드 값 객체"""
    code: str

    def __post_init__(self):
        if not self.code or not self.code.strip():
            raise ValueError("성분 코드는 빈 값일 수 없습니다.")


@dataclass(frozen=True)
class ItemSeq:
    """품목기준코드 값 객체"""
    value: str

    def __post_init__(self):
        if not self.value or len(self.value) > 20:
            raise ValueError(f"유효하지 않은 품목기준코드: {self.value}")
