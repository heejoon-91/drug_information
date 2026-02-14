import os
import django
import requests
import time
from datetime import datetime
from urllib.parse import unquote
import json

# 1. Django 환경 설정
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from drugs.models import DurMaster

class DurUnifiedCollector:
    def __init__(self):
        # .env에서 API 키 로드 및 디코딩 처리
        raw_key = os.getenv('KR_API_KEY')
        self.service_key = unquote(raw_key) if raw_key else ""
        
        # [확정] 성분 기반 최신 API 서비스 주소
        self.base_url = "https://apis.data.go.kr/1471000/DURIrdntInfoService03"
        
        # 각 카테고리별 엔드포인트 및 매핑 필드 정의
        self.api_configs = {
            'getUsjntTabooInfoList02': {'type': 'COMBINED', 'val_key': 'MIXTURE_INGR_KOR_NAME'},
            'getPwnmTabooInfoList02': {'type': 'PREGNANCY', 'val_key': 'GRADE'},
            'getCpctyAtentInfoList02': {'type': 'MAX_CAPACITY', 'val_key': 'MAX_QTY'},
            'getMdctnPdAtentInfoList02': {'type': 'DURATION', 'val_key': 'MAX_DOSAGE_TERM'},
            'getOdsnAtentInfoList02': {'type': 'ELDERLY', 'val_key': None},
            'getSpcifyAgrdeTabooInfoList02': {'type': 'AGE_LIMIT', 'val_key': 'AGE_BASE'},
            'getEfcyDplctInfoList02': {'type': 'EFFICACY_DUPLICATE', 'val_key': 'SERS_NAME'},
        }

    def format_date(self, date_str):
        """YYYYMMDD -> Date 객체 변환"""
        if date_str and len(str(date_str)) == 8:
            try:
                return datetime.strptime(str(date_str), '%Y%m%d').date()
            except: return None
        return None

    def collect_all(self, pages_per_api=5):
        """모든 DUR API를 순회하며 데이터 수집"""
        print(f"--- [START] DUR 통합 데이터 수집 시작 (대상: {len(self.api_configs)}개) ---")
        
        for api_path, config in self.api_configs.items():
            print(f"\n>>> [{config['type']}] 카테고리 진행 중...")
            
            for page in range(1, pages_per_api + 1):
                # JSON 요청 파라미터 포함
                full_url = f"{self.base_url}/{api_path}?serviceKey={self.service_key}&pageNo={page}&numOfRows=100&type=json"
                
                try:
                    response = requests.get(full_url, timeout=15)
                    if response.status_code != 200:
                        print(f"   ! 서버 응답 에러: {response.status_code}")
                        continue

                    data = response.json()
                    
                    # [핵심 교정] body -> items(리스트) -> 요소내 item(딕셔너리) 접근
                    items_list = data.get('body', {}).get('items', [])
                    
                    if not items_list:
                        print(f"   - {page}페이지: 데이터가 더 이상 없습니다.")
                        break

                    success_in_page = 0
                    for wrapper in items_list:
                        # 리스트의 요소가 {"item": {...}} 형태이므로 실제 데이터 본체 추출
                        item = wrapper.get('item') if isinstance(wrapper, dict) else wrapper
                        
                        if not item:
                            continue

                        # 성분 코드 추출
                        ingr_code = item.get('INGR_CODE') or item.get('ingrCode')
                        if not ingr_code:
                            continue

                        # 카테고리별 핵심 수치(Value) 매핑
                        v_key = config['val_key']
                        critical_val = item.get(v_key) if v_key else "대상주의"
                        
                        # DB 저장 (Update or Create)
                        DurMaster.objects.update_or_create(
                            dur_type=config['type'],
                            ingr_code=ingr_code,
                            critical_value=str(critical_val) if critical_val else "주의",
                            defaults={
                                'ingr_eng_name': (item.get('INGR_ENG_NAME') or '').lower().strip(),
                                'ingr_kor_name': item.get('INGR_KOR_NAME') or item.get('ingrName') or '이름없음',
                                'prohbt_content': item.get('PROHBT_CONTENT') or item.get('prohbtContent') or '',
                                'remark': item.get('REMARK') or item.get('remark') or '',
                                'class_name': item.get('CLASS_NAME') or item.get('className') or '',
                                'notification_date': self.format_date(item.get('NOTIFICATION_DATE') or item.get('notificationDate'))
                            }
                        )
                        success_in_page += 1
                    
                    print(f"   - {page}페이지 완료 ({success_in_page}건 저장)")
                    time.sleep(0.3) # API 서버 부하 방지

                except Exception as e:
                    print(f"   ! 에러 발생 ({config['type']}, Page {page}): {str(e)}")
                    
        print("\n--- [FINISH] 모든 DUR 데이터가 성공적으로 저장되었습니다. ---")

if __name__ == "__main__":
    collector = DurUnifiedCollector()
    # 전체 수집 시 pages_per_api를 10~50 정도로 높여서 실행하세요.
    collector.collect_all(pages_per_api=5)