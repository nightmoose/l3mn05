# L3MN05 Architecture (v10+)

**Version**: v10 Baseline (May 1, 2026)  
**Status**: Foundational scaffolding complete — skills implementation in progress

---

## Overview

L3MN05 is a **local-first, secure, multi-agent software and data engineering consultant system**. It runs ~95% on local hardware using Ollama, with optional remote validation via Grok/xAI. 

The system automatically:
- Polls Jira for new work items
- Plans and implements changes using specialized AI skills
- Creates clean feature branches and pull requests
- Updates Jira status and comments
- Supports multiple clients with isolated configurations

**Core Philosophy (v10)**: Move from a monolithic worker script to a **modular Skills + Tools architecture** for maximum extensibility, testability, and maintainability.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Jira (Multi-Client)                       │
│   (To Do → In Progress → Review/Done)                           │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Worker Layer (Status-Driven)                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ worker_scaffold │  │ worker_improve  │  │ worker_review   │ │
│  │   (Intake)      │  │   (Execution)   │  │   (Validation)  │ │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘ │
└───────────┼────────────────────┼────────────────────┼──────────┘
            │                    │                    │
            ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Skills Layer                            │
│  research → code_implementation → data_architect → deployment  │
│           → documentation → final_review → testing             │
│  (Pluggable, per-client enabled list)                           │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Tools Registry (Central)                    │
│  write_file | git_commit_push | notion_publish | memory | jira  │
│  (Registry Pattern — register / get / execute)                   │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Local LLM (Ollama) + Optional Grok            │
│         (Blended mode supported per-client)                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
l3mn05/
├── skills/                    # Pluggable domain-specific capabilities
│   ├── code_implementation/   # Step-by-step code generation
│   ├── data_architect/        # ER diagrams, dbt models, data foundations
│   ├── deployment/            # Vercel, GitHub Actions, Docker, etc.
│   ├── documentation/         # READMEs, API docs, architecture docs
│   ├── final_review/          # Cross-cutting review & validation
│   ├── research/              # Internet research, API docs, best practices
│   └── testing/               # Test generation & execution
│
├── tools/                     # Reusable, cross-cutting primitives
│   ├── file.py                # File read/write operations
│   ├── git.py                 # Git commit/push/branch management
│   ├── jira.py                # Jira API interactions
│   ├── memory.py              # Persistent memory (memory.json)
│   ├── notion.py              # Notion publishing
│   └── registry.py            # Central tool registration & execution
│
├── utils/                     # Shared infrastructure
│   ├── config.py
│   ├── llm.py                 # Ollama + Grok client wrappers
│   ├── worker_core.py
│   └── ...
│
├── workers/ (or root)         # Status-driven orchestrators
│   ├── worker_scaffold.py
│   ├── worker_improve.py
│   └── worker_review.py
│
├── config.yaml                # Per-client settings (skills, LLM mode, Jira, repos)
├── docker-compose.yml
└── README.md
```

---

## Core Components

### 1. Tools Registry (`tools/registry.py`)

The heart of the v10 architecture — a simple, observable **Registry Pattern** implementation.

**Key Functions:**
- `register_tool(name, func, description)` — Register any callable as a tool
- `get_tool(name)` — Retrieve a tool
- `execute_tool(name, **kwargs)` — Execute with logging and error handling

**Pre-registered Core Tools (at import time):**
- `write_file` — Write content to repo files
- `git_commit_push` — Commit + push with branch safety
- `notion_publish` — Publish markdown to Notion
- `load_memory` / `save_memory` — Persistent skill memory

**Benefits:**
- Skills never import implementation details directly
- Easy to mock for testing
- New tools can be added without touching skills
- Timestamped execution logs for observability

### 2. Skills

Skills are **pluggable, focused modules** that encapsulate a specific capability. Each skill:
- Lives in its own subdirectory under `skills/`
- Can declare and use tools via the central registry
- Is enabled/disabled per client in `config.yaml`
- Follows a consistent interface (to be formalized in `BaseSkill`)

**Current Skills (v10 Baseline):**
| Skill                | Purpose                              | Typical Stage     |
|----------------------|--------------------------------------|-------------------|
| `research`           | Internet research, docs, best practices | Early            |
| `code_implementation`| Step-by-step code generation         | Core             |
| `data_architect`     | ER diagrams, dbt, data models        | Core             |
| `deployment`         | CI/CD, hosting, Docker, env files    | Late             |
| `documentation`      | READMEs, architecture, API docs      | Late             |
| `final_review`       | Cross-skill validation & polish      | Final            |
| `testing`            | Test generation & execution          | Final            |

### 3. Workers (Status-Driven Orchestration)

Instead of one giant loop, work is split across Jira-aligned stages:

- **`worker_scaffold.py`** — Polls "To Do", creates branch, runs initial skills (research + planning)
- **`worker_improve.py`** — Runs on "In Progress", executes core implementation skills
- **`worker_review.py`** — Runs on "Review"/"Done", triggers final_review + testing + PR creation

This aligns naturally with real consulting workflows and makes the system easier to debug and scale.

### 4. Configuration & Multi-Client Support

`config.yaml` is the single source of truth:

```yaml
clients:
  example-client:
    jira:
      url: https://your-company.atlassian.net
      ...
    default_repo: your-org/your-repo
    output_repo: your-org/your-output-repo
    enabled_skills: [research, code_implementation, data_architect, final_review]
    llm_mode: blended          # local | remote | blended
    tech_preferences:
      backend: python
      frontend: react
      database: snowflake
