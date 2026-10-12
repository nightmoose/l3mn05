#!/bin/sh
# ollama-startup.sh - Auto-pull model on first run

if [ ! -d /root/.ollama/models/manifests/registry.ollama.ai/library/qwen2.5-coder ]; then
  echo '=== First time setup: Pulling qwen2.5-coder:14b (this may take 5-15 minutes) ==='
  ollama pull qwen2.5-coder:14b
  echo '=== Model pull complete ==='
else
  echo '=== qwen2.5-coder:14b already available ==='
fi

ollama serve