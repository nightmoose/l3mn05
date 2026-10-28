# L3MN05

[![CI](https://github.com/nightmoose/l3mn05/actions/workflows/ci.yml/badge.svg)](https://github.com/nightmoose/l3mn05/actions/workflows/ci.yml)

**A local-first engineering harness. The model that plans the work runs on your machine.**

L3MN05 reads a ticket, asks a local open-weight model (through [Ollama](https://ollama.com)) for a plan, runs that plan through a set of skill prompts, and leaves the result on a feature branch. With the air-gap switch on, the process refuses outbound calls. Remote features say they are disabled.

## Works today

These paths are covered by the smoke tests in CI:

- The tool registry, workers, and orchestrator import with no `config.yaml` on disk.
- Seven skills load from `skills/*/SKILL.md` (research, code implementation, data architect, deployment, documentation, final review, testing). Skills are prompt files. One orchestrator runs them.
- `OLLAMA_BASE_URL` and `OLLAMA_MODEL` choose the local model. Outside Docker the default URL is `http://127.0.0.1:11434/v1`. Compose points workers at `http://ollama:11434/v1`.
- `L3MN05_OFFLINE=1` (or `offline: true` in config) blocks public sockets, `git push` / `pull` / `fetch` / `clone`, `gh`, `curl`, remote model calls, Jira, Notion, Slack, and the chat UI's remote model. Those features return a clear disabled message. Loopback and the configured local-model host stay open.
- `python demo_run.py` reads `demo/sample_ticket.json`, asks the local model for a plan, commits it on a branch, and writes `PR_DRAFT.md`. It does not talk to Jira. While offline it does not push or open a GitHub PR.

## Not in this tree yet

- A measured quality bar for the default `qwen2.5-coder:14b` model. CI does not download weights.
- A live Jira poll or a live `gh pr create`. The code is there. CI has no Jira or GitHub credentials, and offline mode refuses those calls on purpose.
- A full `docker compose up` on a small machine. The Ollama service reserves 12 GB and limits itself to 20 GB so the 14B model has room. That reservation was not started in CI.
- Web research. The research skill asks the model to write notes. It does not fetch pages. `duckduckgo-search` and `tavily-python` are listed in `requirements.txt` and are not called.
- A hard spend cap. `soft_daily_budget_usd` is a config field. Nothing enforces it.
- The chat UI and the Slack bot as offline assistants. They call a remote model (Grok) when the switch is off. When the switch is on they say they are disabled and do not connect.

## Requirements

- Docker, if you use the compose stack, and enough RAM for the model you pull (about 16 GB for the default 14B; smaller tags exist)
- Git
- The `gh` CLI (`gh auth login`) only if you want a GitHub PR opened for you
- Python 3.12 and `pip install -r requirements.txt` if you run the demo outside Docker

## Quickstart

```bash
git clone https://github.com/nightmoose/l3mn05.git
cd l3mn05
cp config.example.yaml config.yaml
cp env.example .env
docker compose up -d
```

The first online start pulls the model named by `OLLAMA_MODEL` (default `qwen2.5-coder:14b`). That download is skipped when `L3MN05_OFFLINE=1`, and the Ollama process is started with `OLLAMA_NO_CLOUD=1` so it does not refresh data from ollama.com. A model has to already be on disk. Workers mount `~/consulting` as their workspace and expect `config.yaml` in this directory.

`./install.sh` does the same copy, build, and start.

## Air-gapped mode

One switch covers the process:

```bash
export L3MN05_OFFLINE=1
```

or in `config.yaml`:

```yaml
offline: true
```

The environment variable wins. `L3MN05_OFFLINE=0` forces the online path even if the file says `offline: true`.

With the switch on:

- Planning uses only the local model. If that model is down, the run stops. It does not call a remote model.
- Jira polling, Notion, Slack, git network operations, and GitHub PR creation say they are disabled.
- Horace chat answers that chat is disabled because it uses a remote model.
- The Slack process does not open a Slack socket. In Docker it stays idle so Compose does not restart-loop.

The switch hooks Python sockets and blocks known network commands (`git` push/pull/fetch/clone, `gh`, `curl`, and similar). It is the application control. A machine with no route to the public internet is the physical air gap. Use both when the policy requires it.

Per-client `llm_mode: local` and `validation.enabled: false` also keep a single client off the remote model. They do not block Jira, GitHub, or Slack. Use `L3MN05_OFFLINE` when nothing should leave the machine.

## Demo without Jira

```bash
pip install -r requirements.txt
# Ollama listening on 127.0.0.1:11434, or set OLLAMA_BASE_URL
L3MN05_OFFLINE=1 python demo_run.py
```

`python worker_scaffold.py --demo` is the same command. The default ticket is `demo/sample_ticket.json`. The branch and `PR_DRAFT.md` land in `.demo-run/` (gitignored). Pass `--repo` to choose another directory. Pass `--execute` to run the parsed skill steps after the plan. Pass `--allow-remote` only if you intentionally want remote fallback.

A 2–3 minute recording script is in [docs/DEMO.md](docs/DEMO.md). A one-page brief is in [docs/ONE-PAGER.md](docs/ONE-PAGER.md).

## How it works

```
Ticket (Jira, or a local JSON file in demo mode)
        │
        ▼
worker_scaffold / worker_improve / worker_review     thin status loops
        │
        ▼
orchestrators.py                                     plan, then each skill
        │
        ├── skills/*/SKILL.md                        prompt + allowed tools
        └── tools/                                   file, git, jira, memory, notion
                │
                ▼
        local model (Ollama)                         remote model only if offline is off
```

Full layout: [architecture.md](architecture.md).

## Configuration

Start from `config.example.yaml`.

```yaml
offline: false
ollama_base_url: "http://127.0.0.1:11434/v1"
local_model: "qwen2.5-coder:14b"
clients:
  example-client:
    llm_mode: local          # local | remote | blended
    enabled_skills: [research, code_implementation, final_review]
```

| Variable | Role |
| --- | --- |
| `L3MN05_OFFLINE` | `1` refuses outbound calls |
| `OLLAMA_BASE_URL` | Local model URL, overrides `ollama_base_url` |
| `OLLAMA_MODEL` | Model name, overrides `local_model` |
| `L3MN05_CONFIG` | Alternate path to the yaml file |
| `REMOTE_API_KEY` / `GROK_API_KEY` | Remote validation and the chat/Slack front ends |

## Tests

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

CI runs that on Ubuntu with Python 3.12 (`.github/workflows/ci.yml`).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md). A new skill is a folder under `skills/` with a `SKILL.md` file. Details are in [architecture.md](architecture.md#adding-a-skill).

## License

MIT © 2026 nightmoose. See [LICENSE](LICENSE).
