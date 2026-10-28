from utils.worker_core import run_main_loop
from orchestrators import run_multi_agent_orchestration

def do_reviews(issue_data, client_id, config):
    run_multi_agent_orchestration(issue_data, client_id, config, mode="review")

if __name__ == "__main__":
    run_main_loop(do_reviews, "review_jql", "review")