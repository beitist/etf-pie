import type { Allocation } from "../types";
import { aggregateRegions } from "../lib/regions";

const REGION_COLORS: Record<string, string> = {
  "Nordamerika": "#2563eb",
  "Europa": "#7c3aed",
  "Asien-Pazifik (DM)": "#0891b2",
  "Schwellenländer Asien": "#ea580c",
  "Lateinamerika": "#16a34a",
  "Naher Osten & Afrika": "#ca8a04",
  "Sonstige": "#94a3b8",
};

interface Props {
  countries: Allocation[];
}

export function RegionTable({ countries }: Props) {
  const regions = aggregateRegions(countries);
  if (regions.length === 0) return null;

  return (
    <div className="region-table">
      <h4>Regionen</h4>
      {regions.map((r) => (
        <div key={r.name} className="region-row">
          <div className="region-bar-track">
            <div
              className="region-bar-fill"
              style={{
                width: `${Math.min(r.weight, 100)}%`,
                background: REGION_COLORS[r.name] || "#94a3b8",
              }}
            />
          </div>
          <div className="region-info">
            <span className="region-name">{r.name}</span>
            <span className="region-weight">{r.weight.toFixed(1)}%</span>
          </div>
          {r.countries.length > 0 && (
            <span className="region-countries">
              {r.countries.join(", ")}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
