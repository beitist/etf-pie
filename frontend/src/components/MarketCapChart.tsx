import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { MarketCap } from "../types";

interface Props {
  marketCap: MarketCap;
}

export function MarketCapChart({ marketCap }: Props) {
  const data = [
    { name: "Large Cap", value: marketCap.large },
    { name: "Mid Cap", value: marketCap.mid },
    { name: "Small Cap", value: marketCap.small },
    { name: "Micro Cap", value: marketCap.micro },
  ].filter((d) => d.value > 0);

  if (data.length === 0) return null;

  return (
    <div className="chart-card">
      <h3>Marktkapitalisierung</h3>
      <ResponsiveContainer width="100%" height={250}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" />
          <YAxis unit="%" />
          <Tooltip formatter={(value) => `${Number(value).toFixed(1)}%`} />
          <Bar dataKey="value" fill="#2563eb" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
