import os
import sys
import django

# 1. Django 환경 설정
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend_django')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from drugs.models import DurMaster
from supabase import create_client, Client

# 2. Supabase 연결 설정
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

def sync_data():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("Error: SUPABASE_URL 또는 SUPABASE_KEY 환경변수가 설정되지 않았습니다.")
        return

    print("--- [START] Supabase 데이터 동기화 시작 ---")

    # 3. 로컬 데이터 조회
    print("1. 로컬 DB에서 데이터 조회 중...")
    local_data = list(DurMaster.objects.all().values())
    total_count = len(local_data)
    print(f"   - 총 {total_count}건의 데이터를 발견했습니다.")

    if total_count == 0:
        print("   - 동기화할 데이터가 없습니다.")
        return

    # 4. Supabase 클라이언트 연결
    print("2. Supabase 연결 및 데이터 삽입 시작...")
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    # 5. 배치 처리 (한 번에 500건씩)
    batch_size = 500
    for i in range(0, total_count, batch_size):
        batch = local_data[i:i + batch_size]

        rows = []
        for item in batch:
            rows.append({
                'dur_seq':                item.get('dur_seq'),
                'dur_type':               item.get('dur_type'),
                'type_name':              item.get('type_name'),
                'ingr_code':              item.get('ingr_code'),
                'ingr_kor_name':          item.get('ingr_kor_name'),
                'ingr_eng_name':          item.get('ingr_eng_name'),
                'form_name':              item.get('form_name'),
                'mix_type':               item.get('mix_type'),
                'mix_ingr':               item.get('mix_ingr'),
                'ori_ingr':               item.get('ori_ingr'),
                'mixture_ingr_code':      item.get('mixture_ingr_code'),
                'mixture_ingr_kor_name':  item.get('mixture_ingr_kor_name'),
                'mixture_ingr_eng_name':  item.get('mixture_ingr_eng_name'),
                'mixture_mix_type':       item.get('mixture_mix_type'),
                'mixture_class':          item.get('mixture_class'),
                'mixture_ori':            item.get('mixture_ori'),
                'grade':                  item.get('grade'),
                'max_qty':                item.get('max_qty'),
                'max_dosage_term':        item.get('max_dosage_term'),
                'age_base':               item.get('age_base'),
                'effect_code':            item.get('effect_code'),
                'sers_name':              item.get('sers_name'),
                'critical_value':         item.get('critical_value'),
                'prohbt_content':         item.get('prohbt_content'),
                'remark':                 item.get('remark'),
                'class_name':             item.get('class_name'),
                'notification_date':      str(item.get('notification_date')) if item.get('notification_date') else None,
                'del_yn':                 item.get('del_yn'),
            })

        try:
            supabase.table('dur_master').insert(rows).execute()
            print(f"   - {min(i + batch_size, total_count)}/{total_count}건 저장 완료...")
        except Exception as e:
            print(f"   ! 배치 저장 실패 ({i}~{i+batch_size}): {e}")

    print("--- [FINISH] 동기화 완료 ---")

if __name__ == "__main__":
    sync_data()
