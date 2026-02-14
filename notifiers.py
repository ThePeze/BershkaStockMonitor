from __future__ import annotations

import httpx

class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str, timeout_seconds: float = 20.0) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.timeout_seconds = timeout_seconds

    def send(self, text: str) -> None:
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        # short-lived request; no need to reuse a client here, but you can later if you want
        r = httpx.post(url, json=payload, timeout=self.timeout_seconds)
        r.raise_for_status()