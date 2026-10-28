#!/usr/bin/env python3
"""Local demo: one ticket file in, a branch and a PR draft out.

Examples:
  L3MN05_OFFLINE=1 python demo_run.py
  python demo_run.py --ticket demo/sample_ticket.json --repo /tmp/l3mn05-demo
  python worker_scaffold.py --demo

By default the offline switch is turned on when L3MN05_OFFLINE is unset, so a
demo does not call a remote model, Jira, Notion, Slack, or GitHub.
Pass --allow-remote to leave remote fallback available.
"""

import argparse
import os

from demo_mode import SAMPLE_TICKET, run_demo


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run one local ticket through L3MN05 (no Jira).")
    parser.add_argument("--ticket", default=str(SAMPLE_TICKET), help="Path to a ticket JSON file.")
    parser.add_argument("--repo", default=None, help="Working repo. Default: .demo-run/ in this project.")
    parser.add_argument("--execute", action="store_true", help="After the plan, run each parsed skill step.")
    parser.add_argument(
        "--allow-remote",
        action="store_true",
        help="Do not force L3MN05_OFFLINE=1. Local model is still preferred.",
    )
    args = parser.parse_args(argv)

    if args.allow_remote:
        os.environ["L3MN05_OFFLINE"] = "0"
    elif not (os.getenv("L3MN05_OFFLINE") or "").strip():
        os.environ["L3MN05_OFFLINE"] = "1"

    print(f"L3MN05 demo")
    print(f"  offline: {os.environ.get('L3MN05_OFFLINE')}")
    print(f"  ticket:  {args.ticket}")
    print("  Jira is not contacted. The ticket is the local file.")

    result = run_demo(ticket_path=args.ticket, repo_dir=args.repo, execute=args.execute)
    print(result.get("message", ""))
    if not result.get("ok"):
        print("The local model did not return a plan. Start Ollama, or set OLLAMA_BASE_URL.")
        print("Offline mode will not fall back to a remote model.")
        return 2

    print(f"Branch:   {result['branch']}")
    print(f"Repo:     {result['repo']}")
    print(f"PR draft: {result['pr_draft']}")
    if result.get("offline"):
        print("GitHub was not contacted. Open PR_DRAFT.md for the title and body.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
