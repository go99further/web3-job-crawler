"""
telegram_preview.py — Telegram public channel preview page scraper.

Source: https://t.me/s/{channel_name} (public preview, no API key required)
Strategy:
  1. Request t.me/s/{channel} public preview page
  2. Parse message bubbles (.tgme_widget_message_text)
  3. Regex-extract job titles, companies, contact info, tech keywords
  4. Filter through web3_filter (Web3 + Junior + Remote)
  5. Return list[TelegramRawJob]
"""

from datetime import datetime, timezone
import re

import httpx
from bs4 import BeautifulSoup, Tag
from pydantic import BaseModel, Field

from src.filter import DEFAULT_HEADERS, fetch_with_retry, filter_web3_job

TELEGRAM_PREVIEW_BASE = "https://t.me/s"
TELEGRAM_PARSER_VERSION = "telegram-preview-v2"

# Default target channels (public Web3 job channels, confirmed accessible)
DEFAULT_WEB3_TG_CHANNELS: list[str] = [
    "cryptojobslist",         # Crypto job aggregator, emoji-structured, stable
    "blockchain_jobs_remote", # Blockchain remote jobs
    "solidity_jobs",          # Solidity / smart contract jobs
    "defi_jobs",              # DeFi jobs
]

# ── Regex: extract job title ──────────────────────────────────────────────
_EMOJI_TITLE_PATTERN = re.compile(
    r"(?:💼|👔|🧑‍💻|👨‍💻|👩‍💻)\s*\n?\s*([^\n💼🏛️🌍💰✅📍🔗]{5,80})",
    re.UNICODE,
)

_TITLE_PATTERNS = [
    _EMOJI_TITLE_PATTERN,
    re.compile(
        r"(?:we['\u2019]?re hiring|hiring)[:\s]+([^\n!?]{5,80})", re.IGNORECASE
    ),
    re.compile(r"(?:position|role|job)[:\s]+([^\n!?]{5,80})", re.IGNORECASE),
    re.compile(
        r"(?:looking for|seeking)[:\s]+(?:a\s+)?([^\n!?]{5,80})", re.IGNORECASE
    ),
    re.compile(r"\[([^\]]{5,60})\]"),
    re.compile(
        r"^([A-Z][^\n]{5,60}(?:Engineer|Developer|Dev|Designer|Analyst|Manager|"
        r"Specialist))",
        re.MULTILINE,
    ),
]

# ── Regex: extract company name (emoji 🏛️ → "at Company") ────────────────
_EMOJI_COMPANY_PATTERN = re.compile(
    r"🏛️\s*\n?\s*(?:at\s+)?([A-Z][^\n]{2,40})",
    re.UNICODE,
)

# ── Regex: extract apply link ─────────────────────────────────────────────
_APPLY_URL_PATTERN = re.compile(
    r"(?:✅|apply\s*→|apply\s+(?:at|via|here|now)[:\s]*)(https?://\S+)",
    re.IGNORECASE | re.UNICODE,
)
# Handle multiline: ✅\nApply →\nhttps://...
_APPLY_URL_MULTILINE_PATTERN = re.compile(
    r"(?:✅|apply\s*[→>])\s*\n\s*(https?://\S+)|"
    r"(?:✅|apply\s*[→>])\s*\n[^\n]*\n\s*(https?://\S+)",
    re.IGNORECASE | re.UNICODE,
)

_CONTACT_PATTERNS = [
    _APPLY_URL_PATTERN,
    _APPLY_URL_MULTILINE_PATTERN,
    re.compile(r"apply\s+(?:at|via|here|now)[:\s]*(https?://\S+)", re.IGNORECASE),
    re.compile(r"(?:apply|dm|contact)[:\s]*(https?://\S+)", re.IGNORECASE),
    re.compile(r"https?://(?:jobs\.|careers\.|apply\.)\S+"),
    re.compile(r"@[\w]{3,32}"),
    re.compile(r"t\.me/[\w/]+"),
]


class TelegramRawJob(BaseModel):
    source_platform: str = "telegram"
    source_url: str
    canonical_url: str | None = None
    raw_title: str
    raw_company_name: str
    raw_description_html: str | None = None
    raw_location_text: str | None = None
    raw_salary_text: str | None = None
    raw_posted_at_text: str | None = None
    company_website: str | None = None
    tags: list[str] = Field(default_factory=list)
    employment_type: str | None = None
    remote_scope: str | None = "worldwide"
    crawled_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    parser_version: str = TELEGRAM_PARSER_VERSION


def _extract_title(text: str) -> str | None:
    """Extract job title from message text. Prefers emoji-structured format."""
    for pattern in _TITLE_PATTERNS:
        match = pattern.search(text)
        if match:
            title = match.group(1).strip().rstrip(".,!?|—-").strip()
            title = re.sub(r"[💼🏛️🌍💰✅📍🔗👔🧑‍💻]", "", title).strip()
            if 3 <= len(title) <= 100:
                return title
    # Fallback: first non-empty, non-pure-emoji line
    for line in text.splitlines():
        line = line.strip()
        clean_line = re.sub(r"[^\w\s]", "", line).strip()
        if 5 <= len(line) <= 100 and len(clean_line) > 3:
            return line
    return None


