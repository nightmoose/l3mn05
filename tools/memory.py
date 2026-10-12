import os
import json
from datetime import datetime
from tools.git import git_commit_push

def load_memory(output_path):
    path = os.path.join(output_path, "memory.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[MEMORY] Load failed: {e}")
    return {}

def save_memory(output_path, memory_dict, repo_full=None):
    path = os.path.join(output_path, "memory.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(memory_dict, f, indent=2, ensure_ascii=False)
        print(f"[MEMORY] Updated {path}")
        git_commit_push(output_path, "Updated memory.json after step", repo_full)
    except Exception as e:
        print(f"[MEMORY] Save failed: {e}")
