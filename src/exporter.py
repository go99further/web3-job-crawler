"""
exporter.py — Export crawled jobs to CSV / JSON files.

Supports:
  - CSV export with human-readable columns
  - JSON export with full structured data
  - Console table output
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _job_to_row(job: Any) -> dict[str, str]:
    """Convert any RawJob model to a flat dict for export."""
    tags = getattr(job, "tags", [])
    clean_tags = [t for t in tags if not t.startswith("telegram:")]
    return {
        "source": getattr(job, "source_platform", ""),
        "title": getattr(job, "raw_title", ""),
        "company": getattr(job, "raw_company_name", ""),
        "location": getattr(job, "raw_location_text", "") or "Remote",
        "salary": getattr(job, "raw_salary_text", "") or "",
        "tags": ", ".join(clean_tags),
        "url": getattr(job, "source_url", ""),
        "posted_at": getattr(job, "raw_posted_at_text", "") or "",
        "crawled_at": str(getattr(job, "crawled_at", "")),
    }


def export_csv(jobs: list[Any], output_dir: str = "data") -> str:
    """Export jobs to a timestamped CSV file. Returns the file path."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filepath = f"{output_dir}/web3_jobs_{timestamp}.csv"

    if not jobs:
        print("  No jobs to export.")
        return filepath

    rows = [_job_to_row(j) for j in jobs]
    fieldnames = list(rows[0].keys())

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return filepath


def export_json(jobs: list[Any], output_dir: str = "data") -> str:
    """Export jobs to a timestamped JSON file. Returns the file path."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filepath = f"{output_dir}/web3_jobs_{timestamp}.json"

    rows = [_job_to_row(j) for j in jobs]

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    return filepath


def print_table(jobs: list[Any]) -> None:
    """Print a formatted table to console."""
    if not jobs:
        print("\n  No jobs found matching the filter criteria.\n")
        return

    rows = [_job_to_row(j) for j in jobs]

    # Column widths
    W = {"#": 3, "src": 14, "ttl": 48, "co": 22, "loc": 14, "sal": 16, "tag": 30}
    total_w = sum(W.values()) + len(W)
    bar = "=" * total_w

    print(f"\n{bar}")
    print(
        f"{'#':<{W['#']}}"
        f"{'Source':<{W['src']}}"
        f"{'Job Title':<{W['ttl']}}"
        f"{'Company':<{W['co']}}"
        f"{'Location':<{W['loc']}}"
        f"{'Salary':<{W['sal']}}"
        f"{'Tags':<{W['tag']}}"
    )
    print(bar)

    for i, row in enumerate(rows, 1):
        print(
            f"{i:<{W['#']}}"
            f"{row['source'][:W['src']-1]:<{W['src']}}"
            f"{row['title'][:W['ttl']-1]:<{W['ttl']}}"
            f"{row['company'][:W['co']-1]:<{W['co']}}"
            f"{row['location'][:W['loc']-1]:<{W['loc']}}"
            f"{(row['salary'] or '-')[:W['sal']-1]:<{W['sal']}}"
            f"{row['tags'][:W['tag']-1]:<{W['tag']}}"
        )
        print(f"   -> {row['url']}")

    print(bar)
    ai_cnt = sum(1 for r in rows if "AI-Friendly" in r["tags"])
    mentor_cnt = sum(1 for r in rows if "Mentorship" in r["tags"])
    print(f"Total: {len(rows)} jobs  |  AI-Friendly: {ai_cnt}  |  Mentorship: {mentor_cnt}")
    print(bar)
