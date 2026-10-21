"""Outgoing email.

Backends:
- console: writes the email to the server log. For local development only, so
  you can click verification/reset links without an email provider.
- smtp:    sends through any SMTP provider (configured with ASZDA_SMTP_* variables).
- memory:  keeps messages in a list; used by the automated tests.
"""

from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

from flask import current_app

log = logging.getLogger(__name__)

# Messages captured by the "memory" backend (tests only).
outbox: list[EmailMessage] = []


@dataclass
class Email:
    to: str
    subject: str
    body: str


def send(email: Email) -> None:
    msg = EmailMessage()
    msg["From"] = current_app.config["MAIL_FROM"]
    msg["To"] = email.to
    msg["Subject"] = email.subject
    msg.set_content(email.body)

    backend = current_app.config["MAIL_BACKEND"]
    if backend == "memory":
        outbox.append(msg)
    elif backend == "console":
        log.warning("[DEV EMAIL — not actually sent]\nTo: %s\nSubject: %s\n\n%s",
                    email.to, email.subject, email.body)
    elif backend == "smtp":
        cfg = current_app.config
        with smtplib.SMTP(cfg["SMTP_HOST"], cfg["SMTP_PORT"], timeout=20) as smtp:
            if cfg["SMTP_USE_TLS"]:
                smtp.starttls()
            if cfg["SMTP_USERNAME"]:
                smtp.login(cfg["SMTP_USERNAME"], cfg["SMTP_PASSWORD"])
            smtp.send_message(msg)
    else:
        raise RuntimeError(f"Unknown ASZDA_MAIL_BACKEND '{backend}'")


def verification_email(to: str, token: str) -> Email:
    link = f"{current_app.config['FRONTEND_URL']}/verify-email?token={token}"
    return Email(
        to=to,
        subject="Confirm your ASZDA email address",
        body=(
            "Welcome to ASZDA Studio.\n\n"
            f"Confirm your email address by opening this link:\n{link}\n\n"
            "The link expires in 48 hours. If you did not create an account, ignore this email."
        ),
    )


def password_reset_email(to: str, token: str) -> Email:
    link = f"{current_app.config['FRONTEND_URL']}/reset-password?token={token}"
    return Email(
        to=to,
        subject="Reset your ASZDA password",
        body=(
            "Someone asked to reset the password for your ASZDA account.\n\n"
            f"Choose a new password here:\n{link}\n\n"
            "The link expires in 60 minutes. If this was not you, you can ignore this email; "
            "your password will not change."
        ),
    )
