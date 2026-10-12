#!/bin/bash
# install.sh - L3MN05 Horace v0.8.1 One-Command Installer
# Simple, complete, no new problems. Installs the clean stack:
# - ollama (processing)
# - l3mn05-worker (ticket creation + agent)
# - horace-chat (Grok-powered UI on port 8080)

set -e

echo "🚀 Installing L3MN05 Horace (simplified Grok chat + local agent)..."

# 1. Create project folder if it doesn't exist
mkdir -p ~/l3mn05
cd ~/l3mn05

# 2. Download the latest clean files from your repo (or we can embed them)
echo "📥 Pulling latest clean files..."
git pull || git clone https://github.com/nightmoose/l3mn05.git .
[ -f config.yaml ] || cp config.example.yaml config.yaml

# 3. Create .env if missing
if [ ! -f .env ]; then
    echo "Creating .env file..."
    cat > .env << EOF
REMOTE_API_KEY=your_xai_key_here   # optional: only for remote validation and the chat/Slack front-ends
GITHUB_TOKEN=your_github_token_here
JIRA_API_TOKEN=your_jira_token_here
EOF
    echo "✅ .env created. Please edit it with your keys before running."
    nano .env
fi

# 4. Make sure all files are present and executable
chmod +x install.sh setup-horace.sh 2>/dev/null || true

# 5. Build and start
echo "🐳 Building and starting containers..."
docker compose down --remove-orphans 2>/dev/null || true
docker compose build --no-cache
docker compose up -d

echo ""
echo "✅ L3MN05 Horace is ready!"
echo "🌐 Open your browser to: http://localhost:8080"
echo "   (or your Tailscale IP:8080)"
echo ""
echo "Horace is now using Grok for conversation and your local Ollama worker for ticket processing."
echo "Just type to him like a real consultant. Say 'create a new ticket...' when ready."
echo ""
echo "To stop: docker compose down"
echo "To update: git pull && ./install.sh"

# Auto-open browser on Mac
if [[ "$OSTYPE" == "darwin"* ]]; then
    open http://localhost:8080
fi