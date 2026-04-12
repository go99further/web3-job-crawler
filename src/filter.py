"""
filter.py — Web3 job keyword filtering + AI career-changer friendliness tagging engine.

Pure-function module with zero external dependencies. Shared by all crawler modules.

Three-layer filter:
  1. Web3 tech keyword whitelist  (is it a Web3 job?)
  2. Junior / entry-level check   (is it beginner-friendly?)
  3. Remote keyword whitelist     (is it remote-friendly?)

Set LOOSE_MODE = True to skip the junior-keyword requirement and only exclude
explicitly senior-titled roles. This typically returns 3-10x more results.
"""

from __future__ import annotations

# Global filter mode flag — set by main.py based on --loose CLI arg
LOOSE_MODE: bool = False

# ---------------------------------------------------------------------------
# Web3 tech keyword whitelist (match ANY one → considered Web3 job)
# ---------------------------------------------------------------------------
WEB3_TECH_KEYWORDS: list[str] = [
    # Core concepts
    "blockchain", "web3", "crypto", "cryptocurrency", "decentralized", "dapp",
    "defi", "nft", "dao", "smart contract", "smart-contract",
    # Major chains / ecosystems
    "ethereum", "solana", "near", "cosmos", "polkadot", "avalanche",
    "polygon", "arbitrum", "optimism", "base", "bsc", "binance smart chain",
    "sui", "aptos", "ton", "starknet", "zksync", "layer2", "layer 2",
    # Languages / frameworks
    "solidity", "vyper", "rust", "move", "cairo",
    "web3.js", "ethers.js", "ethers", "wagmi", "viem", "hardhat",
    "foundry", "truffle", "anchor",
    # Infrastructure & wallets
    "ipfs", "chainlink", "openzeppelin", "uniswap", "aave",
    "metamask", "wallet connect", "walletconnect",
    "wallet", "crypto wallet", "multisig", "gnosis safe", "safe wallet",
    # Protocols / concepts
    "evm", "erc20", "erc721", "erc1155", "consensus", "node operator",
    "validator", "staking", "tokenomics",
    # Trading / DeFi infra
    "exchange", "dex", "cex", "trading", "custody", "on-chain", "onchain",
    "token", "protocol", "liquidity", "yield", "bridge", "cross-chain",
    # Role-specific terms
    "blockchain developer", "crypto developer", "web3 developer",
    "onchain analyst", "defi analyst", "crypto analyst", "crypto trader",
    "blockchain engineer", "protocol engineer", "smart contract engineer",
]

# ---------------------------------------------------------------------------
# Junior / entry-level keyword whitelist
# ---------------------------------------------------------------------------
JUNIOR_KEYWORDS: list[str] = [
    # English titles
    "junior", "jr.", "entry level", "entry-level", "entry_level",
    "associate", "graduate", "new grad", "intern", "internship",
    "trainee", "apprentice", "beginner", "starter",
    # Low experience thresholds
    "0-1 year", "0-2 year", "1-2 year", "0+ year", "no experience",
    "no prior experience", "no blockchain experience",
    # Training / growth oriented
    "willing to train", "training provided", "will train",
    "open to career changer", "career change", "bootcamp",
    "self-taught", "fast learner", "eager to learn",
    "beginner friendly", "beginner-friendly",
    # Chinese
    "初级", "实习", "新人", "应届", "零基础", "培训",
]

# ---------------------------------------------------------------------------
# Senior / expert keyword blacklist (match → exclude)
# ---------------------------------------------------------------------------
SENIOR_BLACKLIST: list[str] = [
    "senior", "sr.", "lead", "tech lead", "principal", "staff engineer",
    "director", "head of", "vp ", "vice president", "chief", "cto",
    "architect", "distinguished",
    # High experience requirements (5+ years is clearly senior)
    "5+ years", "6+ years", "7+ years",
    "8+ years", "10+ years", "5 years of experience", "7 years of experience",
    "experienced professional", "seasoned",
    # Chinese
    "高级", "资深", "专家", "首席", "总监",
]

# ---------------------------------------------------------------------------
# Remote work keyword whitelist
# ---------------------------------------------------------------------------
REMOTE_KEYWORDS: list[str] = [
    "remote", "fully remote", "100% remote", "wfh", "work from home",
    "work from anywhere", "anywhere", "worldwide", "global",
    "distributed team", "distributed", "all timezones", "any timezone",
    "globally", "location independent", "location-independent",
    "全球远程", "远程办公", "居家办公", "在家办公",
]

# ---------------------------------------------------------------------------
# AI career-changer friendliness signals
# ---------------------------------------------------------------------------
AI_FRIENDLY_SIGNALS: list[str] = [
    # Tech background transferability
    "ai", "machine learning", "ml", "deep learning", "python",
    "data science", "computer science", "cs degree", "stem",
    "software engineer", "software development", "transferable",
    # Explicitly welcoming career changers
    "open to career changer", "career change", "no blockchain experience",
    "no crypto experience", "willing to train", "training provided",
    "bootcamp graduate", "self-taught", "non-traditional background",
    # Growth culture signals
    "mentorship", "mentor", "learn on the job", "we will teach",
    "growth mindset", "fast learner welcome",
]

