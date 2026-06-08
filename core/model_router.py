# core/model_router.py

"""
Routes pipeline stages to appropriate model tiers.

Cheap model (fast, low cost):
- Gap matching — semantic similarity, not complex reasoning
- Evidence building — structured extraction from query results
- Schema summarisation

Expensive model (slow, high quality):
- SQL writing — requires accurate schema understanding
- Narration — requires sourced, precise language
- Reasoning — requires multi-step analytical thinking
"""

from config.settings import settings


def get_model_for_stage(stage: str) -> str:
    """
    Return the appropriate model for a given pipeline stage.
    Configured per provider — add new providers here.
    """
    provider = settings.llm_provider

    if provider == "groq":
        return _groq_router(stage)
    elif provider == "ollama":
        return _ollama_router(stage)
    elif provider == "anthropic":
        return settings.anthropic_model
    elif provider == "gemini":
        return settings.gemini_model
    else:
        return settings.groq_model


def _groq_router(stage: str) -> str:
    """
    Groq model routing:
    - Complex reasoning → llama-3.3-70b-versatile (expensive, accurate)
    - Simple extraction → llama-3.1-8b-instant (cheap, fast)
    """
    complex_stages = {
        "sql_writer",
        "narrator",
        "reasoning",
    }
    simple_stages = {
        "gap_matching",
        "evidence_builder",
        "vision_normaliser",
    }

    if stage in complex_stages:
        return "llama-3.3-70b-versatile"
    elif stage in simple_stages:
        return "llama-3.1-8b-instant"
    else:
        return "llama-3.3-70b-versatile"  # default to capable model


def _ollama_router(stage: str) -> str:
    """All Ollama stages use the configured model."""
    return settings.ollama_model