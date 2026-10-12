# tools/git.py
import os
import subprocess
import yaml
from datetime import datetime
from utils.config import WORKSPACE

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

def git_commit_push(repo_path, message, repo_full=None):
    try:
        # Stage all changes
        subprocess.run(["git", "-C", repo_path, "add", "."], check=True, capture_output=True, text=True)

        # Commit (allow empty if no changes)
        commit_result = subprocess.run(
            ["git", "-C", repo_path, "commit", "-m", message, "--allow-empty"],
            capture_output=True, text=True, check=False
        )
        if commit_result.returncode != 0:
            if "nothing to commit" in commit_result.stderr.lower():
                print(f"[{datetime.now()}] [GIT] No changes to commit (ok)")
                return True
            print(f"[{datetime.now()}] [GIT] Commit failed: {commit_result.stderr.strip()}")
            return False

        # Authenticated remote if provided
        if repo_full and GITHUB_TOKEN:
            token_url = f"https://{GITHUB_TOKEN}@github.com/{repo_full}.git"
            subprocess.run(
                ["git", "-C", repo_path, "remote", "set-url", "origin", token_url],
                check=False
            )

        # Try normal push first
        push_cmd = ["git", "-C", repo_path, "push", "--force-with-lease", "-u", "origin", "HEAD"]
        push_result = subprocess.run(push_cmd, capture_output=True, text=True, check=False)

        if push_result.returncode == 0:
            print(f"[{datetime.now()}] [GIT] ✅ Pushed: {message}")
            return True

        # If rejected (stale), automatically pull --rebase and retry once
        if "stale info" in push_result.stderr or "non-fast-forward" in push_result.stderr:
            print(f"[{datetime.now()}] [GIT] Push rejected (stale) — attempting pull --rebase")
            rebase_result = subprocess.run(
                ["git", "-C", repo_path, "pull", "--rebase", "origin", "HEAD"],
                capture_output=True, text=True, check=False
            )
            if rebase_result.returncode != 0:
                print(f"[{datetime.now()}] [GIT] Rebase failed: {rebase_result.stderr.strip()}")
                # Optional: fall back to force push if desperate (risky!)
                # subprocess.run(["git", "-C", repo_path, "push", "--force", "origin", "HEAD"], check=False)
                return False

            # Retry push after rebase
            push_result = subprocess.run(push_cmd, capture_output=True, text=True, check=False)
            if push_result.returncode == 0:
                print(f"[{datetime.now()}] [GIT] ✅ Pushed after rebase: {message}")
                return True

        print(f"[{datetime.now()}] [GIT] Push failed after retry: {push_result.stderr.strip()}")
        return False

    except Exception as e:
        print(f"[{datetime.now()}] [GIT] Commit/push error: {str(e)}")
        return False

def get_repo_paths(client, config=None):
    context_full = client.get("default_repo") or client.get("context_repo")
    output_full = client.get("output_repo") or context_full
    if not context_full:
        raise ValueError(f"Client missing default_repo or context_repo")
    context_slug = context_full.split('/')[-1]
    output_slug = output_full.split('/')[-1]
    return context_full, output_full, os.path.join(WORKSPACE, context_slug), os.path.join(WORKSPACE, output_slug)

def ensure_git_repo(repo_full):
    repo_slug = repo_full.split('/')[-1]
    repo_path = os.path.join(WORKSPACE, repo_slug)
    os.makedirs(repo_path, exist_ok=True)
    if not os.path.exists(os.path.join(repo_path, ".git")):
        print(f"[{datetime.now()}] [GIT] Repo not found. Cloning {repo_full}...")
        clone_url = f"https://{GITHUB_TOKEN}@github.com/{repo_full}.git" if GITHUB_TOKEN else f"https://github.com/{repo_full}.git"
        try:
            subprocess.run(["git", "clone", "--depth", "1", clone_url, repo_path], check=True, capture_output=True, text=True)
            print(f"[{datetime.now()}] [GIT] Cloned successfully")
            return True
        except Exception as e:
            print(f"[{datetime.now()}] [GIT] Clone failed (will init empty): {e}")
            try:
                subprocess.run(["git", "init", repo_path], check=True)
                subprocess.run(["git", "-C", repo_path, "remote", "add", "origin", clone_url], check=True)
                print(f"[{datetime.now()}] [GIT] Empty repo initialized")
                return True
            except Exception as e2:
                print(f"[{datetime.now()}] [GIT] Setup failed: {e2}")
                return False
    return True

