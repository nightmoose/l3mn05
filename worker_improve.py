from utils.worker_core import run_main_loop
from orchestrators import run_multi_agent_orchestration

def do_improvements(issue_data, client_id, config):
    run_multi_agent_orchestration(issue_data, client_id, config, mode="improve")

if __name__ == "__main__":
    run_main_loop(do_improvements, "improve_jql", "improve")