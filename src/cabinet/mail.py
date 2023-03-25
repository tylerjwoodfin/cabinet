"""
Cabinet Mail

Provides functionality for sending email using SMTP and MIMEText.
Does not support Gmail.

A throwaway email is highly recommended.
"""

import smtplib
from typing import List
from urllib.parse import unquote
import sys
import pwd
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from cabinet import Cabinet

cab = Cabinet()

userDir = pwd.getpwuid(os.getuid())[0]

# parameters
port = cab.get("email", "port")
smtp_server = cab.get("email", "smtp_server")
imap_server = cab.get("email", "imap_server")
username = cab.get("email", "from")
password = cab.get("email", "from_pw")


def send(subject: str, body: str, signature: str = '', to_addr: List[str] = None,
         from_name: str = None, logging_enabled: bool = True, is_quiet: bool = False) -> None:
    """
    Sends an email with the given subject and body to the specified recipients.

    Args:
    - subject (str): The subject of the email.
    - body (str): The body of the email.
    - signature (str): The signature to include at the end of the email.
    - to_addr (List): A list of email addresses to send the email to.
    - from_name (str, optional): The name to appear in the "From" field of the email.
        Reads from settings.json -> email -> from_name if unset.
        If this is unset, defaults to `Raspberry Pi`
    - logging_enabled (bool, optional): Whether to log the email send event.
        Defaults to True.
    - is_quiet: Whether to suppress log output.
        Defaults to False.

    Gmail will almost certainly not work.
    """

    from_name = (cab.get("email", "from_name") or "Raspberry Pi") + f" <{username}>"
    signature = signature or f"<br><br>Thanks,<br>{from_name}"

    if to_addr is None:
        to_addr = cab.get("email", "to")

        if to_addr is None:
            cab.log("cabinet -> email -> to is unset", level="error")
            return

    # Parse
    body += unquote(signature)
    message = MIMEMultipart()
    message["Subject"] = unquote(subject)
    message["From"] = from_name
    message["To"] = (', ').join(to_addr)
    message.attach(MIMEText(unquote(body), "html"))

    # Send Email
    server = smtplib.SMTP_SSL(smtp_server, port)

    try:
        server.login(username, password)
        server.send_message(message)

        if logging_enabled:
            cab.log(
                f"Sent Email to {message['To']} as {message['From']}: {subject}", is_quiet=is_quiet)

    except smtplib.SMTPAuthenticationError as err:
        cab.log(
            f"Could not log into {username}; set this with Cabinet.\n\n{err}", level="error")

if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("sys.argv usage: send <subject>, <body>")
