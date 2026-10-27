# L3MN05

**A local-first AI engineering harness. Your code stays on your machine.**

L3MN05 runs a team of AI "skills" (research, coding, data architecture, testing, docs, deployment, final review) on a **local open-weight model through [Ollama](https://ollama.com)**. It picks up tickets, plans the work, writes code on a feature branch, and opens a pull request for you to review. The heavy lifting runs on your own hardware.

- **Local model by default:** `qwen2.5-coder:14b`, pulled automatically on first run. Use a 7B or 3B model on smaller machines.
- **Optional remote validation:** a second-opinion pass from a hosted model (Grok/xAI by default) for planning and final review. Turn it off with `validation.enabled: false` or set a client's `llm_mode: local`.
- **Git-safe:** work lands on feature branches and PRs, never directly on main.
- **Multi-client:** each client gets its own repos, tracker, skills and LLM mode.
- **MIT licensed.**

> Note: the optional chat UI ("Horace", port 8080) and the Slack bot currently use Grok for conversation. The workers that do the engineering run on the local model.

---

## Requirements
- Docker Desktop (Mac/Linux/Windows)
- Git and the `gh` CLI (`gh auth login`) if you want auto-PRs
- About 16 GB RAM for the 14B model (8 GB works with 7B models)

## Quickstart
```bash
git clone https://github.com/nightmoose/l3mn05.git ~/l3mn05
cd ~/l3mn05
cp config.example.yaml config.yaml   # edit: model, clients, tracker, LLM mode
cp env.example .env                  # edit: only the keys you actually use
docker compose up -d
```
The first start pulls the local model (this can take 5–15 minutes). Workers mount `~/consulting` as their workspace.

Or use the installer: `./install.sh`

## How it works
```
Tickets (Jira or Notion)  →  worker_scaffold  →  worker_improve  →  worker_review  →  branch + PR
                                   │                  │                  │
                                   └──── skills/ (SKILL.md) + tools/ (file, git, jira, memory, notion)
                                                      │
                                         Ollama local model  (+ optional remote validation)
```
- **Skills** (`skills/`): pluggable `SKILL.md` modules.
- **Tools** (`tools/`): reusable primitives managed by a central registry.
- **Workers**: status-driven stages that line up with a normal ticket workflow.

Full design: [architecture.md](architecture.md)

## Configuration
Everything lives in `config.yaml` (start from `config.example.yaml`):
```yaml
local_model: "qwen2.5-coder:14b"
clients:
  example-client:
    enabled_skills: [research, code_implementation, final_review]
    llm_mode: local      # local | remote | blended
```

## Status
- ✅ v10 Skills + Tools architecture baseline
- ✅ Central tool registry, 7 skills, multi-stage workers
- 🔄 Individual skill implementations in progress
- 🔄 Migration from the legacy monolithic worker

## Contributing
To add a skill, see [Adding a New Skill](architecture.md#adding-a-new-skill-developer-guide). Also see [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

## License
MIT © 2026 nightmoose. See [LICENSE](LICENSE).

