# web3-job-crawler

Automated scraper for **Web3 remote jobs** across 8 data sources, with smart filtering and email notifications.

Built for career changers (especially from AI/ML backgrounds) who want to break into Web3.

## What It Does

Scrapes **8 data sources** every run, applies a multi-layer filter, and exports results:

```
200+ raw listings → Web3 check → Junior/Senior check → Remote check → 170+ clean results
```

### Data Sources

| # | Source | Method | Typical Results |
|---|--------|--------|-----------------|
| 1 | **Greenhouse** (Coinbase, Ripple, etc.) | JSON API (free, no auth) | ~88 |
| 2 | **X/Twitter** (@web3career, @CryptoJobsList) | Syndication API (no auth) | ~38 |
| 3 | **cryptocurrencyjobs.co** | HTML scraping | ~20 |
| 4 | **builtin.com** | HTML scraping | ~15 |
| 5 | **cryptojobs.com** | HTML scraping | ~6 |
| 6 | **web3.career** | HTML scraping | ~4 |
| 7 | **remote3.co** | HTML scraping | ~4 |
| 8 | **Telegram** (public channels) | HTML + regex | ~4 |
| | **Total** | | **~179** |

### Smart Tagging

- **AI-Friendly** — mentions AI/ML/Python background, transferable skills
- **Mentorship** — offers mentorship, training, pair programming
- **Junior-Confirmed** — explicitly contains junior/entry-level keywords (in loose mode)

## Quick Start

```bash
# Clone
git clone https://github.com/go99further/web3-job-crawler.git
cd web3-job-crawler

# Install dependencies
pip install -r requirements.txt

# Copy and edit config
cp .env.example .env
# Edit .env with your email settings (optional, for notifications)

# Run
python main.py --loose
```

## Usage

```bash
# Loose mode (recommended) — all Web3 remote jobs, exclude senior titles
python main.py --loose

# Strict mode — only junior/entry-level Web3 remote jobs
python main.py

# Run specific source only
python main.py --source greenhouse  # Coinbase, Ripple, etc.
python main.py --source twitter     # X/Twitter
python main.py --source crypto2     # cryptocurrencyjobs.co
python main.py --source builtin     # builtin.com
python main.py --source crypto      # cryptojobs.com
python main.py --source web3        # web3.career
python main.py --source remote3     # remote3.co
python main.py --source tg          # Telegram

# With email notification
python main.py --loose --notify

# Table only, no file export
python main.py --loose --table-only
```

## Two Filter Modes

### Strict Mode (default)
1. Must match Web3 keywords (60+ terms)
2. Must match junior keywords AND not match senior blacklist
3. Must match remote keywords

**Result: ~5 jobs** (very selective)

### Loose Mode (`--loose`)
1. Must match Web3 keywords
2. Title must NOT contain senior/lead/director
3. Must match remote keywords

**Result: ~179 jobs** (much broader, with `Junior-Confirmed` tag on verified entry-level roles)

## Features

- **8 data sources** — Greenhouse, X/Twitter, cryptocurrencyjobs.co, builtin.com, cryptojobs.com, web3.career, remote3.co, Telegram
- **Greenhouse API** — direct access to Coinbase, Ripple, BitGo, Fireblocks, FalconX, Alchemy, ConsenSys, Ava Labs, Paradigm, Figment
- **Smart filter** — Web3 + Junior + Remote triple filter with loose/strict modes
- **AI career-changer tagging** — auto-detects jobs friendly to AI/ML switchers
- **SQLite dedup** — tracks job history, marks new listings
- **CSV + JSON export** — timestamped output files
- **Email notifications** — QQ Mail / Gmail SMTP support
- **GitHub Actions** — auto-crawl twice daily with email notifications
- **Zero API keys needed** — all sources are public (except optional Discord)

## Project Structure

```
web3-job-crawler/
├── main.py                         # CLI entry point
├── src/
│   ├── filter.py                   # Multi-layer filter engine (60+ keywords)
│   ├── exporter.py                 # CSV / JSON / table output
│   ├── storage.py                  # SQLite dedup + history tracking
│   ├── notify.py                   # Email notification (QQ Mail / Gmail)
│   └── crawlers/
│       ├── greenhouse.py           # Greenhouse API (10 companies)
│       ├── twitter.py              # X/Twitter syndication API
│       ├── cryptocurrencyjobs.py   # cryptocurrencyjobs.co
│       ├── builtin.py              # builtin.com
│       ├── crypto_jobs.py          # cryptojobs.com
│       ├── web3_career.py          # web3.career
│       ├── remote3.py              # remote3.co
│       ├── telegram_preview.py     # Telegram public channels
│       └── discord.py              # Discord Bot (opt-in, requires token)
├── data/                           # Exported CSV/JSON + SQLite
├── .env.example                    # Config template
├── .github/workflows/
│   └── daily-crawl.yml             # Auto-crawl twice daily
├── requirements.txt
├── pyproject.toml
└── LICENSE
```

## Customization

### Add Greenhouse Companies

Edit `src/crawlers/greenhouse.py`:

```python
GREENHOUSE_COMPANIES = [
    {"slug": "coinbase", "name": "Coinbase"},
    {"slug": "your-company", "name": "Your Company"},  # Add here
]
```

### Add Telegram Channels

Edit `src/crawlers/telegram_preview.py`:

```python
DEFAULT_WEB3_TG_CHANNELS = [
    "cryptojobslist",
    "your_channel_here",
]
```

### Adjust Filter Keywords

Edit `src/filter.py` — modify `WEB3_TECH_KEYWORDS`, `JUNIOR_KEYWORDS`, `SENIOR_BLACKLIST`, `REMOTE_KEYWORDS`.

## Tech Stack

- **Python 3.11+**
- **httpx** — HTTP client with retry
- **BeautifulSoup4 + lxml** — HTML parsing
- **Pydantic** — data validation
- **SQLite** — built-in local database
- **GitHub Actions** — automated crawling

## License

MIT
