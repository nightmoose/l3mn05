# skills_loader.py
# Loads open-standard Agent Skills from the skills/ directory.
# Each skill folder must contain SKILL.md with YAML frontmatter + instructions.
# Skills can declare allowed_tools for execution safety.
# Simple, robust, no heavy dependencies.

import os
import yaml
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

def load_skills(skills_dir: str = "skills") -> List[Dict[str, Any]]:
    """Load all valid skills. Returns list of dicts."""
    skills = []
    skills_path = Path(skills_dir)
    if not skills_path.exists():
        print(f"[{datetime.now()}] [SKILLS] Creating skills directory: {skills_dir}")
        skills_path.mkdir(parents=True, exist_ok=True)
        return skills

    for skill_folder in skills_path.iterdir():
        if not skill_folder.is_dir():
            continue
        skill_md = skill_folder / "SKILL.md"
        if not skill_md.exists():
            continue

        try:
            content = skill_md.read_text(encoding="utf-8")
            if content.startswith("---"):
                _, frontmatter, instructions = content.split("---", 2)
                metadata = yaml.safe_load(frontmatter.strip()) or {}
            else:
                metadata = {}
                instructions = content

            skill = {
                "name": metadata.get("name", skill_folder.name),
                "description": metadata.get("description", "No description provided."),
                "instructions": instructions.strip(),
                "version": metadata.get("version", "1.0"),
                "triggers": metadata.get("triggers", []),
                "allowed_tools": metadata.get("allowed_tools", ["write_file", "git_commit_push"]),
                "folder": str(skill_folder),
            }
            skills.append(skill)
            print(f"[{datetime.now()}] [SKILLS] Loaded skill: {skill['name']}")
        except Exception as e:
            print(f"[{datetime.now()}] [SKILLS] Failed to load {skill_folder.name}: {e} — skipping")

    print(f"[{datetime.now()}] [SKILLS] Total skills loaded: {len(skills)}")
    return skills