"""
twitter.py — X/Twitter Web3 job scraper via syndication API.

Source: https://syndication.twitter.com (public, no API key required)
Strategy:
  1. Request syndication timeline for known Web3 job accounts
  2. Parse __NEXT_DATA__ JSON embedded in HTML
  3. Regex-extract job titles, companies, apply links from tweet text
  4. Filter through web3_filter (Web3 + Junior/Loose + Remote)
  5. Return list[TwitterRawJob]

No Twitter API key needed — uses the public syndication/embed endpoint.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

import httpx
from pydantic import BaseModel, Field

from src.filter import DEFAULT_HEADERS, filter_web3_job

SYNDICATION_URL = "https://syndication.twitter.com/srv/timeline-profile/screen-name/{username}"
TWITTER_PARSER_VERSION = "twitter-syndication-v1"

# Known Web3 job posting accounts
DEFAULT_TWITTER_ACCOUNTS: list[str] = [
    "CryptoJobsList",    # Active job aggregator, emoji-structured posts
    "web3career",        # Web3.career official account, 100 tweets
    "cryptaborede",      # Crypto jobs
]

# ── Regex: extract structured job info from tweet text ────────────────────

# Pattern: "Job Title\nCompany Name\n$salary\n...\nApply → URL"
_STRUCTURED_JOB = re.compile(
    r"(?:hiring|is hiring|are hiring|they are hiring)\s+"
    r"([^\n$→←]{5,80})",
    re.IGNORECASE,
)

# Title patterns
_TITLE_PATTERNS = [
    # Emoji-prefixed title: "🗣 Job Title (Remote)" or "🥇 Job Title"
    re.compile(
        r"[🗣🥇🔥💼🔹🔸👉🚀💰📢]\s*([^\n($→←]{5,80})",
    ),
    # "Hiring Job Title" or "They are hiring Job Title"
    re.compile(
        r"(?:hiring|is hiring|are hiring|they are hiring)\s+"
        r"([^\n($→←]{5,80})",
        re.IGNORECASE,
    ),
    # Structured: "Job Title\nCompany\n$salary"
    re.compile(
        r"^([A-Z][^\n]{5,70}(?:Engineer|Developer|Designer|Manager|Analyst|"
        r"Specialist|Lead|Intern|Associate|Coordinator|Writer|Marketer|"
        r"Trader|Auditor|Researcher|Moderator|Consultant))\s*[\n(]",
        re.MULTILINE,
    ),
    # "Job Title (Remote)" on its own line
    re.compile(
        r"^([A-Z][^\n]{5,70}\(Remote\))\s*$",
        re.MULTILINE,
    ),
    # "Position: Job Title"
    re.compile(r"(?:position|role|job|title)[:\s]+([^\n]{5,80})", re.IGNORECASE),
]

# Company pattern: line after title, or "at Company", "@ Company"
_COMPANY_PATTERNS = [
    re.compile(r"(?:at|@)\s+([A-Z][\w\s.&]{2,40}?)(?:\n|$)", re.IGNORECASE),
    re.compile(r"\n([A-Z][\w\s.&]{2,40}?)\n.*(?:remote|\$|salary|apply)", re.IGNORECASE),
]

# Apply URL
_APPLY_URL = re.compile(r"(?:apply|https?://)\s*(https?://\S+)", re.IGNORECASE)

# Salary
_SALARY_PATTERN = re.compile(
    r"\$[\d,]+(?:\s*[-–]\s*\$?[\d,]+)?(?:\s*/\s*(?:year|yr|month|mo|week|hr|hour))?",
    re.IGNORECASE,
)


class TwitterRawJob(BaseModel):
    source_platform: str = "twitter"
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
    parser_version: str = TWITTER_PARSER_VERSION


def _extract_tweets(html: str) -> list[dict]:
    """Extract tweets from syndication page's __NEXT_DATA__ JSON."""
    match = re.search(
        r'<script[^>]*id="__NEXT_DATA__"[^>]*>({.*?})</script>',
        html,
        re.DOTALL,
    )
    if not match:
        return []

    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []

    entries = (
        data.get("props", {})
        .get("pageProps", {})
        .get("timeline", {})
        .get("entries", [])
    )

    tweets: list[dict] = []
    for entry in entries:
        tweet = entry.get("content", {}).get("tweet", {})
        full_text = tweet.get("full_text", "")
        if not full_text or len(full_text) < 30:
            continue

        user = tweet.get("user", {})
        tweet_id = tweet.get("id_str", "")
        screen_name = user.get("screen_name", "")

        # Decode unicode escapes
        try:
            decoded_text = full_text.encode("utf-8").decode("unicode_escape")
        except Exception:
            decoded_text = full_text

        tweets.append(
            {
                "text": decoded_text,
                "tweet_id": tweet_id,
                "screen_name": screen_name,
                "created_at": tweet.get("created_at", ""),
                "source_url": f"https://x.com/{screen_name}/status/{tweet_id}"
                if tweet_id
                else "",
                "is_retweet": full_text.startswith("RT @"),
            }
        )

    return tweets


