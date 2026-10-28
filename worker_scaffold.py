# worker_scaffold.py
# Updated for Skills + Tools refactor.
# Changes:
# - No longer imports old integrations or orchestrators in the old way
# - Uses the new run_multi_agent_orchestration from the refactored orchestrators.py
# - Extremely simple and consistent with worker_improve.py
# - The heavy lifting (skills discovery, LLM calls, tool execution) is all handled inside orchestrators.py
# - No code duplication, no brittle agent logic

from utils.worker_core import run_main_loop
from orchestrators import run_multi_agent_orchestration


def do_scaffolds(issue_data, client_id, config):
    """
    Entry point for scaffold mode.
    Simply delegates to the shared orchestration with mode="scaffold".
    All skill loading, planning, and execution happens in orchestrators.py.
    """
    run_multi_agent_orchestration(
        issue_data=issue_data,
        client_id=client_id,
        config=config,
        mode="scaffold"
    )


if __name__ == "__main__":
    import sys
    if "--demo" in sys.argv:
        from demo_run import main as demo_main
        raise SystemExit(demo_main([arg for arg in sys.argv[1:] if arg != "--demo"]))
    # Uses the shared run_main_loop from utils (polling + client handling)
    run_main_loop(do_scaffolds, "scaffold_jql", "scaffold")