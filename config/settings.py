# config/settings.py

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    # ── ONE LINE TO SWITCH PROVIDER ──────────────────────────────
    # "gemini" | "groq" | "anthropic" | "ollama"
    llm_provider: str = os.getenv("LLM_PROVIDER", "gemini")

    # ── Vision provider (must support image input) ───────────────
    # "gemini" | "anthropic"  (groq and ollama don't support vision)
    vision_provider: str = os.getenv("VISION_PROVIDER", "gemini")

    # ── Gemini ───────────────────────────────────────────────────
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    # ── Groq ─────────────────────────────────────────────────────
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    # ── Anthropic ────────────────────────────────────────────────
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

    # ── Ollama (local) ───────────────────────────────────────────
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.2")
    ollama_vision_model: str = os.getenv("OLLAMA_VISION_MODEL", "llava")

    # ── Shared ───────────────────────────────────────────────────
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.2"))
    llm_max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "2048"))

    # ── Database ─────────────────────────────────────────────────
    postgres_url: str = os.getenv(
        "POSTGRES_URL",
        "postgresql://postgres:postgres@localhost:5432/watchdog"
    )

    # ── Dashboard source ─────────────────────────────────────────
    # "snapshot" | "metabase" | "grafana" | "redash"
    dashboard_source: str = os.getenv("DASHBOARD_SOURCE", "snapshot")

    # ── Delivery ─────────────────────────────────────────────────
    email_enabled: bool = os.getenv("EMAIL_ENABLED", "false").lower() == "true"
    slack_enabled: bool = os.getenv("SLACK_ENABLED", "false").lower() == "true"
    slack_webhook_url: str = os.getenv("SLACK_WEBHOOK_URL", "")
    smtp_host: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    alert_recipients: list[str] = None

    def __post_init__(self):
        recipients = os.getenv("ALERT_RECIPIENTS", "")
        self.alert_recipients = [
            r.strip() for r in recipients.split(",") if r.strip()
        ]


settings = Settings()