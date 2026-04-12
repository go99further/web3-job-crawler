"""
web3_career.py — web3.career job listing scraper.

Source: https://web3.career (HTML pages, public access, no API key required)
Strategy:
  1. Request job listing pages, parse with BeautifulSoup
  2. Filter through web3_filter (Web3 + Junior + Remote)
  3. Return list[Web3CareerRawJob]
"""

from datetime import datetime, timezone
from typing import Any

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from src.filter import DEFAULT_HEADERS, fetch_with_retry, filter_web3_job

WEB3_CAREER_BASE_URL = "https://web3.career"
WEB3_CAREER_PARSER_VERSION = "web3career-v1"

MAX_PAGES = 3

WEB3_CAREER_LIST_URLS = [
    "https://web3.career/remote-jobs",
    "https://web3.career/junior-web3-jobs",
    "https://web3.career/entry-level-web3-jobs",
]


class Web3CareerRawJob(BaseModel):
    source_platform: str = "web3_career"
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
    parser_version: str = WEB3_CAREER_PARSER_VERSION


def _parse_job_cards(html: str, base_url: str) -> list[dict[str, Any]]:
    """Parse web3.career listing page, extract job cards.

    HTML structure (confirmed by live testing):
      - <tr class="table_row ..."> per job row
      - Title: <h2> element
      - Company: <h3> element
      - Tags: <td> > <a> links
      - Link: <td> > <a href="/job-slug">
    """
    soup = BeautifulSoup(html, "lxml")
    results: list[dict[str, Any]] = []

    rows = soup.select("tr[class*=table_row]")
    if not rows:
        rows = soup.select("tr[class*=job]")
    if not rows:
        rows = soup.select("tbody tr, table tr")

    for row in rows:
        title_el = row.select_one("h2")
        if not title_el:
            title_el = row.select_one("h3, .job-title, [class*='title']")
        title = title_el.get_text(strip=True) if title_el else None
        if not title:
            continue

        company_el = row.select_one("h3")
        if not company_el:
            company_el = row.select_one(
                ".company, [class*='company'], [class*='employer']"
            )
        company = company_el.get_text(strip=True) if company_el else "Unknown"

        link_el = row.select_one('a[href^="/"]')
        if not link_el:
            link_el = row.select_one("a[href]")
        href = link_el.get("href", "") if link_el else ""
        if not href:
            continue
        job_url = href if href.startswith("http") else f"{base_url}{href}"

        tag_els = row.select(
            "td a[href*='/jobs/'], td a[href*='/tag/'], .tag, [class*='tag']"
        )
        tags = [t.get_text(strip=True) for t in tag_els if t.get_text(strip=True)]

        salary = None
        for td in row.select("td"):
            text = td.get_text(strip=True)
            if "$" in text or "salary" in text.lower():
                salary = text
                break

        location = "Remote"
        for td in row.select("td"):
            text = td.get_text(strip=True).lower()
            if "remote" in text or "worldwide" in text or "anywhere" in text:
                location = td.get_text(strip=True)
                break

        time_el = row.select_one("time")
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
    """Fetch job detail page, extract full JD HTML."""
    try:
        resp = fetch_with_retry(client, url)
        soup = BeautifulSoup(resp.text, "lxml")
        for selector in [
            ".job-description",
            "[class*='description']",
            "article",
            "main",
            ".content",
        ]:
            el = soup.select_one(selector)
            if el:
                return str(el)
        return resp.text[:5000]
    except Exception:
        return None


def parse_web3_career_page(
    html: str, client: httpx.Client,
) -> list[Web3CareerRawJob]:
    """Parse a single page, filter, return structured job list."""
    raw_items = _parse_job_cards(html, WEB3_CAREER_BASE_URL)
    results: list[Web3CareerRawJob] = []
    crawled_at = datetime.now(timezone.utc)

    for item in raw_items:
        title = item["title"]
        location = item.get("location", "")
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

        results.append(
            Web3CareerRawJob(
                source_url=item["url"],
                canonical_url=item["url"],
                raw_title=title,
                raw_company_name=item["company"],
                raw_description_html=description_html,
                raw_location_text=location or "Remote",
                raw_salary_text=item.get("salary"),
                raw_posted_at_text=item.get("posted_at"),
                tags=all_tags,
                remote_scope="worldwide",
                crawled_at=crawled_at,
            )
        )

    return results


def fetch_web3_career_jobs() -> list[Web3CareerRawJob]:
    """Main entry: scrape web3.career job listing pages."""
    all_jobs: list[Web3CareerRawJob] = []
    seen_urls: set[str] = set()

    with httpx.Client(
        headers=DEFAULT_HEADERS, timeout=30.0, follow_redirects=True,
    ) as client:
        for list_url in WEB3_CAREER_LIST_URLS:
            try:
                response = fetch_with_retry(client, list_url)
                jobs = parse_web3_career_page(response.text, client)
                for job in jobs:
                    if job.source_url not in seen_urls:
                        seen_urls.add(job.source_url)
                        all_jobs.append(job)
                print(f"  [web3.career] {list_url}: {len(jobs)} jobs after filter")
            except Exception as exc:
                print(f"  [web3.career] {list_url} failed: {exc}")
                continue

    return all_jobs
