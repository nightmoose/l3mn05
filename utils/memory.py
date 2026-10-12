# utils/memory.py
import os
import json
from datetime import datetime

def load_memory(output_path):
    path = os.path.join(output_path, "memory.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[MEMORY] Load failed: {e}")
    return {}

# In utils/memory.py — update save_memory
def save_memory(output_path, memory_dict, repo_full=None):
    path = os.path.join(output_path, "memory.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(memory_dict, f, indent=2, ensure_ascii=False)
        print(f"[MEMORY] Updated {path}")
        
        # Do NOT import git here. Let the orchestrator/tool handle committing.
        # If you want auto-commit, call execute_tool("git_commit_push", ...) from orchestrators instead.
    except Exception as e:
        print(f"[MEMORY] Save failed: {e}")