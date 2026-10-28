"""Imports must work with no config.yaml, and the tool registry must load."""

import os
import subprocess
import sys

from utils.config import project_root


def test_registry_and_orchestrator_import_without_config():
    env = os.environ.copy()
    env.pop("L3MN05_CONFIG", None)
    env.pop("L3MN05_OFFLINE", None)
    env.pop("OLLAMA_BASE_URL", None)
    script = (
        "import tools.registry, tools.git, utils.llm, orchestrators, "
        "skills_loader, worker_scaffold, worker_improve, worker_review, "
        "l3mn05_chat, l3mn05_slack\n"
        "from tools.git import get_repo_paths\n"
        "full, out, cpath, opath = get_repo_paths({'context_repo': 'acme/widgets'})\n"
        "assert full == 'acme/widgets'\n"
        "assert cpath.endswith('widgets') and opath.endswith('widgets')\n"
        "names = sorted(tools.registry.TOOLS)\n"
        "assert names == ['git_commit_push', 'load_memory', 'notion_publish', 'save_memory', 'write_file']\n"
        "print('ok')\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", script],
        cwd=project_root(),
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "ok" in proc.stdout


def test_registry_lists_tools():
    import tools.registry as registry
    assert set(registry.TOOLS) == {
        "write_file",
        "git_commit_push",
        "notion_publish",
        "load_memory",
        "save_memory",
    }
    assert registry.get_tool("write_file")["func"].__name__ == "write_file"
