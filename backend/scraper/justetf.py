import asyncio
import os
import re

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
from scraper.cache import TTL_CHART, TTL_PROFILE, TTL_SEARCH, cache_get, cache_set

SCRAPE_DELAY = float(os.getenv("SCRAPE_DELAY", "1.0"))
_semaphore = asyncio.Semaphore(1)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}

BASE_URL = "https://www.justETF.com/de"


async def _fetch(url: str) -> str:
    async with _semaphore:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            resp = await client.get(url, headers=HEADERS)
            resp.raise_for_status()
            await asyncio.sleep(SCRAPE_DELAY)
            return resp.text


def _parse_percent(text: str) -> float:
    if not text:
        return 0.0
    cleaned = text.strip().replace("%", "").replace(",", ".").strip()
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


async def search_etf(query: str) -> list[ETFSearchResult]:
    cache_key = f"search:{query}"
    cached = await cache_get(cache_key)
    if cached:
        return [ETFSearchResult(**r) for r in cached]

    url = f"{BASE_URL}/find-etf.html?query={query}"
    html = await _fetch(url)
    soup = BeautifulSoup(html, "lxml")

    results: list[ETFSearchResult] = []

    # justETF search results table
    rows = soup.select("table.table tbody tr")
    for row in rows[:10]:
        name_el = row.select_one("a.productName, td:first-child a")
        if not name_el:
            continue
        name = name_el.get_text(strip=True)
        href = name_el.get("href", "")

        # Extract ISIN from href or text
        isin_match = re.search(r"[A-Z]{2}[A-Z0-9]{10}", str(href) + " " + name)
        isin = isin_match.group(0) if isin_match else ""

        # TER
        ter_el = row.select_one("td.tal, td:nth-child(3)")
        ter = _parse_percent(ter_el.get_text() if ter_el else "")

        if isin:
            results.append(ETFSearchResult(name=name, isin=isin, ter=ter))

    # If no table results, check if we landed on a profile page directly
    if not results:
        isin_el = soup.select_one("span.identifier-isin, .val-isin")
        if isin_el:
            isin = isin_el.get_text(strip=True)
            name_el = soup.select_one("h1.h2")
            name = name_el.get_text(strip=True) if name_el else query
            results.append(ETFSearchResult(name=name, isin=isin))

    await cache_set(cache_key, [r.model_dump() for r in results], TTL_SEARCH)
    return results


async def get_etf_profile(isin: str) -> ETFProfile:
    cache_key = f"profile:{isin}"
    cached = await cache_get(cache_key)
    if cached:
        return ETFProfile(**cached)

    url = f"{BASE_URL}/etf-profile.html?isin={isin}"
    html = await _fetch(url)
    soup = BeautifulSoup(html, "lxml")

    # Name
    name_el = soup.select_one("h1.h2, h1")
    name = name_el.get_text(strip=True) if name_el else isin

    # WKN
    wkn = ""
    wkn_el = soup.select_one("span.identifier-wkn, .val-wkn")
    if wkn_el:
        wkn = wkn_el.get_text(strip=True)

    # TER
    ter = 0.0
    ter_el = soup.find(string=re.compile(r"Gesamtkostenquote|TER"))
    if ter_el:
        parent = ter_el.find_parent("div") or ter_el.find_parent("tr")
        if parent:
            val = parent.find(string=re.compile(r"\d+[,\.]\d+\s*%"))
            if val:
                ter = _parse_percent(val)

    # Fund info
    replication = ""
    distribution = ""
    fund_size = ""

    info_table = soup.select("table.table-quick-info tr, .etf-data tr")
    for row in info_table:
        label = row.select_one("td:first-child, th")
        value = row.select_one("td:last-child")
        if not label or not value:
            continue
        label_text = label.get_text(strip=True).lower()
        val_text = value.get_text(strip=True)
        if "replikation" in label_text or "replication" in label_text:
            replication = val_text
        elif "ausschüttung" in label_text or "ertragsverwendung" in label_text:
            distribution = val_text
        elif "fondsgröße" in label_text or "fund size" in label_text:
            fund_size = val_text

    # Countries
    countries = _parse_allocation_section(soup, ["Länder", "Countries"])

    # Sectors
    sectors = _parse_allocation_section(soup, ["Sektoren", "Sectors", "Branchen"])

    # Holdings
    holdings = _parse_holdings(soup)

    # Market cap
    market_cap = _parse_market_cap(soup)

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
        holdings=holdings,
        market_cap=market_cap,
    )

    await cache_set(cache_key, profile.model_dump(), TTL_PROFILE)
    return profile


