#!/usr/bin/env python3
"""
web3-job-crawler — Scrape Web3 junior/entry-level remote jobs from multiple sources.

Usage:
    python main.py                  # Strict mode: Web3 + Junior + Remote
    python main.py --loose          # Loose mode: Web3 + Remote (exclude senior titles only)
    python main.py --table-only     # Show table only, no file export
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
        "crypto2": ("cryptocurrencyjobs.co", "src.crawlers.cryptocurrencyjobs", "fetch_cryptocurrencyjobs"),
        "twitter": ("X/Twitter", "src.crawlers.twitter", "fetch_twitter_jobs"),
        "builtin": ("builtin.com", "src.crawlers.builtin", "fetch_builtin_jobs"),
        "discord": ("Discord", "src.crawlers.discord", "fetch_discord_jobs"),
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
        description="Scrape Web3 junior/entry-level remote job listings",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                 # Strict: only junior/entry-level Web3 remote jobs
  python main.py --loose         # Loose: all Web3 remote jobs (excludes senior titles)
  python main.py --loose --source web3   # Loose mode, web3.career only
  python main.py --table-only    # Show results without exporting files
""",
    )
    parser.add_argument(
        "--source",
        choices=["web3", "remote3", "crypto", "crypto2", "twitter", "builtin", "discord", "tg"],
        help="Run only a specific crawler (default: all)",
    )
    parser.add_argument(
        "--loose",
        action="store_true",
        help="Loose filter: skip junior-keyword requirement, only exclude senior titles. "
             "Returns 3-10x more results.",
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

    # Set global filter mode
    import src.filter as _filter
    _filter.LOOSE_MODE = args.loose

    mode_label = "LOOSE (Web3 + Remote, exclude senior)" if args.loose else "STRICT (Web3 + Junior + Remote)"

    print("=" * 60)
    print("  web3-job-crawler")
    print(f"  Filter: {mode_label}")
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

    # Save to SQLite for deduplication and history tracking
    from src.storage import upsert_jobs, get_stats
    if unique:
        result = upsert_jobs(unique)
        stats = get_stats()
        print(f"\nDatabase: {stats['total']} total jobs tracked "
              f"({result['new']} new, {result['existing']} seen before)")
        if stats["by_platform"]:
            breakdown = ", ".join(
                f"{k}: {v}" for k, v in stats["by_platform"].items()
            )
            print(f"  By source: {breakdown}")

    # Export files
    if not args.table_only and unique:
        from src.exporter import export_csv, export_json

        csv_path = export_csv(unique, args.output_dir)
        json_path = export_json(unique, args.output_dir)
        print(f"\nExported to:")
        print(f"  CSV:  {csv_path}")
        print(f"  JSON: {json_path}")

    if not unique:
        print("\nTip: Try --loose mode for more results!")
        print("     python main.py --loose")


if __name__ == "__main__":
    main()
