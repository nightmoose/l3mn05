# Local model first. Remote validation is optional and stays off in offline mode.
# The Ollama URL is not hard-coded: OLLAMA_BASE_URL, then config ollama_base_url,
# then http://127.0.0.1:11434/v1. Docker Compose sets the URL to http://ollama:11434/v1.

from datetime import datetime
import os

from openai import OpenAI

from utils.config import config, get_local_model, get_ollama_base_url, load_config
from utils.offline import is_offline, offline_error

_local_client = None
_local_client_url = None


def _get_local_client():
    global _local_client, _local_client_url
    url = get_ollama_base_url()
    if _local_client is None or _local_client_url != url:
        _local_client = OpenAI(base_url=url, api_key="ollama")
        _local_client_url = url
    return _local_client


def call_local_llm(prompt: str, temperature: float = 0.1, max_tokens: int = None):
    """Call the configured local model. Returns None if it is unreachable."""
    model = get_local_model()
    try:
        kwargs = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "timeout": 1800,
            # Unbounded generation on a small local context loops until the
            # server errors. Callers can pass a tighter max_tokens.
            "max_tokens": max_tokens or 2048,
        }

        response = _get_local_client().chat.completions.create(**kwargs)
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[{datetime.now()}] [LOCAL-LLM] Failed ({model} @ {get_ollama_base_url()}): {type(e).__name__}")
        if is_offline():
            print(f"[{datetime.now()}] [LOCAL-LLM] Offline mode: not falling back to a remote model")
        return None


def get_remote_client():
    """Build a remote client from the validation section. None when disabled or offline."""
    if is_offline():
        return None

    val = load_config().get("validation", {}) or {}
    if not val.get("enabled", False):
        return None

    base_url = val.get("base_url")
    api_key_env = val.get("api_key_env")
    api_key = os.getenv(api_key_env) if api_key_env else None
    model = val.get("model")

    if not base_url or not api_key or not model:
        print(f"[{datetime.now()}] [REMOTE] Config incomplete — skipping remote")
        return None

    return OpenAI(base_url=base_url, api_key=api_key), model


def call_remote_llm(prompt: str, temperature: float = 0.1, max_tokens: int = 4000):
    """Direct remote call. Used for quality boosts and fallbacks."""
    if is_offline():
        message = offline_error("Remote validation")
        print(f"[{datetime.now()}] [REMOTE-LLM] {message}")
        return message

    remote = get_remote_client()
    if not remote:
        return "ERROR: Remote LLM disabled or misconfigured in config.yaml"

    client, model = remote
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=120,
        )
        content = response.choices[0].message.content.strip()
        print(f"[{datetime.now()}] [REMOTE-LLM] Success from {model} ({len(content)} chars)")
        return content
    except Exception as e:
        print(f"[{datetime.now()}] [REMOTE-LLM] Failed: {type(e).__name__}")
        return f"ERROR: Remote LLM call failed: {str(e)[:200]}"


def call_llm(prompt: str, temperature: float = 0.1, prefer_remote: bool = False, max_tokens: int = None):
    """
    Main entry used by the orchestrator.
    - prefer_remote=True asks for the remote model (planning / final review).
    - Otherwise local first, remote only as a fallback when remote validation is configured.
    Offline mode always stays on the local model and never opens a remote call.
    """
    if is_offline():
        if prefer_remote:
            print(f"[{datetime.now()}] [LLM] Offline mode: ignoring remote preference. Using the local model.")
        result = call_local_llm(prompt, temperature, max_tokens)
        if result and not str(result).startswith("ERROR"):
            return result
        return offline_error("The local model is unavailable, and remote fallback")

    if prefer_remote:
        print(f"[{datetime.now()}] [LLM] prefer_remote=True → using remote directly")
        return call_remote_llm(prompt, temperature, max_tokens or 4000)

    result = call_local_llm(prompt, temperature, max_tokens)
    if result and not str(result).startswith("ERROR"):
        return result

    print(f"[{datetime.now()}] [LLM] Local failed — falling back to remote")
    return call_remote_llm(prompt, temperature, max_tokens or 4000)


def call_llm_with_review(prompt: str, temperature: float = 0.1):
    """Output plus an optional remote review. The review is skipped offline."""
    output = call_llm(prompt, temperature=temperature)

    if is_offline():
        return output

    if config.get("validation", {}).get("enabled", False):
        review_prompt = (
            "Review and improve this output for clarity, completeness, and correctness:\n\n"
            f"{output}\n\nReturn the improved version only."
        )
        improved = call_remote_llm(review_prompt, temperature=0.1, max_tokens=4000)
        if improved and not improved.startswith("ERROR") and len(improved) > len(output) * 0.7:
            return improved

    return output
