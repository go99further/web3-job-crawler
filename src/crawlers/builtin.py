"""
builtin.py — builtin.com Web3 remote job scraper.

Source: https://builtin.com/jobs/remote/web3 (HTML, public access, no API key required)
Strategy:
  1. Request job listing page, parse div.job-bounded-responsive cards
  2. Filter through web3_filter (Web3 + Junior/Loose + Remote)
  3. Return list[BuiltinRawJob]

HTML structure (confirmed by live testing):
  - Job cards: <div class="job-bounded-responsive ...">
  - Title: <h2> element inside card
  - Company: first text node before title in card
  - Link: <a href="/job/...">
  - Salary/Level: text pipe-separated after location
  - Location: "Remote" or "In-Office or Remote"
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from src.filter import DEFAULT_HEADERS, fetch_with_retry, filter_web3_job

BUILTIN_BASE_URL = "https://builtin.com"
BUILTIN_PARSER_VERSION = "builtin-v1"

BUILTIN_LIST_URLS = [
    "https://builtin.com/jobs/remote/web3",
    "https://builtin.com/jobs/remote/blockchain",
    "https://builtin.com/jobs/remote/crypto",
]


class BuiltinRawJob(BaseModel):
    source_platform: str = "builtin"
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
    parser_version: str = BUILTIN_PARSER_VERSION


def _parse_jobs_page(html: str) -> list[dict]:
    """Parse builtin.com job listing page."""
    soup = BeautifulSoup(html, "lxml")
    results: list[dict] = []

    cards = soup.select("div.job-bounded-responsive")

    for card in cards:
        # Title: h2 element
        title_el = card.select_one("h2")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        if not title or len(title) < 3:
            continue

        # Link: a[href*="/job/"]
        link_el = card.select_one('a[href*="/job/"]')
        href = link_el.get("href", "") if link_el else ""
        if not href:
            continue
        job_url = (
            href if href.startswith("http") else f"{BUILTIN_BASE_URL}{href}"
        )

        # Parse pipe-separated text for structured fields
        full_text = card.get_text(separator="|", strip=True)
        parts = [p.strip() for p in full_text.split("|") if p.strip()]

        # Company: typically the first part before the title
        company = "Unknown"
        for part in parts:
            if part != title and len(part) > 1 and part not in (
                "Saved", "Easy Apply", "Featured",
            ):
                company = part
                break

        # Salary: look for "$" or "Annually"
        salary = None
        for part in parts:
            if "$" in part or "annually" in part.lower() or "/yr" in part.lower():
                salary = part
                break

        # Location
        location = "Unknown"
        for part in parts:
            p_lower = part.lower()
            if "remote" in p_lower:
                location = part
                break

        # Level
        level = None
        for part in parts:
            p_lower = part.lower()
            if p_lower in (
                "senior level", "mid level", "entry level",
                "junior level", "expert/leader", "internship",
            ):
                level = part
                break

        # Posted time
        posted_at = None
        for part in parts:
            if "ago" in part.lower() or "yesterday" in part.lower():
                posted_at = part
                break

        # Tags from collapse section
        collapse_el = card.select_one(".collapse")
        tags: list[str] = []
        if collapse_el:
            collapse_text = collapse_el.get_text(separator="|", strip=True)
            for part in collapse_text.split("|"):
                part = part.strip()
                if (
                    part
                    and len(part) > 2
                    and part not in (salary or "", level or "")
                    and "annually" not in part.lower()
                    and not part.startswith("$")
                ):
                    tags.append(part)

        results.append(
            {
                "title": title,
                "company": company,
                "url": job_url,
                "tags": tags[:8],  # limit tags
                "salary": salary,
                "location": location,
                "posted_at": posted_at,
                "level": level,
            }
        )

    return results


def fetch_builtin_jobs() -> list[BuiltinRawJob]:
    """Main entry: scrape builtin.com Web3/blockchain/crypto remote listings."""
    all_jobs: list[BuiltinRawJob] = []
    seen_urls: set[str] = set()
    crawled_at = datetime.now(timezone.utc)

    with httpx.Client(
        headers=DEFAULT_HEADERS, timeout=30.0, follow_redirects=True,
    ) as client:
        for list_url in BUILTIN_LIST_URLS:
            try:
                response = fetch_with_retry(client, list_url)
            except Exception as exc:
                print(f"  [builtin] {list_url} failed: {exc}")
                continue

            raw_items = _parse_jobs_page(response.text)

            for item in raw_items:
                url = item["url"]
                if url in seen_urls:
                    continue

                title = item["title"]
                location = item.get("location", "Remote")
                tags = item.get("tags", [])

                result = filter_web3_job(
                    title, " ".join(tags), tags, location,
                )
                if not result["pass"]:
                    continue

                seen_urls.add(url)
                extra_tags: list[str] = result["extra_tags"]  # type: ignore[assignment]
                all_tags = list(set(tags + extra_tags))

                all_jobs.append(
                    BuiltinRawJob(
                        source_url=url,
                        canonical_url=url,
                        raw_title=title,
                        raw_company_name=item["company"],
                        raw_location_text=location,
                        raw_salary_text=item.get("salary"),
                        raw_posted_at_text=item.get("posted_at"),
                        tags=all_tags,
                        employment_type=item.get("level"),
                        remote_scope="worldwide" if "remote" in location.lower() else None,
                        crawled_at=crawled_at,
                    )
                )

            print(
                f"  [builtin] {list_url.split('/')[-1]}: "
                f"{len(all_jobs)} total after filter"
            )

    return all_jobs
