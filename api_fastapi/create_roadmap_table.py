import os
from supabase import create_client

def create_table():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    
    if not url or not key:
        print("Please set SUPABASE_URL and SUPABASE_KEY environment variables.")
        return

    client = create_client(url, key)
    
    # Supabase Python client does not support DDL execution directly through the REST API.
    # We must use Postgres function (RPC) or the SQL Editor in the web UI.
    # However, since we cannot click the UI, we'll try to insert a dummy row. 
    # If the table doesn't exist, this script will fail, indicating manual UI creation is needed.

    try:
        res = client.table("roadmap_cache").select("*").limit(1).execute()
        print("Table 'roadmap_cache' already exists.")
    except Exception as e:
        print(f"Table might not exist: {e}")
        print("Attempting to call an RPC 'execute_sql' to create table. Please ensure the function exists.")
        
        sql = """
        CREATE TABLE IF NOT EXISTS public.roadmap_cache (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            query_text TEXT NOT NULL UNIQUE,     
            mapping_result JSONB,               
            pharmacist_card JSONB,              
            dosage_warnings JSONB,              
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_roadmap_cache_query ON public.roadmap_cache (query_text);
        """
        try:
            client.rpc("execute_sql", {"sql": sql}).execute()
            print("Table created via RPC.")
        except Exception as rpc_err:
            print(f"RPC failed: {rpc_err}")
            print("To proceed, you MUST create the 'roadmap_cache' table manually via the Supabase SQL editor.")
            print(sql)

if __name__ == "__main__":
    create_table()
