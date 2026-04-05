"""
ETF database loader from github.com/albertored/etfdb.

Provides 4000+ ETFs with full data: name, ISIN, WKN, TER,
country allocation, sector allocation, top holdings.

Falls back to justETF scraping for ETFs not in the database.
"""

import csv
import io
import json
import logging
import time
from pathlib import Path

import httpx

log = logging.getLogger("etfdb")

DATA_DIR = Path("/app/data")
DB_FILE = DATA_DIR / "etfdb.json"

BASE_URL = "https://raw.githubusercontent.com/albertored/etfdb/main/csv"


def _parse_csv(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text))
    return list(reader)


async def load_etfdb(progress: dict) -> dict:
    """
    Download and parse etfdb CSV files.
    Returns {isin: {name, wkn, ter, countries, sectors, holdings, ...}}
    Cached to disk with 24h TTL.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Check disk cache
    if DB_FILE.exists():
        try:
            data = json.loads(DB_FILE.read_text())
            age_hours = (time.time() - data.get("timestamp", 0)) / 3600
            if age_hours < 24:
                etfs = data.get("etfs", {})
                log.info(f"ETFDB loaded from disk: {len(etfs)} ETFs ({age_hours:.1f}h old)")
                progress["phase"] = f"{len(etfs)} ETFs geladen (aus Cache)"
                progress["total"] = len(etfs)
                progress["done"] = len(etfs)
                progress["status"] = "done"
                return etfs
            log.info(f"ETFDB on disk too old ({age_hours:.1f}h), refreshing")
        except Exception as e:
            log.error(f"ETFDB load error: {e}")

    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        # Download all CSVs in parallel
        progress["phase"] = "ETF-Datenbank herunterladen..."
        log.info("Downloading etfdb CSVs...")

        files = {}
        for name in ["basic_info.csv", "countries.csv", "sectors.csv", "holdings.csv"]:
            progress["phase"] = f"Lade {name}..."
            resp = await client.get(f"{BASE_URL}/{name}")
            resp.raise_for_status()
            files[name] = resp.text
            log.info(f"  Downloaded {name}: {len(resp.text)} bytes")

    # Parse basic info
    progress["phase"] = "Daten verarbeiten..."
    basic_rows = _parse_csv(files["basic_info.csv"])
    country_rows = _parse_csv(files["countries.csv"])
    sector_rows = _parse_csv(files["sectors.csv"])
    holding_rows = _parse_csv(files["holdings.csv"])

    log.info(f"Parsed: {len(basic_rows)} basic, {len(country_rows)} countries, {len(sector_rows)} sectors, {len(holding_rows)} holdings")

    # Build country lookup
    country_data: dict[str, list[dict]] = {}
    if country_rows:
        country_names = [k for k in country_rows[0].keys() if k != "isin"]
        for row in country_rows:
            isin = row.get("isin", "")
            if not isin:
                continue
            countries = []
            for name in country_names:
                val = row.get(name, "").strip()
                if val and val != "0.0":
                    try:
                        weight = float(val)
                        if weight > 0:
                            countries.append({"name": name, "weight": weight})
                    except ValueError:
                        pass
            if countries:
                country_data[isin] = sorted(countries, key=lambda x: x["weight"], reverse=True)

    # Build sector lookup
    sector_data: dict[str, list[dict]] = {}
    if sector_rows:
        sector_names = [k for k in sector_rows[0].keys() if k != "isin"]
        for row in sector_rows:
            isin = row.get("isin", "")
            if not isin:
                continue
            sectors = []
            for name in sector_names:
                val = row.get(name, "").strip()
                if val and val != "0.0":
                    try:
                        weight = float(val)
                        if weight > 0:
                            sectors.append({"name": name, "weight": weight})
                    except ValueError:
                        pass
            if sectors:
                sector_data[isin] = sorted(sectors, key=lambda x: x["weight"], reverse=True)

    # Build holdings lookup
    holding_data: dict[str, list[dict]] = {}
    if holding_rows:
        holding_names = [k for k in holding_rows[0].keys() if k != "isin"]
        for row in holding_rows:
            isin = row.get("isin", "")
            if not isin:
                continue
            holdings = []
            for name in holding_names:
                val = row.get(name, "").strip()
                if val and val != "0.0":
                    try:
                        weight = float(val)
                        if weight > 0:
                            holdings.append({"name": name, "weight": weight})
                    except ValueError:
                        pass
            if holdings:
                holding_data[isin] = sorted(holdings, key=lambda x: x["weight"], reverse=True)[:20]

    # Combine into main dict
    etfs: dict[str, dict] = {}
    for row in basic_rows:
        isin = row.get("isin", "").strip()
        if not isin:
            continue

        def safe_float(val: str) -> float:
            try:
                return float(val.strip()) if val.strip() else 0.0
            except ValueError:
                return 0.0

        etfs[isin] = {
            "name": row.get("name", "").strip(),
            "wkn": row.get("wkn", "").strip(),
            "ter": safe_float(row.get("ter", "")),
            "replication": row.get("replication", "").strip(),
            "distribution": row.get("dividends", "").strip(),
            "fund_size": row.get("size", "").strip(),
            "currency": row.get("currency", "").strip(),
            "countries": country_data.get(isin, []),
            "sectors": sector_data.get(isin, []),
            "holdings": holding_data.get(isin, []),
        }

        if len(etfs) % 1000 == 0:
            progress["phase"] = f"{len(etfs)} ETFs verarbeitet..."

    # Save to disk
    progress["phase"] = "Datenbank speichern..."
    cache = {"timestamp": time.time(), "etfs": etfs}
    DB_FILE.write_text(json.dumps(cache, ensure_ascii=False))
    log.info(f"ETFDB saved: {len(etfs)} ETFs")

    progress["phase"] = f"{len(etfs)} ETFs geladen"
    progress["total"] = len(etfs)
    progress["done"] = len(etfs)
    progress["status"] = "done"

    return etfs
