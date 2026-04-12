"""
crypto_jobs.py — cryptojobs.com HTML scraper.

Source: https://cryptojobs.com (HTML pages, no API key required)
Strategy:
  1. Request job listing page, parse <article> elements with BeautifulSoup
  2. Filter through web3_filter (Web3 + Junior + Remote)
  3. Return list[CryptoJobsRawJob]
"""

from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from src.filter import DEFAULT_HEADERS, fetch_with_retry, filter_web3_job

CRYPTO_JOBS_BASE_URL = "https://cryptojobs.com"
CRYPTO_JOBS_LIST_URL = "https://cryptojobs.com"
CRYPTO_JOBS_PARSER_VERSION = "cryptojobs-v2"


class CryptoJobsRawJob(BaseModel):
    source_platform: str = "crypto_jobs"
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
    parser_version: str = CRYPTO_JOBS_PARSER_VERSION


def _parse_jobs_html(html: str) -> list[dict]:
    """Parse cryptojobs.com HTML page, extract job cards from <article> elements."""
    soup = BeautifulSoup(html, "lxml")
    results: list[dict] = []

    cards = soup.select("article")
    if not cards:
        cards = soup.select(
            '[class*="job-card"], [class*="JobCard"], [class*="listing"]'
        )

    for card in cards:
        title_el = card.select_one("h2, h3, h4, [class*='title'], [class*='Title']")
        title = title_el.get_text(strip=True) if title_el else None
        if not title or len(title) < 3:
            continue

        link_el = card.select_one(
            'a[href*="/job/"], a[href*="/jobs/"], a[href^="/"]'
        )
        if not link_el:
            link_el = card.select_one("a[href]")
        href = link_el.get("href", "") if link_el else ""
        if not href:
            continue
        job_url = href if href.startswith("http") else f"{CRYPTO_JOBS_BASE_URL}{href}"

        company_el = card.select_one(
            '[class*="company"], [class*="Company"], [class*="employer"],'
            '[class*="Employer"], [itemprop="name"]'
        )
        company = company_el.get_text(strip=True) if company_el else "Unknown"

        tag_els = card.select(
            '[class*="tag"], [class*="Tag"], [class*="badge"],'
            '[class*="category"], [class*="skill"]'
        )
        tags = [t.get_text(strip=True) for t in tag_els if t.get_text(strip=True)]

        salary_el = card.select_one(
            '[class*="salary"], [class*="Salary"], [class*="pay"], '
            '[class*="compensation"]'
        )
        salary = salary_el.get_text(strip=True) if salary_el else None

        location_el = card.select_one(
            '[class*="location"], [class*="Location"], [class*="remote"],'
            '[class*="Remote"], [itemprop="jobLocation"]'
        )
        location = location_el.get_text(strip=True) if location_el else "Remote"

        time_el = card.select_one(
            "time, [class*='date'], [class*='Date'], [datetime]"
        )
        posted_at = (
            time_el.get("datetime") or time_el.get_text(strip=True)
            if time_el
            else None
        )

        results.append(
            {
                "title": title,
                "company": company,
                "url": job_url,
                "tags": tags,
                "salary": salary,
                "location": location,
                "posted_at": posted_at,
            }
        )

    return results


def fetch_crypto_jobs() -> list[CryptoJobsRawJob]:
    """Main entry: scrape cryptojobs.com job listings."""
    all_jobs: list[CryptoJobsRawJob] = []
    crawled_at = datetime.now(timezone.utc)

    with httpx.Client(
        headers=DEFAULT_HEADERS, timeout=20.0, follow_redirects=True,
    ) as client:
        try:
            response = fetch_with_retry(client, CRYPTO_JOBS_LIST_URL)
        except Exception as exc:
            print(f"  [cryptojobs] scraping failed: {exc}")
            return []

        raw_items = _parse_jobs_html(response.text)

        for item in raw_items:
            title = item["title"]
            location = item.get("location", "Remote")
            tags = item.get("tags", [])

            result = filter_web3_job(title, " ".join(tags), tags, location)
            if not result["pass"]:
                continue

            extra_tags: list[str] = result["extra_tags"]  # type: ignore[assignment]
            all_tags = list(set(tags + extra_tags))

            all_jobs.append(
                CryptoJobsRawJob(
                    source_url=item["url"],
                    canonical_url=item["url"],
                    raw_title=title,
                    raw_company_name=item["company"],
                    raw_description_html=None,
                    raw_location_text=location,
                    raw_salary_text=item.get("salary"),
                    raw_posted_at_text=item.get("posted_at"),
                    tags=all_tags,
                    remote_scope="worldwide",
                    crawled_at=crawled_at,
                )
            )

    # Deduplicate
    seen_urls: set[str] = set()
    unique: list[CryptoJobsRawJob] = []
    for job in all_jobs:
        if job.source_url not in seen_urls:
            seen_urls.add(job.source_url)
            unique.append(job)

    return unique
