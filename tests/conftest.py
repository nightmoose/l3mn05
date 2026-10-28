"""Keep smoke tests independent of a developer config.yaml or .env switch."""

import os

os.environ["L3MN05_CONFIG"] = "/tmp/l3mn05-missing-config.yaml"
os.environ.pop("L3MN05_OFFLINE", None)
os.environ.pop("OLLAMA_BASE_URL", None)
os.environ.pop("OLLAMA_MODEL", None)

import pytest


@pytest.fixture(autouse=True)
def _reset_config_cache():
    from utils.config import reset_config_cache
    reset_config_cache()
    yield
    reset_config_cache()
