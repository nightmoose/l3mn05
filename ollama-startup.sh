#!/bin/sh
# ollama-startup.sh - serve the local model. Do not pull one while offline.

MODEL="${OLLAMA_MODEL:-qwen2.5-coder:14b}"

if [ "${L3MN05_OFFLINE}" = "1" ] || [ "${L3MN05_OFFLINE}" = "true" ] || [ "${L3MN05_OFFLINE}" = "yes" ]; then
  echo "=== L3MN05 offline mode: not contacting the model registry ==="
  echo "=== Only a model already on disk can serve ==="
  # The Ollama daemon otherwise refreshes recommendation data from ollama.com.
  export OLLAMA_NO_CLOUD=1
  exec ollama serve
fi

case "$MODEL" in
  qwen2.5-coder:14b|qwen2.5-coder)
    if [ ! -d /root/.ollama/models/manifests/registry.ollama.ai/library/qwen2.5-coder ]; then
      echo "=== First time setup: Pulling ${MODEL} (this may take 5-15 minutes) ==="
      ollama pull "$MODEL"
      echo "=== Model pull complete ==="
    else
      echo "=== ${MODEL} already available ==="
    fi
    ;;
  *)
    echo "=== Pulling ${MODEL} ==="
    ollama pull "$MODEL"
    ;;
esac

exec ollama serve
