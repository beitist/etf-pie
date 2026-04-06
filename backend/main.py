import asyncio
import logging
import random

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from models.etf import (
    Allocation,
    ChartPoint,
    ETFProfile,
    ETFSearchResult,
    Holding,
    MarketCap,
)
from scraper.db import (
    find_cheaper_alternative,
    find_proxy_for_index,
    get_allocations,
    get_etf,
    get_stale_requested,
    get_stats,
    mark_requested,
    search_etfs,
)
from scraper.justetf import scrape_alternatives, scrape_etf_profile
from scraper.xetra import load_xetra_instruments

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
log = logging.getLogger("main")

app = FastAPI(title="ETF Portfolio Analyzer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Preload progress ───────────────────────────────────────────────────

_preload_progress: dict = {
    "total": 0, "done": 0, "status": "idle", "errors": [], "phase": ""
}


# ─── Startup: Xetra → background scraper ─────────────────────────────────

@app.on_event("startup")
async def startup():
    asyncio.create_task(_startup_pipeline())


async def _startup_pipeline():
    _preload_progress["status"] = "loading"

    try:
        # Xetra instrument list (ISIN, WKN, short names)
        _preload_progress["phase"] = "Xetra-Liste laden..."
        xetra_count = await load_xetra_instruments(_preload_progress)
        log.info(f"Startup: {xetra_count} ETFs from Xetra")

        stats = get_stats()
        _preload_progress["total"] = stats["total"]
        _preload_progress["done"] = stats["total"]
        _preload_progress["status"] = "done"
        _preload_progress["phase"] = f"{stats['total']} ETFs geladen"

    except Exception as e:
        log.error(f"Startup failed: {e}", exc_info=True)
        _preload_progress["errors"].append(str(e))
        _preload_progress["status"] = "done"
        _preload_progress["phase"] = f"Fehler: {e}"

    # Start background scraper
    asyncio.create_task(_background_scraper())


async def _background_scraper():
    """Refresh justETF data for user-requested ETFs older than 48h."""
    await asyncio.sleep(30)
    log.info("Background scraper started (refreshes user-requested ETFs every 48h)")

    while True:
        try:
            candidates = get_stale_requested(max_age_hours=48, limit=5)
            if not candidates:
                await asyncio.sleep(300)
                continue

            target = random.choice(candidates)
            isin = target["isin"]
            log.info(f"BG-REFRESH: {isin} ({target.get('name_display', '?')})")

            await scrape_etf_profile(isin)

            # Wait 2-4 minutes between scrapes
            delay = 120 + random.randint(0, 120)
            await asyncio.sleep(delay)

        except Exception as e:
            log.error(f"BG-REFRESH error: {e}")
            await asyncio.sleep(300)


# ─── API ─────────────────────────────────────────────────────────────────

@app.get("/api/search", response_model=list[ETFSearchResult])
async def api_search(q: str = Query(..., min_length=2)):
    """Search ETFs by ISIN, WKN, or name."""
    rows = search_etfs(q.strip())
    return [
        ETFSearchResult(
            name=r["name_display"] or r["name_xetra"] or r["isin"],
            isin=r["isin"],
            wkn=r.get("wkn", ""),
            ter=r.get("ter", 0.0),
            replication=r.get("replication", ""),
            distribution=r.get("distribution", ""),
        )
        for r in rows
    ]


@app.get("/api/etf/{isin}", response_model=ETFProfile)
async def api_etf_profile(isin: str):
    """Get ETF profile from DB. If no allocation data, trigger justETF scrape."""
    etf = get_etf(isin)
    if not etf:
        raise HTTPException(status_code=404, detail="ETF not found")

    # Mark as user-requested so background worker keeps it fresh
    mark_requested(isin)

    countries = get_allocations("countries", isin)
    sectors = get_allocations("sectors", isin)
    holdings = get_allocations("holdings", isin)

    # Scrape on demand if never scraped
    never_scraped = not etf.get("last_scraped")
    if never_scraped or (not countries and not sectors):
        log.info(f"Scraping {isin} on demand (never_scraped={never_scraped})...")
        success = await scrape_etf_profile(isin)
        if success:
            etf = get_etf(isin)
            countries = get_allocations("countries", isin)
            sectors = get_allocations("sectors", isin)
            holdings = get_allocations("holdings", isin)

    # Swap-ETF proxy: if still no allocation data, use a physical ETF on the same index
    proxy_isin = None
    if not countries and etf.get("benchmark"):
        proxy_isin = find_proxy_for_index(etf["benchmark"], exclude_isin=isin)
        if proxy_isin:
            log.info(f"  -> using proxy {proxy_isin} for index '{etf['benchmark']}'")
            countries = get_allocations("countries", proxy_isin)
            sectors = sectors or get_allocations("sectors", proxy_isin)
            holdings = holdings or get_allocations("holdings", proxy_isin)

    # Cheaper alternative on same index
    cheaper = find_cheaper_alternative(isin)

    return ETFProfile(
        name=etf["name_display"] or etf["name_xetra"] or isin,
        isin=isin,
        wkn=etf.get("wkn", ""),
        ter=etf.get("ter", 0.0),
        replication=etf.get("replication", ""),
        distribution=etf.get("distribution", ""),
        fund_size=etf.get("fund_size", ""),
        currency=etf.get("currency", "EUR"),
        domicile=etf.get("domicile", ""),
        issuer=etf.get("issuer", ""),
        asset_class=etf.get("asset_class", ""),
        benchmark=etf.get("benchmark", ""),
        return_1m=etf.get("return_1m", 0.0),
        return_3m=etf.get("return_3m", 0.0),
        return_6m=etf.get("return_6m", 0.0),
        return_1y=etf.get("return_1y", 0.0),
        return_3y=etf.get("return_3y", 0.0),
        return_5y=etf.get("return_5y", 0.0),
        return_ytd=etf.get("return_ytd", 0.0),
        volatility_1y=etf.get("volatility_1y", 0.0),
        proxy_isin=proxy_isin or "",
        cheaper_isin=cheaper["isin"] if cheaper else "",
        cheaper_name=cheaper["name_display"] or cheaper.get("name_xetra", "") if cheaper else "",
        cheaper_ter=cheaper["ter"] if cheaper else 0.0,
        countries=[Allocation(**c) for c in countries],
        sectors=[Allocation(**s) for s in sectors],
        holdings=[Holding(name=h["name"], weight=h["weight"]) for h in holdings],
        market_cap=MarketCap(),
    )


@app.get("/api/etf/{isin}/alternatives")
async def api_alternatives(isin: str):
    """Find cheaper ETFs on the same index. DB first, justETF scrape as fallback."""
    etf = get_etf(isin)
    if not etf:
        raise HTTPException(status_code=404, detail="ETF not found")

    benchmark = etf.get("benchmark", "")
    if not benchmark:
        # Need to scrape first to get the benchmark
        await scrape_etf_profile(isin)
        etf = get_etf(isin)
        benchmark = etf.get("benchmark", "") if etf else ""

    if not benchmark:
        return []

    # Try DB first: find all ETFs on the same index
    conn = __import__("scraper.db", fromlist=["get_conn"]).get_conn()
    rows = conn.execute(
        """SELECT isin, name_display, name_xetra, ter, replication, distribution, fund_size
           FROM etfs
           WHERE benchmark = ? AND isin != ? AND ter > 0
           ORDER BY ter ASC""",
        (benchmark, isin),
    ).fetchall()

    if rows:
        return [
            {
                "isin": r["isin"],
                "name": r["name_display"] or r["name_xetra"] or r["isin"],
                "ter": r["ter"],
                "replication": r["replication"] or "",
                "distribution": r["distribution"] or "",
                "fund_size": r["fund_size"] or "",
            }
            for r in rows
        ]

    # Fallback: scrape justETF
    return await scrape_alternatives(isin)


@app.get("/api/preload-status")
async def api_preload_status():
    return _preload_progress


@app.get("/api/db-stats")
async def api_db_stats():
    """Database statistics."""
    return get_stats()


@app.get("/api/health")
async def health():
    return {"status": "ok"}
