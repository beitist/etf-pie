import type { Allocation } from "../types";

export interface Region {
  name: string;
  weight: number;
  countries: string[];
}

// Economic regions (more useful for investment decisions than geographic continents)
const REGION_MAP: Record<string, string> = {
  // North America
  "United States": "Nordamerika",
  "Canada": "Nordamerika",
  // German names
  "USA": "Nordamerika",
  "Kanada": "Nordamerika",
  "Vereinigte Staaten": "Nordamerika",

  // Europe (incl. UK, Switzerland, Nordics)
  "United Kingdom": "Europa",
  "Germany": "Europa",
  "France": "Europa",
  "Switzerland": "Europa",
  "Netherlands": "Europa",
  "Sweden": "Europa",
  "Denmark": "Europa",
  "Norway": "Europa",
  "Finland": "Europa",
  "Spain": "Europa",
  "Italy": "Europa",
  "Belgium": "Europa",
  "Ireland": "Europa",
  "Austria": "Europa",
  "Portugal": "Europa",
  "Luxembourg": "Europa",
  "Greece": "Europa",
  "Poland": "Europa",
  "Czech Republic": "Europa",
  "Hungary": "Europa",
  "Romania": "Europa",
  "Croatia": "Europa",
  "Slovakia": "Europa",
  "Slovenia": "Europa",
  "Lithuania": "Europa",
  "Latvia": "Europa",
  "Estonia": "Europa",
  "Bulgaria": "Europa",
  "Cyprus": "Europa",
  "Malta": "Europa",
  "Iceland": "Europa",
  "Liechtenstein": "Europa",
  "Monaco": "Europa",
  "Jersey": "Europa",
  "Guernsey": "Europa",
  "Isle of Man": "Europa",
  "Faroe Islands": "Europa",
  // German names
  "Großbritannien": "Europa",
  "Vereinigtes Königreich": "Europa",
  "Deutschland": "Europa",
  "Frankreich": "Europa",
  "Schweiz": "Europa",
  "Niederlande": "Europa",
  "Schweden": "Europa",
  "Dänemark": "Europa",
  "Norwegen": "Europa",
  "Finnland": "Europa",
  "Spanien": "Europa",
  "Italien": "Europa",
  "Belgien": "Europa",
  "Irland": "Europa",
  "Österreich": "Europa",
  "Griechenland": "Europa",
  "Polen": "Europa",
  "Tschechien": "Europa",
  "Ungarn": "Europa",
  "Rumänien": "Europa",

  // Asia-Pacific Developed
  "Japan": "Asien-Pazifik (DM)",
  "Australia": "Asien-Pazifik (DM)",
  "New Zealand": "Asien-Pazifik (DM)",
  "Singapore": "Asien-Pazifik (DM)",
  "Hong Kong": "Asien-Pazifik (DM)",
  // German
  "Australien": "Asien-Pazifik (DM)",
  "Neuseeland": "Asien-Pazifik (DM)",
  "Singapur": "Asien-Pazifik (DM)",
  "Hongkong": "Asien-Pazifik (DM)",

  // Emerging Markets Asia
  "China": "Schwellenländer Asien",
  "India": "Schwellenländer Asien",
  "Taiwan": "Schwellenländer Asien",
  "South Korea": "Schwellenländer Asien",
  "Indonesia": "Schwellenländer Asien",
  "Thailand": "Schwellenländer Asien",
  "Malaysia": "Schwellenländer Asien",
  "Philippines": "Schwellenländer Asien",
  "Vietnam": "Schwellenländer Asien",
  "Pakistan": "Schwellenländer Asien",
  "Bangladesh": "Schwellenländer Asien",
  "Sri Lanka": "Schwellenländer Asien",
  // German
  "Indien": "Schwellenländer Asien",
  "Südkorea": "Schwellenländer Asien",
  "Indonesien": "Schwellenländer Asien",
  "Philippinen": "Schwellenländer Asien",

  // Latin America
  "Brazil": "Lateinamerika",
  "Mexico": "Lateinamerika",
  "Chile": "Lateinamerika",
  "Colombia": "Lateinamerika",
  "Peru": "Lateinamerika",
  "Argentina": "Lateinamerika",
  "Uruguay": "Lateinamerika",
  "Panama": "Lateinamerika",
  // German
  "Brasilien": "Lateinamerika",
  "Mexiko": "Lateinamerika",
  "Argentinien": "Lateinamerika",
  "Kolumbien": "Lateinamerika",

  // Middle East & Africa
  "South Africa": "Naher Osten & Afrika",
  "Saudi Arabia": "Naher Osten & Afrika",
  "United Arab Emirates": "Naher Osten & Afrika",
  "Israel": "Naher Osten & Afrika",
  "Qatar": "Naher Osten & Afrika",
  "Kuwait": "Naher Osten & Afrika",
  "Turkey": "Naher Osten & Afrika",
  "Egypt": "Naher Osten & Afrika",
  "Nigeria": "Naher Osten & Afrika",
  "Morocco": "Naher Osten & Afrika",
  "Kenya": "Naher Osten & Afrika",
  "Bahrain": "Naher Osten & Afrika",
  "Oman": "Naher Osten & Afrika",
  "Jordan": "Naher Osten & Afrika",
  // German
  "Südafrika": "Naher Osten & Afrika",
  "Saudi-Arabien": "Naher Osten & Afrika",
  "Vereinigte Arabische Emirate": "Naher Osten & Afrika",
  "Türkei": "Naher Osten & Afrika",
  "Ägypten": "Naher Osten & Afrika",
};

// Display order
const REGION_ORDER = [
  "Nordamerika",
  "Europa",
  "Asien-Pazifik (DM)",
  "Schwellenländer Asien",
  "Lateinamerika",
  "Naher Osten & Afrika",
  "Sonstige",
];

export function aggregateRegions(countries: Allocation[]): Region[] {
  const regionMap = new Map<string, { weight: number; countries: string[] }>();

  for (const c of countries) {
    const region = REGION_MAP[c.name] || "Sonstige";
    const existing = regionMap.get(region) || { weight: 0, countries: [] };
    existing.weight += c.weight;
    if (c.weight >= 0.5) {
      existing.countries.push(c.name);
    }
    regionMap.set(region, existing);
  }

  return REGION_ORDER
    .filter((name) => regionMap.has(name))
    .map((name) => {
      const data = regionMap.get(name)!;
      return {
        name,
        weight: Math.round(data.weight * 100) / 100,
        countries: data.countries.slice(0, 5),
      };
    });
}
