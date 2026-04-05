from pydantic import BaseModel


class Allocation(BaseModel):
    name: str
    weight: float


class Holding(BaseModel):
    name: str
    weight: float
    country: str = ""
    sector: str = ""


class MarketCap(BaseModel):
    large: float = 0.0
    mid: float = 0.0
    small: float = 0.0
    micro: float = 0.0


class ETFProfile(BaseModel):
    name: str
    isin: str
    wkn: str = ""
    ter: float = 0.0
    replication: str = ""
    distribution: str = ""
    fund_size: str = ""
    currency: str = "EUR"
    countries: list[Allocation] = []
    sectors: list[Allocation] = []
    holdings: list[Holding] = []
    market_cap: MarketCap = MarketCap()


class ETFSearchResult(BaseModel):
    name: str
    isin: str
    wkn: str = ""
    ter: float = 0.0
    replication: str = ""
    distribution: str = ""


class ChartPoint(BaseModel):
    date: str
    close: float
