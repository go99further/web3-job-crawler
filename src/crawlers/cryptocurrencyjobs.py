"""
cryptocurrencyjobs.py — cryptocurrencyjobs.co HTML scraper.

Source: https://cryptocurrencyjobs.co/web3/ (HTML, public access, no API key required)
Strategy:
  1. Request job listing page, parse <li class="grid"> cards with BeautifulSoup
  2. Filter through web3_filter (Web3 + Junior + Remote)
  3. Return list[CryptocurrencyJobsRawJob]

HTML structure (confirmed by live testing):
  - Job cards: <li class="grid text-sm text-gray-600 ...">
  - Title: <h2> > <a href="/category/company-slug/">
  - Company: <h3> > <a href="/startups/company/">
  - Tags: <span> elements with tech keyword text
  - Location/type: text nodes with "Remote", "Full-Time" etc.
"""

from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from src.filter import DEFAULT_HEADERS, fetch_with_retry, filter_web3_job

CCJOBS_BASE_URL = "https://cryptocurrencyjobs.co"
CCJOBS_PARSER_VERSION = "ccjobs-v1"

# Multiple category pages to maximize coverage
CCJOBS_LIST_URLS = [
    "https://cryptocurrencyjobs.co/web3/",
    "https://cryptocurrencyjobs.co/remote/",
    "https://cryptocurrencyjobs.co/engineering/",
]


class CryptocurrencyJobsRawJob(BaseModel):
    source_platform: str = "cryptocurrencyjobs"
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
    parser_version: str = CCJOBS_PARSER_VERSION


def _parse_jobs_page(html: str) -> list[dict]:
    """Parse cryptocurrencyjobs.co listing page."""
    soup = BeautifulSoup(html, "lxml")
    results: list[dict] = []

    # Job cards are <li class="grid ..."> elements
    cards = soup.select("li.grid")

    for card in cards:
        # Title: h2 > a
        title_el = card.select_one("h2 a")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        if not title or len(title) < 3:
            continue

        href = title_el.get("href", "")
        if not href:
            continue
        job_url = (
            href if href.startswith("http") else f"{CCJOBS_BASE_URL}{href}"
        )

        # Company: h3 > a
        company_el = card.select_one("h3 a")
        company = company_el.get_text(strip=True) if company_el else "Unknown"

        # Extract all text to find location, type, tags
        card_text = card.get_text(separator="|", strip=True)
        parts = [p.strip() for p in card_text.split("|") if p.strip()]

        # Location: look for "Remote" in text parts
        location = "Unknown"
        for part in parts:
            if "remote" in part.lower():
                location = part
                break

        # Employment type
        emp_type = None
        for part in parts:
            if part.lower() in (
                "full-time", "part-time", "contract", "freelance", "internship",
            ):
                emp_type = part
                break

        # Tags: span elements with tech keywords (skip "·", short text, "Featured")
        tag_els = card.select("span")
        tags = []
        for t in tag_els:
            text = t.get_text(strip=True)
            if (
                text
                and len(text) > 1
                and text != "·"
                and text != "Featured"
                and not text.endswith("d")  # skip "5d", "2d" (posted time)
            ):
                tags.append(text)

        # Posted time: span with "d" suffix like "5d", "2h"
        posted_at = None
        for t in tag_els:
            text = t.get_text(strip=True)
            if text and len(text) <= 4 and (
                text.endswith("d") or text.endswith("h") or text.endswith("m")
            ):
                posted_at = text
                break

        results.append(
            {
                "title": title,
                "company": company,
                "url": job_url,
                "tags": tags,
                "salary": None,
                "location": location,
                "posted_at": posted_at,
                "employment_type": emp_type,
            }
        )

    return results


def _fetch_job_description(client: httpx.Client, url: str) -> str | None:
    """Fetch job detail page, return description HTML."""
    try:
        resp = fetch_with_retry(client, url)
        soup = BeautifulSoup(resp.text, "lxml")
        for selector in [
            "[class*='description']",
            "[class*='content']",
            "article",
            "main section",
            ".prose",
        ]:
            el = soup.select_one(selector)
            if el and len(el.get_text(strip=True)) > 100:
                return str(el)
        return resp.text[:5000]
    except Exception:
        return None


def fetch_cryptocurrencyjobs() -> list[CryptocurrencyJobsRawJob]:
    """Main entry: scrape cryptocurrencyjobs.co listings."""
    all_jobs: list[CryptocurrencyJobsRawJob] = []
    seen_urls: set[str] = set()
    crawled_at = datetime.now(timezone.utc)

    with httpx.Client(
        headers=DEFAULT_HEADERS, timeout=30.0, follow_redirects=True,
    ) as client:
        for list_url in CCJOBS_LIST_URLS:
            try:
                response = fetch_with_retry(client, list_url)
            except Exception as exc:
                print(f"  [cryptocurrencyjobs] {list_url} failed: {exc}")
                continue

            raw_items = _parse_jobs_page(response.text)

            for item in raw_items:
                url = item["url"]
                if url in seen_urls:
                    continue

                title = item["title"]
                location = item.get("location", "Remote")
                tags = item.get("tags", [])

                # Pre-filter: skip if not Web3 at all
                pre_check = filter_web3_job(title, " ".join(tags), tags, location)
                if not pre_check["pass"] and "not_web3" in pre_check["reasons"]:
                    continue

                # Fetch detail page for full description
                description_html = _fetch_job_description(client, url)
                description_text = description_html or ""

                result = filter_web3_job(title, description_text, tags, location)
                if not result["pass"]:
                    continue

                seen_urls.add(url)
                extra_tags: list[str] = result["extra_tags"]  # type: ignore[assignment]
                all_tags = list(set(tags + extra_tags))

                all_jobs.append(
                    CryptocurrencyJobsRawJob(
                        source_url=url,
                        canonical_url=url,
                        raw_title=title,
                        raw_company_name=item["company"],
                        raw_description_html=description_html,
                        raw_location_text=location,
                        raw_salary_text=item.get("salary"),
                        raw_posted_at_text=item.get("posted_at"),
                        tags=all_tags,
                        employment_type=item.get("employment_type"),
                        remote_scope="worldwide",
                        crawled_at=crawled_at,
                    )
                )

            print(
                f"  [cryptocurrencyjobs] {list_url}: "
                f"{len([j for j in all_jobs if j.source_url.startswith(CCJOBS_BASE_URL)])} "
                f"total after filter"
            )

    return all_jobs
