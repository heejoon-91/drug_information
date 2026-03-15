import pandas as pd
import asyncio
import os
import sys

# ?„ë¡œ?íŠ¸ ë£¨íŠ¸ë¥?ê²½ë¡œ??ì¶”ê? (SupabaseService ë¡œë“œ??
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from otc_info.services.supabase_service import SupabaseService

async def sync_kcd9_to_supabase(csv_path):
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found at {csv_path}")
        return

    print(f"Reading data from {csv_path}...")
    df = pd.read_csv(csv_path)
    
    # NaN ì²˜ë¦¬ (?ë¬¸ëª…ì´ ?†ëŠ” ê²½ìš° ?€ë¹?
    df = df.fillna("")
    
    data = df.to_dict(orient='records')
    total_count = len(data)
    print(f"Total records to upload: {total_count}")

    client = SupabaseService.get_client()
    table_name = "kcd_info"
    
    chunk_size = 500
    for i in range(0, total_count, chunk_size):
        chunk = data[i : i + chunk_size]
        try:
            # upsertë¥??¬ìš©?˜ì—¬ ê¸°ì¡´ ì½”ë“œê°€ ?ˆìœ¼ë©??…ë°?´íŠ¸, ?†ìœ¼ë©??½ì…
            client.table(table_name).upsert(chunk, on_conflict="kcd_code").execute()
            print(f"Progress: {min(i + chunk_size, total_count)}/{total_count} uploaded...")
        except Exception as e:
            print(f"Error at chunk {i//chunk_size}: {e}")
            break

    print("KCD 9th revision synchronization completed successfully.")

if __name__ == "__main__":
    csv_file = r"c:\codes\SKN22-4th-1Team\kcd9_classification_v3.csv"
    asyncio.run(sync_kcd9_to_supabase(csv_file))
