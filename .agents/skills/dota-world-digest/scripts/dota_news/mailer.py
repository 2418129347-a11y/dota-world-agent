from __future__ import annotations

import hashlib
import json
import os
import smtplib
import ssl
import time
import urllib.request
from datetime import date
from email.message import EmailMessage
from email.utils import make_msgid
from typing import Any


def resend_config() -> tuple[str, str, str]:
    api_key = os.environ.get("RESEND_API_KEY", "")
    sender = os.environ.get("DIGEST_FROM", "")
    recipient = os.environ.get("DIGEST_TO", "")
    missing = [name for name, value in (("RESEND_API_KEY", api_key), ("DIGEST_FROM", sender), ("DIGEST_TO", recipient)) if not value]
    if missing:
        raise RuntimeError("缺少邮件配置：" + ", ".join(missing))
    return api_key, sender, recipient


def smtp_config() -> tuple[str, int, str, str, str, str]:
    host = os.environ.get("SMTP_HOST", "smtp.qq.com")
    port_text = os.environ.get("SMTP_PORT", "465")
    username = os.environ.get("SMTP_USERNAME", "")
    password = os.environ.get("SMTP_PASSWORD", "")
    sender = os.environ.get("DIGEST_FROM", "") or username
    recipient = os.environ.get("DIGEST_TO", "")
    missing = [
        name
        for name, value in (
            ("SMTP_USERNAME", username),
            ("SMTP_PASSWORD", password),
            ("DIGEST_TO", recipient),
        )
        if not value
    ]
    if missing:
        raise RuntimeError("缺少邮件配置：" + ", ".join(missing))
    try:
        port = int(port_text)
    except ValueError as exc:
        raise RuntimeError("SMTP_PORT 必须是整数") from exc
    return host, port, username, password, sender, recipient


def idempotency_key(day: date, recipient: str) -> str:
    recipient_hash = hashlib.sha256(recipient.lower().encode("utf-8")).hexdigest()[:12]
    return f"dota-world-digest-{day.isoformat()}-{recipient_hash}"


def send_resend(subject: str, html_body: str, text_body: str, day: date, timeout: int = 25) -> dict[str, Any]:
    api_key, sender, recipient = resend_config()
    payload = {"from": sender, "to": [recipient], "subject": subject, "html": html_body, "text": text_body}
    request = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Idempotency-Key": idempotency_key(day, recipient),
            "User-Agent": "DotaWorldDigest/0.1",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.loads(response.read().decode("utf-8"))
    return {"provider": "resend", "id": result.get("id")}


def send_smtp(
    subject: str,
    html_body: str,
    text_body: str,
    timeout: int = 25,
    retries: int = 3,
    retry_delays: tuple[float, ...] = (2.0, 5.0),
) -> dict[str, Any]:
    host, port, username, password, sender, recipient = smtp_config()
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = recipient
    message["Message-ID"] = make_msgid(domain="dota-world-agent.local")
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")
    tls_context = ssl.create_default_context()
    transient_errors = (
        smtplib.SMTPServerDisconnected,
        smtplib.SMTPConnectError,
        TimeoutError,
        ConnectionError,
        OSError,
    )
    attempts = max(1, retries)
    for attempt in range(1, attempts + 1):
        phase = "connect"
        try:
            if port == 465:
                with smtplib.SMTP_SSL(host, port, timeout=timeout, context=tls_context) as client:
                    phase = "login"
                    client.login(username, password)
                    phase = "send"
                    client.send_message(message, from_addr=username, to_addrs=[recipient])
            else:
                with smtplib.SMTP(host, port, timeout=timeout) as client:
                    client.ehlo()
                    client.starttls(context=tls_context)
                    client.ehlo()
                    phase = "login"
                    client.login(username, password)
                    phase = "send"
                    client.send_message(message, from_addr=username, to_addrs=[recipient])
            return {"provider": "smtp", "id": message.get("Message-ID"), "attempts": attempt}
        except transient_errors:
            # A failure after DATA begins is ambiguous: the server may already have
            # accepted the message, so do not retry and risk a duplicate email.
            if phase == "send" or attempt >= attempts:
                raise
            delay = retry_delays[min(attempt - 1, len(retry_delays) - 1)] if retry_delays else 0
            if delay > 0:
                time.sleep(delay)
    raise RuntimeError("SMTP delivery failed")


def send_email(subject: str, html_body: str, text_body: str, day: date, timeout: int = 25) -> dict[str, Any]:
    provider = os.environ.get("MAIL_PROVIDER", "auto").strip().lower()
    if provider == "auto":
        provider = "smtp" if os.environ.get("SMTP_PASSWORD") else "resend"
    if provider == "smtp":
        return send_smtp(subject, html_body, text_body, timeout=timeout)
    if provider == "resend":
        return send_resend(subject, html_body, text_body, day, timeout=timeout)
    raise RuntimeError("MAIL_PROVIDER 仅支持 smtp、resend 或 auto")
