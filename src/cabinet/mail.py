"""
Cabinet Mail

Provides functionality for sending email using SMTP and MIMEText.
Does not support Gmail.

A throwaway email is highly recommended.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
import pwd
import smtplib
import socket
import sys
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.parse import unquote

from prompt_toolkit import HTML, print_formatted_text

import cabinet


def _coerce_smtp_port(value: object) -> int | None:
    """
    Normalize config/JSON values to a valid SMTP port integer.

    Rejects booleans (JSON ``true``/``false`` are not ports), non-numeric strings,
    and fractional floats.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if 1 <= value <= 65535 else None
    if isinstance(value, float):
        if not value.is_integer():
            return None
        iv = int(value)
        return iv if 1 <= iv <= 65535 else None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            iv = int(text, 10)
        except ValueError:
            return None
        return iv if 1 <= iv <= 65535 else None
    return None


def _normalize_recipients(value: object) -> list[str] | None:
    """
    Turn Cabinet/config/CLI values into a non-empty list of recipient strings.

    Accepts ``None``, a single address string (optionally comma-separated),
    or a sequence (e.g. JSON array from ``cabinet.get``).
    """
    if value is None:
        return None
    if isinstance(value, str):
        parts = [p.strip() for p in value.split(",") if p.strip()]
        return parts or None
    if isinstance(value, (list, tuple)):
        out: list[str] = []
        for item in value:
            if item is None:
                continue
            s = str(item).strip()
            if s:
                out.extend(
                    [p.strip() for p in s.split(",") if p.strip()]
                )
        return out or None
    return None


DEFAULT_SMTP_MAX_RETRIES = 3
DEFAULT_SMTP_RETRY_BASE_DELAY = 120


def _coerce_positive_int(value: object, default: int) -> int:
    if isinstance(value, bool) or value is None:
        return default
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, str):
        text = value.strip()
        if text.isdigit():
            return int(text)
    return default


def _smtp_retry_delay_seconds(retry_number: int, base_delay: int) -> int:
    """Seconds to wait before retry ``retry_number`` (1-based)."""
    return base_delay * (2 ** (retry_number - 1))


def _is_transient_smtp_error(err: BaseException) -> bool:
    return isinstance(
        err,
        (
            socket.timeout,
            TimeoutError,
            ConnectionError,
            smtplib.SMTPServerDisconnected,
            smtplib.SMTPConnectError,
        ),
    )


