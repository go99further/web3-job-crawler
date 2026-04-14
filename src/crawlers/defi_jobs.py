"""
defi_jobs.py — defi.jobs HTML scraper.

Source: https://www.defi.jobs (HTML, public access, no API key required)
Strategy:
  1. Request job listing page, parse a.job-link cards
  2. Filter through web3_filter (Web3 + Junior/Loose + Remote)
  3. Return list[DefiJobsRawJob]

HTML structure (confirmed by live testing):
  - Job cards: <a class="job-link w-inline-block" href="/jobs/...">
  - Title: text content of the link element
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from src.filter import DEFAULT_HEADERS, fetch_with_retry, filter_web3_job

DEFI_JOBS_BASE = "https://www.defi.jobs"
DEFI_JOBS_URL = "https://www.defi.jobs"
PARSER_VERSION = "defi-jobs-v1"


class DefiJobsRawJob(BaseModel):
    source_platform: str = "defi_jobs"
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
    """Parse defi.jobs listing page."""
    soup = BeautifulSoup(html, "lxml")
    results: list[dict] = []
    seen_hrefs: set[str] = set()

    cards = soup.select("a.job-link")

    for card in cards:
        href = card.get("href", "")
        if not href or href in seen_hrefs:
            continue
        seen_hrefs.add(href)

        job_url = (
            href if href.startswith("http") else f"{DEFI_JOBS_BASE}{href}"
        )

        # Title: the main text of the card
        title = card.get_text(strip=True)
        if not title or len(title) < 3:
            continue

        # Company: look for sibling or parent company element
        parent = card.parent
        company = "Unknown"
        if parent:
            company_el = parent.select_one(
                "[class*=company], [class*=Company], [class*=employer]"
            )
            if company_el:
                company = company_el.get_text(strip=True)
            else:
                # Try text content around the card
                all_text = parent.get_text(separator="|", strip=True)
                parts = [p.strip() for p in all_text.split("|") if p.strip()]
                for part in parts:
                    if part != title and 2 <= len(part) <= 40 and part[0].isupper():
                        company = part
                        break

        # Location: check for "Remote" in parent text
        parent_text = parent.get_text() if parent else ""
        location = "Remote" if "remote" in parent_text.lower() else "Unknown"

        # Employment type
        emp_type = None
        pt_lower = parent_text.lower()
        if "full-time" in pt_lower or "full time" in pt_lower:
            emp_type = "Full-Time"
        elif "part-time" in pt_lower:
            emp_type = "Part-Time"
        elif "contract" in pt_lower:
            emp_type = "Contract"

        results.append(
            {
                "title": title,
                "company": company,
                "url": job_url,
                "location": location,
                "employment_type": emp_type,
            }
        )

    return results


def fetch_defi_jobs() -> list[DefiJobsRawJob]:
    """Main entry: scrape defi.jobs listings."""
    crawled_at = datetime.now(timezone.utc)

    with httpx.Client(
        headers=DEFAULT_HEADERS, timeout=20.0, follow_redirects=True,
    ) as client:
        try:
            response = fetch_with_retry(client, DEFI_JOBS_URL)
        except Exception as exc:
            print(f"  [defi.jobs] scraping failed: {exc}")
            return []

        raw_items = _parse_jobs(response.text)

    all_jobs: list[DefiJobsRawJob] = []
    for item in raw_items:
        title = item["title"]
        location = item["location"]

        result = filter_web3_job(
            title,
            f"{title} defi blockchain crypto web3",
            ["defi", "crypto", "web3"],
            location,
        )
        if not result["pass"]:
            continue

        extra_tags: list[str] = result["extra_tags"]  # type: ignore[assignment]
        all_tags = list(set(["defi"] + extra_tags))

        all_jobs.append(
            DefiJobsRawJob(
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
