"""
Cabinet Telegram

Send a Telegram message the same way diary-llm does: ``openclaw message send``.
Optional Bot API is used when ``telegram.bot_token`` is set.

``telegram.target`` (chat id) lives in Cabinet data, similar to ``email`` for Mail.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from prompt_toolkit import HTML, print_formatted_text

import cabinet

TELEGRAM_API_ROOT = "https://api.telegram.org"
DEFAULT_CHANNEL = "telegram"
DEFAULT_OPENCLAW_BIN = "openclaw"
DEFAULT_TIMEOUT = 60
DIARY_LLM_OPENCLAW = Path.home() / "git/tools/diary-llm/scripts/openclaw-gateway"


def _default_openclaw_bin() -> str:
    """Prefer diary-llm's Gateway-bundled CLI when present (Homebrew can lag)."""
    if DIARY_LLM_OPENCLAW.is_file() and os.access(DIARY_LLM_OPENCLAW, os.X_OK):
        return str(DIARY_LLM_OPENCLAW)
    return DEFAULT_OPENCLAW_BIN


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
    Sends Telegram messages via OpenClaw, or the Bot API when a token is set.

    Reads ``telegram.target`` (or ``telegram.chat_id``) from Cabinet data.
    Optional: ``telegram.channel``, ``telegram.openclaw_bin``,
    ``telegram.bot_token`` (or ``telegram.token``).
    """

    def __init__(self, cab: cabinet.Cabinet | None = None):
        self.cab = cab if cab is not None else cabinet.Cabinet()
        self.target = _config_str(self.cab, "target", "chat_id")
        self.channel = _config_str(self.cab, "channel") or DEFAULT_CHANNEL
        self.openclaw_bin = _config_str(self.cab, "openclaw_bin") or _default_openclaw_bin()
        self.bot_token = _config_str(self.cab, "bot_token", "token")

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
            True if the message was accepted, False otherwise.
        """
        text = (message or "").strip()
        chat_id = str(target).strip() if target is not None else self.target
        if not text:
            self.cab.log("Telegram message is empty", level="error")
            return False
        if not chat_id:
            self.cab.log("cabinet -> telegram -> target is unset", level="error")
            return False

        if self.bot_token:
            ok = self._send_bot_api(chat_id, text, timeout)
        else:
            ok = self._send_openclaw(chat_id, text, timeout)
        if not ok:
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

    def _send_openclaw(self, chat_id: str, text: str, timeout: int) -> bool:
        """Send via ``openclaw message send``, matching diary-llm."""
        binary = shutil.which(self.openclaw_bin) or self.openclaw_bin
        cmd = [
            binary,
            "message",
            "send",
            "--channel",
            self.channel,
            "--target",
            chat_id,
            "--message",
            text,
        ]
        try:
            proc = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError:
            self.cab.log(
                f"{self.openclaw_bin} not found; set telegram.bot_token "
                "or install OpenClaw",
                level="error",
            )
            return False
        except subprocess.TimeoutExpired:
            self.cab.log("OpenClaw Telegram send timed out", level="error")
            return False
        if proc.returncode == 0:
            return True
        err = (proc.stderr or proc.stdout or "").strip()[:300]
        self.cab.log(
            f"OpenClaw Telegram send failed: {err or proc.returncode}",
            level="error",
        )
        return False

    def _send_bot_api(self, chat_id: str, text: str, timeout: int) -> bool:
        """POST sendMessage to api.telegram.org when a bot token is configured."""
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
            return False
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as err:
            if isinstance(err, json.JSONDecodeError):
                self.cab.log("Telegram returned a non-JSON response", level="error")
            else:
                self.cab.log(f"Telegram send failed: {err}", level="error")
            return False
        if not isinstance(parsed, dict) or not parsed.get("ok"):
            description = ""
            if isinstance(parsed, dict):
                description = str(parsed.get("description") or parsed)[:300]
            self.cab.log(
                f"Telegram API rejected the message: {description}",
                level="error",
            )
            return False
        return True


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
