# llm.py — Flexible dual-LLM setup for Horace (Skills + Tools era)
# Primary: Local (Ollama)
# Secondary: Remote (any OpenAI-compatible endpoint)
# Full remote-only or local-only supported via config.

from openai import OpenAI
from datetime import datetime
import os

from utils.config import config

# ====================== LOCAL LLM ======================
LOCAL_MODEL = config.get("local_model", "qwen2.5-coder:14b")
local_client = OpenAI(
    base_url="http://ollama:11434/v1",
    api_key="ollama"
)

def call_local_llm(prompt: str, temperature: float = 0.1, max_tokens: int = None):
    """Always tries local first. Simple, fast path."""
    try:
        kwargs = {
            "model": LOCAL_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "timeout": 1800,
        }
        if max_tokens:
            kwargs["max_tokens"] = max_tokens

        response = local_client.chat.completions.create(**kwargs)
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[{datetime.now()}] [LOCAL-LLM] Failed ({LOCAL_MODEL}): {type(e).__name__} — falling back to remote if enabled")
        return None  # Signal to try remote


# ====================== REMOTE LLM ======================
def get_remote_client():
    """Build remote client from validation section."""
    val = config.get("validation", {})
    if not val.get("enabled", False):
        return None

    base_url = val.get("base_url")
    api_key = os.getenv(val.get("api_key_env"))
    model = val.get("model")

    if not base_url or not api_key or not model:
        print(f"[{datetime.now()}] [REMOTE] Config incomplete — skipping remote")
        return None

    return OpenAI(base_url=base_url, api_key=api_key), model


remote_client_info = get_remote_client()  # cached at import


def call_remote_llm(prompt: str, temperature: float = 0.1, max_tokens: int = 4000):
    """Direct remote call. Used for quality boosts and fallbacks."""
    if not remote_client_info:
        return f"ERROR: Remote LLM disabled or misconfigured in config.yaml"

    client, model = remote_client_info
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=120
        )
        content = response.choices[0].message.content.strip()
        print(f"[{datetime.now()}] [REMOTE-LLM] Success from {model} ({len(content)} chars)")
        return content
    except Exception as e:
        print(f"[{datetime.now()}] [REMOTE-LLM] Failed: {type(e).__name__}")
        return f"ERROR: Remote LLM call failed: {str(e)[:200]}"


# ====================== MAIN ENTRY POINTS ======================
def call_llm(prompt: str, temperature: float = 0.1, prefer_remote: bool = False, max_tokens: int = None):
    """
    Main function used by Horace and skills.
    - prefer_remote=True  → use remote for high-quality steps (e.g. final-review, plan)
    - Normal flow          → local first, remote as fallback
    """
    if prefer_remote:
        print(f"[{datetime.now()}] [LLM] prefer_remote=True → using remote directly")
        return call_remote_llm(prompt, temperature, max_tokens or 4000)

    # Default: local primary
    result = call_local_llm(prompt, temperature, max_tokens)
    if result and not result.startswith("ERROR"):
        return result

    # Fallback to remote if local failed
    print(f"[{datetime.now()}] [LLM] Local failed — falling back to remote")
    return call_remote_llm(prompt, temperature, max_tokens or 4000)


def call_llm_with_review(prompt: str, temperature: float = 0.1):
    """Convenience: Get output + optional remote review in one go (used in horace_plan)."""
    output = call_llm(prompt, temperature=temperature)

    # Optional auto-review with remote (keeps quality high)
    if config.get("validation", {}).get("enabled", False):
        review_prompt = f"Review and improve this output for clarity, completeness, and correctness:\n\n{output}\n\nReturn the improved version only."
        improved = call_remote_llm(review_prompt, temperature=0.1, max_tokens=4000)
        if not improved.startswith("ERROR") and len(improved) > len(output) * 0.7:
            return improved

    return output