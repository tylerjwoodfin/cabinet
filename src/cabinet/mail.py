"""
cabinet mail

enables quick email sendind checking
"""
import smtplib
import imaplib
from urllib.parse import unquote
import sys
import pwd
import os
import traceback
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from cabinet import cabinet

userDir = pwd.getpwuid(os.getuid())[0]

# Parameters
port = cabinet.get("email", "port")
smtp_server = cabinet.get("email", "smtp_server")
imap_server = cabinet.get("email", "imap_server")
username = cabinet.get("email", "from")
password = cabinet.get("email", "from_pw")


def send(subject, body, signature='', to_addr=cabinet.get("email", "to") or [], from_name=cabinet.get("email", "from_name") or "Raspberry Pi", logging_enabled=True, is_quiet=False):
    """
    Sends email from the given account; see README for restrictions!
    Gmail will almost certainly not work.
    """
    from_name = from_name + f" <{username}>"
    signature = signature or f"<br><br>Thanks,<br>{from_name}"

    if len(to_addr) == 0:
        cabinet.log("cabinet -> email -> to is unset", level="error")
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
            cabinet.log(
                f"Sent Email to {message['To']} as {message['From']}: {subject}", is_quiet=is_quiet)

    except smtplib.SMTPAuthenticationError as err:
        cabinet.log(
            f"Could not log into {username}; set this with cabinet.\n\n{err}", level="error")

def check():
    """
    Returns raw, possibly-encoded emails from the Inbox of the Gmail account described above
    """
    try:
        mail = imaplib.IMAP4_SSL(imap_server)
        mail.login(username, password)
        mail.select('inbox')

        data = mail.search(None, 'ALL')
        mail_ids = data[1]
        id_list = mail_ids[0].split()
        latest_email_id = str(int(id_list[-1]))

        return mail.fetch(latest_email_id, '(RFC822)')

    except Exception as e:
        traceback.print_exc()
        cabinet.log(
            f"Ran into a problem checking mail:{str(e).strip()}", level="error")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("sys.argv usage: send <subject>, <body>")
