"""
Xetra instrument list loader.

Downloads the official Deutsche Börse CSV with all tradable instruments.
Filters for ETFs and populates the SQLite DB with ISIN, WKN, and Xetra short names.
"""

import csv
import logging

import httpx

from scraper.db import get_conn, upsert_etf

log = logging.getLogger("xetra")

XETRA_CSV_URL = (
    "https://www.cashmarket.deutsche-boerse.com/resource/blob/1528/"
    "aa3ee859756c46b307263e7cb0a20854/data/t7-xetr-allTradableInstruments.csv"
)


async def load_xetra_instruments(progress: dict):
    """Download Xetra CSV and insert all ETFs into SQLite."""
    progress["phase"] = "Xetra-Instrumentenliste laden..."
    log.info("Downloading Xetra instrument list...")

    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        resp = await client.get(XETRA_CSV_URL)
        resp.raise_for_status()

    text = resp.text
    lines = text.split("\n")
    log.info(f"Xetra CSV: {len(lines)} lines")

    # Find header row
    header_idx = None
    for i, line in enumerate(lines):
        if "ISIN" in line and "Instrument" in line and "WKN" in line:
            header_idx = i
            break

    if header_idx is None:
        raise RuntimeError("Could not find header row in Xetra CSV")

    reader = csv.DictReader(lines[header_idx:], delimiter=";")
    count = 0

    for row in reader:
        isin = row.get("ISIN", "").strip()
        name = row.get("Instrument", "").strip()
        wkn = row.get("WKN", "").strip()

        if not isin or not name:
            continue

        # Clean WKN (Xetra pads with leading zeros)
        wkn = wkn.lstrip("0") if wkn else ""
        if len(wkn) < 6 and wkn:
            wkn = wkn.zfill(6)

        upsert_etf(
            isin=isin,
            source="xetra",
            wkn=wkn,
            name_xetra=name,
            name_display=name,  # Will be overwritten by justETF later
            currency=row.get("Currency", "").strip() or "EUR",
        )
        count += 1

        if count % 500 == 0:
            progress["phase"] = f"{count} ETFs aus Xetra geladen..."

    log.info(f"Xetra: {count} ETFs imported")
    progress["phase"] = f"{count} ETFs aus Xetra-Liste"
    progress["done"] = count
    return count
