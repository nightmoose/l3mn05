"""Run one ticket from a local file. No Jira, no GitHub clone.

The CLI in demo_run.py turns the offline switch on unless --allow-remote is set.
This module does not force the switch; callers and tests set L3MN05_OFFLINE.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

from utils.config import load_config, project_root
from utils.offline import install_network_guard, is_offline, offline_message

SAMPLE_TICKET = Path(project_root()) / "demo" / "sample_ticket.json"
SAMPLE_REPO = Path(project_root()) / "demo" / "sample_repo"

_SKILL_NAMES = [
    "research",
    "documentation",
    "code_implementation",
    "testing",
    "data_architect",
    "deployment",
    "final_review",
]


def load_ticket(path=None) -> dict:
    ticket_path = Path(path) if path else SAMPLE_TICKET
    data = json.loads(ticket_path.read_text(encoding="utf-8"))
    if "key" not in data or "summary" not in data:
        raise ValueError(f"{ticket_path} needs 'key' and 'summary'")
    data.setdefault("description", "")
    data.setdefault("client_id", "demo")
    return data


def _git(repo, *args, check=True):
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=check,
        capture_output=True,
        text=True,
    )


def prepare_repo(dest) -> Path:
    """Copy the sample project into dest and make sure it has one commit."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    if not any(path for path in dest.iterdir() if path.name != ".git"):
        if SAMPLE_REPO.is_dir():
            for item in SAMPLE_REPO.iterdir():
                target = dest / item.name
                if item.is_dir():
                    shutil.copytree(item, target)
                else:
                    shutil.copy2(item, target)
        else:
            (dest / "README.md").write_text("# Sample service\n", encoding="utf-8")
    if not (dest / ".git").exists():
        _git(dest, "init")
        _git(dest, "config", "user.email", "horace@l3mn05.local")
        _git(dest, "config", "user.name", "Horace L3MN05")
        _git(dest, "add", "-A")
        _git(dest, "commit", "-m", "Initial sample")
    return dest


def _demo_config():
    base = load_config()
    config = dict(base)
    config["skills_dir"] = str(Path(project_root()) / "skills")
    config["grok_review_plan"] = False
    if is_offline():
        config["validation"] = {"enabled": False}
    else:
        config["validation"] = dict(base.get("validation") or {"enabled": False})
    jira_cfg = dict(base.get("jira") or {})
    jira_cfg["write_enabled"] = False
    config["jira"] = jira_cfg
    clients = dict(base.get("clients") or {})
    client_id = "demo"
    demo_client = dict(clients.get(client_id) or {})
    demo_client.setdefault("name", "Demo")
    demo_client["llm_mode"] = "local"
    demo_client["enabled_skills"] = list(demo_client.get("enabled_skills") or _SKILL_NAMES)
    clients[client_id] = demo_client
    config["clients"] = clients
    return config


def run_demo(ticket_path=None, repo_dir=None, execute=False, llm=None) -> dict:
    """Plan (and optionally execute) one local ticket.

    Returns a dict with ok, repo, branch, pr_draft, message.
    Does not call Jira. Push and GitHub PR creation follow the offline switch.
    """
    install_network_guard()
    ticket = load_ticket(ticket_path)
    if repo_dir is None:
        repo_dir = Path(project_root()) / ".demo-run"
    repo = prepare_repo(repo_dir)

    from tools.git import create_branch, gather_repo_context
    import orchestrators

    branch = f"l3mn05-{str(ticket['key']).lower()}"
    create_branch(str(repo), branch)

    config = _demo_config()
    client_id = ticket.get("client_id") or "demo"
    if client_id not in config["clients"]:
        config["clients"][client_id] = dict(config["clients"]["demo"])
        config["clients"][client_id]["llm_mode"] = "local"

    jira_text = f"{ticket['key']}: {ticket['summary']}\n\n{ticket.get('description', '')}"
    repo_context = gather_repo_context(str(repo))
    tech_rules = "Stay inside the ticket. Do not add network calls or new dependencies."

    previous_llm = orchestrators.call_llm
    if llm is not None:
        orchestrators.call_llm = llm
    try:
        plan = orchestrators.horace_plan(
            output_path=str(repo),
            output_full="local/demo",
            jira_text=jira_text,
            repo_context=repo_context,
            tech_rules=tech_rules,
            key=ticket["key"],
            config=config,
            skills=None,
            mode_addon="Offline demo. Plan only what the ticket asks for.",
            client_id=client_id,
            llm_call=llm,
        )
        plan = plan or ""
        failed = (
            not plan.strip()
            or plan.strip().startswith("ERROR")
            or "remote fallback" in plan.lower()
        )
        if failed:
            return {
                "ok": False,
                "repo": str(repo),
                "branch": branch,
                "message": plan.strip() or "The local model returned an empty plan.",
                "offline": is_offline(),
            }

        executed = []
        if execute:
            skills = orchestrators.load_skills(config["skills_dir"])
            steps = orchestrators.parse_skill_steps(plan, skills)
            for name, text in steps:
                orchestrators.run_skill_step(
                    skill_name=name,
                    step_text=text,
                    output_path=str(repo),
                    output_full="local/demo",
                    jira_text=jira_text,
                    repo_context=repo_context,
                    tech_rules=tech_rules,
                    key=ticket["key"],
                    config=config,
                    skills=skills,
                    write_client=None,
                    client_id=client_id,
                )
                executed.append(name)
    finally:
        orchestrators.call_llm = previous_llm

    pr_path = repo / "PR_DRAFT.md"
    lines = [
        f"# {ticket['key']}: {ticket['summary']}",
        "",
        "Prepared by L3MN05 demo mode.",
        f"Branch: `{branch}`",
        "",
    ]
    if is_offline():
        lines.append(offline_message("Opening a GitHub pull request"))
        lines.append("The branch and commits are local. Nothing was pushed.")
    else:
        lines.append("Offline mode is off. A GitHub PR is attempted only when `gh` is authenticated.")
    pr_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _git(repo, "add", "PR_DRAFT.md")
    _git(repo, "commit", "-m", f"PR draft for {ticket['key']}", check=False)

    pr_opened = False
    if not is_offline():
        from tools.git import create_pr
        pr_opened = bool(create_pr(str(repo), ticket["key"], ticket["summary"], branch))

    message = "Demo finished. Plan is on the branch."
    if is_offline():
        message += " " + offline_message("Opening a GitHub pull request")

    return {
        "ok": True,
        "repo": str(repo),
        "branch": branch,
        "plan": plan,
        "pr_draft": str(pr_path),
        "executed": executed,
        "pr_opened": pr_opened,
        "offline": is_offline(),
        "message": message,
    }
