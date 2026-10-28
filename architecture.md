# L3MN05 Architecture

**Updated:** 28 October 2026  
**Status:** Local-first skills runner with an application air-gap switch. Skills are prompt modules. The orchestrator is the runtime.

This document describes the code in this repository. It is not a target-state sketch.

## What it is

L3MN05 plans engineering work with a local OpenAI-compatible model and writes the result onto a git branch. A worker process can poll Jira when the network is allowed. Demo mode reads a ticket from a JSON file and never calls Jira.

The model call, the skill prompts, and the tools are separate:

- **Workers** (`worker_scaffold.py`, `worker_improve.py`, `worker_review.py`) are short loops. They pick a Jira status filter and call `run_multi_agent_orchestration`.
- **Orchestrator** (`orchestrators.py`) asks the model for a plan, parses `## (skill-name)` steps, and runs each step.
- **Skills** (`skills/*/SKILL.md`) are YAML frontmatter plus instructions. `skills_loader.py` loads them. There is no `BaseSkill` class.
- **Tools** (`tools/`) do file write, git, Jira, Notion, and `memory.json`. `tools/registry.py` registers five callables: `write_file`, `git_commit_push`, `notion_publish`, `load_memory`, `save_memory`.
- **Model access** (`utils/llm.py`) talks to the local server first. A remote model is optional and is refused when the offline switch is on.

```
Ticket
  │  Jira poll (online)  or  demo/sample_ticket.json (demo_run.py)
  ▼
worker_*  →  orchestrators.horace_plan  →  local model
                │
                ▼
         parse ## (skill) steps
                │
                ▼
         run_skill_step: prompt = SKILL.md + ticket + repo context
                │
                ▼
         FILE: blocks → tools.file.write_file → git commit
                │
                ▼
         branch left locally
         GitHub PR only when offline mode is off and gh is authenticated
```

## Air gap

`utils/offline.py` is the single switch.

- `L3MN05_OFFLINE=1` or `offline: true`
- The environment variable wins, including `L3MN05_OFFLINE=0` to force the online path

When it is on, call sites for Jira, Notion, Slack, Horace chat, remote validation, `git` network commands, and `gh` return a sentence that the feature is disabled. They do not raise a stack trace for the missing service.

A process-wide hook refuses other outbound sockets and the same network commands if a call site forgets the check. Loopback and the host in `OLLAMA_BASE_URL` stay open so the local model still answers. Docker Compose sets that URL to `http://ollama:11434/v1`. While the switch is on, `ollama-startup.sh` skips `ollama pull` and sets `OLLAMA_NO_CLOUD=1` so the daemon does not refresh recommendation data from ollama.com. A model has to already be on disk.

This is an application switch, not a firewall. Unplug the route when the policy is a real air gap. The Ollama process is a separate binary; `OLLAMA_NO_CLOUD` is the daemon's own opt-out, not a packet filter.

`llm_mode: local` on a client and `validation.enabled: false` stop remote model calls for that path. They do not stop Jira, GitHub, Notion, or Slack.

## Configuration loading

`utils/config.py` does not read `config.yaml` at import. A missing file is an empty mapping. That is what lets tests and `import tools.registry` succeed on a fresh clone before `cp config.example.yaml config.yaml`.

`utils/__init__.py` loads config and the offline guard only. It must not import `utils.worker_core`. That import cycle (`tools.git` → `utils` → `worker_core` → `tools.git`) left `get_repo_paths` half-initialized and broke `import tools.registry`. Workers import `run_main_loop` from `utils.worker_core`.

## Directory layout

```
l3mn05/
├── skills/                  # one folder per skill, each with SKILL.md
├── skills_loader.py
├── orchestrators.py         # plan + skill execution
├── worker_scaffold.py       # Jira "scaffold" loop; --demo delegates to demo_run
├── worker_improve.py
├── worker_review.py
├── demo_run.py              # CLI: local ticket → branch + PR draft
├── demo_mode.py
├── demo/sample_ticket.json
├── demo/sample_repo/        # tiny repo the demo copies
├── tools/
│   ├── registry.py
│   ├── file.py
│   ├── git.py
│   ├── jira.py
│   ├── memory.py
│   └── notion.py
├── utils/
│   ├── config.py            # lazy yaml + env overrides
│   ├── offline.py           # the air-gap switch and network guard
│   ├── llm.py
│   └── worker_core.py       # poll, clone, branch, cleanup
├── l3mn05_chat.py           # Flask UI, remote model, disabled while offline
├── l3mn05_slack.py          # Socket Mode bot, disabled while offline
├── tests/                   # import, config, offline guard, demo
├── .github/workflows/ci.yml
├── docker-compose.yml
├── dockerfile               # workers
├── dockerfile.chat
├── dockerfile.slack
├── config.example.yaml
└── requirements.txt
```

