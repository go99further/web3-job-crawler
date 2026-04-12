from .web3_career import fetch_web3_career_jobs, Web3CareerRawJob
from .remote3 import fetch_remote3_jobs, Remote3RawJob
from .crypto_jobs import fetch_crypto_jobs, CryptoJobsRawJob
from .cryptocurrencyjobs import fetch_cryptocurrencyjobs, CryptocurrencyJobsRawJob
from .telegram_preview import fetch_telegram_jobs, TelegramRawJob

__all__ = [
    "fetch_web3_career_jobs", "Web3CareerRawJob",
    "fetch_remote3_jobs", "Remote3RawJob",
    "fetch_crypto_jobs", "CryptoJobsRawJob",
    "fetch_cryptocurrencyjobs", "CryptocurrencyJobsRawJob",
    "fetch_telegram_jobs", "TelegramRawJob",
]
