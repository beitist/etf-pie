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
    get_allocations,
    get_etf,
    get_least_recently_scraped,
    get_stats,
    search_etfs,
)
from scraper.etfdb import load_etfdb
from scraper.justetf import scrape_etf_profile
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


# ─── Startup: Xetra → etfdb → background scraper ────────────────────────

@app.on_event("startup")
async def startup():
    asyncio.create_task(_startup_pipeline())


async def _startup_pipeline():
    _preload_progress["status"] = "loading"

    try:
        # Step 1: Xetra instrument list (ISIN, WKN, short names)
        _preload_progress["phase"] = "Xetra-Liste laden..."
        xetra_count = await load_xetra_instruments(_preload_progress)
        log.info(f"Startup: {xetra_count} ETFs from Xetra")

        # Step 2: etfdb (fills in allocations, TER, etc.)
        _preload_progress["phase"] = "etfdb-Daten mergen..."
        etfdb_count = await load_etfdb(_preload_progress)
        log.info(f"Startup: {etfdb_count} ETFs from etfdb")

        stats = get_stats()
        _preload_progress["total"] = stats["total"]
        _preload_progress["done"] = stats["total"]
        _preload_progress["status"] = "done"
        _preload_progress["phase"] = f"{stats['total']} ETFs geladen ({stats['with_countries']} mit Allokation)"

    except Exception as e:
        log.error(f"Startup failed: {e}", exc_info=True)
        _preload_progress["errors"].append(str(e))
        _preload_progress["status"] = "done"
        _preload_progress["phase"] = f"Fehler: {e}"

    # Step 3: Start background scraper
    asyncio.create_task(_background_scraper())


async def _background_scraper():
    """Slowly scrape justETF profiles in the background. ~1 ETF per 2-3 minutes."""
    await asyncio.sleep(10)  # Wait for startup to finish
    log.info("Background scraper started")

    while True:
        try:
            candidates = get_least_recently_scraped(limit=5)
            if not candidates:
                await asyncio.sleep(300)
                continue

            # Pick one (slight randomness to avoid patterns)
            target = random.choice(candidates)
            isin = target["isin"]
            log.info(f"BG-SCRAPE: {isin} ({target.get('name_display', '?')})")

            await scrape_etf_profile(isin)

            # Wait 2-4 minutes between scrapes
            delay = 120 + random.randint(0, 120)
            await asyncio.sleep(delay)

        except Exception as e:
            log.error(f"BG-SCRAPE error: {e}")
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

    countries = get_allocations("countries", isin)
    sectors = get_allocations("sectors", isin)
    holdings = get_allocations("holdings", isin)

    # If no allocation data yet, scrape on demand
    if not countries and not sectors:
        log.info(f"No allocation data for {isin}, scraping on demand...")
        success = await scrape_etf_profile(isin)
        if success:
            etf = get_etf(isin)
            countries = get_allocations("countries", isin)
            sectors = get_allocations("sectors", isin)
            holdings = get_allocations("holdings", isin)

    return ETFProfile(
        name=etf["name_display"] or etf["name_xetra"] or isin,
        isin=isin,
        wkn=etf.get("wkn", ""),
        ter=etf.get("ter", 0.0),
        replication=etf.get("replication", ""),
        distribution=etf.get("distribution", ""),
        fund_size=etf.get("fund_size", ""),
        currency=etf.get("currency", "EUR"),
        countries=[Allocation(**c) for c in countries],
        sectors=[Allocation(**s) for s in sectors],
        holdings=[Holding(name=h["name"], weight=h["weight"]) for h in holdings],
        market_cap=MarketCap(),
    )


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
