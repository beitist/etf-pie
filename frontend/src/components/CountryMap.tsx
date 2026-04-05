import { useMemo } from "react";
import {
  ComposableMap,
  Geographies,
  Geography,
  ZoomableGroup,
} from "react-simple-maps";
import type { Allocation } from "../types";

const GEO_URL = "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json";

// Map German/English country names to ISO 3166 names used in topojson
const COUNTRY_NAME_MAP: Record<string, string> = {
  "USA": "United States of America",
  "Vereinigte Staaten": "United States of America",
  "UK": "United Kingdom",
  "Großbritannien": "United Kingdom",
  "Vereinigtes Königreich": "United Kingdom",
  "Schweiz": "Switzerland",
  "Deutschland": "Germany",
  "Frankreich": "France",
  "Niederlande": "Netherlands",
  "Japan": "Japan",
  "Kanada": "Canada",
  "Australien": "Australia",
  "China": "China",
  "Indien": "India",
  "Südkorea": "South Korea",
  "Taiwan": "Taiwan",
  "Brasilien": "Brazil",
  "Irland": "Ireland",
  "Schweden": "Sweden",
  "Dänemark": "Denmark",
  "Spanien": "Spain",
  "Italien": "Italy",
  "Hongkong": "Hong Kong",
  "Singapur": "Singapore",
  "Norwegen": "Norway",
  "Finnland": "Finland",
  "Belgien": "Belgium",
  "Österreich": "Austria",
  "Mexiko": "Mexico",
  "Südafrika": "South Africa",
  "Russland": "Russia",
  "Indonesien": "Indonesia",
  "Thailand": "Thailand",
  "Malaysia": "Malaysia",
  "Philippinen": "Philippines",
  "Türkei": "Turkey",
  "Saudi-Arabien": "Saudi Arabia",
  "Polen": "Poland",
  "Neuseeland": "New Zealand",
  "Portugal": "Portugal",
  "Griechenland": "Greece",
  "Kaimaninseln": "Cayman Is.",
};

function getColor(weight: number): string {
  if (weight <= 0) return "#f1f5f9";
  if (weight < 1) return "#bfdbfe";
  if (weight < 3) return "#93c5fd";
  if (weight < 5) return "#60a5fa";
  if (weight < 10) return "#3b82f6";
  if (weight < 20) return "#2563eb";
  if (weight < 35) return "#1d4ed8";
  return "#1e3a8a";
}

interface Props {
  countries: Allocation[];
}

export function CountryMap({ countries }: Props) {
  const countryWeightMap = useMemo(() => {
    const map = new Map<string, number>();
    for (const c of countries) {
      const mapped = COUNTRY_NAME_MAP[c.name] || c.name;
      map.set(mapped.toLowerCase(), c.weight);
    }
    return map;
  }, [countries]);

  return (
    <div className="chart-card">
      <h3>Weltkarte</h3>
      <div className="map-legend">
        {[
          { label: "< 1%", color: "#bfdbfe" },
          { label: "1-5%", color: "#93c5fd" },
          { label: "5-10%", color: "#60a5fa" },
          { label: "10-20%", color: "#3b82f6" },
          { label: "20-35%", color: "#2563eb" },
          { label: "> 35%", color: "#1e3a8a" },
        ].map((item) => (
          <span key={item.label} className="legend-item">
            <span
              className="legend-swatch"
              style={{ background: item.color }}
            />
            {item.label}
          </span>
        ))}
      </div>
      <ComposableMap
        projectionConfig={{ scale: 147, center: [10, 5] }}
        width={800}
        height={400}
        style={{ width: "100%", height: "auto" }}
      >
        <ZoomableGroup>
          <Geographies geography={GEO_URL}>
            {({ geographies }) =>
              geographies.map((geo) => {
                const name = (geo.properties.name || "").toLowerCase();
                const weight = countryWeightMap.get(name) || 0;
                return (
                  <Geography
                    key={geo.rsmKey}
                    geography={geo}
                    fill={getColor(weight)}
                    stroke="#cbd5e1"
                    strokeWidth={0.5}
                    style={{
                      default: { outline: "none" },
                      hover: { outline: "none", fill: "#f59e0b" },
                      pressed: { outline: "none" },
                    }}
                    data-tooltip-content={
                      weight > 0
                        ? `${geo.properties.name}: ${weight.toFixed(1)}%`
                        : geo.properties.name
                    }
                  />
                );
              })
            }
          </Geographies>
        </ZoomableGroup>
      </ComposableMap>
    </div>
  );
}
