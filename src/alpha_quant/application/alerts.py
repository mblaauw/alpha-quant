"""Alerting and notification system."""

import contextlib
import json
import smtplib
import subprocess
from datetime import UTC, datetime
from email.mime.text import MIMEText
from pathlib import Path
from typing import Literal

import structlog

logger = structlog.get_logger()

AlertLevel = Literal["CRITICAL", "WARNING", "INFO"]

_ALERTS_FILE = Path("data") / "alerts.json"


def _load_alerts() -> list[dict]:
    if not _ALERTS_FILE.exists():
        return []
    try:
        return json.loads(_ALERTS_FILE.read_text())
    except Exception:
        return []


def _save_alerts(alerts: list[dict]) -> None:
    _ALERTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _ALERTS_FILE.write_text(json.dumps(alerts, indent=2, default=str))


def _notify_macos(title: str, message: str) -> None:
    with contextlib.suppress(Exception):
        subprocess.run(
            ["osascript", "-e", f'display notification "{message}" with title "{title}"'],
            capture_output=True,
            timeout=5,
        )


def _send_email(subject: str, body: str, smtp_config: dict | None = None) -> None:
    if smtp_config is None:
        return
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = smtp_config.get("from", "")
        msg["To"] = smtp_config.get("to", "")
        with smtplib.SMTP(smtp_config.get("host", ""), smtp_config.get("port", 587)) as s:
            if smtp_config.get("tls", True):
                s.starttls()
            user = smtp_config.get("user", "")
            pw = smtp_config.get("password", "")
            if user and pw:
                s.login(user, pw)
            s.send_message(msg)
    except Exception:
        logger.exception("email_alert_failed")


def alert(
    level: AlertLevel,
    title: str,
    message: str,
    *,
    macos_notify: bool = False,
    smtp_config: dict | None = None,
) -> None:
    alerts = _load_alerts()
    entry = {
        "level": level,
        "title": title,
        "message": message,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    alerts.append(entry)
    _save_alerts(alerts)

    log_level = 40 if level == "CRITICAL" else (30 if level == "WARNING" else 20)
    logger.log(log_level, "alert", level=level, title=title, message=message)

    if macos_notify:
        _notify_macos(f"[{level}] {title}", message)

    if level == "CRITICAL":
        _send_email(f"[alpha-quant] {title}", message, smtp_config)


def get_recent_alerts(limit: int = 20) -> list[dict]:
    return _load_alerts()[-limit:]


def clear_alerts() -> None:
    if _ALERTS_FILE.exists():
        _ALERTS_FILE.unlink()
