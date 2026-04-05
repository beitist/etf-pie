"""
ETF data provider: etfdb (primary) + justETF scraping (fallback).

- Search: local index from etfdb (4000+ ETFs, updated monthly)
- Profile: etfdb data if available, justETF scraping as fallback
- 3-level cache: Redis → disk → source
"""

import asyncio
import json
import logging
import os
import re
import time
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

from models.etf import (
    Allocation,
    ChartPoint,
    ETFProfile,
    ETFSearchResult,
    Holding,
    MarketCap,
)
from scraper.cache import TTL_CHART, TTL_PROFILE, cache_get, cache_set
from scraper.etfdb import load_etfdb

log = logging.getLogger("scraper")

SCRAPE_DELAY = float(os.getenv("SCRAPE_DELAY", "1.0"))
_semaphore = asyncio.Semaphore(1)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}

BASE_URL = "https://www.justETF.com/de"
DATA_DIR = Path("/app/data")

# Local ETF database
_etfdb: dict[str, dict] = {}


# ─── HTTP ────────────────────────────────────────────────────────────────

async def _fetch(url: str) -> str:
    async with _semaphore:
        log.info(f"FETCH {url}")
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            resp = await client.get(url, headers=HEADERS)
            log.info(f"  -> {resp.status_code} ({len(resp.text)} bytes, final: {resp.url})")
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


# ─── SEARCH ──────────────────────────────────────────────────────────────

async def search_etf(query: str) -> list[ETFSearchResult]:
    """Search ETFs locally by ISIN, WKN, or name substring."""
    log.info(f"SEARCH query='{query}' (db: {len(_etfdb)} ETFs)")
    q = query.strip().upper()
    results: list[ETFSearchResult] = []

    for isin, data in _etfdb.items():
        name = data.get("name", "")
        wkn = data.get("wkn", "")
        if q in isin or q in name.upper() or (wkn and q in wkn.upper()):
            results.append(ETFSearchResult(
                name=name,
                isin=isin,
                wkn=wkn,
                ter=data.get("ter", 0.0),
                replication=data.get("replication", ""),
                distribution=data.get("distribution", ""),
            ))
        if len(results) >= 20:
            break

    log.info(f"  -> {len(results)} results")
    return results


# ─── PROFILE ─────────────────────────────────────────────────────────────

async def get_etf_profile(isin: str) -> ETFProfile:
    """Get ETF profile. Uses etfdb data if available, justETF scraping as fallback."""
    log.info(f"PROFILE isin='{isin}'")

    # L1: Redis/memory cache
    cache_key = f"profile:{isin}"
    cached = await cache_get(cache_key)
    if cached:
        log.info("  -> redis cache hit")
        return ETFProfile(**cached)

    # Try etfdb first
    db_entry = _etfdb.get(isin)
    if db_entry and db_entry.get("countries"):
        log.info("  -> etfdb hit (has country data)")
        profile = _profile_from_etfdb(isin, db_entry)
        await cache_set(cache_key, profile.model_dump(), TTL_PROFILE)
        return profile

    # L2: Disk cache
    disk_path = DATA_DIR / "profiles" / f"{isin}.json"
    if disk_path.exists():
        try:
            data = json.loads(disk_path.read_text())
            age_hours = (time.time() - data.get("_cached_at", 0)) / 3600
            if age_hours < 24:
                log.info(f"  -> disk cache hit ({age_hours:.1f}h old)")
                data.pop("_cached_at", None)
                profile = ETFProfile(**data)
                await cache_set(cache_key, profile.model_dump(), TTL_PROFILE)
                return profile
        except Exception as e:
            log.error(f"  -> disk cache error: {e}")

    # L3: Scrape justETF as fallback
    log.info("  -> falling back to justETF scraping")
    profile = await _scrape_justetf_profile(isin)

    # Save to caches
    profile_data = profile.model_dump()
    await cache_set(cache_key, profile_data, TTL_PROFILE)
    (DATA_DIR / "profiles").mkdir(parents=True, exist_ok=True)
    disk_data = {**profile_data, "_cached_at": time.time()}
    disk_path.write_text(json.dumps(disk_data, ensure_ascii=False))

    return profile


def _profile_from_etfdb(isin: str, data: dict) -> ETFProfile:
    """Build ETFProfile from etfdb data."""
    return ETFProfile(
        name=data.get("name", isin),
        isin=isin,
        wkn=data.get("wkn", ""),
        ter=data.get("ter", 0.0),
        replication=data.get("replication", ""),
        distribution=data.get("distribution", ""),
        fund_size=str(data.get("fund_size", "")),
        currency=data.get("currency", "EUR"),
        countries=[Allocation(**c) for c in data.get("countries", [])],
        sectors=[Allocation(**s) for s in data.get("sectors", [])],
        holdings=[Holding(name=h["name"], weight=h["weight"]) for h in data.get("holdings", [])],
        market_cap=MarketCap(),
    )


