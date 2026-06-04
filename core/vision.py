# core/vision.py

"""
Single entry point for all vision LLM calls.
Switch provider with: VISION_PROVIDER=gemini|anthropic|ollama
Groq does not support vision — falls back to gemini if set to groq.
"""

import json
import base64
from pathlib import Path
from config.settings import settings

EXTRACTION_PROMPT = """
You are analyzing a business dashboard image.

Look at every chart, number, title, axis label, and legend visible.
Extract ALL metrics you can identify.

For EACH chart or metric visible:
1. Read the chart title or label
2. Find the most recent value (rightmost point or latest bar)
3. Look for any comparison text (vs last week, 7-day avg, etc)
4. Determine if the trend is going up, down, or flat

IMPORTANT: If you see a line going DOWN at the right side of a chart,
the direction is "down". If going UP, direction is "up".

Even if you cannot read exact numbers, estimate from the chart shape
and mark confidence as LOW.

Do NOT return empty metrics array. Always extract something.

Return ONLY valid JSON — no markdown, no preamble:
{
  "metrics": [
    {
      "name": "exact chart title or label",
      "value": "most recent value you can read or estimate",
      "unit": "$ or % or count",
      "direction": "up | down | flat | unknown",
      "comparison": "what it compares against if visible",
      "change_value": "absolute change if visible or null",
      "change_pct": "percentage change if visible or null",
      "confidence": "HIGH | MEDIUM | LOW"
    }
  ],
  "time_period": "date range shown on dashboard",
  "dashboard_title": "main title if visible",
  "charts_described": ["one line description of each chart"],
  "reading_notes": "anything unclear or hard to read"
}
"""


def read_dashboard_image(image_path: str) -> dict:
    """Read a dashboard screenshot. Routes to configured vision provider."""
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    image_bytes = path.read_bytes()
    mime_type = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    provider = settings.vision_provider

    # Groq doesn't support vision — warn and fall back to gemini
    if provider == "groq":
        print("  [vision] Groq doesn't support vision — falling back to gemini")
        provider = "gemini"

    if provider == "gemini":
        raw = _vision_gemini(image_bytes, mime_type)
    elif provider == "anthropic":
        raw = _vision_anthropic(image_bytes, mime_type)
    elif provider == "ollama":
        raw = _vision_ollama(image_bytes, mime_type)
    else:
        raise ValueError(f"Unknown vision provider: {provider}")

    return _parse_vision_output(raw)


def _vision_gemini(image_bytes: bytes, mime_type: str) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.gemini_api_key)
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=[
            EXTRACTION_PROMPT,
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
        ]
    )
    return response.text


def _vision_anthropic(image_bytes: bytes, mime_type: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=2048,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": mime_type,
                        "data": base64.b64encode(image_bytes).decode(),
                    },
                },
                {"type": "text", "text": EXTRACTION_PROMPT},
            ],
        }],
    )
    return response.content[0].text


def _vision_ollama(image_bytes: bytes, mime_type: str) -> str:
    import requests
    import base64

    response = requests.post(
        f"{settings.ollama_base_url}/api/generate",
        json={
            "model": settings.ollama_vision_model,
            "prompt": EXTRACTION_PROMPT,
            "images": [base64.b64encode(image_bytes).decode()],
            "stream": False,
        },
        timeout=500,
    )
    response.raise_for_status()
    return response.json()["response"]


def _parse_vision_output(raw: str) -> dict:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:-1])
    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start == -1 or end == 0:
        return {
            "metrics": [],
            "reading_notes": f"Parse error — raw: {cleaned[:200]}",
            "_parse_error": True,
        }
    try:
        return json.loads(cleaned[start:end])
    except json.JSONDecodeError as e:
        return {
            "metrics": [],
            "reading_notes": f"JSON error: {e}",
            "_parse_error": True,
        }