```

---

## Data Flow (Typical Ticket Lifecycle)

1. **Scaffold Stage**
   - `worker_scaffold` picks up "To Do" ticket
   - Creates feature branch `horace-<key>`
   - Runs `research` + initial planning skills
   - Saves context to memory

2. **Improve Stage**
   - `worker_improve` picks up "In Progress"
   - Orchestrates `code_implementation` → `data_architect` → `deployment`
   - Each skill calls tools via registry (e.g., `execute_tool("write_file", ...)`)

3. **Review Stage**
   - `worker_review` triggers `final_review` + `testing` + `documentation`
   - Creates PR via `git_commit_push` tool
   - Updates Jira with summary + link

4. **Memory**
   - `load_memory` / `save_memory` tools allow skills to share decisions across stages and tickets

---

## Design Principles

- **Local First** — Ollama is primary; remote calls are opt-in and auditable
- **Pluggable Everything** — New skills or tools require zero changes to core workers
- **Observable** — Every tool execution is logged with timestamp
- **Client-Isolated** — Each client has its own repos, Jira, memory, and skill list
- **Git-Safe** — All changes happen on isolated branches with clean commits
- **Extensible by Default** — Adding a new skill is as simple as creating a folder + registering tools

---

## Adding a New Skill (Developer Guide)

1. Create `skills/your_skill_name/`
2. Implement the skill (following the emerging `BaseSkill` interface)
3. Register any new tools it needs in `tools/registry.py` (or a skill-specific module)
4. Add the skill name to `enabled_skills` in the relevant client's `config.yaml`
5. (Optional) Add a dedicated worker stage if the skill needs special timing

Example minimal skill skeleton (future):

```python
# skills/your_skill_name/skill.py
from tools.registry import execute_tool

def run(issue, context, memory):
    # Your logic here — call execute_tool("write_file", ...) etc.
    return {"status": "success", "files_written": [...]}
```

---

## Current Status (May 1, 2026)

- ✅ Tools registry implemented and pre-populated
- ✅ Skills directory structure created (7 skills)
- ✅ Multi-stage worker scaffolding in progress
- ✅ Per-client configuration system
- 🔄 Individual skill implementations (in progress)
- 🔄 Full migration from legacy `l3mn05_worker.py`

---

## Roadmap / Future Enhancements

- Formal `BaseSkill` abstract class + validation
- `skills_loader.py` with auto-discovery
- Skill-level unit + integration tests
- Web UI / OpenWebUI integration for manual skill triggering
- Cost tracking & soft budget enforcement per client
- Vector memory / RAG for long-term client context
- Self-improvement loop (use L3MN05 to improve its own skills)

---

**Maintained by**: nightmoose  
**Last Updated**: May 1, 2026 (v10 Baseline)

---

*This document describes the target architecture. Some components are still being implemented on top of the solid v10 foundation.*