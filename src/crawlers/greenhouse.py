"""
greenhouse.py — Greenhouse ATS (Applicant Tracking System) API scraper.

Source: https://boards-api.greenhouse.io/v1/boards/{company}/jobs
Strategy:
  1. Request each company's public job board JSON API (free, no auth)
  2. Optionally fetch full job description from detail endpoint
  3. Filter through web3_filter (Web3 + Junior/Loose + Remote)
  4. Return list[GreenhouseRawJob]

Greenhouse is used by: Coinbase, Ripple, BitGo, Fireblocks, FalconX,
Alchemy, ConsenSys, Avalanche Labs, Paradigm, Figment, and many more.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
from pydantic import BaseModel, Field

from src.filter import DEFAULT_HEADERS, filter_web3_job

GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards/{company}/jobs"
GREENHOUSE_JOB_API = "https://boards-api.greenhouse.io/v1/boards/{company}/jobs/{job_id}"
GREENHOUSE_PARSER_VERSION = "greenhouse-v1"

# Web3 companies on Greenhouse (confirmed working via live API testing)
GREENHOUSE_COMPANIES: list[dict] = [
    {"slug": "coinbase", "name": "Coinbase"},
    {"slug": "ripple", "name": "Ripple"},
    {"slug": "bitgo", "name": "BitGo"},
    {"slug": "fireblocks", "name": "Fireblocks"},
    {"slug": "falconx", "name": "FalconX"},
    {"slug": "alchemy", "name": "Alchemy"},
    {"slug": "consensys", "name": "ConsenSys"},
    {"slug": "avalabs", "name": "Ava Labs"},
    {"slug": "paradigm", "name": "Paradigm"},
    {"slug": "figment", "name": "Figment"},
    {"slug": "layerzerolabs", "name": "LayerZero Labs"},
    {"slug": "aptoslabs", "name": "Aptos Labs"},
    {"slug": "openzeppelin", "name": "OpenZeppelin"},
]


class GreenhouseRawJob(BaseModel):
    source_platform: str = "greenhouse"
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
    parser_version: str = GREENHOUSE_PARSER_VERSION


def _fetch_job_detail(
    client: httpx.Client, company_slug: str, job_id: int,
) -> str | None:
    """Fetch full job description HTML from Greenhouse detail API."""
    url = GREENHOUSE_JOB_API.format(company=company_slug, job_id=job_id)
    try:
        resp = client.get(url, timeout=8.0)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("content", "")
        return None
    except Exception:
        return None


def _fetch_company_jobs(
    client: httpx.Client,
    company: dict,
) -> list[GreenhouseRawJob]:
    """Fetch and filter all jobs for a single company."""
    slug = company["slug"]
    company_name = company["name"]
    url = GREENHOUSE_API.format(company=slug)
    results: list[GreenhouseRawJob] = []
    crawled_at = datetime.now(timezone.utc)

    try:
        resp = client.get(url, timeout=10.0)
        if resp.status_code != 200:
            return []
        data = resp.json()
    except Exception:
        return []

    jobs = data.get("jobs", [])

    for job in jobs:
        title = job.get("title", "")
        if not title:
            continue

        location_obj = job.get("location", {})
        location = location_obj.get("name", "") if location_obj else ""

        departments = [d.get("name", "") for d in job.get("departments", [])]
        offices = [o.get("name", "") for o in job.get("offices", [])]
        tags = [t for t in departments + offices if t]

        job_url = job.get("absolute_url", "")
        updated_at = job.get("updated_at", "")

        # Quick pre-filter: check title + location + tags
        combined_text = f"{title} {location} {' '.join(tags)}"
        pre_result = filter_web3_job(title, combined_text, tags, location)

        if not pre_result["pass"] and "not_web3" in pre_result.get("reasons", []):
            # Not web3-related at all — but for known crypto companies,
            # every job is implicitly web3-related.
            # So we only skip if the filter says not_junior or not_remote
            pass

        # For crypto-native companies, all jobs are web3 by definition
        # So we only filter on junior/senior and remote
        result = filter_web3_job(
            title,
            combined_text + " blockchain crypto web3",  # boost web3 signal
            tags + ["crypto", "web3"],
            location,
        )
        if not result["pass"]:
            continue

        extra_tags: list[str] = result["extra_tags"]  # type: ignore[assignment]
        all_tags = list(set(tags + extra_tags + [f"company:{company_name}"]))

        # Determine remote scope
        loc_lower = location.lower()
        remote_scope = None
        if "remote" in loc_lower:
            remote_scope = "worldwide" if "worldwide" in loc_lower else "remote"

        results.append(
            GreenhouseRawJob(
                source_url=job_url,
                canonical_url=job_url,
                raw_title=title,
                raw_company_name=company_name,
                raw_location_text=location,
                raw_posted_at_text=updated_at,
                tags=all_tags,
                remote_scope=remote_scope,
                crawled_at=crawled_at,
            )
        )

    return results


def fetch_greenhouse_jobs(
    companies: list[dict] | None = None,
) -> list[GreenhouseRawJob]:
    """Main entry: scrape Greenhouse job boards for Web3 companies.

    The Greenhouse API is public, free, and requires no authentication.
    """
    target_companies = companies or GREENHOUSE_COMPANIES
    all_jobs: list[GreenhouseRawJob] = []

    with httpx.Client(
        headers=DEFAULT_HEADERS, timeout=15.0, follow_redirects=True,
    ) as client:
        for company in target_companies:
            jobs = _fetch_company_jobs(client, company)
            all_jobs.extend(jobs)
            if jobs:
                print(
                    f"  [greenhouse] {company['name']}: "
                    f"{len(jobs)} jobs after filter"
                )

    # Deduplicate
    seen: set[str] = set()
    unique: list[GreenhouseRawJob] = []
    for job in all_jobs:
        if job.source_url not in seen:
            seen.add(job.source_url)
            unique.append(job)

    return unique
