from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from models.etf import ChartPoint, ETFProfile, ETFSearchResult
from scraper.justetf import get_chart_data, get_etf_profile, search_etf

app = FastAPI(title="ETF Portfolio Analyzer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.get("/api/health")
async def health():
    return {"status": "ok"}
