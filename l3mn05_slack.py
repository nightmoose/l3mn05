# l3mn05_slack.py
# Slack bot. With L3MN05_OFFLINE=1 it does not connect to Slack or to a remote model.

import os
import json

from utils.offline import install_network_guard, is_offline, offline_message

install_network_guard()

print("=== HORACE SLACK BOT STARTED ===")

SYSTEM_PROMPT = "You are Horace, a senior software/data engineering consultant who works directly with consulting clients. You are helpful, concise, and professional."


def _idle_if_container():
    if os.getenv("L3MN05_CONTAINER") == "1":
        import time
        print("Container will stay idle so Docker does not restart-loop. Unset L3MN05_OFFLINE to connect.")
        while True:
            time.sleep(3600)


def run_bot():
    """Start the bot, or return 0 immediately when offline (unless running in Docker)."""
    if is_offline():
        print(offline_message("The Slack bot (it connects to Slack and a remote model)"))
        print("Engineering workers keep using the local model. This process will not open a socket to Slack.")
        _idle_if_container()
        return 0

    from slack_bolt import App
    from slack_bolt.adapter.socket_mode import SocketModeHandler
    from openai import OpenAI
    import requests

    app = App(token=os.environ["SLACK_BOT_TOKEN"])
    grok = OpenAI(base_url="https://api.x.ai/v1", api_key=os.environ["GROK_API_KEY"])
    worker_url = os.environ["WORKER_URL"]

    try:
        auth = app.client.auth_test()
        bot_user_id = auth["user_id"]
        print(f"✅ Connected as bot: {bot_user_id}")
    except Exception as e:
        print(f"⚠️ Could not get bot ID (non-fatal): {e}")
        bot_user_id = None

    def handle_horace_request(event, say):
        print(f"[PROCESSING] Channel: {event.get('channel')} Text: {event.get('text', '')[:100]}...")

        user_message = event.get("text", "").strip()
        channel_id = event["channel"]

        try:
            response = grok.chat.completions.create(
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
                    args = json.loads(tc.function.arguments)
                    result = requests.post(f"{worker_url}/create_ticket", json=args, timeout=15).json()
                    reply += f"\n\n✅ Created ticket **{result.get('key')}** successfully!"

            say(text=reply, channel=channel_id)
            print(f"[REPLIED] Success to channel {channel_id}")

        except Exception as e:
            print(f"[ERROR] {type(e).__name__}: {e}")
            say(text=f"Error: {str(e)}", channel=channel_id)

    @app.event("app_mention")
    def handle_mention(event, say):
        print(f"[APP_MENTION RECEIVED] in channel {event.get('channel')}")
        handle_horace_request(event, say)

    @app.event("message")
    def handle_message(event, say):
        if event.get("channel_type") != "im":
            return
        if event.get("bot_id") or (bot_user_id and event.get("user") == bot_user_id):
            return
        print(f"[DM RECEIVED] from user {event.get('user')}")
        handle_horace_request(event, say)

    print("=== Starting Socket Mode Handler ===")
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    handler.start()
    return 0


if __name__ == "__main__":
    raise SystemExit(run_bot())
