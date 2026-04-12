"""
remote3.py — remote3.co Web3 remote job scraper.

Source: https://remote3.co/web3-jobs (HTML, public access, no API key required)
Strategy:
  1. Request job listing page, parse with BeautifulSoup
  2. Filter through web3_filter (Web3 + Junior + Remote)
  3. Return list[Remote3RawJob]
"""

from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from src.filter import DEFAULT_HEADERS, fetch_with_retry, filter_web3_job

REMOTE3_BASE_URL = "https://remote3.co"
REMOTE3_JOBS_URL = "https://remote3.co/web3-jobs"
REMOTE3_PARSER_VERSION = "remote3-v1"


class Remote3RawJob(BaseModel):
    source_platform: str = "remote3"
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
    parser_version: str = REMOTE3_PARSER_VERSION


def _parse_job_cards(html: str) -> list[dict]:
    """Parse remote3.co job listing page.

    HTML structure (confirmed by live testing):
      - Job cards: <a class="JobListingItem_..."> elements
      - Title: child element with class containing "jobTitle"
      - Link: the card's own href attribute
    """
    soup = BeautifulSoup(html, "lxml")
    results: list[dict] = []

    cards = soup.select('a[class*="JobListingItem"]')
    if not cards:
        cards = soup.select('[class*="JobListing"] a[href]')
    if not cards:
        cards = soup.select('[class*="job-card"], [class*="JobCard"]')

    seen_hrefs: set[str] = set()

    for card in cards:
        href = card.get("href", "")
        if not href or href in seen_hrefs:
            continue
        seen_hrefs.add(href)
        job_url = href if href.startswith("http") else f"{REMOTE3_BASE_URL}{href}"

        title_el = card.select_one(
            '[class*="jobTitle"], [class*="JobTitle"], h2, h3, h4'
        )
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            all_text = card.get_text(separator="\n", strip=True)
            title = next(
                (ln for ln in all_text.splitlines() if 3 <= len(ln) <= 100), ""
            )
        if not title or len(title) < 3:
            continue

        company_el = card.select_one(
            '[class*="company"], [class*="Company"], [class*="employer"],'
            '[class*="Employer"], [class*="org"], small'
        )
        company = company_el.get_text(strip=True) if company_el else "Unknown"

        tag_els = card.select(
            '[class*="tag"], [class*="Tag"], [class*="skill"], [class*="badge"]'
        )
        tags = [t.get_text(strip=True) for t in tag_els if t.get_text(strip=True)]

        salary_el = card.select_one(
            '[class*="salary"], [class*="Salary"], [class*="pay"]'
        )
        salary = salary_el.get_text(strip=True) if salary_el else None

        location_el = card.select_one(
            '[class*="location"], [class*="Location"], [class*="remote"]'
        )
        location = location_el.get_text(strip=True) if location_el else "Remote"

        time_el = card.select_one("time, [class*='date'], [class*='Date']")
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


def _fetch_job_description(client: httpx.Client, url: str) -> str | None:
    """Fetch job detail page, return full JD HTML."""
    try:
        resp = fetch_with_retry(client, url)
        soup = BeautifulSoup(resp.text, "lxml")
        for selector in [
            ".job-description",
            "[class*='description']",
            "[class*='content']",
            "article",
            "main section",
        ]:
            el = soup.select_one(selector)
            if el and len(el.get_text(strip=True)) > 100:
                return str(el)
        return resp.text[:5000]
    except Exception:
        return None


def fetch_remote3_jobs() -> list[Remote3RawJob]:
    """Main entry: scrape remote3.co Web3 remote job listings."""
    all_jobs: list[Remote3RawJob] = []
    crawled_at = datetime.now(timezone.utc)

    with httpx.Client(
        headers=DEFAULT_HEADERS, timeout=30.0, follow_redirects=True,
    ) as client:
        try:
            response = fetch_with_retry(client, REMOTE3_JOBS_URL)
        except Exception as exc:
            print(f"  [remote3] listing page failed: {exc}")
            return []

        raw_items = _parse_job_cards(response.text)

        for item in raw_items:
            title = item["title"]
            location = item.get("location", "Remote")
            tags = item.get("tags", [])

            pre_check = filter_web3_job(title, " ".join(tags), tags, location)
            if not pre_check["pass"] and "not_web3" in pre_check["reasons"]:
                continue

            description_html = _fetch_job_description(client, item["url"])
            description_text = description_html or ""

            result = filter_web3_job(title, description_text, tags, location)
            if not result["pass"]:
                continue

            extra_tags: list[str] = result["extra_tags"]  # type: ignore[assignment]
            all_tags = list(set(tags + extra_tags))

            all_jobs.append(
                Remote3RawJob(
                    source_url=item["url"],
                    canonical_url=item["url"],
                    raw_title=title,
                    raw_company_name=item["company"],
                    raw_description_html=description_html,
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
    unique: list[Remote3RawJob] = []
    for job in all_jobs:
        if job.source_url not in seen_urls:
            seen_urls.add(job.source_url)
            unique.append(job)

    return unique
