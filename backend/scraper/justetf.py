"""
justETF profile scraper.

Scrapes individual ETF profiles from justETF for:
- Full German display name
- TER, replication, distribution
- Country/sector/holdings allocations

Used as highest-quality data source, runs in background worker.
"""

import asyncio
import logging
import os
import re

import httpx
from bs4 import BeautifulSoup

from models.etf import Allocation, MarketCap
from scraper.db import upsert_allocations, upsert_etf

log = logging.getLogger("justetf")

SCRAPE_DELAY = float(os.getenv("SCRAPE_DELAY", "2.0"))
_semaphore = asyncio.Semaphore(1)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

BASE_URL = "https://www.justETF.com/de"


async def _fetch(url: str) -> str:
    async with _semaphore:
        log.info(f"FETCH {url}")
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            resp = await client.get(url, headers=HEADERS)
            log.info(f"  -> {resp.status_code} ({len(resp.text)} bytes)")
            resp.raise_for_status()
            await asyncio.sleep(SCRAPE_DELAY)
            return resp.text


def _parse_percent(text: str) -> float:
    if not text:
        return 0.0
    cleaned = text.strip().replace("%", "").replace(",", ".").replace(" ", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


async def scrape_etf_profile(isin: str) -> bool:
    """
    Scrape one ETF profile from justETF and save to SQLite.
    Returns True on success.
    """
    log.info(f"SCRAPE {isin}")

    url = f"{BASE_URL}/etf-profile.html?isin={isin}"
    try:
        html = await _fetch(url)
    except Exception as e:
        log.error(f"  -> fetch failed: {e}")
        return False

    soup = BeautifulSoup(html, "lxml")

    # Check redirect to search (invalid ISIN)
    if "/search.html" in str(soup.find("link", rel="canonical") or ""):
        log.warning(f"  -> redirected to search, skipping")
        return False

    # Name
    name_el = soup.select_one("h1")
    name = name_el.get_text(strip=True) if name_el else ""
    if not name or name == isin:
        log.warning(f"  -> no name found")
        return False

    log.info(f"  -> {name}")

    # data-overview: TER, Ertragsverwendung, Replikation, Fondsgröße
    ter = 0.0
    replication = ""
    distribution = ""
    fund_size = ""

    dov = soup.select_one("div.data-overview")
    if dov:
        parts = dov.get_text(separator="|", strip=True).split("|")
        for i, part in enumerate(parts):
            p = part.strip()
            if p.startswith("TER") or "% p.a." in p:
                val = p.replace("TER", "").replace("p.a.", "").strip()
                if not val and i + 1 < len(parts):
                    val = parts[i + 1].replace("p.a.", "").strip()
                ter = _parse_percent(val)
            elif p == "Ertragsverwendung" and i + 1 < len(parts):
                distribution = parts[i + 1].strip()
            elif p == "Replikation" and i + 1 < len(parts):
                replication = parts[i + 1].strip()
            elif p == "Fondsgröße" and i + 1 < len(parts):
                fund_size = parts[i + 1].strip()
                if i + 2 < len(parts) and "Mio" in parts[i + 2]:
                    fund_size += " " + parts[i + 2].strip()

    # WKN
    wkn = ""
    wkn_match = re.search(r"WKN[:\s]*([A-Z0-9]{6})", soup.get_text())
    if wkn_match:
        wkn = wkn_match.group(1)

    # Save ETF base data
    upsert_etf(
        isin=isin,
        source="justetf",
        wkn=wkn,
        name_display=name,
        ter=ter,
        replication=replication,
        distribution=distribution,
        fund_size=fund_size,
        mark_scraped=True,
    )

    # Countries
    countries = _parse_section_by_heading(soup, ["Länder"])
    if countries:
        upsert_allocations("countries", isin, countries, "justetf")
        log.info(f"  -> {len(countries)} countries")

    # Sectors
    sectors = _parse_section_by_heading(soup, ["Sektoren"])
    if sectors:
        upsert_allocations("sectors", isin, sectors, "justetf")
        log.info(f"  -> {len(sectors)} sectors")

    # Holdings
    holdings = _parse_section_by_heading(
        soup, ["Größte 10 Positionen", "Zusammensetzung", "Top 10"]
    )
    if holdings:
        upsert_allocations("holdings", isin, holdings, "justetf")
        log.info(f"  -> {len(holdings)} holdings")

    return True


def _parse_section_by_heading(
    soup: BeautifulSoup, headings: list[str]
) -> list[dict]:
    for heading_text in headings:
        for h in soup.select("h2, h3"):
            if heading_text.lower() in h.get_text(strip=True).lower():
                table = h.find_next("table")
                if not table:
                    continue
                items: list[dict] = []
                for row in table.select("tr"):
                    tds = row.select("td")
                    if len(tds) >= 2:
                        name = tds[0].get_text(strip=True)
                        weight = _parse_percent(tds[1].get_text(strip=True))
                        if name and weight > 0:
                            items.append({"name": name, "weight": weight})
                if items:
                    items.sort(key=lambda x: x["weight"], reverse=True)
                    return items
    return []
