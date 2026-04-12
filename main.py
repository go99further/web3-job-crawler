#!/usr/bin/env python3
"""
web3-job-crawler — Scrape Web3 junior/entry-level remote jobs from multiple sources.

Usage:
    python main.py                  # Run all crawlers, show table, export CSV + JSON
    python main.py --table-only     # Run all crawlers, show table only (no file export)
    python main.py --source web3    # Run only web3.career crawler
    python main.py --source tg      # Run only Telegram crawler
"""

from __future__ import annotations

import argparse
import sys
import time

# Fix Windows console encoding for emoji output
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]


def run_crawlers(source: str | None = None) -> list:
    """Run selected crawlers and return all jobs."""
    all_jobs: list = []

    crawlers = {
        "web3": ("web3.career", "src.crawlers.web3_career", "fetch_web3_career_jobs"),
        "remote3": ("remote3.co", "src.crawlers.remote3", "fetch_remote3_jobs"),
        "crypto": ("cryptojobs.com", "src.crawlers.crypto_jobs", "fetch_crypto_jobs"),
        "tg": ("Telegram", "src.crawlers.telegram_preview", "fetch_telegram_jobs"),
    }

    # Determine which crawlers to run
    if source:
        if source not in crawlers:
            print(f"Unknown source '{source}'. Available: {', '.join(crawlers.keys())}")
            sys.exit(1)
        targets = {source: crawlers[source]}
    else:
        targets = crawlers

    total = len(targets)
    for idx, (key, (label, module_path, func_name)) in enumerate(targets.items(), 1):
        print(f"\n[{idx}/{total}] Scraping {label}...")
        t0 = time.time()

        try:
            import importlib
            mod = importlib.import_module(module_path)
            fetch_fn = getattr(mod, func_name)
            jobs = fetch_fn()
            elapsed = time.time() - t0
            all_jobs.extend(jobs)
            print(f"  -> {len(jobs)} jobs passed filter ({elapsed:.1f}s)")
        except Exception as e:
            elapsed = time.time() - t0
            print(f"  -> FAILED ({elapsed:.1f}s): {e}")

    return all_jobs


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape Web3 junior/entry-level remote job listings"
    )
    parser.add_argument(
        "--source",
        choices=["web3", "remote3", "crypto", "tg"],
        help="Run only a specific crawler (default: all)",
    )
    parser.add_argument(
        "--table-only",
        action="store_true",
        help="Only show table, don't export to files",
    )
    parser.add_argument(
        "--output-dir",
        default="data",
        help="Output directory for CSV/JSON exports (default: data/)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  web3-job-crawler")
    print("  Scraping Web3 Junior/Entry-Level Remote Jobs")
    print("=" * 60)

    # Run crawlers
    all_jobs = run_crawlers(args.source)

    # Deduplicate across sources
    seen: set[str] = set()
    unique: list = []
    for job in all_jobs:
        if job.source_url not in seen:
            seen.add(job.source_url)
            unique.append(job)

    # Display table
    from src.exporter import print_table
    print_table(unique)

    # Export files
    if not args.table_only and unique:
        from src.exporter import export_csv, export_json

        csv_path = export_csv(unique, args.output_dir)
        json_path = export_json(unique, args.output_dir)
        print(f"\nExported to:")
        print(f"  CSV:  {csv_path}")
        print(f"  JSON: {json_path}")

    if not unique:
        print("\nTip: The Web3 junior remote job market is competitive.")
        print("     Try again later — new listings appear daily!")


if __name__ == "__main__":
    main()
