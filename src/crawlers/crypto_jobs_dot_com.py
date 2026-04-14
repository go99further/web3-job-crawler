"""
crypto_jobs_dot_com.py — crypto.jobs HTML scraper.

Source: https://crypto.jobs (HTML, public access, no API key required)
Strategy:
  1. Request job listing page, parse a.job-url cards
  2. Filter through web3_filter (Web3 + Junior/Loose + Remote)
  3. Return list[CryptoJobsDotComRawJob]

HTML structure (confirmed by live testing):
  - Job cards: <a class="job-url" href="/jobs/...">
  - Title: <p class="job-title">
  - Company: <span> (first child span after title)
  - Tags/meta: <div class="hidden-xs"> with emoji-prefixed info
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from src.filter import DEFAULT_HEADERS, fetch_with_retry, filter_web3_job

CRYPTO_JOBS_DOT_COM_BASE = "https://crypto.jobs"
CRYPTO_JOBS_DOT_COM_URL = "https://crypto.jobs"
PARSER_VERSION = "crypto-jobs-dot-com-v1"


class CryptoJobsDotComRawJob(BaseModel):
    source_platform: str = "crypto_jobs_com"
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
    remote_scope: str | None = None
    crawled_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    parser_version: str = PARSER_VERSION


def _parse_jobs(html: str) -> list[dict]:
    """Parse crypto.jobs listing page."""
    soup = BeautifulSoup(html, "lxml")
    results: list[dict] = []

    cards = soup.select("a.job-url")

    for card in cards:
        href = card.get("href", "")
        if not href:
            continue
        job_url = (
            href if href.startswith("http") else f"{CRYPTO_JOBS_DOT_COM_BASE}{href}"
        )

        # Title
        title_el = card.select_one(".job-title, p")
        title = title_el.get_text(strip=True) if title_el else ""
        if not title or len(title) < 3:
            continue

        # Company (span after title)
        spans = card.select("span")
        company = spans[0].get_text(strip=True) if spans else "Unknown"

        # Meta info (emoji-prefixed: 💼 Tech ⏰ Full Time 🌍 Remote)
        meta_el = card.select_one(".hidden-xs, div")
        meta_text = meta_el.get_text(separator=" ", strip=True) if meta_el else ""

        location = "Remote" if "remote" in meta_text.lower() else "Unknown"
        emp_type = None
        if "full time" in meta_text.lower():
            emp_type = "Full-Time"
        elif "part time" in meta_text.lower():
            emp_type = "Part-Time"
        elif "contract" in meta_text.lower():
            emp_type = "Contract"

        # Extract category tags
        tags = []
        if "tech" in meta_text.lower():
            tags.append("Tech")
        if "marketing" in meta_text.lower():
            tags.append("Marketing")
        if "design" in meta_text.lower():
            tags.append("Design")

        results.append(
            {
                "title": title,
                "company": company,
                "url": job_url,
                "tags": tags,
                "location": location,
                "employment_type": emp_type,
            }
        )

    return results


def fetch_crypto_jobs_dot_com() -> list[CryptoJobsDotComRawJob]:
    """Main entry: scrape crypto.jobs listings."""
    crawled_at = datetime.now(timezone.utc)

    with httpx.Client(
        headers=DEFAULT_HEADERS, timeout=20.0, follow_redirects=True,
    ) as client:
        try:
            response = fetch_with_retry(client, CRYPTO_JOBS_DOT_COM_URL)
        except Exception as exc:
            print(f"  [crypto.jobs] scraping failed: {exc}")
            return []

        raw_items = _parse_jobs(response.text)

    all_jobs: list[CryptoJobsDotComRawJob] = []
    for item in raw_items:
        title = item["title"]
        location = item["location"]
        tags = item["tags"]

        result = filter_web3_job(
            title,
            f"{title} {' '.join(tags)} crypto web3 blockchain",
            tags + ["crypto", "web3"],
            location,
        )
        if not result["pass"]:
            continue

        extra_tags: list[str] = result["extra_tags"]  # type: ignore[assignment]
        all_tags = list(set(tags + extra_tags))

        all_jobs.append(
            CryptoJobsDotComRawJob(
                source_url=item["url"],
                canonical_url=item["url"],
                raw_title=title,
                raw_company_name=item["company"],
                raw_location_text=location,
                tags=all_tags,
                employment_type=item.get("employment_type"),
                remote_scope="worldwide" if location == "Remote" else None,
                crawled_at=crawled_at,
            )
        )

    return all_jobs
