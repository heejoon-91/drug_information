
import os

target_dir = "/Users/kh_xj/Desktop/4th-project/api_fastapi/prompts"
files_to_check = ["system_prompts.py", "answer_prompts.py"]

print(f"--- Checking directory: {target_dir} ---")
if os.path.exists(target_dir):
    print("Directory exists.")
    files = os.listdir(target_dir)
    print(f"Files in directory: {files}")
    
    for fname in files_to_check:
        fpath = os.path.join(target_dir, fname)
        if os.path.exists(fpath):
            print(f"\n[FOUND] {fname}")
            with open(fpath, 'r', encoding='utf-8') as f:
                print(f"--- Content Preview ({fname}) ---")
                print(f.read()[:100] + "...")
        else:
            print(f"\n[MISSING] {fname}")
else:
    print("Directory DOES NOT exist.")
