"""
Cabinet Telegram

Send a Telegram message using the Bot API.

Credentials live in Cabinet data under ``telegram``, similar to ``email`` for Mail.
``telegram.target`` matches diary-llm's chat id key.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

from prompt_toolkit import HTML, print_formatted_text

import cabinet

TELEGRAM_API_ROOT = "https://api.telegram.org"
DEFAULT_TIMEOUT = 10


def _config_str(cab: cabinet.Cabinet, *keys: str) -> str | None:
    """Return the first non-empty string from ``telegram.<key>``."""
    for key in keys:
        value = cab.get("telegram", key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


class Telegram:
    """
    Sends Telegram messages via ``https://api.telegram.org``.

    Reads ``telegram.bot_token`` (or ``telegram.token``) and ``telegram.target``
    (or ``telegram.chat_id``) from Cabinet data.
    """

    def __init__(self, cab: cabinet.Cabinet | None = None):
        self.cab = cab if cab is not None else cabinet.Cabinet()
        self.bot_token = _config_str(self.cab, "bot_token", "token")
        self.target = _config_str(self.cab, "target", "chat_id")

    def send(
        self,
        message: str,
        target: str | int | None = None,
        logging_enabled: bool = True,
        is_quiet: bool = False,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> bool:
        """
        Send ``message`` to ``target``, or to ``telegram.target`` when unset.

        Returns:
            True if Telegram accepted the message, False otherwise.
        """
        text = (message or "").strip()
        chat_id = str(target).strip() if target is not None else self.target
        error = None
        if not text:
            error = "Telegram message is empty"
        elif not chat_id:
            error = "cabinet -> telegram -> target is unset"
        elif not self.bot_token:
            error = "cabinet -> telegram -> bot_token is unset"
        if error:
            self.cab.log(error, level="error")
            return False

        parsed = self._post_send_message(chat_id, text, timeout)
        if parsed is None:
            return False
        if not parsed.get("ok"):
            description = str(parsed.get("description") or parsed)[:300]
            self.cab.log(
                f"Telegram API rejected the message: {description}",
                level="error",
            )
            return False

        if logging_enabled:
            self.cab.log(
                f"Sent Telegram message to {chat_id}: {text[:80]}",
                level="debug",
            )
        if not is_quiet:
            print_formatted_text(
                HTML("<ansigreen><b>Telegram message sent.</b></ansigreen>")
            )
        return True

    def _post_send_message(
        self, chat_id: str, text: str, timeout: int
    ) -> dict | None:
        """POST sendMessage; return parsed JSON or None after logging a failure."""
        url = f"{TELEGRAM_API_ROOT}/bot{self.bot_token}/sendMessage"
        payload = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8")
            parsed = json.loads(body)
        except urllib.error.HTTPError as err:
            detail = err.read().decode("utf-8", errors="replace")
            self.cab.log(
                f"Telegram HTTP {err.code}: {detail[:300]}",
                level="error",
            )
            return None
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as err:
            if isinstance(err, json.JSONDecodeError):
                self.cab.log("Telegram returned a non-JSON response", level="error")
            else:
                self.cab.log(f"Telegram send failed: {err}", level="error")
            return None
        if not isinstance(parsed, dict):
            self.cab.log("Telegram returned a non-JSON object", level="error")
            return None
        return parsed


def telegram(
    message: str,
    target: str | int | None = None,
    logging_enabled: bool = True,
    is_quiet: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
) -> bool:
    """Send a Telegram message. ``import cabinet; cabinet.telegram('hi')``."""
    return Telegram().send(
        message,
        target=target,
        logging_enabled=logging_enabled,
        is_quiet=is_quiet,
        timeout=timeout,
    )


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("Usage: cabinet --telegram <message>")
