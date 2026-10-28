"""The offline switch must refuse real outbound calls, not only skip a helper."""

import os
import socket
import subprocess

import pytest

from utils.offline import OfflineBlocked, install_network_guard, offline_message


@pytest.fixture(autouse=True)
def _guard():
    install_network_guard()


def test_public_ip_is_blocked(monkeypatch):
    monkeypatch.setenv("L3MN05_OFFLINE", "1")
    sock = socket.socket()
    sock.settimeout(1)
    with pytest.raises(OfflineBlocked):
        sock.connect(("1.1.1.1", 443))


def test_documentation_ip_is_blocked(monkeypatch):
    monkeypatch.setenv("L3MN05_OFFLINE", "1")
    with pytest.raises(OfflineBlocked):
        socket.getaddrinfo("203.0.113.1", 443)


def test_example_com_is_blocked(monkeypatch):
    monkeypatch.setenv("L3MN05_OFFLINE", "1")
    import urllib.request
    with pytest.raises(OfflineBlocked):
        urllib.request.urlopen("http://example.com", timeout=2)


def test_httpx_to_public_host_is_blocked(monkeypatch):
    monkeypatch.setenv("L3MN05_OFFLINE", "1")
    import httpx
    with pytest.raises(OfflineBlocked):
        httpx.get("https://example.com", timeout=2)


def test_udp_send_to_public_dns_is_blocked(monkeypatch):
    monkeypatch.setenv("L3MN05_OFFLINE", "1")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        with pytest.raises(OfflineBlocked):
            sock.sendto(b"hi", ("1.1.1.1", 53))
    finally:
        sock.close()


def test_werkzeug_interface_probe_is_allowed(monkeypatch):
    """Flask logs its bind address by UDP-connecting to this fixed host."""
    monkeypatch.setenv("L3MN05_OFFLINE", "1")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("10.253.155.219", 58162))
    except OfflineBlocked:
        pytest.fail("interface probe must stay open so the chat server can start")
    finally:
        sock.close()


def test_loopback_is_not_blocked(monkeypatch):
    monkeypatch.setenv("L3MN05_OFFLINE", "1")
    sock = socket.socket()
    sock.settimeout(0.2)
    try:
        sock.connect(("127.0.0.1", 9))
    except OfflineBlocked:
        pytest.fail("loopback must stay open for the local model")
    except OSError:
        pass
    finally:
        sock.close()


def test_only_configured_model_host_is_allowed(monkeypatch):
    monkeypatch.setenv("L3MN05_OFFLINE", "1")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://10.255.255.1:11434")
    from utils.config import reset_config_cache
    from utils.offline import _check_host
    reset_config_cache()
    _check_host("10.255.255.1")
    _check_host("ollama")
    with pytest.raises(OfflineBlocked):
        _check_host("10.255.255.2")
    with pytest.raises(OfflineBlocked):
        _check_host("api.x.ai")


def test_online_mode_does_not_block_dns(monkeypatch):
    monkeypatch.setenv("L3MN05_OFFLINE", "0")
    try:
        socket.getaddrinfo("example.com", 80)
    except OfflineBlocked:
        pytest.fail("offline guard fired while L3MN05_OFFLINE=0")
    except OSError:
        pass


def test_git_push_and_gh_are_blocked(monkeypatch):
    monkeypatch.setenv("L3MN05_OFFLINE", "1")
    with pytest.raises(OfflineBlocked):
        subprocess.run(["git", "push"], check=False)
    with pytest.raises(OfflineBlocked):
        subprocess.run(["gh", "pr", "create"], check=False)
    with pytest.raises(OfflineBlocked):
        subprocess.run(["curl", "https://example.com"], check=False)


def test_git_status_is_local(monkeypatch, tmp_path):
    monkeypatch.setenv("L3MN05_OFFLINE", "1")
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    proc = subprocess.run(["git", "-C", str(tmp_path), "status"], check=True, capture_output=True, text=True)
    assert proc.returncode == 0


def test_call_llm_offline_never_calls_remote(monkeypatch):
    monkeypatch.setenv("L3MN05_OFFLINE", "1")
    from utils import llm

    monkeypatch.setattr(llm, "call_local_llm", lambda *args, **kwargs: "LOCAL-PLAN")

    def boom(*args, **kwargs):
        raise AssertionError("remote model was called")

    monkeypatch.setattr(llm, "call_remote_llm", boom)
    assert llm.call_llm("plan this", prefer_remote=True) == "LOCAL-PLAN"


def test_call_llm_offline_does_not_fall_back_when_local_is_down(monkeypatch):
    monkeypatch.setenv("L3MN05_OFFLINE", "1")
    from utils import llm

    monkeypatch.setattr(llm, "call_local_llm", lambda *args, **kwargs: None)

    def boom(*args, **kwargs):
        raise AssertionError("remote fallback was called")

    monkeypatch.setattr(llm, "call_remote_llm", boom)
    text = llm.call_llm("plan this", prefer_remote=True)
    assert text.startswith("ERROR:")
    assert "offline mode is on" in text.lower()
    assert "disabled" in text.lower()


