import asyncio
import logging

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from models.etf import ChartPoint, ETFProfile, ETFSearchResult
from scraper.justetf import (
    get_chart_data,
    get_etf_profile,
    get_preload_progress,
    preload_etf_index,
    search_etf,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

app = FastAPI(title="ETF Portfolio Analyzer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    """Build local ETF index on startup (names + ISINs only)."""
    asyncio.create_task(preload_etf_index())


@app.get("/api/search", response_model=list[ETFSearchResult])
async def api_search(q: str = Query(..., min_length=2)):
    """Search ETFs by ISIN, WKN, or free text name (local index)."""
    return await search_etf(q)


@app.get("/api/etf/{isin}", response_model=ETFProfile)
async def api_etf_profile(isin: str):
    """Get full ETF profile with allocations (scraped on demand, cached 24h)."""
    try:
        return await get_etf_profile(isin)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Scraping error: {e}")


@app.get("/api/chart/{isin}", response_model=list[ChartPoint])
async def api_chart(isin: str, period: str = Query("2y")):
    """Get historical chart data for an ETF."""
    try:
        return await get_chart_data(isin, period)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Scraping error: {e}")


@app.get("/api/preload-status")
async def api_preload_status():
    """Return index build progress for the loading modal."""
    return get_preload_progress()


@app.get("/api/health")
async def health():
    return {"status": "ok"}
