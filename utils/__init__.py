"""Light package init.

Do not import worker_core here. tools.git imports utils.config while that
module is still loading, and worker_core imports tools.git. Importing
worker_core from this file was a circular import that also broke
tools.registry (ImportError: get_repo_paths from a partially initialized
tools.git). Import the loop from utils.worker_core.
"""

from . import offline as _offline  # noqa: F401  installs the outbound-call guard
from .config import (
    config,
    config_file_path,
    get_agent_output_path,
    get_local_model,
    get_ollama_base_url,
    get_ollama_host,
    get_workspace,
    load_config,
    project_root,
    reset_config_cache,
)
from .offline import OfflineBlocked, install_network_guard, is_offline, offline_error, offline_message


def __getattr__(name):
    if name in ("run_main_loop", "run_worker_base"):
        from .worker_core import run_main_loop, run_worker_base
        return {"run_main_loop": run_main_loop, "run_worker_base": run_worker_base}[name]
    raise AttributeError(f"module 'utils' has no attribute {name}")
