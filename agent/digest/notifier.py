from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger("notifier")


def _format_job_block(rank: int, job: Dict[str, Any]) -> str:
    title   = job.get("title", "Unknown Role")
    company = job.get("company", "Unknown Company")
    score   = job.get("score", "?")
    ratio   = job.get("match_ratio", 0)
    url     = job.get("url", "")
    matched = ", ".join(job.get("matched_skills", [])[:5]) or "—"
    salary  = job.get("salary_range") or "undisclosed"
    loc     = job.get("location_type", job.get("location", "remote"))
    return (
        f"#{rank}  {title} @ {company}\n"
        f"    Score: {score}/100  |  Match: {ratio:.0%}  |  Salary: {salary}\n"
        f"    Location: {loc}\n"
        f"    Skills: {matched}\n"
        f"    {url}"
    )


def _format_plain(jobs: List[Dict[str, Any]], intro: str = "") -> str:
    lines = [intro or "🔍 Top AI/ML Job Leads Today\n"]
    for i, job in enumerate(jobs, 1):
        lines.append(_format_job_block(i, job))
        lines.append("")
    return "\n".join(lines).strip()


def _format_html(jobs: List[Dict[str, Any]], intro: str = "") -> str:
    rows = ""
    for i, job in enumerate(jobs, 1):
        title   = job.get("title", "Unknown Role")
        company = job.get("company", "Unknown Company")
        score   = job.get("score", "?")
        ratio   = job.get("match_ratio", 0)
        url     = job.get("url", "#")
        matched = ", ".join(job.get("matched_skills", [])[:5]) or "—"
        salary  = job.get("salary_range") or "undisclosed"
        loc     = job.get("location_type", job.get("location", "remote"))
        rows += (
            f"<tr>"
            f"<td style='padding:8px;font-weight:bold'>{i}</td>"
            f"<td style='padding:8px'><a href='{url}' style='color:#0070f3'>{title}</a><br>"
            f"<small>{company}</small></td>"
            f"<td style='padding:8px;text-align:center'>{score}/100</td>"
            f"<td style='padding:8px;text-align:center'>{ratio:.0%}</td>"
            f"<td style='padding:8px'>{matched}</td>"
            f"<td style='padding:8px'>{salary}<br><small>{loc}</small></td>"
            f"</tr>"
        )
    header_style = "background:#0070f3;color:#fff;padding:8px"
    table = (
        f"<table border='0' cellspacing='0' cellpadding='0' "
        f"style='border-collapse:collapse;width:100%;font-family:sans-serif;font-size:13px'>"
        f"<thead><tr>"
        f"<th style='{header_style}'>#</th>"
        f"<th style='{header_style}'>Role</th>"
        f"<th style='{header_style}'>Score</th>"
        f"<th style='{header_style}'>Match</th>"
        f"<th style='{header_style}'>Skills</th>"
        f"<th style='{header_style}'>Salary / Location</th>"
        f"</tr></thead><tbody>{rows}</tbody></table>"
    )
    heading = intro or "Top AI/ML Job Leads Today"
    return (
        f"<html><body style='font-family:sans-serif;max-width:800px;margin:auto'>"
        f"<h2 style='color:#0070f3'>🔍 {heading}</h2>{table}"
        f"<p style='color:#888;font-size:11px'>Job Search Agent</p></body></html>"
    )


class TelegramNotifier:
    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
    ):
        self._token   = bot_token   or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self._chat_id = chat_id     or os.environ.get("TELEGRAM_CHAT_ID", "")

    def send(self, jobs: List[Dict[str, Any]], intro: str = "") -> bool:
        if not self._token or not self._chat_id:
            logger.warning("TelegramNotifier: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set")
            return False
        text = _format_plain(jobs, intro)
        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        payload = {
            "chat_id":    self._chat_id,
            "text":       text,
            "parse_mode": "HTML",
        }
        try:
            resp = requests.post(url, json=payload, timeout=15)
            resp.raise_for_status()
            logger.info("Telegram: message sent")
            return True
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False