MENTORSHIP_KEYWORDS: list[str] = [
    "mentorship", "mentor", "training", "learn on the job",
    "guide you", "coaching", "pair programming", "onboarding support",
]


# ---------------------------------------------------------------------------
# Core filter functions
# ---------------------------------------------------------------------------

def is_web3_job(title: str, description: str, tags: list[str]) -> bool:
    """Check if a job is Web3-related (matches any tech keyword)."""
    combined = f"{title} {description} {' '.join(tags)}".lower()
    return any(kw in combined for kw in WEB3_TECH_KEYWORDS)


def is_junior_job(title: str, description: str) -> bool:
    """Check if a job is junior / entry-level.

    Rule: must match at least one JUNIOR keyword AND not match any SENIOR blacklist.
    """
    combined = f"{title} {description}".lower()
    has_junior = any(kw in combined for kw in JUNIOR_KEYWORDS)
    has_senior = any(kw in combined for kw in SENIOR_BLACKLIST)

    # If the title explicitly contains a senior term, reject immediately
    title_lower = title.lower()
    title_is_senior = any(kw in title_lower for kw in SENIOR_BLACKLIST)

    return has_junior and not has_senior and not title_is_senior


def is_remote_job(title: str, description: str, location: str | None) -> bool:
    """Check if a job is fully remote (matches any remote keyword)."""
    combined = f"{title} {description} {location or ''}".lower()
    return any(kw in combined for kw in REMOTE_KEYWORDS)


def get_ai_friendly_tags(description: str, title: str = "") -> list[str]:
    """Analyze job description and return AI career-changer friendliness tags.

    Returns e.g. ["AI-Friendly", "Mentorship"]
    """
    tags: list[str] = []
    combined = f"{title} {description}".lower()

    ai_signal_count = sum(1 for sig in AI_FRIENDLY_SIGNALS if sig in combined)
    if ai_signal_count >= 2:
        tags.append("AI-Friendly")

    if any(kw in combined for kw in MENTORSHIP_KEYWORDS):
        tags.append("Mentorship")

    return tags


def filter_web3_job(
    title: str,
    description: str,
    tags: list[str],
    location: str | None,
    *,
    loose: bool | None = None,
) -> dict[str, bool | list[str]]:
    """Run all filter layers on a single job listing.

    Args:
        loose: If True, skip the junior-keyword requirement — only exclude
               jobs whose title contains senior/lead/director keywords.
               If None, reads from global LOOSE_MODE flag.

    Returns:
        {
            "pass": bool,            # True = passed all filters
            "extra_tags": list[str]  # Extra tags (e.g. "AI-Friendly")
            "reasons": list[str]     # Rejection reasons if failed
        }
    """
    use_loose = loose if loose is not None else LOOSE_MODE
    reasons: list[str] = []

    if not is_web3_job(title, description, tags):
        reasons.append("not_web3")
        return {"pass": False, "extra_tags": [], "reasons": reasons}

    if use_loose:
        # Loose mode: only reject if title explicitly says senior/lead/etc.
        title_lower = title.lower()
        if any(kw in title_lower for kw in SENIOR_BLACKLIST):
            reasons.append("title_is_senior")
            return {"pass": False, "extra_tags": [], "reasons": reasons}
    else:
        # Strict mode: must match junior keyword AND not match senior
        if not is_junior_job(title, description):
            reasons.append("not_junior")
            return {"pass": False, "extra_tags": [], "reasons": reasons}

    if not is_remote_job(title, description, location):
        reasons.append("not_remote")
        return {"pass": False, "extra_tags": [], "reasons": reasons}

    extra_tags = get_ai_friendly_tags(description, title)

    # In loose mode, tag jobs that DO have junior keywords for easy identification
    if use_loose and is_junior_job(title, description):
        extra_tags.append("Junior-Confirmed")

    return {"pass": True, "extra_tags": extra_tags, "reasons": []}


# ---------------------------------------------------------------------------
# HTTP utilities (shared by all crawlers)
# ---------------------------------------------------------------------------

import httpx  # noqa: E402


def fetch_with_retry(
    client: httpx.Client, url: str, max_attempts: int = 2,
) -> httpx.Response:
    """HTTP GET with retry. Raises RuntimeError after max_attempts failures."""
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            response = client.get(url)
            response.raise_for_status()
            return response
        except httpx.HTTPError as exc:
            last_exc = exc
            if attempt == max_attempts - 1:
                break
    raise RuntimeError(f"Request failed ({max_attempts} attempts): {url}") from last_exc


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
