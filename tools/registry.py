# tools/registry.py
# Central tool registry — now imports cleanly from the tools/ package.

from typing import Dict, Any, Callable
from datetime import datetime

# All imports are now from the tools/ package
from tools.file import write_file
from tools.memory import load_memory, save_memory
from tools.git import git_commit_push
from tools.notion import publish_to_notion

TOOLS: Dict[str, Dict[str, Any]] = {}

def register_tool(name: str, func: Callable, description: str):
    TOOLS[name] = {"func": func, "description": description}
    print(f"[{datetime.now()}] [TOOLS] Registered: {name}")

# Register core tools
register_tool("write_file", write_file, "Write content to a file in the repo.")
register_tool("git_commit_push", git_commit_push, "Commit and push changes to the output repo.")
register_tool("notion_publish", publish_to_notion, "Publish markdown content to Notion.")
register_tool("load_memory", load_memory, "Load memory.json from output path.")
register_tool("save_memory", save_memory, "Save memory.json.")

def get_tool(name: str):
    return TOOLS.get(name)

def execute_tool(name: str, **kwargs):
    """Execute a registered tool."""
    tool = get_tool(name)
    if not tool:
        raise ValueError(f"Unknown tool: {name}")
    print(f"[{datetime.now()}] [TOOLS] Executing {name}")
    return tool["func"](**kwargs)