class WhatsAppNotifier:
    def __init__(
        self,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
        from_number: Optional[str] = None,
        to_number: Optional[str] = None,
    ):
        self._sid    = account_sid  or os.environ.get("TWILIO_ACCOUNT_SID", "")
        self._token  = auth_token   or os.environ.get("TWILIO_AUTH_TOKEN", "")
        self._from   = from_number  or os.environ.get("TWILIO_WHATSAPP_FROM", "")
        self._to     = to_number    or os.environ.get("TWILIO_WHATSAPP_TO", "")

    def send(self, jobs: List[Dict[str, Any]], intro: str = "") -> bool:
        if not all([self._sid, self._token, self._from, self._to]):
            logger.warning("WhatsAppNotifier: Twilio credentials not fully set")
            return False
        text = _format_plain(jobs, intro)
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self._sid}/Messages.json"
        data = {
            "From": f"whatsapp:{self._from}",
            "To":   f"whatsapp:{self._to}",
            "Body": text,
        }
        try:
            resp = requests.post(
                url,
                data=data,
                auth=(self._sid, self._token),
                timeout=15,
            )
            resp.raise_for_status()
            logger.info("WhatsApp: message sent")
            return True
        except Exception as e:
            logger.error(f"WhatsApp send failed: {e}")
            return False


class EmailNotifier:
    def __init__(
        self,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        from_addr: Optional[str] = None,
        to_addr: Optional[str] = None,
    ):
        self._host     = smtp_host     or os.environ.get("SMTP_HOST", "smtp.gmail.com")
        self._port     = smtp_port     or int(os.environ.get("SMTP_PORT") or "465")
        self._user     = smtp_user     or os.environ.get("SMTP_USER", "")
        self._password = smtp_password or os.environ.get("SMTP_PASSWORD", "")
        self._from     = from_addr     or os.environ.get("DIGEST_FROM_EMAIL", self._user)
        self._to       = to_addr       or os.environ.get("DIGEST_TO_EMAIL", "")

    def send(self, jobs: List[Dict[str, Any]], intro: str = "", subject: str = "") -> bool:
        if not all([self._user, self._password, self._to]):
            logger.warning("EmailNotifier: SMTP_USER, SMTP_PASSWORD, or DIGEST_TO_EMAIL not set")
            return False
        subject = subject or "Daily AI/ML Job Digest – Top Leads"
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = self._from
        msg["To"]      = self._to
        msg.attach(MIMEText(_format_plain(jobs, intro), "plain"))
        msg.attach(MIMEText(_format_html(jobs, intro),  "html"))
        try:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(self._host, self._port, context=ctx) as server:
                server.login(self._user, self._password)
                server.sendmail(self._from, self._to, msg.as_string())
            logger.info(f"Email digest sent to {self._to}")
            return True
        except Exception as e:
            logger.error(f"Email send failed: {e}")
            return False


