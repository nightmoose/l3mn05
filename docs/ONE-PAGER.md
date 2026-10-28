# L3MN05

**On-prem engineering agents. The model that reads the code stays on the customer's machine.**

Leave-behind for a conversation about air-gapped, on-prem AI. 28 October 2026.

## The problem

Regulated and security-conscious teams already know what they want from a coding agent: pick up a ticket, plan the change, open a branch a human can review. They will not send the repository to a vendor's model to get it. Most "AI software engineer" products assume that upload. The teams that cannot make that assumption are left with a chatbot in a browser and a pile of copy-paste.

## The product

L3MN05 is a local-first harness. A worker reads a ticket, a local open-weight model (Ollama, default `qwen2.5-coder:14b`) writes a plan, skill prompts turn that plan into files, and the files land on a feature branch. A human reviews the branch. The default path does not need a cloud model.

One switch, `L3MN05_OFFLINE=1`, makes the process refuse outbound calls. Jira, GitHub, Notion, Slack, and remote models then answer that they are disabled, instead of failing on a timeout or a missing key. The local model endpoint stays reachable. Teams that want a hard air gap run this on a machine with no public route. The switch is what stops the software from trying the network anyway.

Remote validation (a second model, off by default in an offline demo) is there for teams whose policy allows a second opinion. It is not required to plan or to write the branch.

## What is working, and was checked

Checked in this repository's smoke tests (they run in GitHub Actions on every pull request):

- The system imports and the tool registry loads with no config file and no network.
- Seven skill prompts load from disk. Adding a skill is a markdown file, not a new service.
- The offline switch blocks real outbound sockets (public IPs and HTTPS) and blocks `git push`, `gh`, and `curl`. Loopback stays open for the local model.
- With the switch on, chat, Slack, Jira, Notion, and remote-model fallback report that they are disabled and do not open those connections.
- Demo mode reads a sample ticket from a local file, writes a plan onto a branch, and writes a pull-request draft. It does not contact Jira. While offline it does not push.

Also checked while preparing this page, outside CI: the worker, chat, and Slack images build; with the switch on, chat answers that it is disabled and Slack exits without connecting; `docker compose up` brings Ollama up without downloading a model and with Ollama cloud turned off. A small local model (`qwen2.5-coder:0.5b`) then produced a plan, a branch, and a PR draft. That plan is generic. It shows the loop runs on the machine. It is not a quality claim for the default 14B model. The cast is `docs/demo.cast`.

## What we are not claiming

- A benchmark of the 14B model. The tests use a stand-in for the model call so CI does not download weights.
- A live Jira project or a GitHub PR opened by the agent in CI. Those paths exist and are refused on purpose while the switch is on.
- That the research skill browses the web. It writes from the ticket and the repo.
- Production logos, revenue, or a deployed design-partner count.

## How a first pilot looks

1. A workstation or a server that can hold the model (about 16 GB RAM for the default 14B; smaller tags run on less).
2. `L3MN05_OFFLINE=1` for the first week, ticket supplied as a file, branch reviewed by their engineer.
3. Turn Jira and GitHub back on only if their policy allows those two connections. The model stays local either way.

The demo script is `docs/DEMO.md`. Two or three minutes: switch on, a public URL refused, a local ticket in, a branch and a PR draft out.

## Ask

A design partner with a real constraint on where source code can go. We run L3MN05 on their hardware, on their ticket, with the offline switch on, and they review the branch. That is the pilot.
