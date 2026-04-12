# web3-job-crawler

Automated scraper for **Web3 junior / entry-level remote jobs** across multiple platforms.

Built for career changers (especially from AI/ML backgrounds) who want to break into Web3.

## What It Does

Scrapes 4 data sources every run and applies a **3-layer filter**:

```
Raw listings  →  Web3 keyword check  →  Junior/Entry-level check  →  Remote check  →  Clean results
  (100+)            (is it Web3?)       (is it beginner-friendly?)   (is it remote?)     (5-15)
```

### Data Sources

| Source | URL | Method |
|--------|-----|--------|
| web3.career | https://web3.career | HTML scraping |
| remote3.co | https://remote3.co/web3-jobs | HTML scraping |
| cryptojobs.com | https://cryptojobs.com | HTML scraping |
| Telegram | `t.me/s/{channel}` public preview | HTML + regex |

### Smart Tagging

Jobs that match career-changer-friendly signals get extra tags:

- **AI-Friendly** — mentions AI/ML/Python background, transferable skills, or welcomes career changers
- **Mentorship** — offers mentorship, training, pair programming, or onboarding support

## Quick Start

```bash
# Clone
git clone https://github.com/go99further/web3-job-crawler.git
cd web3-job-crawler

# Install dependencies
pip install -r requirements.txt

# Run
python main.py
```

### Output

```
============================================================
  web3-job-crawler
  Scraping Web3 Junior/Entry-Level Remote Jobs
============================================================

[1/4] Scraping web3.career...
  -> 1 jobs passed filter (4.2s)

[2/4] Scraping remote3.co...
  -> 1 jobs passed filter (3.1s)

[3/4] Scraping cryptojobs.com...
  -> 3 jobs passed filter (1.8s)

[4/4] Scraping Telegram...
  -> 0 jobs passed filter (2.5s)

=================================================
#  Source        Job Title                 Company       Location   Tags
=================================================
1  cryptojobs   Junior Data Engineer      CryptoFirm    Remote     Analytical Thinking
2  cryptojobs   Entry-Level Specialist    TokenCo       Remote     AI-Friendly
3  web3.career  Web3 Bootcamp             Metana        Remote     Mentorship
...
=================================================
Total: 5 jobs  |  AI-Friendly: 1  |  Mentorship: 1

Exported to:
  CSV:  data/web3_jobs_20260412_143022.csv
  JSON: data/web3_jobs_20260412_143022.json
```

## Usage

```bash
# Run all crawlers (default)
python main.py

# Run specific source only
python main.py --source web3       # web3.career only
python main.py --source remote3    # remote3.co only
python main.py --source crypto     # cryptojobs.com only
python main.py --source tg         # Telegram only

# Show table only, no file export
python main.py --table-only

# Custom output directory
python main.py --output-dir ./my_exports
```

## Project Structure

```
web3-job-crawler/
├── main.py                         # CLI entry point
├── src/
│   ├── filter.py                   # 3-layer filter engine (Web3 + Junior + Remote)
│   ├── exporter.py                 # CSV / JSON / table output
│   └── crawlers/
│       ├── web3_career.py          # web3.career scraper
│       ├── remote3.py              # remote3.co scraper
│       ├── crypto_jobs.py          # cryptojobs.com scraper
│       └── telegram_preview.py     # Telegram public channel scraper
├── data/                           # Exported CSV/JSON files (gitignored)
├── requirements.txt
├── pyproject.toml
└── LICENSE
```

## Filter Rules

### Layer 1: Web3 Keywords (50+)
Matches any of: `blockchain`, `web3`, `solidity`, `ethereum`, `defi`, `nft`, `dao`, `smart contract`, `wallet`, `token`, `protocol`, and more.

### Layer 2: Junior / Entry-Level
**Must match**: `junior`, `entry level`, `intern`, `trainee`, `bootcamp`, `no experience`, `willing to train`, etc.
**Must NOT match**: `senior`, `lead`, `principal`, `director`, `5+ years`, etc.

### Layer 3: Remote
Matches: `remote`, `worldwide`, `work from anywhere`, `distributed`, etc.

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

- **Python 3.11+**
- **httpx** — async-capable HTTP client
- **BeautifulSoup4 + lxml** — HTML parsing
- **Pydantic** — data validation & models
- Zero database dependencies — pure file output (CSV/JSON)

## Why This Exists

The Web3 job market is noisy. Most job boards mix senior roles, on-site positions, and non-crypto jobs together. This tool cuts through the noise for people who are:

- Transitioning from AI/ML/traditional tech into Web3
- Looking for their first Web3 role (junior / intern / entry-level)
- Only interested in remote positions

## License

MIT
