from django.db import models

# 1. 고도화된 e약은요 & 제품허가 통합 테이블
class EYakInfo(models.Model):
    # 기본 정보 (제품 허가 목록 API 기반)
    item_seq = models.CharField(max_length=20, primary_key=True, verbose_name="품목기준코드")
    item_name = models.TextField(verbose_name="제품명") # db_index 제거
    item_eng_name = models.TextField(blank=True, null=True, verbose_name="제품명(영문)")
    entp_name = models.CharField(max_length=255, blank=True, null=True, verbose_name="업체명")
    
    # [중요] 전문/일반 구분 (제품 허가 목록의 SPCLTY_PBLC 또는 ETC_OTC_CODE)
    etc_otcc_name = models.CharField(max_length=50, blank=True, null=True, verbose_name="전문/일반")
    
    # [핵심] 주성분 정보 (제품 주성분 상세정보 API에서 추출한 성분명들을 콤마로 연결하여 저장)
    # DUR 성분 기반 검색과 e약은요 제품 검색을 잇는 가교 역할을 합니다.
    main_ingr_name = models.TextField(blank=True, null=True, verbose_name="주성분명 통합")
    
    # 상세 가이드 (e약은요 및 상세정보 API 데이터)
    efficacy = models.TextField(blank=True, null=True, verbose_name="효능")
    use_method = models.TextField(blank=True, null=True, verbose_name="사용법")
    precautions = models.TextField(blank=True, null=True, verbose_name="주의사항")
    interaction = models.TextField(blank=True, null=True, verbose_name="상호작용")
    side_effects = models.TextField(blank=True, null=True, verbose_name="부작용")
    
    # 문서 링크 (제품 허가 상세정보 API의 PDF 다운로드 링크 등)
    # 텍스트 데이터가 부족할 경우 LLM이 직접 참고할 수 있는 리소스로 활용합니다.
    ee_doc_url = models.URLField(max_length=500, blank=True, null=True, verbose_name="효능효과문서URL")
    ud_doc_url = models.URLField(max_length=500, blank=True, null=True, verbose_name="용법용량문서URL")
    nb_doc_url = models.URLField(max_length=500, blank=True, null=True, verbose_name="주의사항문서URL")
    
    # 메타 데이터
    item_image = models.URLField(max_length=500, blank=True, null=True, verbose_name="제품이미지URL")
    source_updated_at = models.DateField(null=True, blank=True, verbose_name="식약처수정일")
    last_synced_at = models.DateTimeField(auto_now=True, verbose_name="시스템동기화일")

    class Meta:
        db_table = 'eyak_info'
        verbose_name = "의약품 상세 정보"
        verbose_name_plural = "의약품 상세 정보 목록"

# 1.5. 의약품 제품 허가 정보 (검색용)
class DrugPermitInfo(models.Model):
    item_seq = models.CharField(max_length=50, primary_key=True, verbose_name="품목기준코드")
    item_name = models.TextField(verbose_name="제품명")
    item_eng_name = models.TextField(blank=True, null=True, verbose_name="제품명(영문)")
    entp_name = models.CharField(max_length=255, blank=True, null=True, verbose_name="업체명")
    main_ingr_name = models.TextField(blank=True, null=True, verbose_name="주성분")
    etc_otcc_name = models.CharField(max_length=50, blank=True, null=True, verbose_name="전문/일반")
    # valid_term = models.TextField(blank=True, null=True, verbose_name="유효기한") # 스크린샷에 안 보임, 안전을 위해 주석 처리
    
    class Meta:
        db_table = 'drug_permit_info'
        managed = False  # 이미 존재하는 테이블이라고 가정
        verbose_name = "의약품 허가 정보"
        verbose_name_plural = "의약품 허가 정보 목록"

# 2. DUR 통합 마스터 테이블 (기존 유지)
class DurMaster(models.Model):
    dur_type = models.CharField(max_length=50, db_index=True, verbose_name="금기유형")
    ingr_code = models.CharField(max_length=20, db_index=True, verbose_name="성분코드")
    ingr_eng_name = models.CharField(max_length=255, db_index=True, verbose_name="성분명(영문)")
    ingr_kor_name = models.CharField(max_length=255, verbose_name="성분명(국문)")
    critical_value = models.CharField(max_length=255, blank=True, null=True, verbose_name="핵심주의값")
    prohbt_content = models.TextField(blank=True, null=True, verbose_name="금기내용")
    remark = models.TextField(blank=True, null=True, verbose_name="비고")
    class_name = models.CharField(max_length=255, blank=True, null=True, verbose_name="효능군/계열")
    notification_date = models.DateField(null=True, blank=True, verbose_name="공고일자")
    last_synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'dur_master'
        unique_together = ('dur_type', 'ingr_code', 'critical_value')

# 3. 사용자 건강 정보 프로필
from django.contrib.auth.models import User

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile', verbose_name="사용자")
    current_medications = models.TextField(blank=True, null=True, verbose_name="복용 중인 약")
    allergies = models.TextField(blank=True, null=True, verbose_name="알러지")
    chronic_diseases = models.TextField(blank=True, null=True, verbose_name="기저질환")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="수정일")

    class Meta:
        db_table = 'user_profile'
        verbose_name = "사용자 프로필"
        verbose_name_plural = "사용자 프로필 목록"
