import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import type { Allocation } from "../types";

const COLORS = [
  "#2563eb", "#7c3aed", "#db2777", "#ea580c", "#ca8a04",
  "#16a34a", "#0891b2", "#6366f1", "#e11d48", "#84cc16",
  "#94a3b8",
];

interface Props {
  title: string;
  data: Allocation[];
}

export function AllocationChart({ title, data }: Props) {
  if (data.length === 0) return null;

  return (
    <div className="chart-card">
      <h3>{title}</h3>
      <ResponsiveContainer width="100%" height={300}>
        <PieChart>
          <Pie
            data={data}
            dataKey="weight"
            nameKey="name"
            cx="50%"
            cy="50%"
            innerRadius={60}
            outerRadius={110}
            paddingAngle={2}
            label={({ name, value }) =>
              `${name} ${Number(value).toFixed(1)}%`
            }
          >
            {data.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip
            formatter={(value) => `${Number(value).toFixed(2)}%`}
          />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
