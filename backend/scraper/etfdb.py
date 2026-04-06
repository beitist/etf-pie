"""
ETF database loader from github.com/albertored/etfdb.

Merges 4000+ ETFs with country/sector/holdings data into SQLite.
Used as secondary source after Xetra (fills in allocation data).
"""

import csv
import io
import logging

import httpx

from scraper.db import upsert_allocations, upsert_etf

log = logging.getLogger("etfdb")

BASE_URL = "https://raw.githubusercontent.com/albertored/etfdb/main/csv"


def _parse_csv(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text)))


async def load_etfdb(progress: dict):
    """Download etfdb CSVs and merge into SQLite."""
    progress["phase"] = "etfdb-Daten herunterladen..."
    log.info("Downloading etfdb CSVs...")

    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        files = {}
        for name in ["basic_info.csv", "countries.csv", "sectors.csv", "holdings.csv"]:
            progress["phase"] = f"Lade {name}..."
            resp = await client.get(f"{BASE_URL}/{name}")
            resp.raise_for_status()
            files[name] = resp.text
            log.info(f"  Downloaded {name}: {len(resp.text)} bytes")

    # Parse
    progress["phase"] = "etfdb-Daten verarbeiten..."
    basic_rows = _parse_csv(files["basic_info.csv"])
    country_rows = _parse_csv(files["countries.csv"])
    sector_rows = _parse_csv(files["sectors.csv"])
    holding_rows = _parse_csv(files["holdings.csv"])

    # Build allocation lookups
    country_data = _build_allocation_lookup(country_rows)
    sector_data = _build_allocation_lookup(sector_rows)
    holding_data = _build_allocation_lookup(holding_rows, limit=20)

    # Merge basic info
    count = 0
    for row in basic_rows:
        isin = row.get("isin", "").strip()
        if not isin:
            continue

        def safe_float(val: str) -> float:
            try:
                return float(val.strip()) if val.strip() else 0.0
            except ValueError:
                return 0.0

        upsert_etf(
            isin=isin,
            source="etfdb",
            wkn=row.get("wkn", "").strip(),
            name_display=row.get("name", "").strip(),
            ter=safe_float(row.get("ter", "")),
            replication=row.get("replication", "").strip(),
            distribution=row.get("dividends", "").strip(),
            fund_size=row.get("size", "").strip(),
            currency=row.get("currency", "").strip(),
        )

        # Allocations
        if isin in country_data:
            upsert_allocations("countries", isin, country_data[isin], "etfdb")
        if isin in sector_data:
            upsert_allocations("sectors", isin, sector_data[isin], "etfdb")
        if isin in holding_data:
            upsert_allocations("holdings", isin, holding_data[isin], "etfdb")

        count += 1
        if count % 500 == 0:
            progress["phase"] = f"{count} ETFs aus etfdb verarbeitet..."

    log.info(f"etfdb: {count} ETFs merged")
    progress["phase"] = f"{count} ETFs aus etfdb gemergt"
    return count


def _build_allocation_lookup(
    rows: list[dict], limit: int = 0
) -> dict[str, list[dict]]:
    if not rows:
        return {}

    field_names = [k for k in rows[0].keys() if k != "isin"]
    result: dict[str, list[dict]] = {}

    for row in rows:
        isin = row.get("isin", "").strip()
        if not isin:
            continue
        items = []
        for name in field_names:
            val = row.get(name, "").strip()
            if val and val != "0.0":
                try:
                    weight = float(val)
                    if weight > 0:
                        items.append({"name": name, "weight": weight})
                except ValueError:
                    pass
        if items:
            items.sort(key=lambda x: x["weight"], reverse=True)
            if limit:
                items = items[:limit]
            result[isin] = items

    return result
