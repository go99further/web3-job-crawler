"""
discord.py — Discord Web3 job channel scraper via Bot API.

Source: Discord servers with Web3 job channels
Strategy:
  1. Use Bot token to list joined guilds
  2. Find channels with job-related names (#jobs, #hiring, #careers, etc.)
  3. Read recent messages from those channels
  4. Regex-extract job titles, companies, apply links
  5. Filter through web3_filter (Web3 + Junior/Loose + Remote)
  6. Return list[DiscordRawJob]

Setup:
  1. Create a Discord Bot at https://discord.com/developers/applications
  2. Set DISCORD_BOT_TOKEN in .env file
  3. Invite bot to Web3 job Discord servers using the OAuth2 link
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone

import httpx
from pydantic import BaseModel, Field

from src.filter import filter_web3_job

DISCORD_API_BASE = "https://discord.com/api/v10"
DISCORD_PARSER_VERSION = "discord-v1"

# Channel name patterns that likely contain job postings
JOB_CHANNEL_PATTERNS = [
    "job", "hiring", "career", "recruit", "opportunity", "openings",
    "gig", "position", "vacancy", "work", "employ",
]

# Load token from .env or environment
def _get_bot_token() -> str | None:
    """Load Discord Bot token from environment or .env file."""
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if token:
        return token

    # Try reading .env file
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    try:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("DISCORD_BOT_TOKEN="):
                    return line.split("=", 1)[1].strip()
    except FileNotFoundError:
        pass

    return None


class DiscordRawJob(BaseModel):
    source_platform: str = "discord"
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
    parser_version: str = DISCORD_PARSER_VERSION


# ── Regex: extract job info from Discord messages ─────────────────────────

_TITLE_PATTERNS = [
    # "🔹 Job Title" or "💼 Job Title"
    re.compile(r"[💼🔹🔸👉🚀📢]\s*([^\n]{5,80})"),
    # "**Job Title**" (Discord bold)
    re.compile(r"\*\*([^\n*]{5,80})\*\*"),
    # "Job Title\n" at the start
    re.compile(
        r"^([A-Z][^\n]{5,70}(?:Engineer|Developer|Designer|Manager|Analyst|"
        r"Specialist|Intern|Associate|Coordinator|Trader|Auditor|Researcher|"
        r"Moderator|Writer|Marketer))\s*[\n(]",
        re.MULTILINE,
    ),
    # "Hiring: Job Title" or "Role: Job Title"
    re.compile(
        r"(?:hiring|role|position|job|title)[:\s]+([^\n]{5,80})",
        re.IGNORECASE,
    ),
]

_COMPANY_PATTERNS = [
    # "**Company Name**" or "at Company"
    re.compile(r"(?:at|@|company)[:\s]+([A-Z][\w\s.&]{2,40})", re.IGNORECASE),
    re.compile(r"\*\*([A-Z][\w\s.&]{2,30})\*\*\s+(?:is hiring|hiring|looking)"),
]

_SALARY_PATTERN = re.compile(
    r"\$[\d,]+(?:\s*[-–]\s*\$?[\d,]+)?(?:\s*/\s*(?:year|yr|month|mo|week|hr))?",
    re.IGNORECASE,
)

_URL_PATTERN = re.compile(r"https?://\S+")


def _extract_title(text: str) -> str | None:
    """Extract job title from Discord message."""
    for pattern in _TITLE_PATTERNS:
        m = pattern.search(text)
        if m:
            title = m.group(1).strip().rstrip(".,!?|—-*").strip()
            if 3 <= len(title) <= 100:
                return title

    # Fallback: first line with job-related words
    for line in text.splitlines():
        line = line.strip().strip("*").strip()
        if (
            10 <= len(line) <= 80
            and any(
                kw in line.lower()
                for kw in [
                    "engineer", "developer", "manager", "analyst",
                    "designer", "intern", "trader", "moderator",
                ]
            )
        ):
            return line
    return None


def _extract_company(text: str, guild_name: str) -> str:
    """Extract company name from message."""
    for pattern in _COMPANY_PATTERNS:
        m = pattern.search(text)
        if m:
            company = m.group(1).strip()
            if 2 <= len(company) <= 50:
                return company
    return guild_name


def _extract_tags(text: str) -> list[str]:
    """Extract tech keywords from message."""
    tech_pattern = re.compile(
        r"\b(Solidity|Web3|Ethereum|DeFi|NFT|DAO|Hardhat|Foundry|"
        r"React|TypeScript|Python|Rust|Go|Node\.js|"
        r"Blockchain|Crypto|EVM|Smart Contract|Remote)\b",
        re.IGNORECASE,
    )
    return list({w.lower() for w in tech_pattern.findall(text)})


def _is_job_posting(text: str) -> bool:
    """Check if a message looks like a job posting."""
    indicators = [
        "hiring", "apply", "position", "role", "opportunity",
        "looking for", "we need", "join us", "open role",
        "salary", "remote", "full-time", "part-time", "contract",
        "responsibilities", "requirements", "qualifications",
    ]
    text_lower = text.lower()
    return sum(1 for ind in indicators if ind in text_lower) >= 2


def fetch_discord_jobs() -> list[DiscordRawJob]:
    """Main entry: scrape job postings from Discord servers the bot has joined.

    Requires DISCORD_BOT_TOKEN in .env or environment.
    """
    token = _get_bot_token()
    if not token:
        print("  [discord] No DISCORD_BOT_TOKEN found in .env or environment")
        print("  [discord] Set up: https://discord.com/developers/applications")
        return []

    headers = {
        "Authorization": f"Bot {token}",
        "User-Agent": "web3-job-crawler/1.0",
    }

    all_jobs: list[DiscordRawJob] = []
    crawled_at = datetime.now(timezone.utc)

    with httpx.Client(headers=headers, timeout=15.0) as client:
        # 1. List guilds
        try:
            resp = client.get(f"{DISCORD_API_BASE}/users/@me/guilds")
            if resp.status_code != 200:
                print(f"  [discord] Failed to list guilds: HTTP {resp.status_code}")
                return []
            guilds = resp.json()
        except Exception as exc:
            print(f"  [discord] API error: {exc}")
            return []

        if not guilds:
            print("  [discord] Bot has not joined any servers yet")
            print("  [discord] Invite it using your OAuth2 link to Web3 job servers")
            return []

        for guild in guilds:
            guild_id = guild["id"]
            guild_name = guild["name"]

            # 2. List channels in this guild
            try:
                resp = client.get(f"{DISCORD_API_BASE}/guilds/{guild_id}/channels")
                if resp.status_code != 200:
                    continue
                channels = resp.json()
            except Exception:
                continue

            # 3. Find job-related text channels (type=0 is text channel)
            job_channels = []
            for ch in channels:
                if ch.get("type") != 0:  # text channel only
                    continue
                ch_name = ch.get("name", "").lower()
                if any(pat in ch_name for pat in JOB_CHANNEL_PATTERNS):
                    job_channels.append(ch)

            if not job_channels:
                # Fallback: try "general" channel
                for ch in channels:
                    if ch.get("type") == 0 and ch.get("name", "").lower() in (
                        "general", "chat", "main",
                    ):
                        job_channels.append(ch)
                        break

            # 4. Read recent messages from job channels
            for ch in job_channels:
                ch_id = ch["id"]
                ch_name = ch.get("name", "unknown")

                try:
                    resp = client.get(
                        f"{DISCORD_API_BASE}/channels/{ch_id}/messages",
                        params={"limit": 50},
                    )
                    if resp.status_code != 200:
                        continue
                    messages = resp.json()
                except Exception:
                    continue

                channel_jobs = 0
                for msg in messages:
                    text = msg.get("content", "")
                    if len(text) < 30:
                        continue

                    if not _is_job_posting(text):
                        continue

                    title = _extract_title(text)
                    if not title:
                        continue

                    company = _extract_company(text, guild_name)
                    tags = _extract_tags(text)

                    # Location
                    location = "Remote" if "remote" in text.lower() else "Unknown"

                    # Salary
                    salary_m = _SALARY_PATTERN.search(text)
                    salary = salary_m.group(0) if salary_m else None

                    # Apply URL
                    urls = _URL_PATTERN.findall(text)
                    apply_url = urls[0] if urls else None

                    # Message URL
                    msg_id = msg.get("id", "")
                    source_url = (
                        f"https://discord.com/channels/{guild_id}/{ch_id}/{msg_id}"
                    )

                    # Posted time
                    posted_at = msg.get("timestamp", "")

                    # Filter
                    result = filter_web3_job(title, text, tags, location)
                    if not result["pass"]:
                        continue

                    extra_tags: list[str] = result["extra_tags"]  # type: ignore[assignment]
                    all_tags = list(
                        set(tags + extra_tags + [f"discord:{guild_name}"])
                    )

                    all_jobs.append(
                        DiscordRawJob(
                            source_url=source_url,
                            canonical_url=apply_url or source_url,
                            raw_title=title,
                            raw_company_name=company,
                            raw_description_html=f"<p>{text}</p>",
                            raw_location_text=location,
                            raw_salary_text=salary,
                            raw_posted_at_text=posted_at,
                            tags=all_tags,
                            remote_scope="worldwide"
                            if "remote" in text.lower()
                            else None,
                            crawled_at=crawled_at,
                        )
                    )
                    channel_jobs += 1

                if channel_jobs > 0:
                    print(
                        f"  [discord] {guild_name}/#{ch_name}: "
                        f"{channel_jobs} jobs found"
                    )

        print(f"  [discord] Total: {len(all_jobs)} jobs from {len(guilds)} server(s)")

    # Deduplicate
    seen: set[str] = set()
    unique: list[DiscordRawJob] = []
    for job in all_jobs:
        if job.source_url not in seen:
            seen.add(job.source_url)
            unique.append(job)

    return unique