class ComposioNotifier:
    _COMPOSIO_BASE = "https://backend.composio.dev"

    _ACTION_MAP = {
        "telegram": "TELEGRAM_SEND_MESSAGE",
        "slack":    "SLACK_SEND_MESSAGE",
        "whatsapp": "WHATSAPP_SEND_MESSAGE",
        "gmail":    "GMAIL_SEND_EMAIL",
        "discord":  "DISCORD_SEND_MESSAGE",
    }

    def __init__(
        self,
        api_key:   Optional[str] = None,
        entity_id: Optional[str] = None,
    ):
        self._api_key   = api_key   or os.environ.get("COMPOSIO_API_KEY",   "")
        self._entity_id = entity_id or os.environ.get("COMPOSIO_ENTITY_ID", "default")

    def _headers(self) -> dict:
        return {"x-api-key": self._api_key, "Content-Type": "application/json"}

    def execute_action(self, action_id: str, input_data: dict) -> bool:
        if not self._api_key:
            logger.warning("ComposioNotifier: COMPOSIO_API_KEY not set")
            return False
        url = f"{self._COMPOSIO_BASE}/api/v2/actions/{action_id}/execute"
        payload = {"entityId": self._entity_id, "input": input_data}
        try:
            resp = requests.post(url, json=payload, headers=self._headers(), timeout=20)
            resp.raise_for_status()
            logger.info(f"Composio {action_id} executed successfully")
            return True
        except Exception as e:
            logger.error(f"Composio action {action_id} failed: {e}")
            return False

    def send_telegram(self, jobs: List[Dict[str, Any]], intro: str = "",
                      chat_id: Optional[str] = None) -> bool:
        cid = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
        if not cid:
            logger.warning("ComposioNotifier.send_telegram: TELEGRAM_CHAT_ID not set")
            return False
        text = _format_plain(jobs, intro)
        return self.execute_action("TELEGRAM_SEND_MESSAGE", {
            "chat_id":    cid,
            "text":       text,
            "parse_mode": "HTML",
        })

    def send_slack(self, jobs: List[Dict[str, Any]], intro: str = "",
                   channel: Optional[str] = None) -> bool:
        ch = channel or os.environ.get("SLACK_CHANNEL", "")
        if not ch:
            logger.warning("ComposioNotifier.send_slack: SLACK_CHANNEL not set")
            return False
        text = _format_plain(jobs, intro)
        return self.execute_action("SLACK_SEND_MESSAGE", {"channel": ch, "text": text})

    def send_whatsapp(self, jobs: List[Dict[str, Any]], intro: str = "",
                      to_number: Optional[str] = None) -> bool:
        to = to_number or os.environ.get("WHATSAPP_TO", "")
        if not to:
            logger.warning("ComposioNotifier.send_whatsapp: WHATSAPP_TO not set")
            return False
        text = _format_plain(jobs, intro)
        return self.execute_action("WHATSAPP_SEND_MESSAGE", {"to": to, "text": text})

    def send_gmail(self, jobs: List[Dict[str, Any]], intro: str = "",
                   to_email: Optional[str] = None, subject: str = "") -> bool:
        to = to_email or os.environ.get("DIGEST_TO_EMAIL", "")
        if not to:
            logger.warning("ComposioNotifier.send_gmail: DIGEST_TO_EMAIL not set")
            return False
        return self.execute_action("GMAIL_SEND_EMAIL", {
            "to":      to,
            "subject": subject or "Daily AI/ML Job Digest",
            "body":    _format_html(jobs, intro),
            "is_html": True,
        })

    def send(self, jobs: List[Dict[str, Any]], intro: str = "") -> bool:
        tg  = self.send_telegram(jobs, intro=intro)
        sl  = self.send_slack(jobs, intro=intro)
        return tg or sl

    def get_connections(self) -> List[Dict]:
        if not self._api_key:
            return []
        try:
            resp = requests.get(
                f"{self._COMPOSIO_BASE}/api/v1/connectedAccounts",
                headers=self._headers(), timeout=10,
            )
            resp.raise_for_status()
            return resp.json().get("items", [])
        except Exception as e:
            logger.error(f"ComposioNotifier.get_connections failed: {e}")
            return []

    def get_connection_url(self, app_name: str) -> Optional[str]:
        if not self._api_key:
            return None
        try:
            resp = requests.post(
                f"{self._COMPOSIO_BASE}/api/v1/connectedAccounts",
                json={"appName": app_name.lower(), "entityId": self._entity_id},
                headers=self._headers(), timeout=10,
            )
            resp.raise_for_status()
            return resp.json().get("redirectUrl")
        except Exception as e:
            logger.error(f"ComposioNotifier.get_connection_url({app_name}) failed: {e}")
            return None
