"""
Notifications Module.

Handles all alert delivery:
- Telegram: Real-time signals and alerts
- Email: Daily summaries and important alerts
"""

from .telegram_bot import TelegramNotifier, send_telegram_alert
from .email_sender import EmailNotifier, send_email_alert

__all__ = [
    # Telegram
    "TelegramNotifier",
    "send_telegram_alert",
    # Email
    "EmailNotifier", 
    "send_email_alert",
]
