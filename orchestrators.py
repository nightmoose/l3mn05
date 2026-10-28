# orchestrators.py — Skills + Tools orchestrator (final clean version)
# Key changes based on your request:
# - Skills are now self-contained: no shared iteration logic, no per-role special flags.
# - run_skill_step is minimal: load instructions → call LLM → parse FILE blocks → execute only allowed tools.
# - final_review skill fully owns consolidation + memory update.
# - deployment skill owns Notion publishing.
# - Only truly shared helpers remain (refresh context, basic plan review).
# - Local LLM is primary; remote used for planning and critical skills.

import os
import re
from datetime import datetime

# Clean imports — no more broad "from utils import *"
from utils.worker_core import run_worker_base
from tools.registry import execute_tool
from tools.file import write_file
from tools.memory import load_memory, save_memory
from tools.git import git_commit_push, refresh_repo_context, create_pr
from tools.notion import publish_to_notion
from tools.jira import JiraClient   # keep if you didn't move jira.py yet

from utils.config import load_config
from utils.llm import call_llm
from utils.offline import is_offline
from skills_loader import load_skills

def get_llm_mode_for_client(client_id, config):
    """Return 'local', 'remote', or 'blended' for the client."""
    if not client_id or "clients" not in config or client_id not in config["clients"]:
        return "blended"
    return config["clients"][client_id].get("llm_mode", "blended")

def run_multi_agent_orchestration(
    issue_data,
    client_id,
    config,
    mode="improve",
    extra_horace_instructions=""
):
    def worker_logic(key, repo_context, jira_text, output_path, output_full, branch_name, write_client, tech_rules, config_from_base, client_id_from_base):
        mode_upper = mode.upper()
        print(f"[{datetime.now()}] [{mode_upper}] === START {mode} processing for {key} ===")

        # Discover skills dynamically
        skills = load_skills(config.get("skills_dir", "skills"))

        full_instructions = f"{mode} mode.\n{extra_horace_instructions}".strip()

        print(f"[{datetime.now()}] [{mode_upper}] === CALLING HORACE (Skills planner) ===")
        plan_content = horace_plan(
            output_path=output_path,
            output_full=output_full,
            jira_text=jira_text,
            repo_context=repo_context,
            tech_rules=tech_rules,
            key=key,
            config=config,
            skills=skills,
            mode_addon=full_instructions,
            client_id=client_id
        )

        print(f"[{datetime.now()}] [{mode_upper}] Parsing skill steps...")
        skill_steps = parse_skill_steps(plan_content, skills)

        if not skill_steps:
            print(f"[{datetime.now()}] [{mode_upper}] WARNING: No valid skill steps parsed")
            write_file(output_path, "no-steps.md", "No valid skill steps parsed from Horace plan.")
            git_commit_push(output_path, f"No steps parsed for {key}", output_full)
            return

        for skill_name, step_text in skill_steps:
            print(f"[{datetime.now()}] [{mode_upper}] Executing skill → {skill_name}")
            # success = run_skill_step(
            #     skill_name=skill_name,
            #     step_text=step_text,
            #     output_path=output_path,
            #     output_full=output_full,
            #     jira_text=jira_text,
            #     repo_context=repo_context,
            #     tech_rules=tech_rules,
            #     key=key,
            #     config=config,
            #     skills=skills,
            #     write_client=write_client,
            #     client_id=client_id
            # )
            
            # NEW: Pre-process / split if the step looks too broad
            sub_steps = split_step_if_needed(skill_name, step_text, config)
            
            for sub_skill, sub_text in sub_steps:
                print(f"[{datetime.now()}] [{mode_upper}] Executing sub-step → {sub_skill}: {sub_text[:80]}...")
                success = run_skill_step(
                    skill_name=sub_skill,
                    step_text=sub_text,
                    output_path=output_path,
                    output_full=output_full,
                    jira_text=jira_text,
                    repo_context=repo_context,
                    tech_rules=tech_rules,
                    key=key,
                    config=config,
                    skills=skills,
                    write_client=write_client,
                    client_id=client_id
            )

            if not success:
                print(f"[{datetime.now()}] [WARNING] Skill {skill_name} produced no output")

            # Refresh context so subsequent skills see previous changes
            repo_context = refresh_repo_context(output_path) + "\n" + tech_rules

        # Final publication and PR (kept at orchestrator level — common to all modes)
        print(f"[{mode_upper}] === FINAL PUBLICATION & PR ===")
        memory = load_memory(output_path)
        final_doc = memory.get("final_doc")
        if final_doc and os.path.exists(os.path.join(output_path, final_doc)):
            with open(os.path.join(output_path, final_doc), "r", encoding="utf-8") as f:
                content = f.read()
            if "notion" in memory.get("publish_targets", []):
                url = publish_to_notion(config, memory.get("publish_title", f"{key} Documentation"), content,
                                       memory.get("publish_parent_id"))
                if url:
                    memory.setdefault("published_urls", []).append(url)
                    save_memory(output_path, memory, output_full)

        git_commit_push(output_path, f"Final artifacts for {key}", output_full)

        write_enabled = config.get("jira", {}).get("write_enabled", False)
        if write_enabled:
            try:
                pr_title = f"{key}: {mode.capitalize()} complete"
                create_pr(output_path, key, pr_title, branch_name)
            except Exception as e:
                if "already exists" not in str(e).lower():
                    print(f"[{datetime.now()}] [PR] Warning: {e}")

            write_client.add_comment(key, f"**🤖 Horace {mode.capitalize()} processing complete**\nBranch: {branch_name}")
            write_client.transition_issue(key, config.get("jira", {}).get("done_status", "In Progress"))

        print(f"[{datetime.now()}] [{mode_upper}] === FINISHED {key} ===\n")

    run_worker_base(issue_data, client_id, config, mode.upper(), worker_logic)