def _extract_company(text: str, channel: str) -> str:
    """Extract company name from message text."""
    m = _EMOJI_COMPANY_PATTERN.search(text)
    if m:
        company = m.group(1).strip().rstrip(".,|—-").strip()
        if 2 <= len(company) <= 50:
            return company

    company_match = re.search(
        r"(?:company|firm|startup|protocol|project|at)[:\s]+([A-Z][\w\s]{2,30})",
        text,
        re.IGNORECASE,
    )
    if company_match:
        return company_match.group(1).strip()

    return f"@{channel}"


def _extract_contact(text: str) -> str | None:
    """Extract contact info or apply link from message text."""
    for pattern in _CONTACT_PATTERNS:
        match = pattern.search(text)
        if match:
            val = (
                next((g for g in match.groups() if g), None)
                if match.lastindex
                else match.group(0)
            )
            if val:
                return val.strip()
    return None


def _extract_tags_from_text(text: str) -> list[str]:
    """Extract possible tech tags from message text (#hashtags + tech terms)."""
    hashtags = re.findall(r"#([\w]+)", text)
    tech_pattern = re.compile(
        r"\b(Solidity|Web3|Ethereum|DeFi|NFT|DAO|Hardhat|Foundry|"
        r"React|Next\.js|TypeScript|Python|Rust|Go|Node\.js|"
        r"Blockchain|Crypto|EVM|Smart Contract)\b",
        re.IGNORECASE,
    )
    tech_words = tech_pattern.findall(text)
    return list({tag.lower() for tag in hashtags + tech_words})


def _parse_channel_messages(html: str, channel: str) -> list[dict]:
    """Parse Telegram public preview page, extract message list."""
    soup = BeautifulSoup(html, "lxml")
    results: list[dict] = []

    messages = soup.select(".tgme_widget_message_wrap, .tgme_widget_message")

    for msg in messages:
        text_el: Tag | None = msg.select_one(  # type: ignore[assignment]
            ".tgme_widget_message_text"
        )
        if not text_el:
            continue
        text = text_el.get_text(separator="\n", strip=True)
        if len(text) < 30:
            continue

        msg_wrap = msg.select_one("[data-post]")
        post_id = msg_wrap.get("data-post", "") if msg_wrap else ""
        if post_id:
            source_url = f"https://t.me/{post_id}"
        else:
            link_el = msg.select_one(
                "a.tgme_widget_message_date, a[href*='t.me']"
            )
            source_url = (
                link_el.get("href", "") if link_el else f"https://t.me/{channel}"
            )

        time_el = msg.select_one("time")
        posted_at = time_el.get("datetime") if time_el else None

        results.append(
            {
                "text": text,
                "text_html": str(text_el),
                "source_url": source_url,
                "posted_at": posted_at,
                "channel": channel,
            }
        )

    return results


def fetch_telegram_channel(
    channel: str,
    client: httpx.Client,
) -> list[TelegramRawJob]:
    """Scrape a single Telegram channel's public preview page."""
    url = f"{TELEGRAM_PREVIEW_BASE}/{channel}"
    crawled_at = datetime.now(timezone.utc)
    results: list[TelegramRawJob] = []

    try:
        response = fetch_with_retry(client, url)
    except Exception as exc:
        print(f"  [telegram] @{channel} failed: {exc}")
        return []

    messages = _parse_channel_messages(response.text, channel)

    for msg in messages:
        text: str = msg["text"]
        text_html: str = msg["text_html"]
        source_url: str = msg["source_url"]

        title = _extract_title(text)
        if not title:
            continue

        contact = _extract_contact(text)
        tags = _extract_tags_from_text(text)
        company = _extract_company(text, channel)

        full_description = text_html
        if contact:
            full_description += (
                f"\n\n<p><strong>Apply:</strong> {contact}</p>"
            )

        result = filter_web3_job(title, text, tags, "remote")
        if not result["pass"]:
            continue

        extra_tags: list[str] = result["extra_tags"]  # type: ignore[assignment]
        all_tags = list(set(tags + extra_tags + [f"telegram:{channel}"]))

        results.append(
            TelegramRawJob(
                source_url=source_url,
                canonical_url=source_url,
                raw_title=title,
                raw_company_name=company,
                raw_description_html=full_description,
                raw_location_text="Remote / Worldwide",
                raw_salary_text=None,
                raw_posted_at_text=msg.get("posted_at"),
                tags=all_tags,
                remote_scope="worldwide",
                crawled_at=crawled_at,
            )
        )

    return results


def fetch_telegram_jobs(
    channels: list[str] | None = None,
) -> list[TelegramRawJob]:
    """Main entry: scrape all target Telegram channels for Web3 job posts."""
    target_channels = channels or DEFAULT_WEB3_TG_CHANNELS
    all_jobs: list[TelegramRawJob] = []

    tg_headers = {
        **DEFAULT_HEADERS,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    with httpx.Client(
        headers=tg_headers, timeout=20.0, follow_redirects=True,
    ) as client:
        for channel in target_channels:
            jobs = fetch_telegram_channel(channel, client)
            all_jobs.extend(jobs)
            print(f"  [telegram] @{channel}: {len(jobs)} valid jobs")

    # Deduplicate
    seen_urls: set[str] = set()
    unique: list[TelegramRawJob] = []
    for job in all_jobs:
        if job.source_url not in seen_urls:
            seen_urls.add(job.source_url)
            unique.append(job)

    return unique
