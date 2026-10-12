# utils/worker_core.py
# Full restored original ticket lifecycle functions from agent.py + jira.py
# Only the parts that make tickets work (polling, mirror, clone, branch, cleanup).
# No old agent/run_agent_step code.

import os
import tempfile
import shutil
import time
import subprocess
import yaml
from datetime import datetime

from utils.config import WORKSPACE, config
import tools.jira as source
from tools.git import get_repo_paths, gather_repo_context, create_branch, create_pr, refresh_repo_context
from tools.notion import publish_to_notion


def run_main_loop(process_func, jql_type, log_prefix="WORKER"):
    """Original main polling loop."""
    print(f"[{datetime.now()}] [{log_prefix}] Worker ready. Polling Jira...")

    while True:
        try:
            for client_id, client in config.get("clients", {}).items():
                client_jira = source.JiraClient(client["jira"])
                jql = get_client_jql(config, client_id, jql_type)
                print(f"[{datetime.now()}] [{log_prefix}] Using JQL for '{client_id}': {jql}")

                issues = client_jira.get_pending_tickets(jql)
                for issue_data in issues:
                    try:
                        process_func(issue_data, client_id, config)
                    except Exception as issue_e:
                        print(f"[{datetime.now()}] [{log_prefix}] Issue error (skipping {issue_data.get('key', 'UNKNOWN')}): {issue_e}")
                    time.sleep(8)
        except Exception as e:
            print(f"[{datetime.now()}] [{log_prefix}] Loop error (retrying): {e}")
        time.sleep(config.get('jira', {}).get('poll_minutes', 15) * 60)


def get_client_jql(config, client_id, jql_type):
    """Original JQL builder with project filter and processed keys exclusion."""
    client = config["clients"][client_id]
    client_jira = client.get("jira", {})

    base_jql = config["jira"][jql_type]
    filters = []

    project = client_jira.get("project_key")
    if project:
        if isinstance(project, list):
            proj_filter = f"project in ({','.join(f'\"{p}\"' for p in project)})"
        else:
            proj_filter = f'project = "{project}"'
        filters.append(proj_filter)

    output_jira_config = config.get("output_jira")
    if output_jira_config:
        output_client = source.JiraClient(output_jira_config)
        mirror_jql = config.get("jira", {}).get("mirror_jql", 'project = "HORACE" ORDER BY created DESC')
        processed_keys = output_client.get_processed_original_keys(mirror_jql)
        if processed_keys:
            exclusion = f"key not in ({','.join(processed_keys)})"
            filters.append(exclusion)

    if filters:
        filter_str = " AND " + " AND ".join(filters)
        if "ORDER BY" in base_jql.upper():
            order_by_index = base_jql.upper().rfind("ORDER BY")
            before_order = base_jql[:order_by_index].strip()
            order_by_clause = base_jql[order_by_index:]
            return f"{before_order}{filter_str} {order_by_clause}"
        else:
            return f"{base_jql}{filter_str}"
    return base_jql


def process_ticket_base(issue_data, client_id, config, log_prefix="WORKER"):
    """Original ticket setup with safe description handling from your original code."""
    client = config["clients"][client_id]

    context_full, output_full, _, _ = get_repo_paths(client, config)

    summary = issue_data.get('fields', {}).get('summary', 'No summary')
    desc_raw = issue_data.get('fields', {}).get('description', '')
    # Original safe handling for description (ADF or string)
    description = desc_raw if isinstance(desc_raw, dict) and 'version' in desc_raw and 'type' in desc_raw else str(desc_raw or "")

    output_jira_config = config.get("output_jira")
    write_client = source.JiraClient(output_jira_config)

    epic_key = client.get("context_epic_key")
    key = write_client.create_mirror_ticket(
        summary,
        description,
        client["jira"]["url"],
        issue_data.get('key'),
        worker_prefix=log_prefix,
        epic_key=epic_key
    )

    # Context repo clone
    temp_dir = tempfile.mkdtemp(dir=WORKSPACE)
    context_token = os.getenv(f"GITHUB_TOKEN_{client_id.upper()}") or os.getenv("GITHUB_TOKEN")
    clone_cmd = ["git", "clone", f"https://oauth2:{context_token}@github.com/{context_full}.git", temp_dir]
    subprocess.run(clone_cmd, check=True, capture_output=True, text=True)
    context_path = temp_dir

    # Output repo clone
    output_path = temp_dir if context_full == output_full else tempfile.mkdtemp(dir=WORKSPACE)
    if context_full != output_full:
        output_token = os.getenv("GITHUB_TOKEN")
        output_clone_cmd = ["git", "clone", f"https://oauth2:{output_token}@github.com/{output_full}.git", output_path]
        subprocess.run(output_clone_cmd, check=True, capture_output=True, text=True)

    subprocess.run(["git", "-C", output_path, "pull", "origin", "main"], check=True, capture_output=True, text=True)

    repo_context = gather_repo_context(context_path)
    branch_name = f"l3mn05-{key}"
    create_branch(output_path, branch_name)

    return key, repo_context, description, output_path, output_full, branch_name, write_client, context_path


def run_worker_base(issue_data, client_id, config, log_prefix, worker_func):
    """Original wrapper that sets up the ticket then calls worker_logic."""
    output_path = None
    context_path = None
    try:
        unpacked = process_ticket_base(issue_data, client_id, config, log_prefix)
        key, repo_context, jira_text, output_path, output_full, branch_name, write_client, context_path = unpacked

        tech_rules = ""
        worker_func(key, repo_context, jira_text, output_path, output_full, branch_name, write_client, tech_rules, config, client_id)

    except Exception as e:
        print(f"[{datetime.now()}] [ERROR] Processing failed for {issue_data.get('key', 'UNKNOWN')}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if output_path:
            shutil.rmtree(output_path, ignore_errors=True)
        if context_path and context_path != output_path:
            shutil.rmtree(context_path, ignore_errors=True)
        print(f"[{datetime.now()}] [CLEANUP] Temp dirs removed")