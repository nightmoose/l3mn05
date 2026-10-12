# l3mn05_slack.py - Fixed v2 (Feb 2026)
# Changes explained in comments below - everything else is exactly as you had it

import os
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from openai import OpenAI
import requests
import json   # added for safer tool parsing (no eval)

print("=== HORACE SLACK BOT STARTED ===")

app = App(token=os.environ["SLACK_BOT_TOKEN"])

GROK = OpenAI(base_url="https://api.x.ai/v1", api_key=os.environ["GROK_API_KEY"])
WORKER_URL = os.environ["WORKER_URL"]

SYSTEM_PROMPT = "You are Horace, a senior software/data engineering consultant who works directly with consulting clients. You are helpful, concise, and professional."

# Get our own user ID once at startup (helps skip self-replies)
try:
    auth = app.client.auth_test()
    BOT_USER_ID = auth["user_id"]
    print(f"✅ Connected as bot: {BOT_USER_ID}")
except Exception as e:
    print(f"⚠️ Could not get bot ID (non-fatal): {e}")
    BOT_USER_ID = None

# Shared logic so we don't duplicate the Grok call
def handle_horace_request(event, say):
    print(f"[PROCESSING] Channel: {event.get('channel')} Text: {event.get('text')[:100]}...")

    user_message = event.get("text", "").strip()
    channel_id = event["channel"]

    try:
        response = GROK.chat.completions.create(
            model="grok-4",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ],
            tools=[{
                "type": "function",
                "function": {
                    "name": "create_jira_ticket",
                    "description": "Create a new Jira ticket",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "description": {"type": "string"}
                        },
                        "required": ["title", "description"]
                    }
                }
            }]
        )

        msg = response.choices[0].message
        reply = msg.content or "Understood."

        if msg.tool_calls:
            tc = msg.tool_calls[0]
            if tc.function.name == "create_jira_ticket":
                args = json.loads(tc.function.arguments)  # safer than eval
                r = requests.post(f"{WORKER_URL}/create_ticket", json=args, timeout=15)
                result = r.json()
                reply += f"\n\n✅ Created ticket **{result.get('key')}** successfully!"

        say(text=reply, channel=channel_id)
        print(f"[REPLIED] Success to channel {channel_id}")

    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}")
        say(text=f"Error: {str(e)}", channel=channel_id)

# === NEW: handles @Horace mentions in any channel ===
@app.event("app_mention")
def handle_mention(event, say):
    print(f"[APP_MENTION RECEIVED] in channel {event.get('channel')}")
    handle_horace_request(event, say)

# === UPDATED: handles only DMs (ignores channel messages) ===
@app.event("message")
def handle_message(event, say):
    if event.get("channel_type") != "im":          # only direct messages
        return
    if event.get("bot_id") or (BOT_USER_ID and event.get("user") == BOT_USER_ID):
        return  # never reply to ourselves
    
    print(f"[DM RECEIVED] from user {event.get('user')}")
    handle_horace_request(event, say)

if __name__ == "__main__":
    print("=== Starting Socket Mode Handler ===")
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    handler.start()