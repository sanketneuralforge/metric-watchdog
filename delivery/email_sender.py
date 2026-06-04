# delivery/email_sender.py

"""
Email delivery for the morning briefing.
Uses SMTP — works with Gmail, Outlook, or any SMTP server.

Gmail setup:
1. Enable 2FA on your Google account
2. Go to myaccount.google.com/apppasswords
3. Create an app password for "Mail"
4. Use that password as SMTP_PASSWORD in .env
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from config.settings import settings


def send_briefing(
    briefing_text: str,
    briefing_html: str,
    subject: str = None,
    recipients: list[str] = None,
) -> bool:
    """
    Send the morning briefing via email.
    Returns True if sent successfully, False otherwise.
    """
    if not settings.email_enabled:
        print("  [email] Email disabled — skipping")
        return False

    if not settings.smtp_user or not settings.smtp_password:
        print("  [email] SMTP credentials not configured — skipping")
        return False

    to = recipients or settings.alert_recipients
    if not to:
        print("  [email] No recipients configured — skipping")
        return False

    subject = subject or f"Metric Watchdog — Morning Briefing"

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.smtp_user
        msg["To"] = ", ".join(to)

        # Plain text fallback
        msg.attach(MIMEText(briefing_text, "plain"))
        # HTML version
        msg.attach(MIMEText(briefing_html, "html"))

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_user, to, msg.as_string())

        print(f"  [email] Sent to {', '.join(to)}")
        return True

    except Exception as e:
        print(f"  [email] Failed: {e}")
        return False