def _extract_title(text: str) -> str | None:
    """Extract job title from tweet text."""
    for pattern in _TITLE_PATTERNS:
        m = pattern.search(text)
        if m:
            title = m.group(1).strip().rstrip(".,!?|—-()").strip()
            # Reject generic non-titles
            if title.lower().startswith("web3 jobs"):
                continue
            if title.lower().startswith("highlights"):
                continue
            if title.lower().startswith("in web3"):
                continue
            if 3 <= len(title) <= 100:
                return title

    # Fallback: first line that looks like a job title (must be specific)
    for line in text.splitlines():
        line = line.strip()
        if (
            10 <= len(line) <= 80
            and line[0].isupper()
            and not line.lower().startswith("web3 jobs")
            and not line.lower().startswith("this is")
            and any(
                kw in line.lower()
                for kw in [
                    "engineer", "developer", "manager", "analyst",
                    "designer", "intern", "trader", "moderator",
                    "specialist", "coordinator", "associate",
                ]
            )
        ):
            return line.rstrip(".,!?|—-()").strip()
    return None


def _extract_company(text: str, screen_name: str) -> str:
    """Extract company name from tweet text."""
    for pattern in _COMPANY_PATTERNS:
        m = pattern.search(text)
        if m:
            company = m.group(1).strip().rstrip(".,|—-").strip()
            if 2 <= len(company) <= 50:
                return company
    return f"@{screen_name}"


def _extract_tags(text: str) -> list[str]:
    """Extract hashtags and tech keywords from tweet."""
    hashtags = re.findall(r"#(\w+)", text)
    tech_pattern = re.compile(
        r"\b(Solidity|Web3|Ethereum|DeFi|NFT|DAO|Hardhat|Foundry|"
        r"React|TypeScript|Python|Rust|Go|Node\.js|"
        r"Blockchain|Crypto|EVM|Smart Contract|Remote)\b",
        re.IGNORECASE,
    )
    tech_words = tech_pattern.findall(text)
    return list({tag.lower() for tag in hashtags + tech_words})


def fetch_twitter_account(
    username: str,
    client: httpx.Client,
) -> list[TwitterRawJob]:
    """Fetch tweets from a single Twitter account's syndication timeline."""
    url = SYNDICATION_URL.format(username=username)
    crawled_at = datetime.now(timezone.utc)
    results: list[TwitterRawJob] = []

    try:
        resp = client.get(url, timeout=15.0)
        if resp.status_code != 200:
            print(f"  [twitter] @{username}: HTTP {resp.status_code}")
            return []
    except Exception as exc:
        print(f"  [twitter] @{username} failed: {exc}")
        return []

    tweets = _extract_tweets(resp.text)

    for tweet in tweets:
        # Skip retweets
        if tweet["is_retweet"]:
            continue

        text: str = tweet["text"]

        # Must look like a job posting (not a meme, news, or promo)
        job_indicators = [
            "hiring", "apply", "position", "role", "open role",
            "looking for", "we need", "join us", "opportunity",
            "salary:", "salary range", "/year", "/month",
        ]
        text_lower = text.lower()
        if not any(ind in text_lower for ind in job_indicators):
            continue

        # Skip non-job content
        skip_signals = [
            "intelligence report", "we analyzed", "rounded up",
            "best platforms", "top 10", "tips for", "how to",
            "thread", "1/", "meme", "applying for job at",
        ]
        if any(sig in text_lower for sig in skip_signals):
            continue

        title = _extract_title(text)
        if not title:
            continue

        company = _extract_company(text, tweet["screen_name"])
        tags = _extract_tags(text)

        # Extract salary
        salary_match = _SALARY_PATTERN.search(text)
        salary = salary_match.group(0) if salary_match else None

        # Extract apply URL
        apply_match = _APPLY_URL.search(text)
        apply_url = apply_match.group(1) if apply_match else None

        # Location
        location = "Remote" if "remote" in text.lower() else "Unknown"

        # Build description
        description_html = f"<p>{text}</p>"
        if apply_url:
            description_html += f'\n<p><strong>Apply:</strong> <a href="{apply_url}">{apply_url}</a></p>'

        # Filter
        result = filter_web3_job(title, text, tags, location)
        if not result["pass"]:
            continue

        extra_tags: list[str] = result["extra_tags"]  # type: ignore[assignment]
        all_tags = list(set(tags + extra_tags + [f"twitter:@{tweet['screen_name']}"]))

        results.append(
            TwitterRawJob(
                source_url=tweet["source_url"],
                canonical_url=apply_url or tweet["source_url"],
                raw_title=title,
                raw_company_name=company,
                raw_description_html=description_html,
                raw_location_text=location,
                raw_salary_text=salary,
                raw_posted_at_text=tweet["created_at"],
                tags=all_tags,
                remote_scope="worldwide" if "remote" in text.lower() else None,
                crawled_at=crawled_at,
            )
        )

    return results


def fetch_twitter_jobs(
    accounts: list[str] | None = None,
) -> list[TwitterRawJob]:
    """Main entry: scrape Web3 job tweets from known accounts.

    Uses Twitter's public syndication API — no API key needed.
    """
    target_accounts = accounts or DEFAULT_TWITTER_ACCOUNTS
    all_jobs: list[TwitterRawJob] = []

    headers = {
        "User-Agent": DEFAULT_HEADERS["User-Agent"],
        "Accept": "text/html,application/xhtml+xml,*/*",
        "Accept-Language": "en-US,en;q=0.9",
    }

    with httpx.Client(
        headers=headers, timeout=20.0, follow_redirects=True,
    ) as client:
        for username in target_accounts:
            jobs = fetch_twitter_account(username, client)
            all_jobs.extend(jobs)
            print(f"  [twitter] @{username}: {len(jobs)} valid jobs")

    # Deduplicate
    seen_urls: set[str] = set()
    unique: list[TwitterRawJob] = []
    for job in all_jobs:
        if job.source_url not in seen_urls:
            seen_urls.add(job.source_url)
            unique.append(job)

    return unique