def gather_repo_context(repo_path):
    """Load config and guidelines from the actual repo path (was fragile relative open)."""
    context = []
    
    # FIXED: Use full path based on WORKSPACE instead of open("config.yaml")
    # This prevents crashes when cwd != project root. Falls back gracefully.
    config_path = os.path.join(os.path.dirname(WORKSPACE), "config.yaml")  # config.yaml lives next to the workspace dir
    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
    except (FileNotFoundError, OSError):
        config = {}  # safe default - never crashes

    guidelines_path = os.path.join(repo_path, "horace_style.md")
    if os.path.exists(guidelines_path):
        try:
            with open(guidelines_path, 'r', encoding='utf-8') as f:
                content = f.read()[:800]
            context.append(f"HOUSE STYLE GUIDE (client override):\n{content}\n---")
        except:
            pass
    else:
        default = config.get("default_guidelines", "Use standard best practices.")
        context.append(f"HOUSE STYLE GUIDE (default):\n{default}\n---")

    files_read = 0
    for root, dirs, files in os.walk(repo_path):
        if '.git' in dirs:
            dirs.remove('.git')
        for file in files:
            if files_read >= 10:
                break
            if file.endswith(('.py', '.html', '.css', '.sql', '.md', '.js', '.gitignore', 'README.md', '.yaml', '.yml')):
                full_path = os.path.join(root, file)
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        content = f.read()[:500]
                    context.append(f"File: {file}\n{content}\n---")
                    files_read += 1
                except:
                    pass
    if not context:
        return "No guidelines or repo found. Use clean, modern, readable code with type hints and comments."
    summary = "Existing repo context and style guidelines:\n" + "\n".join(context)[:1500]
    summary += "\nFollow the house style guide first, then adapt to the client repo patterns."
    return summary

def reset_to_clean_main(repo_path):
    try:
        print(f"[{datetime.now()}] [GIT] Resetting to clean main...")
        subprocess.run(["git", "-C", repo_path, "checkout", "main"], check=True, capture_output=True, text=True)
        subprocess.run(["git", "-C", repo_path, "pull", "origin", "main"], check=True, capture_output=True, text=True)
        subprocess.run(["git", "-C", repo_path, "reset", "--hard", "origin/main"], check=True, capture_output=True, text=True)
        subprocess.run(["git", "-C", repo_path, "clean", "-fd"], check=False, capture_output=True, text=True)
        print(f"[{datetime.now()}] [GIT] ✅ Blank slate ready")
        return True
    except Exception as e:
        print(f"[{datetime.now()}] [GIT] Reset warning (continuing): {e}")
        return False

def create_branch(repo_path, branch_name):
    try:
        subprocess.run(["git", "-C", repo_path, "checkout", "-B", branch_name], check=True, capture_output=True, text=True)
        print(f"[{datetime.now()}] [GIT] Branch {branch_name} created")
        return branch_name
    except Exception as e:
        print(f"[{datetime.now()}] [GIT] Branch error: {e}")
        return None

def create_pr(repo_path, key, summary, branch_name):
    try:
        title = f"L3MN05 {key}: {summary[:80]}"
        body = f"Automated by L3MN05 Done Worker.\nJira: {key}\nBranch: {branch_name}"
        result = subprocess.run(["gh", "pr", "create", "--head", branch_name, "--title", title, "--body", body], cwd=repo_path, capture_output=True, text=True, check=True, env=os.environ.copy())
        print(f"[{datetime.now()}] [PR] Created → {result.stdout.strip()}")
        return True
    except Exception as e:
        if "already exists" in str(e).lower():
            print(f"[{datetime.now()}] [PR] Already exists (ok)")
            return True
        print(f"[{datetime.now()}] [PR] Skipped: {e}")
        return False
    
def refresh_repo_context(repo_path):
    """Long-term solution: Re-scan the entire output repo after each agent.
    Later agents now see what previous agents wrote."""
    context = []
    files_read = 0
    for root, dirs, files in os.walk(repo_path):
        if '.git' in dirs:
            dirs.remove('.git')
        for file in files:
            if files_read >= 15:  # limit to avoid token explosion
                break
            if file.endswith(('.md', '.py', '.sql', '.yml', '.yaml', '.json')):
                full_path = os.path.join(root, file)
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        content = f.read()[:800]
                    context.append(f"File: {full_path}\n{content}\n---")
                    files_read += 1
                except:
                    pass
    summary = "Updated repo context after previous agents:\n" + "\n".join(context)[:3000]
    print(f"[{datetime.now()}] [REFRESH] Repo context refreshed ({files_read} files, {len(summary)} chars)")
    return summary