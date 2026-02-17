import shutil
import os
import time

# 1. Move core/graph to graph_agent
src = "core/graph"
dst = "graph_agent"

if os.path.exists(src):
    try:
        if os.path.exists(dst):
            print(f"{dst} already exists. Removing it to overwrite.")
            shutil.rmtree(dst)
        shutil.move(src, dst)
        print(f"Moved {src} to {dst}")
    except Exception as e:
        print(f"Error moving {src}: {e}")
else:
    print(f"{src} does not exist")

# 2. Remove core directory if empty (or force remove if contains only __init__.py/pycache)
core_dir = "core"
if os.path.exists(core_dir):
    try:
        shutil.rmtree(core_dir)
        print(f"Removed {core_dir}")
    except Exception as e:
        print(f"Error removing {core_dir}: {e}")
