import os
import subprocess

import pytest

from demo_mode import load_ticket, run_demo
from utils.config import project_root
from pathlib import Path


def _fake_llm(prompt, temperature=0.1, prefer_remote=False, max_tokens=None):
    if "Available Skills" in prompt or "You are Horace" in prompt:
        return (
            "# Plan for DEMO-1\n"
            "## (documentation) Describe the health endpoint\n"
            "- Write docs/health.md for GET /health\n"
        )
    return (
        "FILE: docs/health.md\n"
        "```markdown\n"
        "# Health\n"
        "GET /health returns status ok.\n"
        "```\n"
    )


def test_sample_ticket_loads():
    ticket = load_ticket()
    assert ticket["key"] == "DEMO-1"
    assert "health" in ticket["summary"].lower()


def test_demo_plans_branch_without_network(monkeypatch, tmp_path):
    monkeypatch.setenv("L3MN05_OFFLINE", "1")
    attempts = []
    import socket
    current = socket.socket.connect

    def wrapped(self, address):
        attempts.append(address)
        return current(self, address)

    monkeypatch.setattr(socket.socket, "connect", wrapped)

    real_run = subprocess.run

    def spy(cmd, *args, **kwargs):
        if isinstance(cmd, (list, tuple)):
            flat = [str(part) for part in cmd]
            if "push" in flat or (flat and os.path.basename(flat[0]) == "gh"):
                raise AssertionError(f"outbound git command: {flat}")
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", spy)

    result = run_demo(repo_dir=tmp_path / "repo", llm=_fake_llm, execute=False)
    assert result["ok"] is True
    assert result["offline"] is True
    assert result["branch"] == "l3mn05-demo-1"
    assert result["pr_opened"] is False
    repo = result["repo"]
    plan = open(os.path.join(repo, "plan.md"), encoding="utf-8").read()
    assert "# Plan for DEMO-1" in plan
    draft = open(result["pr_draft"], encoding="utf-8").read()
    assert "disabled" in draft.lower()
    assert "DEMO-1" in draft
    log = subprocess.run(
        ["git", "-C", repo, "branch", "--show-current"],
        check=True, capture_output=True, text=True,
    )
    assert log.stdout.strip() == "l3mn05-demo-1"
    assert attempts == []


def test_demo_execute_writes_file(monkeypatch, tmp_path):
    monkeypatch.setenv("L3MN05_OFFLINE", "1")
    result = run_demo(repo_dir=tmp_path / "repo", llm=_fake_llm, execute=True)
    assert result["ok"] is True
    assert "documentation" in result["executed"]
    health = os.path.join(result["repo"], "docs", "health.md")
    assert os.path.exists(health)
    assert "Health" in open(health, encoding="utf-8").read()


def test_cli_defaults_to_offline(monkeypatch):
    monkeypatch.delenv("L3MN05_OFFLINE", raising=False)
    captured = {}

    def fake_run(ticket_path=None, repo_dir=None, execute=False, llm=None):
        captured["offline"] = os.environ.get("L3MN05_OFFLINE")
        captured["ticket"] = ticket_path
        return {
            "ok": True,
            "message": "ok",
            "branch": "l3mn05-demo-1",
            "repo": "/tmp/demo",
            "pr_draft": "/tmp/demo/PR_DRAFT.md",
        }

    import demo_run
    monkeypatch.setattr(demo_run, "run_demo", fake_run)
    ticket = str(Path(project_root()) / "demo" / "sample_ticket.json")
    assert demo_run.main(["--ticket", ticket]) == 0
    assert captured["offline"] == "1"


def test_skills_discovered():
    from skills_loader import load_skills
    skills = load_skills(str(Path(project_root()) / "skills"))
    names = {skill["name"] for skill in skills}
    assert names == {
        "research",
        "code_implementation",
        "data_architect",
        "deployment",
        "documentation",
        "final_review",
        "testing",
    }


def test_compose_wires_offline_switch_and_ollama_url():
    from pathlib import Path
    import yaml
    root = Path(project_root())
    text = (root / "docker-compose.yml").read_text(encoding="utf-8")
    doc = yaml.safe_load(text)
    assert "OLLAMA_BASE_URL=http://ollama:11434/v1" in text
    assert "L3MN05_OFFLINE=" in text
    for name in ("ollama", "worker-scaffold", "worker-improve", "worker-review", "horace-chat", "horace-slack"):
        assert name in doc["services"]
    startup = (root / "ollama-startup.sh").read_text(encoding="utf-8")
    assert "L3MN05_OFFLINE" in startup
    assert "OLLAMA_NO_CLOUD=1" in startup
    assert "not contacting the model registry" in startup or "not downloading" in startup
    assert "COPY utils/ utils/" in (root / "dockerfile.chat").read_text(encoding="utf-8")
    assert "COPY utils/ utils/" in (root / "dockerfile.slack").read_text(encoding="utf-8")
