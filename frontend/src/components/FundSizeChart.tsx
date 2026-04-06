import { useMemo } from "react";
import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import type { Position } from "../types";

const SIZE_BUCKETS = [
  { label: "< 100 Mio (klein)", max: 100, color: "#ef4444" },
  { label: "100–500 Mio", max: 500, color: "#f59e0b" },
  { label: "500 Mio – 1 Mrd", max: 1000, color: "#2563eb" },
  { label: "> 1 Mrd", max: Infinity, color: "#16a34a" },
];

function parseFundSize(raw: string): number {
  // Parses strings like "EUR 108.801 Mio.", "EUR 2.500", "1,234", "500"
  if (!raw) return 0;
  const text = raw.replace(/EUR|USD|GBP|CHF/gi, "").trim();
  // Check for "Mio" or "Mrd"
  const isMrd = /mrd/i.test(text);
  const isMio = /mio/i.test(text);
  // Extract number: handle both "108.801" (German thousands) and "108,801"
  const numMatch = text.match(/[\d.,]+/);
  if (!numMatch) return 0;
  let numStr = numMatch[0];
  // German format: 108.801 = 108801, 1.234,56 = 1234.56
  // If has dots and no comma: dots are thousand separators
  if (numStr.includes(".") && !numStr.includes(",")) {
    numStr = numStr.replace(/\./g, "");
  } else if (numStr.includes(",")) {
    numStr = numStr.replace(/\./g, "").replace(",", ".");
  }
  let val = parseFloat(numStr) || 0;
  if (isMrd) val *= 1000;
  // If no Mio/Mrd suffix but value < 100, assume it's in Mrd
  // Otherwise assume Mio
  if (!isMio && !isMrd && val > 0) {
    // Raw number from etfdb is in Mio already
  }
  return val; // in Mio
}

interface Props {
  positions: Position[];
}

export function FundSizeChart({ positions }: Props) {
  const data = useMemo(() => {
    const buckets = SIZE_BUCKETS.map((b) => ({
      name: b.label,
      weight: 0,
      color: b.color,
    }));

    const active = positions.filter((p) => p.etfData && p.weight > 0);

    for (const p of active) {
      const sizeMio = parseFundSize(p.etfData!.fund_size);
      if (sizeMio <= 0) continue;

      const bucketIdx = SIZE_BUCKETS.findIndex((b) => sizeMio < b.max);
      if (bucketIdx >= 0) {
        buckets[bucketIdx].weight += p.weight;
      }
    }

    return buckets.filter((b) => b.weight > 0);
  }, [positions]);

  if (data.length === 0) return null;

  return (
    <div className="chart-card chart-card--full">
      <h3>Fondsgrößen-Verteilung</h3>
      <p className="chart-subtitle">
        Anteil deines Sparplans nach Fondsgröße (Schließungsrisiko bei &lt; 100 Mio)
      </p>
      <ResponsiveContainer width="100%" height={350}>
        <PieChart>
          <Pie
            data={data}
            dataKey="weight"
            nameKey="name"
            cx="50%"
            cy="50%"
            innerRadius={80}
            outerRadius={140}
            paddingAngle={2}
            label={({ name, value, x, y, textAnchor }) => (
              <text
                x={x}
                y={y}
                textAnchor={textAnchor}
                dominantBaseline="central"
                fontSize={12}
                fill="#334155"
              >
                {`${name}: ${Number(value).toFixed(1)}%`}
              </text>
            )}
          >
            {data.map((entry, i) => (
              <Cell key={i} fill={entry.color} />
            ))}
          </Pie>
          <Tooltip
            formatter={(value) => `${Number(value).toFixed(1)}%`}
          />
          <Legend wrapperStyle={{ fontSize: "12px" }} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
