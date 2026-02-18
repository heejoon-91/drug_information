import os
import django
import requests
import time
from datetime import datetime
from urllib.parse import unquote

import sys

# 1. Django 환경 설정 (상위 디렉토리의 backend_django 추가)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend_django')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from drugs.models import DrugPermitInfo

class DrugEnrichmentCollector:
    def __init__(self):
        raw_key = os.getenv('KR_API_KEY')
        self.service_key = unquote(raw_key) if raw_key else ""
        self.base_url = "https://apis.data.go.kr/1471000/DrugPrdtPrmsnInfoService07"

    def format_date(self, date_str):
        if date_str and len(str(date_str)) >= 8:
            try: return datetime.strptime(str(date_str)[:8], '%Y%m%d').date()
            except: return None
        return None

    def collect_all_basic_info(self, start_page=1):
        """데이터가 끝날 때까지 모든 제품 목록 수집"""
        print(f"--- [START] 전수 데이터 수집 시작 (시작 페이지: {start_page}) ---")
        page = start_page
        
        while True:
            params = {
                'serviceKey': self.service_key,
                'pageNo': page,
                'numOfRows': 100,
                'type': 'json'
            }
            
            try:
                # 1. 제품 허가 목록 API 호출
                url = f"{self.base_url}/getDrugPrdtPrmsnInq07"
                response = requests.get(url, params=params, timeout=20)
                data = response.json()
                
                body = data.get('body', {})
                items = body.get('items', [])
                total_count = body.get('totalCount', 0)

                if not items:
                    print(f"   - {page}페이지: 데이터가 더 이상 없습니다. 수집을 종료합니다.")
                    break

                for item in items:
                    # [데이터 매핑] 대문자 키 대응
                    item_seq = item.get('ITEM_SEQ')
                    DrugPermitInfo.objects.update_or_create(
                        item_seq=item_seq,
                        defaults={
                            'item_name': item.get('ITEM_NAME'),
                            'item_eng_name': item.get('ITEM_ENG_NAME'),
                            'entp_name': item.get('ENTP_NAME'),
                            'etc_otcc_name': item.get('SPCLTY_PBLC'),
                            'main_ingr_name': item.get('ITEM_INGR_NAME'),
                            'permit_date': self.format_date(item.get('ITEM_PERMIT_DATE')),
                            'valid_term': item.get('VALID_TERM')
                        }
                    )

                print(f"   - {page}페이지 완료 (진행률: {round((page*100/total_count)*100, 2)}% / 전체 {total_count}건)")
                page += 1
                
                # API 호출 속도 조절 (일일 쿼터 및 서버 부하 고려)
                if page % 10 == 0:
                    time.sleep(1) 
                else:
                    time.sleep(0.1)

            except Exception as e:
                print(f"   ! {page}페이지 에러 발생: {e}")
                time.sleep(5) # 에러 발생 시 잠시 대기 후 재시도
                continue

        print("--- [FINISH] 모든 기본 정보 수집 완료 ---")

if __name__ == "__main__":
    collector = DrugEnrichmentCollector()
    # 11페이지부터 이어서 수집하려면 start_page=11 설정
    collector.collect_all_basic_info(start_page=11)