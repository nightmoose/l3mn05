import os
import yaml
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
config_path = os.path.join(project_root, "config.yaml")

with open(config_path) as f:
    config = yaml.safe_load(f)
LOCAL_MODEL = config.get("local_model", "qwen2.5-coder:14b")

# NEW: Define WORKSPACE from config (fixes potential NameError)
WORKSPACE = config.get("workspace", "/workspace")


def get_agent_output_path(key: str, agent_role_key: str, topic: str = "", config=None) -> str:
    if config is None:
        with open("config.yaml") as f:
            config = yaml.safe_load(f)
    
    cfg = config["agents"].get(agent_role_key, {})
    folder = cfg.get("folder", "output")
    suffix = cfg.get("filename_suffix", agent_role_key)
    ext = cfg.get("extension", ".md")
    
    # Simple slug: lower, replace non-alphanum with -, strip extras
    import re
    topic_slug = re.sub(r'[^a-z0-9]+', '-', topic.lower()).strip('-')[:60]
    
    filename = f"{key.lower()}-{suffix}"
    if topic_slug:
        filename += f"-{topic_slug}"
    filename += ext
    
    return f"{folder}/{filename}"