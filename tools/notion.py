import os
import re
from datetime import datetime

from notion_client import Client

from utils.offline import is_offline, offline_message

def get_notion_client():
    if is_offline():
        print(offline_message("Notion"))
        return None
    api_key = os.getenv("NOTION_API_KEY")
    if not api_key:
        print(f"[{datetime.now()}] [VIOLET] No NOTION_API_KEY in env - falling back to markdown")
        return None
    try:
        client = Client(auth=api_key)
        client.users.me()  # quick validation
        print(f"[{datetime.now()}] [VIOLET] Notion client authenticated")
        return client
    except Exception as e:
        print(f"[{datetime.now()}] [VIOLET] Notion auth failed: {e}")
        return None
    
def publish_to_notion(config, title, content, parent_id):
    if is_offline():
        print(offline_message("Notion publishing"))
        return None
    api_key_env = config["notion"]["api_key_env"]
    api_key = os.getenv(api_key_env)
    if not api_key:
        print("[PUBLISH] No Notion API key — skipping")
        return None

    notion = Client(auth=api_key)  # REMOVED duplicate 'from notion_client import Client' inside function (already imported at top)

    try:
        page = notion.pages.create(
            parent={"page_id": parent_id},
            properties={
                "title": {"title": [{"text": {"content": title}}]}
            },
            children=[  # basic block — expand with your real block converter if needed
                {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": content[:2000]}}]}}
            ]
        )
        url = page["url"]
        print(f"[PUBLISH] Created Notion page: {url}")
        return url
    except Exception as e:
        print(f"[PUBLISH] Notion error: {str(e)}")
        return None

def markdown_to_notion_blocks(md_content):
    """Convert markdown to Notion blocks - splits long paragraphs to avoid 2000 char limit."""
    blocks = []
    lines = md_content.splitlines()
    current_para_lines = []  # Buffer lines for current paragraph

    MAX_RICH_TEXT_LEN = 1900  # Safety margin under 2000

    def flush_para():
        if not current_para_lines:
            return
        # Join lines, but split into chunks if too long
        full_text = "\n".join(current_para_lines).strip()
        if not full_text:
            current_para_lines.clear()
            return

        # Split into chunks ≤ MAX_RICH_TEXT_LEN
        while full_text:
            chunk = full_text[:MAX_RICH_TEXT_LEN]
            # Try to split on last newline or space to avoid mid-word cut
            last_break = chunk.rfind("\n")
            if last_break == -1:
                last_break = chunk.rfind(" ")
            if last_break > 0:
                chunk = chunk[:last_break]
                full_text = full_text[last_break:].lstrip()
            else:
                full_text = full_text[len(chunk):].lstrip()

            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": chunk}}]
                }
            })

        current_para_lines.clear()

    in_list = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush_para()
            continue

        if stripped.startswith(("# ", "## ", "### ")):
            flush_para()
            level = stripped.count("#", 0, 3)
            text = stripped[level+1:].strip()
            block_type = f"heading_{level}"
            heading_key = f"heading_{level}"  # IMPROVED: clearer variable (was ugly .format in dict key) - exactly the same runtime result
            blocks.append({
                "object": "block",
                "type": block_type,
                heading_key: {"rich_text": [{"type": "text", "text": {"content": text}}]}
            })
        elif stripped.startswith(("- ", "* ")):
            flush_para()
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": stripped[2:].strip()}}]}
            })
        elif re.match(r'^\d+\.\s', stripped):
            flush_para()
            content = re.sub(r'^\d+\.\s*', '', stripped)
            blocks.append({
                "object": "block",
                "type": "numbered_list_item",
                "numbered_list_item": {"rich_text": [{"type": "text", "text": {"content": content}}]}
            })
        else:
            # Regular text → buffer
            current_para_lines.append(stripped)

    flush_para()  # final flush

    return blocks