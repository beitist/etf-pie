# ETF Portfolio Analyzer

Self-hosted web tool for analyzing ETF portfolio diversification. Enter your ETF positions, adjust euro amounts, and get interactive charts showing country allocation, sector breakdown, top holdings, and more.

![License](https://img.shields.io/badge/license-MIT-blue)

## Features

- **Portfolio Builder** – Add ETFs by ISIN, WKN, or name search (~4400 instruments from Xetra)
- **Diversification Analysis** – Weighted country, sector, and holdings breakdown as pie charts (normalized to 100%)
- **Region Aggregation** – Economic regions: Nordamerika, Europa, Asien-Pazifik DM, Schwellenländer Asien, Lateinamerika, Naher Osten & Afrika
- **World Heatmap** – Interactive map showing geographic allocation
- **Fund Size Distribution** – Portfolio weight by fund size with closure risk warning
- **ETF Detail Panel** – Expandable view per ETF: issuer, domicile, benchmark, TER, replication, performance (1M–5Y), volatility
- **Cheaper Alternative Search** – Find ETFs on the same index with lower TER (DB first, justETF scrape as fallback)
- **Swap-ETF Support** – Automatically uses allocation data from a physical ETF on the same index as proxy
- **Portfolio Projection** – Blended scenario simulation (Konservativ/Ausgewogen/Optimistisch) mixing 1Y/3Y/5Y returns
- **Overlap Detection** – See which stocks appear in multiple ETFs
- **Warning System** – Alerts for country concentration and position risk
- **Shareable Links** – Portfolio encoded in URL hash, works even with empty DB

## Data Sources

| Source | Data | Update |
|--------|------|--------|
| **Xetra / Deutsche Börse** | ISIN, WKN, instrument names (~4400 instruments) | Daily CSV on startup |
| **justETF** | Full German names, TER, allocations, performance, fund details | On-demand + background refresh (48h) |

Data is stored in a local SQLite database with source tracking and timestamps. The background worker only refreshes ETFs that users have actually looked at. Unknown ISINs (e.g. from shared links) are scraped on demand.

## Tech Stack

- **Frontend**: React, Vite, TypeScript, Zustand, Recharts, react-simple-maps
- **Backend**: FastAPI, Python 3.12, BeautifulSoup, httpx
- **Database**: SQLite (persistent volume) + Redis (cache)
- **Deployment**: Docker Compose, designed for Coolify with Traefik

## Quick Start

### Docker Compose

```bash
git clone https://github.com/beitist/etf-pie.git
cd etf-pie
docker compose up -d
```

App is available at `http://localhost` (via nginx on port 80).

### Coolify

1. Create a new Docker Compose resource pointing to this repo
2. Set build pack to **Docker Compose**
3. Assign a domain to the **nginx** service
4. Deploy

> The nginx service needs to be in the `coolify` external network for Traefik routing. This is configured in `docker-compose.yaml`.

## Architecture

```
                    ┌──────────────┐
                    │   Traefik    │  (Coolify-managed, HTTPS + Let's Encrypt)
                    └──────┬───────┘
                           │
                    ┌──────┴───────┐
                    │    nginx     │  Entry point, routes / and /api
                    └──────┬───────┘
              ┌────────────┴────────────┐
              │                         │
       ┌──────┴──────┐         ┌───────┴───────┐
       │  Frontend   │         │    Backend    │
       │  React/Vite │         │    FastAPI    │
       │  Port 3000  │         │   Port 8000  │
       └─────────────┘         └───────┬───────┘
                                       │
                               ┌───────┴───────┐
                               │    SQLite     │  ETF data, allocations,
                               │  /app/data/   │  performance, source tracking
                               └───────────────┘
                                       │
                               ┌───────┴───────┐
                               │    Redis      │  Fast cache layer
                               └───────────────┘
```

### Data Pipeline

1. **Startup**: Xetra CSV → ~4400 instruments with ISIN, WKN, short names
2. **On-demand**: User selects ETF → justETF scrape (name, TER, countries, sectors, holdings, performance)
3. **Background**: Worker refreshes user-requested ETFs every 48h
4. **Swap-ETF proxy**: If no allocation data, uses physical ETF on same index

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/search?q=msci` | Search ETFs by name, ISIN, or WKN |
| `GET /api/etf/{isin}` | Full ETF profile with allocations + performance |
| `GET /api/etf/{isin}/alternatives` | Find ETFs on the same index (DB first, justETF fallback) |
| `GET /api/preload-status` | Startup data loading progress |
| `GET /api/db-stats` | Database statistics (total, scraped, with allocations) |
| `GET /api/health` | Health check |

## License

MIT
