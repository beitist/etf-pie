import { useCallback, useEffect, useRef, useState } from "react";
import type { ETFSearchResult } from "../types";
import { searchETF } from "../lib/api";
import { usePortfolioStore } from "../stores/portfolio";

export function AddETFSearch() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ETFSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const addPosition = usePortfolioStore((s) => s.addPosition);
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  const doSearch = useCallback(async (q: string) => {
    if (q.length < 2) {
      setResults([]);
      return;
    }
    setLoading(true);
    try {
      const res = await searchETF(q);
      setResults(res);
      setOpen(true);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => doSearch(query), 350);
    return () => clearTimeout(timerRef.current);
  }, [query, doSearch]);

  const handleSelect = (result: ETFSearchResult) => {
    addPosition(result.isin, result.name);
    setQuery("");
    setResults([]);
    setOpen(false);
  };

  return (
    <div className="add-etf-search">
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="ETF suchen: ISIN, WKN oder Name (z.B. 'MSCI World')..."
        onFocus={() => results.length > 0 && setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 200)}
      />
      {loading && <span className="search-loading">Suche...</span>}
      {open && results.length > 0 && (
        <ul className="search-results">
          {results.map((r) => (
            <li key={r.isin} onMouseDown={() => handleSelect(r)}>
              <strong>{r.name}</strong>
              <span className="search-meta">
                {r.isin} {r.ter > 0 && `· TER ${r.ter}%`}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
