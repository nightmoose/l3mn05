import os
import subprocess
    			
def write_file(repo_path, file_path, content):
    full_path = os.path.join(repo_path, file_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    try:
        with open(full_path, 'w') as f:
            f.write(content)
        subprocess.run(["git", "-C", repo_path, "add", file_path], check=True)
        return True
    except Exception as e:
        print(f"[{datetime.now()}] [FILE] Write error: {e}")
        return False