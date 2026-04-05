import type { Allocation, CountryLimit, Position } from "../types";

interface Props {
  countries: Allocation[];
  limits: CountryLimit[];
  positions: Position[];
}

export function WarningBanner({ countries, limits, positions }: Props) {
  const warnings: string[] = [];

  // Check country limits
  for (const limit of limits) {
    const country = countries.find(
      (c) => c.name.toLowerCase() === limit.country.toLowerCase()
    );
    if (country && country.weight > limit.max) {
      warnings.push(
        `${country.name}: ${country.weight.toFixed(1)}% (Limit: ${limit.max}%)`
      );
    }
  }

  // Check concentration risk
  for (const p of positions) {
    if (p.weight > 50) {
      warnings.push(
        `Klumpenrisiko: ${p.name} hat ${p.weight.toFixed(1)}% Gewicht`
      );
    }
  }

  if (warnings.length === 0) return null;

  return (
    <div className="warning-banner">
      <strong>Warnungen</strong>
      <ul>
        {warnings.map((w, i) => (
          <li key={i}>{w}</li>
        ))}
      </ul>
    </div>
  );
}
