"""
SQLite ETF database.

Stores all ETF data with source tracking and timestamps.
Data flows: Xetra (names) → etfdb (allocations) → justETF (full scrape, overwrites).
"""

import logging
import sqlite3
import time
from pathlib import Path

log = logging.getLogger("db")

DATA_DIR = Path("/app/data")
DB_PATH = DATA_DIR / "etf.db"

_conn: sqlite3.Connection | None = None


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA foreign_keys=ON")
        _init_schema(_conn)
    return _conn


def _init_schema(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS etfs (
            isin TEXT PRIMARY KEY,
            wkn TEXT DEFAULT '',
            name_xetra TEXT DEFAULT '',
            name_display TEXT DEFAULT '',
            ter REAL DEFAULT 0.0,
            replication TEXT DEFAULT '',
            distribution TEXT DEFAULT '',
            fund_size TEXT DEFAULT '',
            currency TEXT DEFAULT '',
            domicile TEXT DEFAULT '',
            issuer TEXT DEFAULT '',
            asset_class TEXT DEFAULT '',
            benchmark TEXT DEFAULT '',
            return_1m REAL DEFAULT 0,
            return_3m REAL DEFAULT 0,
            return_6m REAL DEFAULT 0,
            return_1y REAL DEFAULT 0,
            return_3y REAL DEFAULT 0,
            return_5y REAL DEFAULT 0,
            return_ytd REAL DEFAULT 0,
            volatility_1y REAL DEFAULT 0,
            source TEXT DEFAULT '',
            last_updated REAL DEFAULT 0,
            last_scraped REAL DEFAULT 0,
            requested INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS countries (
            isin TEXT NOT NULL,
            name TEXT NOT NULL,
            weight REAL NOT NULL,
            source TEXT DEFAULT '',
            last_updated REAL DEFAULT 0,
            PRIMARY KEY (isin, name)
        );

        CREATE TABLE IF NOT EXISTS sectors (
            isin TEXT NOT NULL,
            name TEXT NOT NULL,
            weight REAL NOT NULL,
            source TEXT DEFAULT '',
            last_updated REAL DEFAULT 0,
            PRIMARY KEY (isin, name)
        );

        CREATE TABLE IF NOT EXISTS holdings (
            isin TEXT NOT NULL,
            name TEXT NOT NULL,
            weight REAL NOT NULL,
            source TEXT DEFAULT '',
            last_updated REAL DEFAULT 0,
            PRIMARY KEY (isin, name)
        );

        CREATE INDEX IF NOT EXISTS idx_etfs_last_scraped ON etfs(last_scraped);
        CREATE INDEX IF NOT EXISTS idx_etfs_name ON etfs(name_display);
        CREATE INDEX IF NOT EXISTS idx_countries_isin ON countries(isin);
        CREATE INDEX IF NOT EXISTS idx_sectors_isin ON sectors(isin);
        CREATE INDEX IF NOT EXISTS idx_holdings_isin ON holdings(isin);
    """)
    conn.commit()
    log.info(f"DB initialized at {DB_PATH}")


# ─── ETF CRUD ────────────────────────────────────────────────────────────


# Fields that should only be set if non-empty (don't overwrite good data with blanks)
_STR_FIELDS = [
    "wkn", "name_xetra", "name_display", "replication", "distribution",
    "fund_size", "currency", "domicile", "issuer", "asset_class", "benchmark",
]
_FLOAT_FIELDS = [
    "ter", "return_1m", "return_3m", "return_6m", "return_1y",
    "return_3y", "return_5y", "return_ytd", "volatility_1y",
]


def upsert_etf(isin: str, source: str, mark_scraped: bool = False, **kwargs):
    conn = get_conn()
    now = time.time()

    row = conn.execute("SELECT * FROM etfs WHERE isin = ?", (isin,)).fetchone()

    if row is None:
        # Insert with all provided fields
        fields = {"isin": isin, "source": source, "last_updated": now}
        if mark_scraped:
            fields["last_scraped"] = now
        for k in _STR_FIELDS:
            if k in kwargs and kwargs[k]:
                fields[k] = kwargs[k]
        for k in _FLOAT_FIELDS:
            if k in kwargs and kwargs[k]:
                fields[k] = kwargs[k]
        cols = ", ".join(fields.keys())
        placeholders = ", ".join("?" for _ in fields)
        conn.execute(f"INSERT INTO etfs ({cols}) VALUES ({placeholders})", list(fields.values()))
    else:
        # Update only non-empty fields
        updates = []
        params = []
        for k in _STR_FIELDS:
            if k in kwargs and kwargs[k]:
                updates.append(f"{k} = ?")
                params.append(kwargs[k])
        for k in _FLOAT_FIELDS:
            if k in kwargs and kwargs[k]:
                updates.append(f"{k} = ?")
                params.append(kwargs[k])

        updates.append("source = ?")
        params.append(source)
        updates.append("last_updated = ?")
        params.append(now)
        if mark_scraped:
            updates.append("last_scraped = ?")
            params.append(now)

        params.append(isin)
        conn.execute(f"UPDATE etfs SET {', '.join(updates)} WHERE isin = ?", params)

    conn.commit()


def upsert_allocations(
    table: str,
    isin: str,
    items: list[dict],
    source: str,
):
    """Replace all allocations for an ISIN in the given table."""
    assert table in ("countries", "sectors", "holdings")
    conn = get_conn()
    now = time.time()
    conn.execute(f"DELETE FROM {table} WHERE isin = ?", (isin,))
    for item in items:
        conn.execute(
            f"INSERT INTO {table} (isin, name, weight, source, last_updated) VALUES (?, ?, ?, ?, ?)",
            (isin, item["name"], item["weight"], source, now),
        )
    conn.commit()


def get_etf(isin: str) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM etfs WHERE isin = ?", (isin,)).fetchone()
    if not row:
        return None
    return dict(row)


def get_allocations(table: str, isin: str) -> list[dict]:
    assert table in ("countries", "sectors", "holdings")
    conn = get_conn()
    rows = conn.execute(
        f"SELECT name, weight FROM {table} WHERE isin = ? ORDER BY weight DESC",
        (isin,),
    ).fetchall()
    return [{"name": r["name"], "weight": r["weight"]} for r in rows]


def search_etfs(query: str, limit: int = 20) -> list[dict]:
    conn = get_conn()
    q = f"%{query}%"
    rows = conn.execute(
        """SELECT isin, wkn, name_xetra, name_display, ter, replication, distribution
           FROM etfs
           WHERE isin LIKE ? OR wkn LIKE ? OR name_display LIKE ? OR name_xetra LIKE ?
           LIMIT ?""",
        (q, q, q, q, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def mark_requested(isin: str):
    """Mark an ETF as user-requested (eligible for background refresh)."""
    conn = get_conn()
    conn.execute("UPDATE etfs SET requested = 1 WHERE isin = ?", (isin,))
    conn.commit()


def get_stale_requested(max_age_hours: float = 24, limit: int = 5) -> list[dict]:
    """Get user-requested ETFs whose scrape is older than max_age_hours."""
    conn = get_conn()
    cutoff = time.time() - (max_age_hours * 3600)
    rows = conn.execute(
        """SELECT isin, name_display FROM etfs
           WHERE requested = 1 AND last_scraped < ?
           ORDER BY last_scraped ASC
           LIMIT ?""",
        (cutoff, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def find_proxy_for_index(benchmark: str, exclude_isin: str = "") -> str | None:
    """Find a physical ETF on the same index that has country allocation data."""
    if not benchmark:
        return None
    conn = get_conn()
    row = conn.execute(
        """SELECT e.isin FROM etfs e
           JOIN countries c ON e.isin = c.isin
           WHERE e.benchmark = ? AND e.isin != ?
           GROUP BY e.isin
           HAVING COUNT(c.name) >= 3
           ORDER BY e.fund_size DESC
           LIMIT 1""",
        (benchmark, exclude_isin),
    ).fetchone()
    return row["isin"] if row else None


def find_cheaper_alternative(isin: str) -> dict | None:
    """Find a cheaper ETF on the same index."""
    conn = get_conn()
    etf = conn.execute(
        "SELECT benchmark, ter FROM etfs WHERE isin = ?", (isin,)
    ).fetchone()
    if not etf or not etf["benchmark"] or not etf["ter"]:
        return None
    row = conn.execute(
        """SELECT isin, name_display, name_xetra, ter, replication
           FROM etfs
           WHERE benchmark = ? AND isin != ? AND ter > 0 AND ter < ?
           ORDER BY ter ASC
           LIMIT 1""",
        (etf["benchmark"], isin, etf["ter"]),
    ).fetchone()
    return dict(row) if row else None


def get_stats() -> dict:
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) FROM etfs").fetchone()[0]
    scraped = conn.execute("SELECT COUNT(*) FROM etfs WHERE last_scraped > 0").fetchone()[0]
    with_countries = conn.execute(
        "SELECT COUNT(DISTINCT isin) FROM countries"
    ).fetchone()[0]
    return {"total": total, "scraped": scraped, "with_countries": with_countries}
