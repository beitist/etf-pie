"""
justETF profile scraper + ESMA-powered search index.

- Search index: built from ESMA FIRDS (7000+ ETFs, official EU data)
- Profile data: scraped from justETF on demand (countries, sectors, holdings)
- 3-level cache: Redis → disk → scrape
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
from scraper.esma import build_etf_index

log = logging.getLogger("scraper")

SCRAPE_DELAY = float(os.getenv("SCRAPE_DELAY", "1.0"))
_semaphore = asyncio.Semaphore(1)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}

BASE_URL = "https://www.justETF.com/de"
DATA_DIR = Path("/app/data")

# Local ETF index: {isin: {name, short_name, currency}}
_etf_index: dict[str, dict] = {}


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


# ─── SEARCH (ESMA-powered local index) ──────────────────────────────────

async def search_etf(query: str) -> list[ETFSearchResult]:
    """Search ETFs locally by ISIN or name substring."""
    log.info(f"SEARCH query='{query}' (index: {len(_etf_index)} ETFs)")
    q = query.strip().upper()
    results: list[ETFSearchResult] = []

    for isin, data in _etf_index.items():
        name = data.get("name", "")
        short = data.get("short_name", "")
        if q in isin or q in name.upper() or q in short.upper():
            results.append(ETFSearchResult(
                name=name,
                isin=isin,
                wkn=data.get("wkn", ""),
            ))
        if len(results) >= 20:
            break

    log.info(f"  -> {len(results)} results")
    return results


# ─── PROFILE (scrape justETF on demand, cache aggressively) ─────────────

async def get_etf_profile(isin: str) -> ETFProfile:
    log.info(f"PROFILE isin='{isin}'")

    # L1: Redis/memory cache
    cache_key = f"profile:{isin}"
    cached = await cache_get(cache_key)
    if cached:
        log.info("  -> redis cache hit")
        return ETFProfile(**cached)

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

    # L3: Scrape justETF
    url = f"{BASE_URL}/etf-profile.html?isin={isin}"
    try:
        html = await _fetch(url)
    except Exception as e:
        log.error(f"  -> fetch failed: {e}")
        raise

    soup = BeautifulSoup(html, "lxml")

    if "/search.html" in str(soup.find("link", rel="canonical") or ""):
        log.warning("  -> redirected to search, ISIN might be invalid")

    # Name
    name_el = soup.select_one("h1")
    name = name_el.get_text(strip=True) if name_el else isin
    log.info(f"  -> name: {name}")

    # data-overview div: TER, Ertragsverwendung, Replikation, Fondsgröße
    ter = 0.0
    replication = ""
    distribution = ""
    fund_size = ""

    dov = soup.select_one("div.data-overview")
    if dov:
        dov_text = dov.get_text(separator="|", strip=True)
        log.info(f"  -> data-overview: {dov_text[:200]}")
        parts = dov_text.split("|")
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
    log.info(f"  -> ter={ter}, replication={replication}, distribution={distribution}")

    # WKN
    wkn = ""
    wkn_match = re.search(r"WKN[:\s]*([A-Z0-9]{6})", soup.get_text())
    if wkn_match:
        wkn = wkn_match.group(1)

    # Parse sections by heading
    countries = _parse_section_by_heading(soup, ["Länder"])
    sectors = _parse_section_by_heading(soup, ["Sektoren"])
    holdings = _parse_section_by_heading(soup, ["Größte 10 Positionen", "Zusammensetzung", "Top 10"])
    market_cap = _parse_market_cap(soup)

    log.info(f"  -> countries={len(countries)}, sectors={len(sectors)}, holdings={len(holdings)}")

    profile = ETFProfile(
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

    # Save to all caches
    profile_data = profile.model_dump()
    await cache_set(cache_key, profile_data, TTL_PROFILE)

    (DATA_DIR / "profiles").mkdir(parents=True, exist_ok=True)
    disk_data = {**profile_data, "_cached_at": time.time()}
    disk_path.write_text(json.dumps(disk_data, ensure_ascii=False))

    return profile


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
    """Build local ETF index from ESMA FIRDS data."""
    global _etf_index
    _preload_progress["status"] = "loading"
    _preload_progress["phase"] = "ESMA ETF-Index laden..."

    try:
        _etf_index = await build_etf_index(_preload_progress)
    except Exception as e:
        log.error(f"ESMA index build failed: {e}")
        _preload_progress["errors"].append(str(e))
        _preload_progress["status"] = "done"
        _preload_progress["phase"] = f"Fehler: {e}"


def get_preload_progress() -> dict:
    return _preload_progress
