import os
import sys
import django
from supabase import create_client, Client
from tqdm import tqdm
from datetime import date, datetime

# Django Setup
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend_django')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from drugs.models import DrugPermitInfo, DurMaster, UserProfile, EYakInfo, UnifiedDrugInfo

def get_supabase_client() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        print("Error: SUPABASE_URL and SUPABASE_KEY must be set in .env")
        sys.exit(1)
    return create_client(url, key)

def sync_model(client: Client, model, table_name, batch_size=1000):
    print(f"Starting sync for {table_name}...")
    
    queryset = model.objects.all()
    total_count = queryset.count()
    
    if total_count == 0:
        print(f"No data found in {table_name}. Skipping.")
        return

    print(f"Found {total_count} records in {table_name}.")
    
    # Process in batches
    objects = []
    
    # Using iterator to avoid memory issues with large datasets
    for obj in tqdm(queryset.iterator(), total=total_count, desc=f"Syncing {table_name}"):
        # Convert model instance to dict
        data = {}
        for field in model._meta.fields:
            value = getattr(obj, field.name)
            # Handle date/datetime serialization
            if value is not None:
                 if isinstance(value, (date, datetime)):
                     data[field.name] = value.isoformat()
                 else:
                     data[field.name] = value
        
        objects.append(data)
        
        if len(objects) >= batch_size:
            try:
                # upsert: insert or update on conflict (usually primary key)
                client.table(table_name).upsert(objects).execute()
                objects = []
            except Exception as e:
                print(f"Error syncing batch to {table_name}: {e}")
                # Optional: break or continue? continue for now
    
    # Sync remaining
    if objects:
        try:
            client.table(table_name).upsert(objects).execute()
        except Exception as e:
            print(f"Error syncing final batch to {table_name}: {e}")

    print(f"Finished sync for {table_name}.\n")

if __name__ == "__main__":
    supabase = get_supabase_client()
    
    # Map Models to Supabase Tables
    # Ensure table names in Supabase match these
    sync_tasks = [
        # (DrugPermitInfo, "drug_permit_info"),
        # (DurMaster, "dur_master"),
        # (EYakInfo, "eyak_info"),
        (UnifiedDrugInfo, "unified_drug_info"),
    ]
    
    for model, table_name in sync_tasks:
        sync_model(supabase, model, table_name)
