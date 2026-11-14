"""
KnowledgeVault backend - outgoing email (KV-53).

    send_email(to, subject, body) -> bool

Used for password reset links. Two modes, chosen by the environment:

  * SMTP_HOST is set: the message is sent through that mail server (Gmail,
    Amazon SES SMTP, any provider). Port 465 uses SSL, anything else uses
    STARTTLS. SMTP_USER and SMTP_PASSWORD log in; MAIL_FROM is the sender
    (default: SMTP_USER).
  * SMTP_HOST is not set: nothing is sent, and the whole message (so the reset
    link) is written to the server log at WARNING level. That is enough to try
    the feature on a laptop, or to read a link off the server for a demo:
        docker compose -f docker-compose.prod.yml logs backend | grep -A6 "Email is not set up"

Sending never raises. A mail server that is down must not turn a password
reset request into an error page (and must not reveal whether an account
exists), so a failure is logged and False is returned.
"""

import logging
import smtplib
from email.message import EmailMessage

from settings import MAIL_FROM, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USER

logger = logging.getLogger("knowledgevault.mail")

SMTP_TIMEOUT_SECONDS = 15


def send_email(to: str, subject: str, body: str) -> bool:
    """Send a plain-text email. True if it was handed to the mail server."""
    if not SMTP_HOST:
        logger.warning("Email is not set up (SMTP_HOST is empty), so nothing was sent.\nTo: %s\nSubject: %s\n\n%s", to, subject, body)
        return False

    message = EmailMessage()
    message["From"] = MAIL_FROM or "knowledgevault@localhost"
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    try:
        if SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT_SECONDS)
        else:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT_SECONDS)
        with server:
            if SMTP_PORT != 465:
                server.starttls()
            if SMTP_USER:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(message)
    except Exception:
        logger.exception("Could not send an email to %s through %s:%s", to, SMTP_HOST, SMTP_PORT)
        return False
    return True
