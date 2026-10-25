"""Отправка писем FL HUB.

Два канала доставки:
  1. SMTP — если задан FLHUB_SMTP_HOST (плюс порт/логин/пароль из окружения).
  2. Outbox — если SMTP не настроен: письмо кладётся в data/outbox/, а код
     печатается в лог сервера, чтобы локально можно было пройти регистрацию.
"""
from __future__ import annotations

import os
import smtplib
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from pathlib import Path

import db

SMTP_HOST = os.environ.get("FLHUB_SMTP_HOST", "").strip()
SMTP_PORT = int(os.environ.get("FLHUB_SMTP_PORT", "587"))
SMTP_USER = os.environ.get("FLHUB_SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("FLHUB_SMTP_PASSWORD", "")
# STARTTLS для порта 587, SMTPS (implicit TLS) для порта 465.
SMTP_STARTTLS = os.environ.get("FLHUB_SMTP_STARTTLS", "1") != "0"
SMTP_SSL = os.environ.get("FLHUB_SMTP_SSL", "0") == "1"
SMTP_TIMEOUT = int(os.environ.get("FLHUB_SMTP_TIMEOUT", "15"))

FROM_ADDR = os.environ.get("FLHUB_EMAIL_FROM", "no-reply@flhub.local")
FROM_NAME = os.environ.get("FLHUB_EMAIL_FROM_NAME", "FL HUB")
SITE_URL = os.environ.get("FLHUB_URL", "").strip().rstrip("/")

OUTBOX_DIR = db.DATA_DIR / "outbox"


class MailError(Exception):
    """Письмо не удалось доставить выбранным каналом."""


def smtp_configured() -> bool:
    return bool(SMTP_HOST)


def send_email(to_addr: str, subject: str, text_body: str) -> str:
    """Отправляет письмо и возвращает имя канала: "smtp" или "outbox"."""
    message = EmailMessage()
    message["From"] = formataddr((FROM_NAME, FROM_ADDR))
    message["To"] = to_addr
    message["Subject"] = subject
    message["Date"] = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    message["Message-ID"] = make_msgid(domain=FROM_ADDR.split("@")[-1] or "flhub.local")
    message.set_content(text_body)

    if smtp_configured():
        _send_via_smtp(message)
        return "smtp"
    _save_to_outbox(message)
    return "outbox"


def _send_via_smtp(message: EmailMessage) -> None:
    with ssl.create_default_context() as context:
        try:
            if SMTP_SSL:
                server = smtplib.SMTP_SSL(
                    SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT, context=context
                )
            else:
                server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT)
        except OSError as error:
            raise MailError(f"SMTP: нет связи с сервером ({error})") from error

        try:
            if not SMTP_SSL and SMTP_STARTTLS and server.has_extn("starttls"):
                server.starttls(context=context)
            if SMTP_USER:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(message)
        except smtplib.SMTPException as error:
            raise MailError(f"SMTP: сервер отклонил письмо ({error})") from error
        except OSError as error:
            raise MailError(f"SMTP: обрыв соединения ({error})") from error
        finally:
            try:
                server.quit()
            except Exception:
                pass


def _save_to_outbox(message: EmailMessage) -> None:
    OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    recipient = "".join(ch for ch in str(message["To"]) if ch.isalnum() or ch in "._@-")
    path = OUTBOX_DIR / f"{stamp}-{recipient}.eml"
    path.write_bytes(bytes(message))
    code = _extract_code(message.get_body(("plain",)).get_content())
    banner = [
        "",
        "─" * 58,
        f"FL HUB · SMTP не настроен — письмо сохранено в {path.relative_to(db.DATA_DIR.parent)}",
        f"  Кому:  {message['To']}",
        f"  Тема:  {message['Subject']}",
    ]
    if code:
        banner.append(f"  КОД:   {code}")
    banner.append("─" * 58)
    print("\n".join(banner), flush=True)


def _extract_code(body: str) -> str:
    for line in (body or "").splitlines():
        stripped = line.strip()
        if stripped.isdigit() and len(stripped) == 6:
            return stripped
    return ""


def verification_text(username: str, code: str, minutes: int) -> str:
    """Текст письма с кодом подтверждения."""
    lines = [
        f"Привет, {username}!",
        "",
        "Чтобы подтвердить регистрацию в FL HUB, введи этот код:",
        "",
        f"{code}",
        "",
        f"Код действует {minutes} минут и подходит один раз.",
        "Если ты не регистрировался в FL HUB — просто проигнорируй письмо,",
        "аккаунт останется неактивным.",
    ]
    if SITE_URL:
        lines += ["", f"FL HUB: {SITE_URL}"]
    lines += ["", "— Команда FL HUB"]
    return "\n".join(lines) + "\n"
