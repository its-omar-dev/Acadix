"""Groq client wrapper with the existing model fallback order."""
import threading
import time

from groq import Groq, RateLimitError

from acadix.ai.prompts import roadmap_prompt

MODELS = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
]
_lock = threading.Lock()
_resting = {}
_client = None
_client_key = None


def _get_client():
    global _client, _client_key
    from flask import current_app

    api_key = current_app.config.get("GROQ_API_KEY", "")
    if not api_key:
        return None
    if _client is None or _client_key != api_key:
        _client = Groq(api_key=api_key)
        _client_key = api_key
    return _client


def generate_roadmap(topic, level="مبتدئ"):
    """Generate the legacy Markdown roadmap; preserves the existing frontend contract."""
    client = _get_client()
    if client is None:
        return None

    prompt = roadmap_prompt(topic, level)
    now = time.time()
    for model in MODELS:
        with _lock:
            if _resting.get(model, 0) > now:
                continue
        try:
            extra = {"extra_body": {"reasoning_effort": "low"}} if "gpt-oss" in model else {}
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2200,
                **extra,
            )
            content = response.choices[0].message.content
            if content and content.strip():
                return content
        except RateLimitError:
            with _lock:
                _resting[model] = now + 600
        except Exception:
            continue
    return None


def all_models_busy():
    now = time.time()
    with _lock:
        return all(_resting.get(model, 0) > now for model in MODELS)