def horace_plan(
    output_path,
    output_full,
    jira_text,
    repo_context,
    tech_rules,
    key,
    config=None,
    skills=None,
    mode_addon="",
    client_id=None,
    llm_call=None,
):
    if config is None:
        config = load_config()
    if skills is None:
        skills = load_skills(config.get("skills_dir", "skills"))

    print(f"[{datetime.now()}] [HORACE] Creating plan with {len(skills)} skills...")

    # Get client-specific tech preferences
    tech_prefs = ""
    if client_id and "clients" in config and client_id in config["clients"]:
        prefs = config["clients"][client_id].get("tech_preferences", {})
        if prefs:
            tech_prefs = "\nClient-specific tech preferences (MUST FOLLOW):\n"
            for key, value in prefs.items():
                tech_prefs += f"- {key}: {value}\n"

    # NEW: Filter skills based on per-client enabled_skills
    enabled_for_client = []
    if client_id and "clients" in config and client_id in config["clients"]:
        client_config = config["clients"][client_id]
        enabled_names = [name.lower() for name in client_config.get("enabled_skills", [])]
        if enabled_names:
            enabled_for_client = [s for s in skills if s["name"].lower() in enabled_names]
        else:
            enabled_for_client = skills  # use all if not specified
    else:
        enabled_for_client = skills

    print(f"[{datetime.now()}] [HORACE] Using {len(enabled_for_client)} enabled skills for client '{client_id}'")

    # Build skills list for prompt using only enabled ones
    skills_text = "\nAvailable Skills (use ONLY these exact names in (parentheses)):\n"
    for s in sorted(enabled_for_client, key=lambda x: x["name"]):
        skills_text += f"- ({s['name']}) {s['description']}\n"

    prompt = f"""You are Horace, expert architect and coordinator.

Jira ticket summary:
{jira_text}

Repo context:
{repo_context}

Global tech rules:
{tech_rules}

{tech_prefs}

{skills_text}

Mode instructions: {mode_addon}

Rules:
- Use ONLY the exact skill names shown above in (parentheses).
- Create clear, result-oriented steps.
- Output ONLY the plan Markdown. No extra text.

STRICT PLANNING RULES:
- Break work into SMALL, focused steps (aim for 15-25 steps total).
- Each step must be narrow and completable in one skill call.
- Use ONLY the technologies and practices from the tech_preferences and tech_rules above.
- Stay strictly within the Jira ticket scope.

Output format:
# Plan for {key}
## (skill-name) Step Title
- Bullet describing what the skill should accomplish (keep it narrow)

Start directly with # Plan for {key}."""

    #plan_content = call_llm(prompt, temperature=0.1, prefer_remote=True)
    llm_mode = get_llm_mode_for_client(client_id, config)
    prefer_remote = (llm_mode == "remote") or (llm_mode == "blended")
    if is_offline():
        prefer_remote = False

    invoke = llm_call or call_llm
    plan_content = invoke(prompt, temperature=0.1, prefer_remote=prefer_remote) or ""

    # Optional strict review with remote LLM. Skipped entirely while offline.
    if (
        not is_offline()
        and config.get("grok_review_plan", True)
        and config.get("validation", {}).get("enabled", False)
    ):
        review_prompt = f"""Rewrite the plan below to strictly use only the listed skill names.
Start directly with # Plan for {key}.
Output ONLY the corrected Markdown plan.

Original:
{plan_content}"""
        corrected = invoke(review_prompt, temperature=0.1, prefer_remote=True)
        if len(corrected.strip()) > 200 and "# Plan for" in corrected:
            plan_content = corrected
            print(f"[{datetime.now()}] [HORACE] Remote plan review applied")

    write_file(output_path, "plan.md", plan_content)
    git_commit_push(output_path, f"Horace plan for {key}", output_full)
    return plan_content


