# web3-job-crawler

Automated scraper for **Web3 junior / entry-level remote jobs** across multiple platforms.

Built for career changers (especially from AI/ML backgrounds) who want to break into Web3.

## What It Does

Scrapes **5 data sources** every run and applies a **3-layer filter**:

```
Raw listings  →  Web3 keyword check  →  Junior/Entry-level check  →  Remote check  →  Clean results
  (200+)           (is it Web3?)       (is it beginner-friendly?)   (is it remote?)     (5-36+)
```

### Data Sources

| Source | URL | Method |
|--------|-----|--------|
| web3.career | https://web3.career | HTML scraping |
| remote3.co | https://remote3.co/web3-jobs | HTML scraping |
| cryptojobs.com | https://cryptojobs.com | HTML scraping |
| cryptocurrencyjobs.co | https://cryptocurrencyjobs.co | HTML scraping |
| Telegram | `t.me/s/{channel}` public preview | HTML + regex |

### Smart Tagging

Jobs that match career-changer-friendly signals get extra tags:

- **AI-Friendly** — mentions AI/ML/Python background, transferable skills, or welcomes career changers
- **Mentorship** — offers mentorship, training, pair programming, or onboarding support
- **Junior-Confirmed** — explicitly contains junior/entry-level keywords (in loose mode)

## Quick Start

```bash
# Clone
git clone https://github.com/go99further/web3-job-crawler.git
cd web3-job-crawler

# Install dependencies
pip install -r requirements.txt

# Run (strict mode — only junior/entry-level jobs)
python main.py

# Run (loose mode — all Web3 remote jobs, excluding senior titles)
python main.py --loose
```

### Output Example (loose mode, 36 results)

```
============================================================
  web3-job-crawler
  Filter: LOOSE (Web3 + Remote, exclude senior)
============================================================

[1/5] Scraping web3.career...       -> 4 jobs (16.9s)
[2/5] Scraping remote3.co...        -> 4 jobs (22.8s)
[3/5] Scraping cryptojobs.com...    -> 4 jobs (12.6s)
[4/5] Scraping cryptocurrencyjobs.. -> 19 jobs (25.6s)
[5/5] Scraping Telegram...          -> 5 jobs (5.8s)

Total: 36 jobs  |  AI-Friendly: 27  |  Mentorship: 3

Database: 36 total jobs tracked (36 new, 0 seen before)

Exported to:
  CSV:  data/web3_jobs_20260412.csv
  JSON: data/web3_jobs_20260412.json
```

## Usage

```bash
# Strict mode: only junior/entry-level Web3 remote jobs
python main.py

# Loose mode: all Web3 remote jobs (excludes senior titles only) — recommended
python main.py --loose

# Run specific source only
python main.py --source web3       # web3.career only
python main.py --source remote3    # remote3.co only
python main.py --source crypto     # cryptojobs.com only
python main.py --source crypto2    # cryptocurrencyjobs.co only
python main.py --source tg         # Telegram only

# Show table only, no file export
python main.py --table-only

# Custom output directory
python main.py --output-dir ./my_exports
```

## Two Filter Modes

### Strict Mode (default)
All three layers must pass:
1. **Web3 keywords** (60+ terms) — must match at least one
2. **Junior keywords** — must match AND must NOT match senior blacklist
3. **Remote keywords** — must match at least one

Typical result: **3-5 jobs** (very selective)

### Loose Mode (`--loose`) — Recommended
Only two layers:
1. **Web3 keywords** — must match at least one
2. **Remote keywords** — must match at least one
3. Title must NOT contain senior/lead/director (but no junior keyword required)

Typical result: **20-40 jobs** (much broader, with `Junior-Confirmed` tag on verified entry-level roles)

## Project Structure

```
web3-job-crawler/
├── main.py                         # CLI entry point
├── src/
│   ├── filter.py                   # 3-layer filter engine (60+ Web3 keywords)
│   ├── exporter.py                 # CSV / JSON / table output
│   ├── storage.py                  # SQLite dedup + history tracking
│   └── crawlers/
│       ├── web3_career.py          # web3.career scraper
│       ├── remote3.py              # remote3.co scraper
│       ├── crypto_jobs.py          # cryptojobs.com scraper
│       ├── cryptocurrencyjobs.py   # cryptocurrencyjobs.co scraper
│       └── telegram_preview.py     # Telegram public channel scraper
├── data/                           # Exported CSV/JSON files
├── .github/workflows/
│   └── daily-crawl.yml             # GitHub Actions: auto-crawl twice daily
├── requirements.txt
├── pyproject.toml
└── LICENSE
```

## Features

- **5 data sources** — web3.career, remote3.co, cryptojobs.com, cryptocurrencyjobs.co, Telegram
- **3-layer filter** — Web3 + Junior + Remote (strict) or Web3 + Remote (loose)
- **AI career-changer tagging** — auto-detects jobs friendly to AI/ML background switchers
- **SQLite dedup** — tracks job history, marks new listings, avoids duplicates
- **CSV + JSON export** — timestamped output files for analysis
- **GitHub Actions** — auto-crawl twice daily, results committed to repo
- **Zero API keys needed** — all sources are public HTML pages

## Customization

### Add Telegram Channels

Edit `src/crawlers/telegram_preview.py`:

```python
DEFAULT_WEB3_TG_CHANNELS = [
    "cryptojobslist",
    "blockchain_jobs_remote",
    "your_channel_here",     # Add your own
]
```

### Adjust Filter Sensitivity

Edit `src/filter.py` to add/remove keywords from:
- `WEB3_TECH_KEYWORDS` — what counts as a "Web3 job"
- `JUNIOR_KEYWORDS` — what counts as "entry-level"
- `SENIOR_BLACKLIST` — what to exclude
- `REMOTE_KEYWORDS` — what counts as "remote"

## Tech Stack

- **Python 3.11+** — no legacy compatibility burden
- **httpx** — modern HTTP client with retry support
- **BeautifulSoup4 + lxml** — robust HTML parsing
- **Pydantic** — data validation & structured models
- **SQLite** — built-in, zero-config local database
- **GitHub Actions** — free CI/CD for automated crawling

## Why This Exists

The Web3 job market is noisy. Most job boards mix senior roles, on-site positions, and non-crypto jobs together. This tool cuts through the noise for people who are:

- Transitioning from AI/ML/traditional tech into Web3
- Looking for their first Web3 role (junior / intern / entry-level)
- Only interested in remote positions

## License

MIT
