import asyncio
import time
import os
import sys
import django
from dotenv import load_dotenv

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(os.path.join(project_root, 'backend_django'))
load_dotenv(os.path.join(project_root, '.env'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from services.drug_service import DrugService
from services.supabase_service import SupabaseService

# Supabase 패치 적용 (메인과 동일한 환경 구성)
DrugService.get_dur_by_ingr = SupabaseService.get_dur_by_ingr
DrugService.get_enriched_dur_info = SupabaseService.get_enriched_dur_info

from graph_agent import nodes as nodes_v1
from graph_agent import nodes_v2

async def measure(nodes_module, query: str, version: str):
    print(f"\n=============================================")
    print(f"[{version}] 실행 시작 (질문: '{query}')")
    print(f"=============================================")
    state = {"query": query, "user_profile": {}}
    
    start_total = time.time()
    
    # 1. Classify
    t0 = time.time()
    res = await nodes_module.classify_node(state)
    state.update(res)
    t1 = time.time()
    t_classify = t1 - t0
    print(f"[{version}] 1. 의도 분류 (classify_node)     : {t_classify:.2f} 초")
    
    # 2. Retrieve FDA
    t0 = time.time()
    res = await nodes_module.retrieve_fda_node(state)
    state.update(res)
    t1 = time.time()
    t_fda = t1 - t0
    print(f"[{version}] 2. FDA 조회 (retrieve_fda_node)  : {t_fda:.2f} 초")
    
    # 3. Retrieve DUR
    t0 = time.time()
    res = await nodes_module.retrieve_dur_node(state)
    state.update(res)
    t1 = time.time()
    t_dur = t1 - t0
    print(f"[{version}] 3. DUR 조회 (retrieve_dur_node)  : {t_dur:.2f} 초")
    
    # 4. Generate Answer
    t0 = time.time()
    if category := state.get("category"):
        if category == "symptom_recommendation":
            res = await nodes_module.generate_symptom_answer_node(state)
        elif category == "product_request":
            res = await nodes_module.generate_product_answer_node(state)
        else:
            res = await nodes_module.generate_general_answer_node(state)
        state.update(res)
    t1 = time.time()
    t_ans = t1 - t0
    print(f"[{version}] 4. 답변 생성 (generate_answer)   : {t_ans:.2f} 초")
    
    total = time.time() - start_total
    print(f"---------------------------------------------")
    print(f"[{version}] 체감 응답 속도(총 소요 시간)     : {total:.2f} 초")
    print(f"=============================================\n")
    return t_classify, t_fda, t_dur, t_ans, total

async def main():
    query = "머리가 아파요"
    
    # Warm-up (초기 커넥션 등에 의한 속도 저하 방지)
    import httpx
    # 실제 비교
    v1_times = await measure(nodes_v1, query, "V1_기존")
    v2_times = await measure(nodes_v2, query, "V2_최적화")
    
    diff = v1_times[4] - v2_times[4]
    accel = (v1_times[4] / v2_times[4]) if v2_times[4] > 0 else 0
    
    print(f"🚀 [결과 요약]")
    print(f"- 생성단계(Generate) 소요 시간: {v1_times[3]:.2f}초 -> {v2_times[3]:.2f}초 (▼ {v1_times[3]-v2_times[3]:.2f}초 단축)")
    print(f"- 총 응답 파이프라인 단축: {diff:.2f}초 개선 (약 {accel:.1f}배 속도 향상)")

if __name__ == "__main__":
    asyncio.run(main())
