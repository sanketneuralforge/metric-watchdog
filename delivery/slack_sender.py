# delivery/slack_sender.py

"""
Slack delivery via incoming webhook.
One environment variable to switch on: SLACK_ENABLED=true

Setup:
1. Go to api.slack.com/apps
2. Create app → Incoming Webhooks → Add webhook to workspace
3. Copy webhook URL to SLACK_WEBHOOK_URL in .env
"""

import requests
from config.settings import settings


def send_briefing(briefing_text: str, severity: str = "WARNING") -> bool:
    """
    Send briefing to Slack via incoming webhook.
    Returns True if sent successfully.
    """
    if not settings.slack_enabled:
        print("  [slack] Slack disabled — skipping")
        return False

    if not settings.slack_webhook_url:
        print("  [slack] No webhook URL configured — skipping")
        return False

    # Slack color for attachment sidebar
    color = (
        "#dc2626" if severity == "CRITICAL"
        else "#d97706" if severity == "WARNING"
        else "#16a34a"
    )

    payload = {
        "attachments": [
            {
                "color": color,
                "text": briefing_text,
                "mrkdwn_in": ["text"],
            }
        ]
    }

    try:
        response = requests.post(
            settings.slack_webhook_url,
            json=payload,
            timeout=10,
        )
        response.raise_for_status()
        print("  [slack] Sent successfully")
        return True
    except Exception as e:
        print(f"  [slack] Failed: {e}")
        return False