def _parse_allocation_section(
    soup: BeautifulSoup, headings: list[str]
) -> list[Allocation]:
    allocations: list[Allocation] = []
    for heading in headings:
        section = soup.find(string=re.compile(heading, re.IGNORECASE))
        if not section:
            continue
        container = section.find_parent("div", class_=re.compile(r"tab-pane|card|section"))
        if not container:
            container = section.find_parent("div")
        if not container:
            continue

        rows = container.select("tr, .bar-item, li")
        for row in rows:
            texts = row.get_text(separator="|", strip=True).split("|")
            texts = [t.strip() for t in texts if t.strip()]
            if len(texts) >= 2:
                name_text = texts[0]
                weight_text = next(
                    (t for t in texts if "%" in t), texts[-1]
                )
                weight = _parse_percent(weight_text)
                if weight > 0 and name_text and name_text != weight_text:
                    allocations.append(Allocation(name=name_text, weight=weight))
        if allocations:
            break
    return sorted(allocations, key=lambda a: a.weight, reverse=True)


def _parse_holdings(soup: BeautifulSoup) -> list[Holding]:
    holdings: list[Holding] = []
    section = soup.find(string=re.compile(r"Top\s*\d*\s*(Holdings|Positionen)", re.IGNORECASE))
    if not section:
        return holdings
    container = section.find_parent("div", class_=re.compile(r"tab-pane|card|section"))
    if not container:
        container = section.find_parent("div")
    if not container:
        return holdings

    rows = container.select("tr")
    for row in rows:
        cols = row.select("td")
        if len(cols) >= 2:
            name = cols[0].get_text(strip=True)
            weight_text = next(
                (c.get_text(strip=True) for c in cols if "%" in c.get_text()), ""
            )
            weight = _parse_percent(weight_text)
            if name and weight > 0:
                holdings.append(Holding(name=name, weight=weight))
    return sorted(holdings, key=lambda h: h.weight, reverse=True)[:20]


def _parse_market_cap(soup: BeautifulSoup) -> MarketCap:
    mc = MarketCap()
    section = soup.find(string=re.compile(r"Marktkapitalisierung|Market.?Cap", re.IGNORECASE))
    if not section:
        return mc
    container = section.find_parent("div")
    if not container:
        return mc

    text = container.get_text()
    for label, field in [
        ("Large", "large"),
        ("Mid", "mid"),
        ("Small", "small"),
        ("Micro", "micro"),
    ]:
        match = re.search(rf"{label}[^0-9]*(\d+[,\.]\d+)\s*%", text, re.IGNORECASE)
        if match:
            setattr(mc, field, _parse_percent(match.group(1) + "%"))
    return mc


async def get_chart_data(isin: str, period: str = "2y") -> list[ChartPoint]:
    cache_key = f"chart:{isin}:{period}"
    cached = await cache_get(cache_key)
    if cached:
        return [ChartPoint(**p) for p in cached]

    # justETF chart data endpoint
    period_map = {"1m": 1, "3m": 3, "6m": 6, "1y": 12, "2y": 24, "5y": 60}
    months = period_map.get(period, 24)

    url = f"{BASE_URL}/etf-profile.html?isin={isin}&tab=chart"
    html = await _fetch(url)
    soup = BeautifulSoup(html, "lxml")

    points: list[ChartPoint] = []

    # Try to find chart data in script tags
    scripts = soup.find_all("script")
    for script in scripts:
        text = script.string or ""
        # Look for chart data arrays
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
