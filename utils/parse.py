import os
import re
from datetime import datetime
# Shared parsers/helpers moved here (no duplication)
def parse_implementation(raw_output):
    files = {}
    lines = raw_output.splitlines()
    i = 0
    current_file = None
    current_content = []

    while i < len(lines):
        line = lines[i].strip()

        # Flexible FILE: detection
        if any(p in line.upper() for p in ["FILE:", "# FILE:", "FILE ", "PATH:"]):
            if current_file:  # save previous
                files[current_file] = "\n".join(current_content).strip()
            current_file = line.split(":", 1)[1].strip() if ":" in line else "untitled.md"
            current_content = []
            i += 1
            # Skip opening ```
            if i < len(lines) and "```" in lines[i]:
                i += 1
            continue

        if current_file:
            current_content.append(lines[i])
        i += 1

    # Save last file
    if current_file:
        files[current_file] = "\n".join(current_content).strip()

    # Ultimate fallback: entire response as one file
    if not files and raw_output.strip():
        files["docs/full_output.md"] = raw_output.strip()

    print(f"[{datetime.now()}] [PARSE] Extracted {len(files)} files: {list(files.keys())}")
    return files