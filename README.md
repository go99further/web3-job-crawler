# web3-job-crawler

Automated scraper for **Web3 remote jobs** across 8 data sources, with smart filtering and email notifications.

Built for career changers (especially from AI/ML backgrounds) who want to break into Web3.

## What It Does

Scrapes **10 data sources** every run, applies a multi-layer filter, and exports results:

```
200+ raw listings → Web3 check → Junior/Senior check → Remote check → 170+ clean results
```

### Data Sources

| # | Source | Method | Typical Results |
|---|--------|--------|-----------------|
| 1 | **Greenhouse** (Coinbase, Ripple, LayerZero, etc.) | JSON API (free, no auth) | ~90 |
| 2 | **X/Twitter** (@web3career, @CryptoJobsList) | Syndication API (no auth) | ~38 |
| 3 | **cryptocurrencyjobs.co** | HTML scraping | ~20 |
| 4 | **defi.jobs** | HTML scraping | ~15 |
| 5 | **builtin.com** | HTML scraping | ~15 |
| 6 | **cryptojobs.com** | HTML scraping | ~6 |
| 7 | **web3.career** | HTML scraping | ~4 |
| 8 | **remote3.co** | HTML scraping | ~4 |
| 9 | **crypto.jobs** | HTML scraping | ~3 |
| 10 | **Telegram** (public channels) | HTML + regex | ~4 |
| | **Total** | | **~200** |

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

**Result: ~200 jobs** (much broader, with `Junior-Confirmed` tag on verified entry-level roles)

## Features

- **10 data sources** — Greenhouse (13 companies), X/Twitter, cryptocurrencyjobs.co, defi.jobs, builtin.com, cryptojobs.com, crypto.jobs, web3.career, remote3.co, Telegram
- **Greenhouse API** — direct access to Coinbase, Ripple, BitGo, Fireblocks, FalconX, Alchemy, ConsenSys, Ava Labs, Paradigm, Figment, LayerZero, Aptos, OpenZeppelin
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
│       ├── greenhouse.py           # Greenhouse API (13 companies)
│       ├── twitter.py              # X/Twitter syndication API
│       ├── cryptocurrencyjobs.py   # cryptocurrencyjobs.co
│       ├── defi_jobs.py            # defi.jobs
│       ├── builtin.py              # builtin.com
│       ├── crypto_jobs.py          # cryptojobs.com
│       ├── crypto_jobs_dot_com.py  # crypto.jobs
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

---

## Manual Job Search Platforms

The following platforms cannot be auto-scraped (login required, JS rendering, or anti-bot protection), but are excellent sources for Web3 jobs. **Check them manually.**

### Job Boards (Login Required)

| Platform | URL | Search Terms |
|----------|-----|-------------|
| **LinkedIn** | https://linkedin.com/jobs | `web3 remote`, `blockchain junior`, `solidity intern` |
| **AngelList / Wellfound** | https://wellfound.com/jobs | Filter: Crypto/Web3 + Remote |
| **Indeed** | https://indeed.com | `web3 developer remote`, `blockchain entry level` |
| **Glassdoor** | https://glassdoor.com/Job | `crypto remote`, `web3 engineer` |

### Web3 Job Boards (Anti-Bot / JS Rendered)

| Platform | URL | Notes |
|----------|-----|-------|
| **CryptoJobsList** | https://cryptojobslist.com | Large Web3 board, Cloudflare protected |
| **Ethlance** | https://ethlance.com | Decentralized job market on Ethereum |
| **Dework** | https://app.dework.xyz | Web3 task/bounty platform, great for first contributions |
| **Layer3** | https://app.layer3.xyz | Web3 quests & bounties, earn while learning |
| **Gitcoin** | https://gitcoin.co | Grants & bounties — ideal first step into Web3 |

### VC Portfolio Company Pages

These top crypto VCs list all their portfolio companies' open roles:

| VC | Portfolio Jobs |
|----|---------------|
| **Paradigm** | https://jobs.paradigm.xyz |
| **a16z Crypto** | https://a16zcrypto.com/portfolio |
| **Polychain Capital** | https://jobs.polychain.capital |
| **Multicoin Capital** | https://multicoin.capital/portfolio |

### Community / Forums

| Platform | URL | How to Use |
|----------|-----|-----------|
| **Hacker News** | https://news.ycombinator.com | Monthly "Who is hiring?" thread (1st of each month), search `web3 remote` |
| **Reddit** | https://reddit.com/r/web3jobs | Web3 job subreddit |
| **Farcaster** | https://warpcast.com | Web3 social network, teams post hiring there |

### DAO / Bounty Platforms

Great for getting your first Web3 experience without a formal job:

| Platform | URL | Best For |
|----------|-----|---------|
| **Dework** | https://app.dework.xyz | DAO task management, paid bounties |
| **Layer3** | https://app.layer3.xyz | Quests & campaigns, earn crypto |
| **Gitcoin** | https://gitcoin.co | Open source bounties & grants |
| **Coordinape** | https://coordinape.com | DAO contributor rewards |
| **DAOhaus** | https://daohaus.club | Discover and join DAOs |

### Top Web3 Company Career Pages

These companies frequently hire and are worth checking directly:

| Company | Careers Page |
|---------|-------------|
| Coinbase | https://www.coinbase.com/careers |
| Binance | https://www.binance.com/en/careers |
| ConsenSys (MetaMask) | https://consensys.io/open-roles |
| Chainlink | https://chain.link/careers |
| Polygon | https://polygon.technology/careers |
| Solana Foundation | https://jobs.solana.com |
| Alchemy | https://www.alchemy.com/careers |
| OpenZeppelin | https://www.openzeppelin.com/jobs |
| LayerZero | https://layerzero.network/careers |
| Aptos Labs | https://aptoslabs.com/careers |
