"""
Cabinet Mail

Provides functionality for sending email using SMTP and MIMEText.
Does not support Gmail.

A throwaway email is highly recommended.
"""

import smtplib
from urllib.parse import unquote
import socket
import pwd
import sys
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
        # port should be int; TODO update Cabinet to support type casting
        self.port = self.cab.get("email", "port")

        self.smtp_server: str | None = self.cab.get("email", "smtp_server")
        self.imap_server: str | None = self.cab.get("email", "imap_server")
        self.username = self.cab.get("email", "from")
        self.password = self.cab.get("email", "from_pw")

    def send(self, subject: str,
             body: str,
             signature: str = '',
             to_addr = None, # should be List[str]; TODO update Cabinet to support type casting
             from_name: str | None = None,
             logging_enabled: bool = True,
             is_quiet: bool = False) -> None:
        """
        Sends an email with the given subject and body to the specified recipients.

        Args:
        - subject (str): The subject of the email.
        - body (str): The body of the email.
        - signature (str): The signature to include at the end of the email.
        - to_addr (List): A list of email addresses to send the email to.
        - from_name (str, optional): The name to appear in the "From" field of the email.
            Reads from cabinet -> email -> from_name if unset.
            If this is unset, defaults to machine's hostname or `Cabinet`
        - logging_enabled (bool, optional): Whether to log the email send event.
            Defaults to True.
        - is_quiet: Whether to suppress log output.
            Defaults to False.

        Raises:
        - smtplib.SMTPAuthenticationError: If the SMTP server rejects the login credentials.

        Gmail will almost certainly not work.
        """

        hostname = socket.gethostname()
        if hostname:
            hostname = hostname.capitalize().replace(".local", "")

        cab_from_name = self.cab.get("email", "from_name") or hostname or "Cabinet"

        # send IP if reminder came directly from outside of server
        client_name = os.getenv('SSH_CONNECTION')

        if client_name:
            client_name = client_name.strip().replace('\n', '').replace('\r', '').split(" ")[0]
        else:
            client_name = ""

        email_from = f'{cab_from_name}<br>{client_name}'

        # Set default `from_name` if unset.
        if from_name is None:
            from_name = f"{cab_from_name} <{self.username}>"

        # Set default `to_addr` if unset.
        if to_addr is None:
            to_addr = self.cab.get("email", "to")

            if to_addr is None:
                self.cab.log("cabinet -> email -> to is unset", level="error")
                return

        # Append `signature` to the `body` of the email.
        signature = signature or f"<br><br>Thanks,<br>{email_from}"
        body += unquote(signature)

        # Create the message object.
        message = MIMEMultipart()
        message["Subject"] = unquote(subject)
        message["From"] = from_name
        message["To"] = (', ').join(to_addr)
        message.attach(MIMEText(unquote(body), "html"))

        if not self.smtp_server:
            self.cab.log("No SMTP Server set", level="error")
            return

        if not self.port:
            self.cab.log("No port set", level="error")
            return

        if not isinstance(self.port, int):
            self.cab.log(f"Port is not an integer (received '{self.port}')", level="error")
            return

        server = smtplib.SMTP_SSL(self.smtp_server, self.port)

        try:

            if not self.username or not self.password:
                self.cab.log("Username/password not set", level="error")
                return
            server.login(self.username, self.password)

            # Send the email.
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
