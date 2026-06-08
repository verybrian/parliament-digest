import logging
import requests
from urllib.parse import unquote
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

BILLS_URL = "https://parliament.go.ke/the-national-assembly/house-business/bills"
REQUEST_TIMEOUT = 30

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://parliament.go.ke/",
}


def _bill_id_from_url(url: str) -> str:
    filename = url.rstrip("/").split("/")[-1]
    return unquote(filename).lower()


def fetch_bills() -> list:
    log.info("Fetching bills listing: %s", BILLS_URL)
    resp = requests.get(BILLS_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT, verify=False)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    bills = []

    for div in soup.select("div.post-title"):
        a = div.find("a", href=True)
        if not a:
            continue
        url = a["href"].strip()
        title = a.get_text(strip=True)
        if url.startswith("/"):
            url = "https://parliament.go.ke" + url
        if not url.lower().endswith(".pdf"):
            continue
        bills.append({"id": _bill_id_from_url(url), "title": title, "url": url})

    if not bills:
        raise ValueError("No bills found — the site layout may have changed.")

    log.info("Found %d bill(s) on the first page", len(bills))
    return bills