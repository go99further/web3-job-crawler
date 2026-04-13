"""
notify.py — Email notification for new job listings.

Sends a summary email when new jobs are found during a crawl run.
Uses Python's built-in smtplib — zero additional dependencies.

Supports Gmail (via App Password) and any SMTP server.
"""

from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone


def _get_email_config() -> dict | None:
    """Load email config from environment or .env file."""
    config = {
        "smtp_server": os.environ.get("SMTP_SERVER", "smtp.gmail.com"),
        "smtp_port": int(os.environ.get("SMTP_PORT", "587")),
        "sender_email": os.environ.get("SENDER_EMAIL", ""),
        "sender_password": os.environ.get("SENDER_PASSWORD", ""),
        "recipient_email": os.environ.get("RECIPIENT_EMAIL", ""),
    }

    # Try .env file if env vars not set
    if not config["sender_email"]:
        env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
        try:
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        key, val = line.split("=", 1)
                        key = key.strip()
                        val = val.strip()
                        if key == "SENDER_EMAIL":
                            config["sender_email"] = val
                        elif key == "SENDER_PASSWORD":
                            config["sender_password"] = val
                        elif key == "RECIPIENT_EMAIL":
                            config["recipient_email"] = val
                        elif key == "SMTP_SERVER":
                            config["smtp_server"] = val
                        elif key == "SMTP_PORT":
                            config["smtp_port"] = int(val)
        except FileNotFoundError:
            pass

    if not config["sender_email"] or not config["sender_password"]:
        return None

    # Default: send to self
    if not config["recipient_email"]:
        config["recipient_email"] = config["sender_email"]

    return config


def _build_html_email(new_jobs: list[dict], stats: dict) -> str:
    """Build an HTML email body with the new job listings."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    rows = ""
    for i, job in enumerate(new_jobs, 1):
        source = job.get("source_platform", "")
        title = job.get("title", "")
        company = job.get("company", "")
        location = job.get("location", "")
        url = job.get("url", "#")
        tags = job.get("tags", "")

        rows += f"""
        <tr style="border-bottom: 1px solid #eee;">
            <td style="padding: 8px;">{i}</td>
            <td style="padding: 8px;">{source}</td>
            <td style="padding: 8px;"><a href="{url}">{title}</a></td>
            <td style="padding: 8px;">{company}</td>
            <td style="padding: 8px;">{location}</td>
            <td style="padding: 8px; font-size: 12px;">{tags}</td>
        </tr>"""

    total = stats.get("total", 0)
    new_count = stats.get("new_this_run", 0)
    by_platform = stats.get("by_platform", {})
    platform_summary = ", ".join(f"{k}: {v}" for k, v in by_platform.items())

    return f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 900px; margin: 0 auto;">
        <h2>Web3 Job Crawler Report</h2>
        <p><strong>{now}</strong> — {new_count} new jobs found (total tracked: {total})</p>
        <p style="font-size: 13px; color: #666;">Sources: {platform_summary}</p>

        <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
            <thead>
                <tr style="background: #f5f5f5;">
                    <th style="padding: 8px; text-align: left;">#</th>
                    <th style="padding: 8px; text-align: left;">Source</th>
                    <th style="padding: 8px; text-align: left;">Title</th>
                    <th style="padding: 8px; text-align: left;">Company</th>
                    <th style="padding: 8px; text-align: left;">Location</th>
                    <th style="padding: 8px; text-align: left;">Tags</th>
                </tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>

        <p style="margin-top: 20px; font-size: 12px; color: #999;">
            Sent by <a href="https://github.com/go99further/web3-job-crawler">web3-job-crawler</a>
        </p>
    </body>
    </html>
    """


def send_new_jobs_email(
    new_jobs: list[dict],
    stats: dict,
) -> bool:
    """Send email notification with new job listings.

    Args:
        new_jobs: List of dicts with keys: source_platform, title, company,
                  location, url, tags
        stats: Dict from storage.get_stats()

    Returns:
        True if email sent successfully, False otherwise.
    """
    config = _get_email_config()
    if not config:
        print("  [email] No email config found. Set SENDER_EMAIL and SENDER_PASSWORD in .env")
        return False

    if not new_jobs:
        print("  [email] No new jobs to report — skipping email")
        return False

    html = _build_html_email(new_jobs, stats)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[Web3 Jobs] {len(new_jobs)} new listings — {now}"
    msg["From"] = config["sender_email"]
    msg["To"] = config["recipient_email"]
    msg.attach(MIMEText(html, "html"))

    try:
        port = config["smtp_port"]
        if port == 465:
            # SSL mode (port 465)
            with smtplib.SMTP_SSL(config["smtp_server"], port, timeout=30) as server:
                server.login(config["sender_email"], config["sender_password"])
                server.send_message(msg)
        else:
            # STARTTLS mode (port 587)
            with smtplib.SMTP(config["smtp_server"], port, timeout=30) as server:
                server.starttls()
                server.login(config["sender_email"], config["sender_password"])
                server.send_message(msg)
        print(f"  [email] Sent to {config['recipient_email']} ({len(new_jobs)} new jobs)")
        return True
    except Exception as exc:
        # Retry with SSL port 465 if STARTTLS (587) failed
        if port != 465:
            try:
                print(f"  [email] Port {port} failed, retrying with SSL port 465...")
                with smtplib.SMTP_SSL(config["smtp_server"], 465, timeout=30) as server:
                    server.login(config["sender_email"], config["sender_password"])
                    server.send_message(msg)
                print(f"  [email] Sent to {config['recipient_email']} ({len(new_jobs)} new jobs)")
                return True
            except Exception as exc2:
                print(f"  [email] Failed on both ports: {exc2}")
                return False
        print(f"  [email] Failed to send: {exc}")
        return False