async def _scrape_justetf_profile(isin: str) -> ETFProfile:
    """Scrape full ETF profile from justETF (fallback for ETFs not in etfdb)."""
    url = f"{BASE_URL}/etf-profile.html?isin={isin}"
    try:
        html = await _fetch(url)
    except Exception as e:
        log.error(f"  -> fetch failed: {e}")
        # Return minimal profile from etfdb if available
        db_entry = _etfdb.get(isin, {})
        return ETFProfile(
            name=db_entry.get("name", isin),
            isin=isin,
            wkn=db_entry.get("wkn", ""),
            ter=db_entry.get("ter", 0.0),
        )

    soup = BeautifulSoup(html, "lxml")

    name_el = soup.select_one("h1")
    name = name_el.get_text(strip=True) if name_el else isin

    # data-overview div
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

    wkn = ""
    wkn_match = re.search(r"WKN[:\s]*([A-Z0-9]{6})", soup.get_text())
    if wkn_match:
        wkn = wkn_match.group(1)

    countries = _parse_section_by_heading(soup, ["Länder"])
    sectors = _parse_section_by_heading(soup, ["Sektoren"])
    holdings = _parse_section_by_heading(soup, ["Größte 10 Positionen", "Zusammensetzung", "Top 10"])
    market_cap = _parse_market_cap(soup)

    log.info(f"  -> scraped: countries={len(countries)}, sectors={len(sectors)}, holdings={len(holdings)}")

    return ETFProfile(
        name=name,
        isin=isin,
        wkn=wkn,
        ter=ter,
        replication=replication,
        distribution=distribution,
        fund_size=fund_size,
        countries=countries,
        sectors=sectors,
        holdings=[Holding(name=a.name, weight=a.weight) for a in holdings],
        market_cap=market_cap,
    )


def _parse_section_by_heading(soup: BeautifulSoup, headings: list[str]) -> list[Allocation]:
    for heading_text in headings:
        for h in soup.select("h2, h3"):
            if heading_text.lower() in h.get_text(strip=True).lower():
                table = h.find_next("table")
                if not table:
                    continue
                allocations: list[Allocation] = []
                for row in table.select("tr"):
                    tds = row.select("td")
                    if len(tds) >= 2:
                        name = tds[0].get_text(strip=True)
                        weight = _parse_percent(tds[1].get_text(strip=True))
                        if name and weight > 0:
                            allocations.append(Allocation(name=name, weight=weight))
                if allocations:
                    return sorted(allocations, key=lambda a: a.weight, reverse=True)
    return []


def _parse_market_cap(soup: BeautifulSoup) -> MarketCap:
    mc = MarketCap()
    for h in soup.select("h2, h3"):
        text = h.get_text(strip=True)
        if "Marktkapitalisierung" in text or "Market" in text:
            table = h.find_next("table")
            if table:
                for row in table.select("tr"):
                    tds = row.select("td")
                    if len(tds) >= 2:
                        label = tds[0].get_text(strip=True).lower()
                        val = _parse_percent(tds[1].get_text(strip=True))
                        if "large" in label or "groß" in label:
                            mc.large = val
                        elif "mid" in label or "mittel" in label:
                            mc.mid = val
                        elif "small" in label or "klein" in label:
                            mc.small = val
                        elif "micro" in label:
                            mc.micro = val
            break
    return mc


# ─── CHART DATA ──────────────────────────────────────────────────────────

async def get_chart_data(isin: str, period: str = "2y") -> list[ChartPoint]:
    cache_key = f"chart:{isin}:{period}"
    cached = await cache_get(cache_key)
    if cached:
        return [ChartPoint(**p) for p in cached]

    period_map = {"1m": 1, "3m": 3, "6m": 6, "1y": 12, "2y": 24, "5y": 60}
    months = period_map.get(period, 24)

    url = f"{BASE_URL}/etf-profile.html?isin={isin}&tab=chart"
    html = await _fetch(url)

    points: list[ChartPoint] = []
    scripts = BeautifulSoup(html, "lxml").find_all("script")
    for script in scripts:
        text = script.string or ""
        date_matches = re.findall(r'"(\d{4}-\d{2}-\d{2})"', text)
        value_matches = re.findall(r'(\d+\.\d+)', text)
        if date_matches and value_matches and len(date_matches) == len(value_matches):
            for date, val in zip(date_matches[-months * 21:], value_matches[-months * 21:]):
                try:
                    points.append(ChartPoint(date=date, close=float(val)))
                except ValueError:
                    continue
            break

    if points:
        await cache_set(cache_key, [p.model_dump() for p in points], TTL_CHART)
    return points


# ─── PRELOAD ─────────────────────────────────────────────────────────────

_preload_progress: dict = {"total": 0, "done": 0, "status": "idle", "errors": [], "phase": ""}


async def preload_etf_index():
    """Load ETF database from etfdb GitHub repo."""
    global _etfdb
    _preload_progress["status"] = "loading"
    _preload_progress["phase"] = "ETF-Datenbank laden..."

    try:
        _etfdb = await load_etfdb(_preload_progress)
        log.info(f"ETF database loaded: {len(_etfdb)} ETFs")
    except Exception as e:
        log.error(f"ETF database load failed: {e}")
        _preload_progress["errors"].append(str(e))
        _preload_progress["status"] = "done"
        _preload_progress["phase"] = f"Fehler: {e}"


def get_preload_progress() -> dict:
    return _preload_progress
