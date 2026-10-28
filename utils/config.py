"""Lazy configuration.

Importing this module does not open config.yaml. The file is read the first
time a caller asks for a value. A missing file is an empty config, not an
import error.

Overrides:
  L3MN05_CONFIG       path to the yaml file (default: <repo>/config.yaml)
  L3MN05_WORKSPACE    workspace directory
  OLLAMA_BASE_URL     OpenAI-compatible base URL of the local model server
  OLLAMA_MODEL        model name passed to that server
"""

import os
from typing import Any, Optional
from urllib.parse import urlparse, urlunparse

import yaml
from dotenv import load_dotenv

load_dotenv()

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_cache: Optional[dict] = None
_cache_path: Optional[str] = None


def project_root() -> str:
    return _PROJECT_ROOT


def config_file_path() -> str:
    override = os.getenv("L3MN05_CONFIG")
    if override:
        return override
    return os.path.join(_PROJECT_ROOT, "config.yaml")


def load_config(*, reload: bool = False) -> dict:
    """Return the config mapping. Missing file → {}."""
    global _cache, _cache_path
    path = config_file_path()
    if not reload and _cache is not None and _cache_path == path:
        return _cache
    data: dict[str, Any] = {}
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"Config at {path} must be a mapping")
        data = loaded
    _cache = data
    _cache_path = path
    return data


def reset_config_cache() -> None:
    global _cache, _cache_path
    _cache = None
    _cache_path = None


class ConfigView:
    """Mapping facade. Reads config.yaml on use, not at import."""

    def _data(self) -> dict:
        return load_config()

    def get(self, key, default=None):
        return self._data().get(key, default)

    def __getitem__(self, key):
        return self._data()[key]

    def __contains__(self, key):
        return key in self._data()

    def __iter__(self):
        return iter(self._data())

    def __bool__(self):
        return bool(self._data())

    def __len__(self):
        return len(self._data())

    def keys(self):
        return self._data().keys()

    def items(self):
        return self._data().items()

    def values(self):
        return self._data().values()


config = ConfigView()


def get_workspace() -> str:
    return os.getenv("L3MN05_WORKSPACE") or load_config().get("workspace") or "/workspace"


def get_local_model() -> str:
    return os.getenv("OLLAMA_MODEL") or load_config().get("local_model") or "qwen2.5-coder:14b"


def get_ollama_base_url() -> str:
    """Local model URL. Env wins, then config, then localhost (not the Docker hostname)."""
    raw = (
        os.getenv("OLLAMA_BASE_URL")
        or load_config().get("ollama_base_url")
        or "http://127.0.0.1:11434/v1"
    )
    raw = str(raw).strip()
    if "://" not in raw:
        raw = "http://" + raw
    parsed = urlparse(raw)
    path = (parsed.path or "").rstrip("/")
    if path in ("", "/"):
        path = "/v1"
    return urlunparse(parsed._replace(path=path))


def get_ollama_host() -> Optional[str]:
    host = urlparse(get_ollama_base_url()).hostname
    return host.lower() if host else None


def get_agent_output_path(key: str, agent_role_key: str, topic: str = "", config=None) -> str:
    if config is None:
        config = load_config()

    cfg = config.get("agents", {}).get(agent_role_key, {})
    folder = cfg.get("folder", "output")
    suffix = cfg.get("filename_suffix", agent_role_key)
    ext = cfg.get("extension", ".md")

    import re
    topic_slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")[:60]

    filename = f"{key.lower()}-{suffix}"
    if topic_slug:
        filename += f"-{topic_slug}"
    filename += ext

    return f"{folder}/{filename}"


def __getattr__(name):
    # Backward compatible for `from utils.config import WORKSPACE`.
    # The value is resolved at attribute access. Call get_workspace() if you
    # need it to follow later config changes.
    if name == "WORKSPACE":
        return get_workspace()
    if name == "LOCAL_MODEL":
        return get_local_model()
    if name == "config_path":
        return config_file_path()
    raise AttributeError(f"module 'utils.config' has no attribute {name}")
