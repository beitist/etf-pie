"""
ESMA FIRDS ETF Index Builder.

Downloads the FULINS_C (Collective Investment Instruments) file from ESMA,
extracts all ETFs (UCITS/ETF in name), and builds a local search index.
File is ~3 MB zipped, contains ~7000 ETFs.

Data is official, free, and updated daily by ESMA.
"""

import io
import json
import logging
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import httpx

log = logging.getLogger("esma")

DATA_DIR = Path("/app/data")
INDEX_FILE = DATA_DIR / "etf_index.json"

ESMA_FILES_URL = (
    "https://registers.esma.europa.eu/solr/esma_registers_firds_files/select"
    "?q=*:*&fq=file_type:FULINS&fq=file_name:FULINS_C_*"
    "&rows=1&sort=publication_date+desc&wt=json&fl=download_link,publication_date"
)

NS = "urn:iso:std:iso:20022:tech:xsd:auth.017.001.02"


def _find(el: ET.Element, tag: str) -> str:
    child = el.find(f"{{{NS}}}{tag}")
    return child.text.strip() if child is not None and child.text else ""


async def build_etf_index(progress: dict) -> dict[str, dict]:
    """
    Download ESMA FULINS_C, parse ETFs, return {isin: {name, short_name, currency}}.
    Caches to disk with 24h TTL.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Check disk cache
    if INDEX_FILE.exists():
        try:
            data = json.loads(INDEX_FILE.read_text())
            age_hours = (time.time() - data.get("timestamp", 0)) / 3600
            if age_hours < 24:
                etfs = data.get("etfs", {})
                log.info(f"INDEX loaded from disk: {len(etfs)} ETFs ({age_hours:.1f}h old)")
                progress["phase"] = f"{len(etfs)} ETFs geladen (aus Cache)"
                progress["total"] = len(etfs)
                progress["done"] = len(etfs)
                progress["status"] = "done"
                return etfs
            log.info(f"INDEX on disk too old ({age_hours:.1f}h), refreshing")
        except Exception as e:
            log.error(f"INDEX load error: {e}")

    # Find latest FULINS_C download URL
    progress["phase"] = "ESMA-Register abfragen..."
    log.info("Fetching latest FULINS_C URL from ESMA...")

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(ESMA_FILES_URL, headers={"Accept": "application/json"})
        resp.raise_for_status()
        files = resp.json()["response"]["docs"]
        if not files:
            raise RuntimeError("No FULINS_C files found on ESMA")
        download_url = files[0]["download_link"]
        log.info(f"Download URL: {download_url}")

        # Download ZIP
        progress["phase"] = "ESMA-Datei herunterladen (3 MB)..."
        log.info("Downloading FULINS_C...")
        resp = await client.get(download_url, timeout=120)
        resp.raise_for_status()
        zip_bytes = resp.content
        log.info(f"Downloaded: {len(zip_bytes) / 1024 / 1024:.1f} MB")

    # Unzip
    progress["phase"] = "ETFs extrahieren..."
    z = zipfile.ZipFile(io.BytesIO(zip_bytes))
    xml_data = z.read(z.namelist()[0])
    log.info(f"XML: {len(xml_data) / 1024 / 1024:.0f} MB, parsing...")

    # Parse - extract ETFs
    etfs: dict[str, dict] = {}
    record_count = 0

    for event, elem in ET.iterparse(io.BytesIO(xml_data), events=("end",)):
        if not elem.tag.endswith("RefData"):
            continue
        record_count += 1

        attrs = elem.find(f".//{{{NS}}}FinInstrmGnlAttrbts")
        if attrs is None:
            elem.clear()
            continue

        isin = _find(attrs, "Id")
        name = _find(attrs, "FullNm")

        if not isin or not name:
            elem.clear()
            continue

        # Filter: only ETFs/UCITS
        name_upper = name.upper()
        if "ETF" not in name_upper and "UCITS" not in name_upper:
            elem.clear()
            continue

        # Skip duplicates (keep first/longest name)
        if isin in etfs and len(etfs[isin]["name"]) >= len(name):
            elem.clear()
            continue

        etfs[isin] = {
            "name": name,
            "short_name": _find(attrs, "ShrtNm"),
            "currency": _find(attrs, "NtnlCcy"),
        }

        elem.clear()

        # Progress update every 500 ETFs
        if len(etfs) % 500 == 0:
            progress["phase"] = f"{len(etfs)} ETFs gefunden..."
            progress["done"] = len(etfs)

    log.info(f"Parsed {record_count} records, found {len(etfs)} ETFs")

    # Save to disk
    progress["phase"] = "Index speichern..."
    cache_data = {"timestamp": time.time(), "etfs": etfs}
    INDEX_FILE.write_text(json.dumps(cache_data, ensure_ascii=False))
    log.info(f"INDEX saved: {len(etfs)} ETFs")

    progress["phase"] = f"{len(etfs)} ETFs indexiert"
    progress["total"] = len(etfs)
    progress["done"] = len(etfs)
    progress["status"] = "done"

    return etfs
