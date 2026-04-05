import asyncio
import logging

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from models.etf import ChartPoint, ETFProfile, ETFSearchResult
from scraper.justetf import (
    POPULAR_ETFS,
    get_chart_data,
    get_etf_profile,
    get_preload_progress,
    preload_popular_etfs,
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
    """Start preloading popular ETFs in the background."""
    asyncio.create_task(preload_popular_etfs())


@app.get("/api/search", response_model=list[ETFSearchResult])
async def api_search(q: str = Query(..., min_length=2)):
    """Search ETFs by ISIN, WKN, or free text name."""
    try:
        return await search_etf(q)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Scraping error: {e}")


@app.get("/api/etf/{isin}", response_model=ETFProfile)
async def api_etf_profile(isin: str):
    """Get full ETF profile with allocations."""
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


@app.get("/api/popular")
async def api_popular():
    """Return list of popular ETFs (for quick-add)."""
    return POPULAR_ETFS


@app.get("/api/preload-status")
async def api_preload_status():
    """Return preload progress for the loading modal."""
    return get_preload_progress()


@app.get("/api/health")
async def health():
    return {"status": "ok"}
