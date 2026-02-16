"""
Lightweight notification module using ntfy.sh.

Setup:
  1. Install the ntfy app on your phone (iOS / Android)
  2. Subscribe to a topic of your choosing (e.g. "adrian-trades")
  3. Set NTFY_TOPIC=adrian-trades and NTFY_ENABLED=on in .env

Usage:
  from notify import send
  send("NVDA crossed above 200-day MA", title="Trade Signal")
"""

import requests
from config import NTFY_TOPIC, NTFY_ENABLED


def send(message: str, *, title: str = "IBKR Alert", priority: int = 3, tags: str = "chart_with_upwards_trend"):
    """
    Send a push notification via ntfy.sh.

    Args:
        message: The notification body.
        title:   Notification title.
        priority: 1 (min) to 5 (max urgent). 3 = default.
        tags:    Comma-separated emoji shortcodes for the notification icon.
    """
    if not NTFY_ENABLED:
        print(f"  [notify OFF] {title}: {message}")
        return False

    if not NTFY_TOPIC:
        print("  [notify] NTFY_TOPIC not set in .env — skipping.")
        return False

    url = f"https://ntfy.sh/{NTFY_TOPIC}"

    try:
        resp = requests.post(url, json={
            "topic": NTFY_TOPIC,
            "title": title,
            "message": message,
            "priority": priority,
            "tags": [tags],
        }, timeout=10)

        if resp.status_code == 200:
            print(f"  [notify] Sent: {title}")
            return True
        print(f"  [notify] Unexpected status: {resp.status_code}")
        return False
    except Exception as e:
        print(f"  [notify] Failed: {e}")
        return False
