import asyncio
import json
import logging
import os
import re
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

log = logging.getLogger("scraper")

SCRAPE_DELAY = float(os.getenv("SCRAPE_DELAY", "1.0"))
_semaphore = asyncio.Semaphore(1)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}

BASE_URL = "https://www.justETF.com/de"
DATA_DIR = Path("/app/data")

# Pages to scrape for building the ETF index
INDEX_PAGES = [
    f"{BASE_URL}/how-to/msci-world-etfs.html",
    f"{BASE_URL}/how-to/msci-emerging-markets-etfs.html",
    f"{BASE_URL}/how-to/sp-500-etfs.html",
    f"{BASE_URL}/how-to/dax-etfs.html",
    f"{BASE_URL}/how-to/dividend-etfs-world.html",
    f"{BASE_URL}/how-to/invest-in-artificial-intelligence.html",
    f"{BASE_URL}/how-to/invest-in-bitcoin.html",
]

# Local ETF index: {isin: {name, wkn}}
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


# ─── LOCAL ETF INDEX (name + ISIN only, no heavy scraping) ──────────────

def _load_index_from_disk() -> bool:
    """Load ETF index from local JSON file."""
    global _etf_index
    path = DATA_DIR / "etf_index.json"
    if path.exists():
        try:
            data = json.loads(path.read_text())
            ts = data.get("timestamp", 0)
            import time
            age_hours = (time.time() - ts) / 3600
            if age_hours < 24:
                _etf_index = data.get("etfs", {})
                log.info(f"INDEX loaded from disk: {len(_etf_index)} ETFs ({age_hours:.1f}h old)")
                return True
            else:
                log.info(f"INDEX on disk too old ({age_hours:.1f}h), refreshing")
        except Exception as e:
            log.error(f"INDEX load error: {e}")
    return False


def _save_index_to_disk():
    """Persist ETF index to disk."""
    import time
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / "etf_index.json"
    data = {"timestamp": time.time(), "etfs": _etf_index}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    log.info(f"INDEX saved to disk: {len(_etf_index)} ETFs")


async def _build_index_from_page(url: str):
    """Scrape one justETF how-to page for ETF names + ISINs."""
    try:
        html = await _fetch(url)
    except Exception as e:
        log.error(f"INDEX page failed {url}: {e}")
        return

    soup = BeautifulSoup(html, "lxml")

    # Method 1: Find ISINs in table cells
    for table in soup.select("table"):
        for row in table.select("tr"):
            tds = row.select("td")
            for td in tds:
                text = td.get_text(strip=True)
                if re.match(r"^[A-Z]{2}[A-Z0-9]{10}$", text):
                    isin = text
                    name_link = row.select_one("a")
                    name_td = tds[0] if tds else None
                    name = ""
                    if name_link:
                        name = name_link.get_text(strip=True)
                    elif name_td:
                        name = name_td.get_text(strip=True)
                    if isin and name and isin != name and isin not in _etf_index:
                        _etf_index[isin] = {"name": name}

    # Method 2: Links with isin= parameter
    for a in soup.select("a[href*='isin=']"):
        href = a.get("href", "")
        m = re.search(r"isin=([A-Z]{2}[A-Z0-9]{10})", href)
        if m:
            isin = m.group(1)
            name = a.get_text(strip=True)
            if isin and name and len(name) > 5 and isin not in _etf_index:
                _etf_index[isin] = {"name": name}


# ─── SEARCH (local index) ───────────────────────────────────────────────

async def search_etf(query: str) -> list[ETFSearchResult]:
    """Search ETFs locally by ISIN, WKN, or name substring."""
    log.info(f"SEARCH query='{query}' (index: {len(_etf_index)} ETFs)")
    q = query.strip().upper()
    results: list[ETFSearchResult] = []

    for isin, data in _etf_index.items():
        name = data.get("name", "")
        wkn = data.get("wkn", "")
        if (
            q in isin
            or q in name.upper()
            or (wkn and q in wkn.upper())
        ):
            results.append(ETFSearchResult(name=name, isin=isin, wkn=wkn))
        if len(results) >= 20:
            break

    log.info(f"  -> {len(results)} results")
    return results


# ─── PROFILE (scrape on demand, cache aggressively) ─────────────────────

async def get_etf_profile(isin: str) -> ETFProfile:
    log.info(f"PROFILE isin='{isin}'")

    # Check redis/memory cache
    cache_key = f"profile:{isin}"
    cached = await cache_get(cache_key)
    if cached:
        log.info(f"  -> cache hit")
        return ETFProfile(**cached)

    # Check disk cache
    disk_path = DATA_DIR / "profiles" / f"{isin}.json"
    if disk_path.exists():
        try:
            import time
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

    # Scrape
    url = f"{BASE_URL}/etf-profile.html?isin={isin}"
    try:
        html = await _fetch(url)
    except Exception as e:
        log.error(f"  -> fetch failed: {e}")
        raise

    soup = BeautifulSoup(html, "lxml")

    # Check if we got redirected to search (invalid ISIN)
    if "/search.html" in str(soup.find("link", rel="canonical") or ""):
        log.warning(f"  -> redirected to search, ISIN might be invalid")

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
                # Next part or this part has the TER value
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

    # WKN - from etf-data-table or page
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

    # Disk cache
    import time
    (DATA_DIR / "profiles").mkdir(parents=True, exist_ok=True)
    disk_data = {**profile_data, "_cached_at": time.time()}
    disk_path.write_text(json.dumps(disk_data, ensure_ascii=False))

    return profile


def _parse_section_by_heading(soup: BeautifulSoup, headings: list[str]) -> list[Allocation]:
    """Find a section by its h2/h3 heading, then parse the next table."""
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
    """Build local ETF index from justETF pages. Only scrapes names + ISINs."""
    _preload_progress["status"] = "loading"
    _preload_progress["phase"] = "ETF-Index aufbauen"

    # Try disk first
    if _load_index_from_disk():
        _preload_progress["total"] = len(_etf_index)
        _preload_progress["done"] = len(_etf_index)
        _preload_progress["status"] = "done"
        _preload_progress["phase"] = f"{len(_etf_index)} ETFs geladen (aus Cache)"
        return

    # Scrape index pages
    _preload_progress["total"] = len(INDEX_PAGES)
    _preload_progress["done"] = 0

    for i, url in enumerate(INDEX_PAGES):
        _preload_progress["phase"] = f"Seite {i + 1}/{len(INDEX_PAGES)} laden"
        try:
            await _build_index_from_page(url)
        except Exception as e:
            log.error(f"INDEX page error: {e}")
            _preload_progress["errors"].append(str(e))
        _preload_progress["done"] = i + 1
        log.info(f"INDEX progress: {i + 1}/{len(INDEX_PAGES)}, total ETFs: {len(_etf_index)}")

    if _etf_index:
        _save_index_to_disk()

    _preload_progress["total"] = len(_etf_index)
    _preload_progress["done"] = len(_etf_index)
    _preload_progress["status"] = "done"
    _preload_progress["phase"] = f"{len(_etf_index)} ETFs indexiert"
    log.info(f"INDEX complete: {len(_etf_index)} ETFs from {len(INDEX_PAGES)} pages")


def get_preload_progress() -> dict:
    return _preload_progress
