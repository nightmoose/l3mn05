# l3mn05_chat.py - Multi-Client FINAL (Feb 28 2026)
# Changes explained:
#   - Dropdown is ALWAYS visible (even with 1 or 2 clients)
#   - Added "Select client:" label + console debug (open F12 → Console to see it working)
#   - Reads clients dynamically from config.yaml (one entry per client)
#   - Everything else (chat history, Grok tool call, cost counter, Markdown) unchanged
# Simple, complete, no new problems.

from flask import Flask, render_template_string, request, jsonify, session
import os
import yaml
from openai import OpenAI
import markdown
import requests
import json
from datetime import timedelta  # NEW: For permanent session lifetime

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY") or "horace_fixed_secret_2026"  # NEW: Fixed key (env or fallback) to survive restarts
app.config['SESSION_PERMANENT'] = True  # NEW: Make sessions permanent
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)  # NEW: Sessions last 7 days

print("=== Horace Chat (Multi-Client FINAL) starting ===")

GROK_API_KEY = os.getenv("GROK_API_KEY")
WORKER_URL = os.getenv("WORKER_URL", "http://l3mn05-worker:5000")

with open("config.yaml") as f:
    CONFIG = yaml.safe_load(f)
CLIENTS = CONFIG.get("clients", {"example-client": {"name": "Example Client"}})

if not GROK_API_KEY:
    print("ERROR: GROK_API_KEY missing!")
    GROK = None
else:
    print(f"Grok API key loaded")
    GROK = OpenAI(base_url="https://api.x.ai/v1", api_key=GROK_API_KEY)

def estimate_cost(prompt_tokens, completion_tokens):
    return (prompt_tokens * 0.000005) + (completion_tokens * 0.000015)

HTML = """<!DOCTYPE html>
<html><head><title>Horace - Multi-Client</title>
<style>
body { font-family: system-ui; background: #0f172a; color: #e2e8f0; margin:0; padding:20px; }
#chat { max-width: 800px; margin: 40px auto; }
.message { margin: 15px 0; padding: 12px 16px; border-radius: 12px; max-width: 80%; line-height: 1.6; }
.user { background: #334155; margin-left: auto; }
.horace { background: #1e2937; }
select, input { width: 100%; padding: 14px; border-radius: 8px; border: none; background: #1e2937; color: white; font-size: 16px; margin-bottom: 10px; }
button { padding: 14px 24px; background: #3b82f6; border: none; border-radius: 8px; color: white; font-weight: bold; }
.cost { position:fixed;top:10px;right:10px;background:#1e2937;padding:8px 12px;border-radius:8px;font-size:14px; }
.label { margin-bottom: 5px; font-size: 14px; color: #94a3b8; }
</style>
</head>
<body>
<div class="cost">Cost so far: $<span id="cost">0.00</span></div>

<div class="label">Select client:</div>
<select id="client" onchange="selectClient()">
  <option>Loading clients...</option>
</select>

<div id="chat"></div>
<input id="input" placeholder="Ask Horace anything..." onkeypress="if(event.key==='Enter') send()">
<button onclick="send()">Send</button>

<script>
let history = [];
let currentClient = "example-client";

async function populateClients() {
  console.log("[Horace Chat] populateClients started");
  const select = document.getElementById('client');
  select.innerHTML = '';

  try {
    const res = await fetch('/clients');
    const clients = await res.json();
    console.log("[Horace Chat] Clients from server:", clients);

    for (let key in clients) {
      const opt = document.createElement('option');
      opt.value = key;
      opt.textContent = clients[key];
      if (key === currentClient) opt.selected = true;
      select.appendChild(opt);
    }
    console.log("[Horace Chat] Dropdown ready with", Object.keys(clients).length, "clients");
  } catch (e) {
    console.error('[Horace Chat] Fetch failed:', e);
    const opt = document.createElement('option');
    opt.value = 'example-client';
    opt.textContent = 'Default Client';
    select.appendChild(opt);
  }
}
populateClients();

function selectClient() {
  currentClient = document.getElementById('client').value;
  console.log("[Horace Chat] Switched client to:", currentClient);
}

async function send() {
  const input = document.getElementById('input');
  const text = input.value.trim();
  if (!text) return;
  add(text, 'user');
  input.value = '';

  const res = await fetch('/chat', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({message: text, history: history, client_id: currentClient})
  });
  const data = await res.json();
  add(data.reply, 'horace');
  history = data.history;
  document.getElementById('cost').textContent = data.cost.toFixed(4);
}

function add(msg, role) {
  const div = document.createElement('div');
  div.className = `message ${role}`;
  div.innerHTML = `<strong>${role==='user'?'You':'Horace'}:</strong> ${msg}`;
  document.getElementById('chat').appendChild(div);
  window.scrollTo(0, document.body.scrollHeight);
}
</script>
</body></html>
"""

@app.route('/')
def home():
    if 'cost' not in session:
        session['cost'] = 0.0
    if 'current_client' not in session:
        session["current_client"] = "example-client"
    return render_template_string(HTML)

@app.route('/clients')
def get_clients():
    client_options = {cid: c['name'] for cid, c in CLIENTS.items()}
    return jsonify(client_options)

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    message = data['message']
    history = data.get('history', [])
    client_id = data.get('client_id', session.get("current_client", "example-client"))
    session['current_client'] = client_id

    try:
        messages = [
            {"role": "system", "content": f"You are Horace, senior consultant working for {CLIENTS[client_id]['name']}. Be helpful, concise, professional."}
        ] + history + [{"role": "user", "content": message}]

        response = GROK.chat.completions.create(
            model="grok-4",
            messages=messages,
            tools=[{
                "type": "function",
                "function": {
                    "name": "create_jira_ticket",
                    "description": "Create a new Jira ticket for the selected client",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "client_id": {"type": "string", "default": client_id}
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
                args.setdefault("client_id", client_id)
                print(f"[TOOL] Creating ticket for client {client_id}")
                r = requests.post(f"{WORKER_URL}/create_ticket", json=args, timeout=15)
                result = r.json()
                reply += f"\n\n✅ Created ticket **{result.get('key')}** for {CLIENTS[client_id]['name']}!"

        reply_html = markdown.markdown(reply, extensions=['tables', 'fenced_code'])

        session['cost'] += estimate_cost(300, 200)

        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": reply})

        return jsonify({"reply": reply_html, "history": history, "cost": session['cost']})

    except Exception as e:
        print(f"[ERROR] {e}")
        return jsonify({"reply": f"Error: {str(e)}", "history": history, "cost": session.get('cost', 0)})

print("=== Horace Chat ready on http://localhost:8080 ===")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)