def parse_skill_steps(plan_content: str, skills: list):
    """Parse ## (skillname) lines — only accept known skills."""
    known = {s["name"].lower() for s in skills}
    steps = []
    for line in plan_content.splitlines():
        stripped = line.strip()
        if stripped.startswith("## ("):
            match = re.match(r'## \(([^)]+)\)\s*(.*)', stripped)
            if match:
                name = match.group(1).strip().lower()
                text = match.group(2).strip()
                if name in known:
                    steps.append((name, text))
                    print(f"[PARSE] Valid step: {name}")
                else:
                    print(f"[PARSE] Unknown skill: {name} — skipped")
    return steps


def run_skill_step(
    skill_name: str,
    step_text: str,
    output_path: str,
    output_full: str,
    jira_text: str,
    repo_context: str,
    tech_rules: str,
    key: str,
    config: dict,
    skills: list,
    write_client=None,
    client_id=None
):
    """Skill executor with robust raw output saving + strict FILE parsing."""
    skill = next((s for s in skills if s["name"].lower() == skill_name.lower()), None)
    if not skill:
        print(f"[ERROR] Skill '{skill_name}' not found")
        return False

    print(f"[{datetime.now()}] [SKILL:{skill_name.upper()}] Starting: {step_text[:80]}...")

    # Safe handling for jira_text (it can be dict or str)
    if isinstance(jira_text, dict):
        jira_text_str = str(jira_text)
    else:
        jira_text_str = str(jira_text or "")

    full_prompt = "JIRA TICKET (STAY STRICTLY WITHIN THIS SCOPE - DO NOT ADD FEATURES NOT MENTIONED HERE):\n" + \
                  jira_text_str + "\n\n" + \
                  skill['instructions'] + "\n\n" + \
                  "Task: " + step_text + "\n\n" + \
                  "Current repo context:\n" + repo_context + "\n\n" + \
                  "Tech rules:\n" + tech_rules + "\n\n" + \
                  "STRICT RULES:\n" + \
                  "- Base EVERYTHING you do ONLY on the Jira ticket description above.\n" + \
                  "- Do NOT invent, assume, or add any features, modules, or functionality that are not explicitly mentioned in the Jira ticket.\n" + \
                  "- Always use exact FILE: blocks when creating or updating files.\n" + \
                  "- Example:\n" + \
                  "  FILE: docs/example.md\n" + \
                  "  ```markdown\n" + \
                  "  content\n" + \
                  "  ```\n" + \
                  "- You may only use these tools: " + ", ".join(skill.get("allowed_tools", [])) + "\n" + \
                  "- Be precise and production-ready."

    # Determine LLM mode per client
    llm_mode = get_llm_mode_for_client(client_id, config) if 'get_llm_mode_for_client' in globals() else "blended"
    prefer_remote = (llm_mode == "remote") or (llm_mode == "blended" and skill_name in ("final_review", "documentation"))

    raw_output = call_llm(full_prompt, temperature=0.2, prefer_remote=prefer_remote)

    # ALWAYS SAVE RAW OUTPUT
    steps_dir = os.path.join(output_path, "steps")
    os.makedirs(steps_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_filename = f"{key}-{skill_name}-{timestamp}.raw.md"
    raw_path = os.path.join(steps_dir, raw_filename)

    with open(raw_path, "w", encoding="utf-8") as f:
        f.write(f"# Raw LLM Output - Skill: {skill_name}\n")
        f.write(f"# Task: {step_text}\n")
        f.write(f"# Timestamp: {timestamp}\n\n")
        f.write("---\n\n")
        f.write(raw_output)

    print(f"[{datetime.now()}] [SKILL:{skill_name.upper()}] Raw output saved → steps/{raw_filename} ({len(raw_output)} chars)")

    # STRICT FILE: parsing for actual file creation
    updated = False
    file_blocks = re.findall(r'FILE:\s*([^\n]+?)\s*\n```[\w]*\n(.*?)\n```', raw_output, re.DOTALL | re.IGNORECASE)

    if not file_blocks:
        file_blocks = re.findall(r'(?:FILE|PATH):\s*([^\n]+?)\s*\n```[\w]*\n(.*?)\n```', raw_output, re.DOTALL | re.IGNORECASE)

    if not file_blocks and raw_output.strip():
        default_path = f"docs/{key}-{skill_name}.md"
        file_blocks = [(default_path, raw_output)]
        print(f"[{datetime.now()}] [SKILL:{skill_name.upper()}] Using fallback: entire output saved as {default_path}")

    for rel_path, content in file_blocks:
        if content and content.strip():
            clean_path = rel_path.strip()
            write_file(output_path, clean_path, content.strip())
            updated = True
            print(f"[{datetime.now()}] [SKILL:{skill_name.upper()}] Wrote file: {clean_path}")

    # Commit if allowed
    allowed = {t.lower() for t in skill.get("allowed_tools", [])}
    if updated and "git_commit_push" in allowed:
        execute_tool("git_commit_push",
                     repo_path=output_path,
                     message=f"{skill_name}: {step_text[:80]}",
                     repo_full=output_full)

    if not updated:
        print(f"[{datetime.now()}] [WARNING] Skill {skill_name} produced no parsed files (raw output was saved)")

    return updated


def horace_cleanup(output_path, output_full, jira_text, repo_context, tech_rules, key, config=None, client_id=None):
    """Optional lightweight cleanup. Can be removed once final_review skill is reliable."""
    print(f"[{datetime.now()}] [HORACE-CLEANUP] Final polish pass for {key} (can be replaced by final_review skill)")
    return True

def split_step_if_needed(skill_name, step_text, config):
    """Optional: Break a single step into smaller sub-steps if it's too broad."""
    # Simple heuristic for now — we can make it smarter later
    if len(step_text) > 300 or any(word in step_text.lower() for word in ["scaffold", "build", "implement", "create all", "full"]):
        # For broad steps, split into 2-3 smaller ones
        sub_steps = [
            f"Break down and plan the {skill_name} step in detail",
            f"Execute the core part of {step_text[:100]}...",
            f"Review and polish the output from the {skill_name} step"
        ]
        return [(skill_name, sub) for sub in sub_steps]
    return [(skill_name, step_text)]