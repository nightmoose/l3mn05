from utils.config import (
    get_local_model,
    get_ollama_base_url,
    load_config,
    reset_config_cache,
)


def test_missing_config_is_empty(monkeypatch):
    monkeypatch.setenv("L3MN05_CONFIG", "/tmp/l3mn05-definitely-missing.yaml")
    reset_config_cache()
    assert load_config() == {}


def test_config_file_is_read(monkeypatch, tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("local_model: test-model\nworkspace: /tmp/ws\n", encoding="utf-8")
    monkeypatch.setenv("L3MN05_CONFIG", str(path))
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    monkeypatch.delenv("L3MN05_WORKSPACE", raising=False)
    reset_config_cache()
    assert load_config()["local_model"] == "test-model"
    assert get_local_model() == "test-model"
    from utils.config import get_workspace
    assert get_workspace() == "/tmp/ws"


def test_ollama_url_env_overrides_and_adds_v1(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")
    reset_config_cache()
    assert get_ollama_base_url() == "http://ollama:11434/v1"


def test_ollama_url_keeps_existing_v1(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1")
    assert get_ollama_base_url() == "http://127.0.0.1:11434/v1"


def test_ollama_url_from_config_when_env_unset(monkeypatch, tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text('ollama_base_url: "http://127.0.0.1:11434/v1"\n', encoding="utf-8")
    monkeypatch.setenv("L3MN05_CONFIG", str(path))
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    reset_config_cache()
    assert get_ollama_base_url() == "http://127.0.0.1:11434/v1"


def test_default_ollama_url_is_localhost(monkeypatch):
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.setenv("L3MN05_CONFIG", "/tmp/l3mn05-definitely-missing.yaml")
    reset_config_cache()
    assert get_ollama_base_url() == "http://127.0.0.1:11434/v1"


def test_model_env_overrides_config(monkeypatch, tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("local_model: from-file\n", encoding="utf-8")
    monkeypatch.setenv("L3MN05_CONFIG", str(path))
    monkeypatch.setenv("OLLAMA_MODEL", "from-env")
    reset_config_cache()
    assert get_local_model() == "from-env"


def test_offline_flag_from_config_and_env(monkeypatch, tmp_path):
    from utils.offline import is_offline
    path = tmp_path / "config.yaml"
    path.write_text("offline: true\n", encoding="utf-8")
    monkeypatch.setenv("L3MN05_CONFIG", str(path))
    monkeypatch.delenv("L3MN05_OFFLINE", raising=False)
    reset_config_cache()
    assert is_offline() is True

    monkeypatch.setenv("L3MN05_OFFLINE", "0")
    assert is_offline() is False

    monkeypatch.setenv("L3MN05_OFFLINE", "1")
    path.write_text("offline: false\n", encoding="utf-8")
    reset_config_cache()
    assert is_offline() is True
