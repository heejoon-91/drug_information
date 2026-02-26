"""
domain/drug/entities.py
도메인 엔티티 - 순수 Python (DB/프레임워크 의존성 없음)
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DrugEntity:
    """의약품 기본 정보 엔티티"""
    item_seq: str
    item_name: str
    entp_name: Optional[str] = None
    etc_otcc_name: Optional[str] = None       # 전문/일반
    main_ingr_eng: Optional[str] = None
    main_ingr_kor: Optional[str] = None
    efficacy: Optional[str] = None
    use_method: Optional[str] = None
    precautions: Optional[str] = None
    interaction: Optional[str] = None
    side_effects: Optional[str] = None
    item_image: Optional[str] = None


@dataclass
class DurInfoEntity:
    """DUR 금기 정보 엔티티"""
    dur_type: str                              # 예: "PREGNANCY", "COMBINED"
    ingr_kor_name: Optional[str] = None
    ingr_eng_name: Optional[str] = None
    prohbt_content: Optional[str] = None      # 금기 내용
    remark: Optional[str] = None              # 비고
    critical_value: Optional[str] = None      # 핵심 주의값
    grade: Optional[str] = None               # 금기 등급
    mixture_ingr_kor_name: Optional[str] = None
    mixture_ingr_eng_name: Optional[str] = None

    @property
    def warning_text(self) -> str:
        """금기 내용 또는 비고 반환"""
        return self.prohbt_content or self.remark or ""


@dataclass
class IngredientEntity:
    """성분 정보 엔티티 (FDA / DUR 검색용)"""
    name: str                                  # 영문 성분명 (대문자)
    kor_name: Optional[str] = None
    can_take: bool = True
    reason: Optional[str] = None
    dur_warning_types: list = field(default_factory=list)
    kr_durs: list = field(default_factory=list)
    fda_warning: Optional[str] = None
    products: list = field(default_factory=list)


@dataclass
class FdaDrugResult:
    """FDA API 검색 결과 엔티티"""
    brand_name: str
    active_ingredients: str
    indications: str
    warnings: str
    dosage: str
