# core/llm.py

"""
Single entry point for all text LLM calls.
Switch provider with one env variable: LLM_PROVIDER=gemini|groq|anthropic|ollama
"""

import json
import time
import os
from config.settings import settings


# core/llm.py — update call_llm signature

def call_llm(
    system_prompt: str,
    user_message: str,
    mode: str = "unknown",
    stage: str = "default",          # ← new
    temperature: float | None = None,
    max_retries: int = 3,
    max_tokens: int | None = None,
) -> str:
    """Route to the configured LLM provider with model routing."""
    from core.model_router import get_model_for_stage
    temp = temperature if temperature is not None else settings.llm_temperature
    provider = os.getenv("LLM_PROVIDER", settings.llm_provider)
    model = get_model_for_stage(stage)

    for attempt in range(max_retries):
        try:
            if provider == "gemini":
                return _call_gemini(system_prompt, user_message, temp, model)
            elif provider == "groq":
                return _call_groq(system_prompt, user_message, temp, model, max_tokens)
            elif provider == "anthropic":
                return _call_anthropic(system_prompt, user_message, temp, model)
            elif provider == "ollama":
                return _call_ollama(system_prompt, user_message, temp)
            else:
                raise ValueError(f"Unknown LLM provider: {provider}")
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            wait = (2 ** attempt) + 0.5
            print(f"  [llm] {provider} retry {attempt+1}/{max_retries} "
                  f"— waiting {wait:.1f}s — error: {e}")
            time.sleep(wait)

    raise RuntimeError(f"LLM call failed after {max_retries} retries")


def _call_gemini(system_prompt: str, user_message: str, temperature: float) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.gemini_api_key)
    response = client.models.generate_content(
        model=settings.gemini_model,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
            max_output_tokens=settings.llm_max_tokens,
        ),
        contents=user_message,
    )
    return response.text


def _call_groq(
    system_prompt: str,
    user_message: str,
    temperature: float,
    model: str | None = None,
    max_tokens: int | None = None,
) -> str:
    from groq import Groq
    import os
    api_key = os.getenv("GROQ_API_KEY", settings.groq_api_key)
    if not api_key:
        raise ValueError("GROQ_API_KEY not set")
    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=model or settings.groq_model,
        temperature=temperature,
        max_tokens=max_tokens or 2048,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )
    return response.choices[0].message.content


def _call_anthropic(system_prompt: str, user_message: str, temperature: float) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=settings.llm_max_tokens,
        temperature=temperature,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return response.content[0].text


def _call_ollama(system_prompt: str, user_message: str, temperature: float) -> str:
    import requests
    response = requests.post(
        f"{settings.ollama_base_url}/api/generate",
        json={
            "model": settings.ollama_model,
            "prompt": f"{system_prompt}\n\n{user_message}",
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": settings.llm_max_tokens,
            },
        },
        timeout=200,
    )
    response.raise_for_status()
    return response.json()["response"]


def parse_json_response(raw: str) -> dict:
    import re
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:-1])
    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON found in: {cleaned[:200]}")
    json_str = cleaned[start:end]
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        # Fix literal newlines inside string values
        json_str = re.sub(
            r'("(?:[^"\\]|\\.)*")',
            lambda m: m.group(0).replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t'),
            json_str
        )
        return json.loads(json_str)