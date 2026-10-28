# Demo script (about 2–3 minutes)

Audience: someone who needs to see an air-gapped run, not a tour of the repo.

You need a local model endpoint. On a pitch machine that is Ollama with `qwen2.5-coder:14b` (or a smaller tag). This script assumes Ollama is already serving. The offline switch will not download a model for you.

Record the terminal full screen. Hide tokens. Do not open the chat UI in this take: with the switch on it only says chat is disabled, and with the switch off it calls a remote model.

## Before you hit record

```bash
cd ~/l3mn05
cp config.example.yaml config.yaml   # once
# Ollama on 127.0.0.1:11434, or:
# export OLLAMA_BASE_URL=http://127.0.0.1:11434/v1
export OLLAMA_MODEL=qwen2.5-coder:14b
export L3MN05_OFFLINE=1
rm -rf .demo-run
```

Confirm the model answers once, off camera:

```bash
curl -s http://127.0.0.1:11434/api/tags | head
```

## 0:00 — the switch

Say: "This process is not allowed to call the network. The only model it can use is the one on this machine."

```bash
echo "L3MN05_OFFLINE=$L3MN05_OFFLINE"
python - <<'PY'
import urllib.request
from utils.offline import OfflineBlocked
try:
    urllib.request.urlopen("https://example.com", timeout=3)
    print("UNEXPECTED: example.com was reachable")
except OfflineBlocked as exc:
    print(exc)
PY
```

You should see: `Offline mode is on. Outbound DNS lookup to example.com is disabled. Only the local model is used.`

## 0:25 — ticket in

```bash
python demo_run.py --ticket demo/sample_ticket.json
```

Say: "The ticket is a file on disk. Jira is not contacted."

Wait for the plan. On a 14B model this is the long beat. If you need it shorter, use a smaller tag you already trust, and say the tag out loud.

You should see:

- `offline: 1`
- `Jira is not contacted`
- a line that git push / GitHub PR open is disabled
- `Branch: l3mn05-demo-1`
- `PR draft: .demo-run/PR_DRAFT.md`

If the model is down you get exit code 2 and a line that remote fallback is disabled. That is the correct failure. Do not flip the switch to "make the demo work."

## 1:40 — branch and draft

```bash
git -C .demo-run branch --show-current
git -C .demo-run log --oneline
echo "----- plan -----"
sed -n '1,40p' .demo-run/plan.md
echo "----- PR draft -----"
cat .demo-run/PR_DRAFT.md
```

Say: "The plan is a commit on `l3mn05-demo-1`. The pull request title and body are in the repo. Nothing was pushed. On a connected run, this is where `gh pr create` runs. Offline, that command is refused."

Optional, if you have ten seconds:

```bash
python - <<'PY'
import subprocess
from utils.offline import OfflineBlocked
try:
    subprocess.run(["gh", "pr", "create", "--help"], check=False)
except OfflineBlocked as exc:
    print(exc)
PY
```

## 2:20 — close

Say: "Same switch covers Jira, Notion, Slack, and the chat UI. Turn it off only when this machine is allowed to use those services. The workers still prefer the local model either way."

Stop recording.

## What not to claim in the voiceover

- Don't say the skills browsed the web. They are prompts.
- Don't say a GitHub PR was opened in this take. The draft is local.
- Don't say chat works offline. It answers that it is disabled.
- If you used a model other than the default 14B, name it.

## Cast checked into the repo

`docs/demo.cast` is an asciinema recording from 28 October 2026. Play it with `asciinema play docs/demo.cast`.

That take is a real local model, not a stub: Ollama serving `qwen2.5-coder:0.5b` on `127.0.0.1:11434`, `L3MN05_OFFLINE=1`, then `demo_run.py`. The default 14B tag was not loaded. The 0.5B plan in the cast is wide and generic. Treat the cast as proof the switch, the local client, the branch, and the PR draft work. It is not a quality claim about `qwen2.5-coder:14b`.