There is no `l3mn05_worker.py` monolith in this tree. The three workers are the entry points.

## Skills

Each skill folder holds `SKILL.md`:

```markdown
---
name: "documentation"
description: "Writes README and design notes"
allowed_tools: ["write_file", "git_commit_push"]
---

Instructions for the model.
```

`load_skills()` returns name, description, instructions, and `allowed_tools`. The orchestrator puts the instructions into the prompt. It then keeps `FILE:` fenced blocks and writes those files. If `git_commit_push` is in `allowed_tools` and a file was written, it commits. Other tool names in the frontmatter are not dispatched from model text. Notion publishing is a separate step in the orchestrator, and only if memory lists Notion as a target.

A client's `enabled_skills` list filters which names the planner may use. An unknown `## (name)` line is skipped.

The research skill does not call a search API. It asks the model to write a factual note from the ticket and the repo context.

## Tools and git

`git_commit_push` commits locally, then pushes. Offline, the commit stays and the push is skipped with a disabled message. `create_pr` calls `gh pr create` only when the switch is off. Demo mode always writes `PR_DRAFT.md` so the title and body exist either way.

`worker_core.process_ticket_base` clones the client repos, opens a mirror ticket, and creates `l3mn05-<key>`. That path is online-only. Offline, the worker loop tells you to use `demo_run.py` and does not open Jira.

## Model routing

`call_llm` is the entry the orchestrator uses.

| Switch | `llm_mode` | What runs |
| --- | --- | --- |
| offline | any | Local model only. Remote preference is ignored. No fallback. |
| online | `local` | Local, then remote only if the local call fails and validation is configured |
| online | `remote` | Remote for the plan and for skill steps |
| online | `blended` | Remote for the plan; remote for `final_review` and `documentation`; local otherwise |

`prefer_remote` and `grok_review_plan` do nothing while offline. The remote client is built from `validation.base_url`, `validation.api_key_env`, and `validation.model` at call time, not at import.

Default local URL when nothing is set: `http://127.0.0.1:11434/v1`. A bare host:port gets `/v1` appended. `OLLAMA_MODEL` overrides `local_model`.

Local calls send `max_tokens` (2048 when the caller does not set one). A small model with a 4k context will otherwise keep generating until the server aborts.

## Chat and Slack

`l3mn05_chat.py` is a Flask app on port 8080. It reads client names from config when a request arrives, so import does not need `config.yaml`. The reply path calls a remote model. Offline, `POST /chat` returns HTTP 200 and a sentence that chat is disabled.

`l3mn05_slack.py` connects to Slack Socket Mode and the same remote model. Offline, `run_bot()` returns without connecting. In a container (`L3MN05_CONTAINER=1`) it idles so Compose does not restart it.

Both images copy `utils/` so they can see the switch. The worker image copies the whole tree.

## Tests

`pytest` covers:

- a fresh interpreter importing the registry, workers, chat, and Slack with no config file
- env and file overrides for the model URL and the offline flag
- real socket and HTTP calls to public hosts raising `OfflineBlocked` while loopback is allowed
- `git push`, `gh`, and `curl` refused by the subprocess hook
- Jira, Notion, chat, Slack, and the worker poll taking the disabled path
- demo mode writing `plan.md` and `PR_DRAFT.md` on a local branch with a stand-in model function, and making no socket connections

CI is `.github/workflows/ci.yml`.

## Adding a skill

1. Create `skills/your_skill/SKILL.md` with `name`, `description`, and `allowed_tools`.
2. Add the name to the client's `enabled_skills` if that client should use it.
3. The planner only emits steps for names `load_skills` found. No registry edit is required unless you add a new tool.
4. New tools go in `tools/`, then `register_tool` in `tools/registry.py`.

## Not built

- A Python `BaseSkill` type. The loader is the interface.
- Retrieval over past tickets, or a vector store.
- Enforcement of `soft_daily_budget_usd`.
- Live web fetch inside the research skill.
- A quality eval for model output. The smoke tests check wiring with a fake model function.

## Design choices that are in force

- Local model by default, remote only when configured and when the switch is off.
- Work lands on a branch. Offline mode does not push that branch.
- One client block in config owns repos, tracker, skill list, and `llm_mode`.
- Package import stays light so tools can load config without pulling the worker loop.
