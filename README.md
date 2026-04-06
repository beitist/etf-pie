# ETF Portfolio Analyzer

Self-hosted web tool for analyzing ETF portfolio diversification. Enter your ETF positions, adjust amounts, and get interactive charts showing country allocation, sector breakdown, top holdings, and more.

![License](https://img.shields.io/badge/license-MIT-blue)

## Features

- **Portfolio Builder** – Add ETFs by ISIN, WKN, or name search (~3000+ ETFs)
- **Diversification Analysis** – Weighted country, sector, and holdings breakdown as pie charts
- **World Heatmap** – Interactive map showing geographic allocation
- **ETF Detail Panel** – Expandable view per ETF with fund data and performance (1M–5Y returns)
- **Sparplan Simulator** – Project portfolio growth with start amount, monthly savings, and custom return rate
- **Overlap Detection** – See which stocks appear in multiple ETFs
- **Warning System** – Alerts for country concentration and position risk
- **Shareable Links** – Portfolio encoded in URL hash for bookmarking and sharing

## Data Sources

| Source | Data | Update |
|--------|------|--------|
| **Xetra / Deutsche Börse** | ISIN, WKN, German trading names (~2300 ETFs) | Daily CSV |
| **etfdb** (albertored/etfdb) | Country/sector/holdings allocation, TER | Monthly |
| **justETF** | Full German names, performance, fund details | On-demand + background refresh (7d) |

Data is stored in a local SQLite database with source tracking. The background worker only refreshes ETFs that users have actually looked at.

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

App is available at `http://localhost:3000` (via nginx).

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

1. **Startup**: Xetra CSV (names + ISINs) → etfdb merge (allocations)
2. **On-demand**: User opens ETF → justETF scrape if no data yet
3. **Background**: Worker refreshes user-requested ETFs every 7 days

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/search?q=msci` | Search ETFs by name, ISIN, or WKN |
| `GET /api/etf/{isin}` | Full ETF profile with allocations |
| `GET /api/preload-status` | Startup data loading progress |
| `GET /api/db-stats` | Database statistics |
| `GET /api/health` | Health check |

## License

MIT
