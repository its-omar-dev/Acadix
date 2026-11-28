"""Groq client wrapper with the existing model fallback order."""
import threading
import time

from groq import Groq, RateLimitError

from acadix.ai.prompts import roadmap_prompt, streaming_roadmap_prompt

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



def stream_roadmap(topic, level="مبتدئ"):
    """Yield model text deltas; retry another model only before emitting output."""
    client = _get_client()
    if client is None:
        return

    prompt = streaming_roadmap_prompt(topic, level)
    now = time.time()
    for model in MODELS:
        with _lock:
            if _resting.get(model, 0) > now:
                continue
        received = False
        try:
            extra = {"extra_body": {"reasoning_effort": "low"}} if "gpt-oss" in model else {}
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2200,
                stream=True,
                **extra,
            )
            for chunk in response:
                choices = getattr(chunk, "choices", None) or []
                if not choices:
                    continue
                delta = getattr(choices[0], "delta", None)
                content = getattr(delta, "content", None) if delta else None
                if content:
                    received = True
                    yield content
            if received:
                return
        except RateLimitError:
            with _lock:
                _resting[model] = now + 600
            if received:
                raise
        except Exception:
            if received:
                raise
            continue

TUTOR_MODES = {
    "simple": "اشرح ببساطة شديدة وبجمل قصيرة، وافترض أن الطالب مبتدئ.",
    "steps": "اشرح خطوة بخطوة، ولا تنتقل للخطوة التالية قبل توضيح الحالية.",
    "examples": "استخدم أمثلة عملية وتشبيهات من الحياة اليومية لتوضيح الفكرة.",
    "quiz": "حوّل الموضوع إلى تدريب تفاعلي: اسأل سؤالاً واحداً في كل مرة، وانتظر إجابة الطالب ثم صححها.",
    "socratic": "استخدم أسلوب سقراط: لا تعطِ الحل مباشرة، بل وجّه الطالب بأسئلة وتلميحات تدريجية."
}


def chat_with_tutor(messages, mode="simple", topic=""):
    """Answer one bounded tutoring turn using the existing Groq key and model fallback."""
    client = _get_client()
    if client is None:
        return None

    style = TUTOR_MODES.get(mode, TUTOR_MODES["simple"])
    system_prompt = (
        "أنت المدرّس الذكي في منصة Acadix. مهمتك تعليم الطالب لا مجرد إعطائه الإجابة. "
        "أجب باللغة العربية ما لم يطلب الطالب لغة أخرى. "
        "كن دقيقاً، منظماً، مشجعاً، ولا تخترع حقائق أو مصادر. "
        "إذا لم تعرف فقل ذلك بوضوح. استخدم أمثلة مناسبة لمستوى الطالب، "
        "وقسّم الشرح الطويل إلى أجزاء صغيرة. لا تدّعِ أنك نفذت كوداً أو تحققت من نتيجة لم تنفذها. "
        f"أسلوب الشرح المطلوب: {style} "
        f"الموضوع الذي يتعلمه الطالب (إن وجد): {topic[:120]}"
    )
    now = time.time()
    for model in MODELS:
        with _lock:
            if _resting.get(model, 0) > now:
                continue
        try:
            extra = {"extra_body": {"reasoning_effort": "low"}} if "gpt-oss" in model else {}
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system_prompt}, *messages],
                temperature=0.6,
                max_tokens=1000,
                **extra,
            )
            content = response.choices[0].message.content
            if content and content.strip():
                return content.strip()
        except RateLimitError:
            with _lock:
                _resting[model] = now + 600
        except Exception:
            continue
    return None