def test_call_remote_llm_does_not_construct_client(monkeypatch):
    monkeypatch.setenv("L3MN05_OFFLINE", "1")
    from utils import llm

    def boom(*args, **kwargs):
        raise AssertionError("OpenAI client constructed")

    monkeypatch.setattr(llm, "OpenAI", boom)
    text = llm.call_remote_llm("hello")
    assert "Remote validation" in text
    assert "disabled" in text


def test_local_client_uses_env_url(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:9/v1")
    monkeypatch.setenv("OLLAMA_MODEL", "unit-test-model")
    monkeypatch.setenv("L3MN05_OFFLINE", "1")
    from utils.config import reset_config_cache
    from utils import llm
    reset_config_cache()
    llm._local_client = None
    llm._local_client_url = None
    captured = {}

    class _Msg:
        content = " hello "

    class _Choice:
        message = _Msg()

    class _Resp:
        choices = [_Choice()]

    class _Completions:
        def create(self, **kwargs):
            captured["kwargs"] = kwargs
            return _Resp()

    class _Chat:
        completions = _Completions()

    class _Client:
        def __init__(self, base_url, api_key):
            captured["base_url"] = base_url
            self.chat = _Chat()

    monkeypatch.setattr(llm, "OpenAI", _Client)
    assert llm.call_local_llm("hi") == "hello"
    assert captured["base_url"] == "http://127.0.0.1:9/v1"
    assert captured["kwargs"]["model"] == "unit-test-model"
    assert captured["kwargs"]["max_tokens"] == 2048


def test_jira_notion_git_and_pr_say_disabled(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("L3MN05_OFFLINE", "1")

    def explode(*args, **kwargs):
        raise AssertionError("network client constructed")

    import tools.jira as jira_mod
    import tools.notion as notion_mod
    monkeypatch.setattr(jira_mod, "JIRA", explode)
    monkeypatch.setattr(notion_mod, "Client", explode)

    client = jira_mod.JiraClient({
        "url": "https://example.atlassian.net",
        "username": "a",
        "token_env": "MISSING",
        "project_key": "X",
    })
    assert client.get_pending_tickets("project = X") == []
    assert notion_mod.publish_to_notion({"notion": {"api_key_env": "NOTION_API_KEY"}}, "t", "c", "p") is None

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "horace@l3mn05.local"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Horace L3MN05"], cwd=repo, check=True)
    (repo / "README.md").write_text("hi\n", encoding="utf-8")

    pushed = []
    real_run = subprocess.run

    def spy(cmd, *args, **kwargs):
        if isinstance(cmd, (list, tuple)) and "push" in list(cmd):
            pushed.append(list(cmd))
            raise AssertionError(f"push attempted: {cmd}")
        if isinstance(cmd, (list, tuple)) and cmd and os.path.basename(str(cmd[0])) == "gh":
            pushed.append(list(cmd))
            raise AssertionError(f"gh attempted: {cmd}")
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", spy)
    from tools.git import create_pr, git_commit_push
    assert git_commit_push(str(repo), "local commit") is True
    assert create_pr(str(repo), "DEMO-1", "summary", "l3mn05-demo-1") is False
    assert pushed == []
    log = subprocess.run(["git", "-C", str(repo), "log", "--oneline"], check=True, capture_output=True, text=True)
    assert "local commit" in log.stdout
    err = capsys.readouterr().out
    assert "disabled" in err.lower()
    assert offline_message("git push") in err or "git push" in err


def test_chat_offline_does_not_call_grok(monkeypatch):
    monkeypatch.setenv("L3MN05_OFFLINE", "1")
    import l3mn05_chat

    def boom(*args, **kwargs):
        raise AssertionError("remote chat client constructed")

    monkeypatch.setattr(l3mn05_chat, "_grok_client", boom)
    response = l3mn05_chat.app.test_client().post("/chat", json={"message": "hi", "history": []})
    body = response.get_json()
    assert response.status_code == 200
    assert body["offline"] is True
    assert "disabled" in body["reply"].lower()
    assert "remote model" in body["reply"].lower()


def test_slack_offline_does_not_connect(monkeypatch, capsys):
    monkeypatch.setenv("L3MN05_OFFLINE", "1")
    monkeypatch.delenv("L3MN05_CONTAINER", raising=False)
    import l3mn05_slack
    assert l3mn05_slack.run_bot() == 0
    text = capsys.readouterr().out
    assert "disabled" in text.lower()
    assert "slack" in text.lower()


def test_worker_loop_does_not_poll_jira(monkeypatch):
    monkeypatch.setenv("L3MN05_OFFLINE", "1")
    monkeypatch.delenv("L3MN05_CONTAINER", raising=False)
    from utils.worker_core import run_main_loop
    calls = []
    run_main_loop(lambda *args, **kwargs: calls.append(1), "scaffold_jql", "scaffold")
    assert calls == []
