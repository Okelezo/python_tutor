from __future__ import annotations

import os

import httpx


def _cfg() -> tuple[str, str, str]:
    base_url = os.environ.get("PYTUTOR_AI_BASE_URL") or "https://api.openai.com/v1"
    api_key = os.environ.get("PYTUTOR_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
    model = os.environ.get("PYTUTOR_AI_MODEL") or "gpt-4o-mini"
    return base_url, api_key, model


def ai_enabled() -> bool:
    _, api_key, _ = _cfg()
    return bool(api_key.strip())


def chat(
    prompt: str,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> str:
    base_url_cfg, api_key_cfg, model_cfg = _cfg()
    base_url = base_url or base_url_cfg
    api_key = (api_key or api_key_cfg).strip()
    model = model or model_cfg

    if not api_key:
        raise RuntimeError(
            "AI is not configured. Set PYTUTOR_OPENAI_API_KEY (or OPENAI_API_KEY) to enable AI hints/review."
        )

    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are a Python tutor. Be concise, practical, and guide the learner with hints instead of full answers unless asked.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }

    with httpx.Client(timeout=30) as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    try:
        return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return str(data)


def make_hint_prompt(*, exercise_title: str, prompt_md: str, code: str) -> str:
    return (
        f"Exercise: {exercise_title}\n\n"
        f"Prompt:\n{prompt_md}\n\n"
        f"Learner code:\n```python\n{code}\n```\n\n"
        "Give a short hint (no full solution). Point out the next step and one common mistake to avoid."
    )


def make_explain_prompt(*, exercise_title: str, prompt_md: str, code: str) -> str:
    return (
        f"Exercise: {exercise_title}\n\n"
        f"Prompt:\n{prompt_md}\n\n"
        f"Learner code:\n```python\n{code}\n```\n\n"
        "Explain what this code currently does, where it deviates from the prompt (if it does), and how to fix it."
    )


def make_review_prompt(*, exercise_title: str, code: str) -> str:
    return (
        f"Exercise: {exercise_title}\n\n"
        f"Code:\n```python\n{code}\n```\n\n"
        "Provide a code review focusing on correctness, readability, naming, edge cases, and pythonic style."
    )
