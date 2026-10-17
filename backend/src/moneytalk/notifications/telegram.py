"""Envío por Telegram (Bot API). Crear el bot con @BotFather y obtener el chat_id
escribiéndole al bot y consultando https://api.telegram.org/bot<TOKEN>/getUpdates."""

import html
import logging

import httpx

from moneytalk.config import Settings

log = logging.getLogger(__name__)

MAX_LEN = 4000  # el límite de Telegram es 4096


class TelegramNotifier:
    def __init__(self, settings: Settings, http: httpx.Client | None = None) -> None:
        self._token = settings.telegram_bot_token
        self._chat_id = settings.telegram_chat_id
        self._http = http or httpx.Client(timeout=15)

    @property
    def enabled(self) -> bool:
        return bool(self._token and self._chat_id)

    def send(self, text_html: str) -> bool:
        if not self.enabled:
            log.info("Telegram no configurado; mensaje omitido")
            return False
        try:
            resp = self._http.post(
                f"https://api.telegram.org/bot{self._token}/sendMessage",
                json={
                    "chat_id": self._chat_id,
                    "text": text_html[:MAX_LEN],
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            # No loguear la URL: contiene el token del bot.
            log.warning("Telegram falló: %s", type(exc).__name__)
            return False
        return True


def esc(text: str) -> str:
    return html.escape(text, quote=False)