class Mail:
    """
    Provides functionality for sending email using SMTP and MIMEText.
    Does not support Gmail.
    A throwaway email is highly recommended.
    """

    def __init__(self):
        self.user_dir = pwd.getpwuid(os.getuid())[0]
        self.cab = cabinet.Cabinet()

        raw_port = self.cab.get("email", "port")
        self.port = _coerce_smtp_port(raw_port)

        self.smtp_server: str | None = self.cab.get("email", "smtp_server")
        self.imap_server: str | None = self.cab.get("email", "imap_server")
        self.username = self.cab.get("email", "from")
        self.password = self.cab.get("email", "from_pw")

    def send(
        self,
        subject: str,
        body: str,
        signature: str = "",
        to_addr: str | Sequence[object] | None = None,
        from_name: str | None = None,
        logging_enabled: bool = True,
        is_quiet: bool = False,
        timeout: int = 4,
        max_retries: int | None = None,
        retry_base_delay: int | None = None,
    ) -> bool:
        """
        Sends an email with the given subject and body to the specified recipients.

        Args:
        - subject (str): The subject of the email.
        - body (str): The body of the email.
        - signature (str): The signature to include at the end of the email.
        - to_addr: Recipient(s) as ``list[str]``, comma-separated ``str``, single ``str``,
            or ``None`` to use ``cabinet -> email -> to`` (also normalized the same way).
        - from_name (str, optional): The name to appear in the "From" field of the email.
            Reads from cabinet -> email -> from_name if unset.
            If this is unset, defaults to machine's hostname or `Cabinet`
        - logging_enabled (bool, optional): Whether to log the email send event.
            Defaults to True.
        - is_quiet: Whether to suppress log output.
            Defaults to False.
        - timeout (int, optional): Timeout in seconds for SMTP operations.
            Defaults to 4 seconds.
        - max_retries (int, optional): Retries after transient SMTP failures.
            Defaults to cabinet -> email -> smtp_max_retries or 3.
        - retry_base_delay (int, optional): Base delay in seconds for exponential
            backoff between retries. Defaults to cabinet -> email ->
            smtp_retry_base_delay or 120.

        Returns:
        - bool: True if the email was sent, False otherwise.

        Gmail will almost certainly not work.
        """

        if max_retries is None:
            max_retries = _coerce_positive_int(
                self.cab.get("email", "smtp_max_retries"),
                DEFAULT_SMTP_MAX_RETRIES,
            )
        if retry_base_delay is None:
            retry_base_delay = _coerce_positive_int(
                self.cab.get("email", "smtp_retry_base_delay"),
                DEFAULT_SMTP_RETRY_BASE_DELAY,
            )

        hostname = socket.gethostname()
        if hostname:
            hostname = hostname.capitalize().replace(".local", "")

        cab_from_name = self.cab.get("email", "from_name") or hostname or "Cabinet"

        # send IP if reminder came directly from outside of server
        client_name = os.getenv("SSH_CONNECTION")

        if client_name:
            client_name = (
                client_name.strip().replace("\n", "").replace("\r", "").split(" ")[0]
            )
        else:
            client_name = ""

        email_from = f"{cab_from_name}<br>{client_name}"

        # Set default `from_name` if unset.
        if from_name is None:
            from_name = f"{cab_from_name} <{self.username}>"

        # Debug: Log the to_addr parameter as received
        self.cab.log(
            f"Mail.send() received to_addr: {to_addr} (type: {type(to_addr).__name__})",
            level="debug"
        )

        if to_addr is None:
            to_addr = _normalize_recipients(self.cab.get("email", "to"))
            self.cab.log(
                f"Mail.send() using default from config: {to_addr}",
                level="debug",
            )

            if to_addr is None:
                self.cab.log("cabinet -> email -> to is unset", level="error")
                return False
        else:
            to_addr = _normalize_recipients(to_addr)
            if to_addr is None:
                self.cab.log("to_addr was empty after normalization", level="error")
                return False

        # Remove duplicates while preserving order
        seen = set()
        to_addr = [addr for addr in to_addr if addr not in seen and not seen.add(addr)]

        # Debug: Log the final to_addr being used
        self.cab.log(
            f"Mail.send() final to_addr: {to_addr} (type: {type(to_addr).__name__})",
            level="debug"
        )

        # Append `signature` to the `body` of the email.
        signature = signature or f"<br><br>Thanks,<br>{email_from}"
        body += unquote(signature)

        # Create the message object.
        message = MIMEMultipart()
        message["Subject"] = unquote(subject)
        message["From"] = from_name
        message["To"] = (", ").join(to_addr)
        message.attach(MIMEText(unquote(body), "html"))

        if not self.smtp_server:
            self.cab.log("No SMTP Server set", level="error")
            return False

        if self.port is None:
            self.cab.log(
                "No valid SMTP port (email.port must be an integer 1–65535, "
                "e.g. 587 or 465)",
                level="error",
            )
            return False

        if not self.username or not self.password:
            self.cab.log("Username/password not set", level="error")
            return False

        max_attempts = max_retries + 1
        for attempt in range(1, max_attempts + 1):
            server = None
            try:
                self.cab.log(
                    f"SMTP send attempt {attempt}/{max_attempts} for {subject!r}",
                    level="info",
                )
                server = self._connect_smtp(timeout)
                self.cab.log(
                    f"Attempting SMTP login with username: {self.username}",
                    level="debug",
                )
                server.login(self.username, self.password)
                server.send_message(message)

                if logging_enabled:
                    self.cab.log(
                        f"Sent Email to {message['To']} as {message['From']}: {subject}",
                        level="debug",
                    )
                if attempt > 1:
                    self.cab.log(
                        f"SMTP send succeeded on attempt {attempt}/{max_attempts} "
                        f"for {subject!r}",
                        level="info",
                    )
                if not is_quiet:
                    print_formatted_text(
                        HTML("<ansigreen><b>Email sent.</b></ansigreen>")
                    )
                return True

            except smtplib.SMTPAuthenticationError as err:
                self.cab.log(
                    f"SMTP authentication failed for {self.username}.\n"
                    f"Error: {err}\n"
                    f"For Proton Mail, ensure:\n"
                    f"  1. Username matches the email address used when generating the SMTP token\n"
                    f"  2. Password is the SMTP token (not your regular password)\n"
                    f"  3. Token was generated for the correct email address",
                    level="error",
                )
                return False
            except Exception as err:  # pylint: disable=broad-exception-caught
                if not _is_transient_smtp_error(err):
                    self.cab.log(
                        f"SMTP send failed with non-retryable error: {err}",
                        level="error",
                    )
                    return False

                if attempt < max_attempts:
                    delay = _smtp_retry_delay_seconds(attempt, retry_base_delay)
                    self.cab.log(
                        f"SMTP attempt {attempt}/{max_attempts} failed after "
                        f"{timeout} seconds: {err}. Retrying in {delay} seconds.",
                        level="warning",
                    )
                    time.sleep(delay)
                else:
                    self.cab.log(
                        f"SMTP connection failed after {max_attempts} attempts "
                        f"({timeout}s timeout each): {err}",
                        level="error",
                    )
            finally:
                if server:
                    try:
                        server.quit()
                    except Exception:  # pylint: disable=broad-exception-caught
                        try:
                            server.close()
                        except Exception:  # pylint: disable=broad-exception-caught
                            pass

        return False

    def _connect_smtp(self, timeout: int) -> smtplib.SMTP:
        """Open an authenticated-ready SMTP connection (login still required)."""
        if self.port == 465:
            server = smtplib.SMTP_SSL(
                self.smtp_server, self.port, timeout=timeout
            )
        elif self.port == 587:
            server = smtplib.SMTP(self.smtp_server, self.port, timeout=timeout)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(
                self.smtp_server, self.port, timeout=timeout
            )
        return server


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("Usage: cabinet --mail -s <subject> -b <body> --to <to, optional>")
