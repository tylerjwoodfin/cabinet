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
import cabinet

class Mail:
    """
    Provides functionality for sending email using SMTP and MIMEText.
    Does not support Gmail.
    A throwaway email is highly recommended.
    """

    def __init__(self):
        self.user_dir = pwd.getpwuid(os.getuid())[0]
        self.cab = cabinet.Cabinet()

        # parameters
        self.port = self.cab.get("email", "port")
        self.smtp_server = self.cab.get("email", "smtp_server")
        self.imap_server = self.cab.get("email", "imap_server")
        self.username = self.cab.get("email", "from")
        self.password = self.cab.get("email", "from_pw")

    def send(self, subject: str, body: str, signature: str = '', to_addr: List[str] = None,
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

        Raises:
        - smtplib.SMTPAuthenticationError: If the SMTP server rejects the login credentials.

        Gmail will almost certainly not work.
        """

        # Set default `from_name` if unset.
        if from_name is None:
            from_name = (self.cab.get("email", "from_name")
                         or "Raspberry Pi") + f" <{self.username}>"

        # Set default `to_addr` if unset.
        if to_addr is None:
            to_addr = self.cab.get("email", "to")

            if to_addr is None:
                self.cab.log("cabinet -> email -> to is unset", level="error")
                return

        # Append `signature` to the `body` of the email.
        signature = signature or f"<br><br>Thanks,<br>{from_name}"
        body += unquote(signature)

        # Create the message object.
        message = MIMEMultipart()
        message["Subject"] = unquote(subject)
        message["From"] = from_name
        message["To"] = (', ').join(to_addr)
        message.attach(MIMEText(unquote(body), "html"))

        # Send the email.
        server = smtplib.SMTP_SSL(self.smtp_server, self.port)

        try:
            server.login(self.username, self.password)

            server.send_message(message)

            if logging_enabled:
                self.cab.log(
                    f"Sent Email to {message['To']} as {message['From']}: {subject}",
                    is_quiet=is_quiet)

        except smtplib.SMTPAuthenticationError as err:
            self.cab.log(
                f"Could not log into {self.username}; set this with Cabinet.\n\n{err}",
                level="error")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("Usage: cabinet --mail -s <subject> -b <body> --to <to, optional>")
