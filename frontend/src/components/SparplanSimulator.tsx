import { useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

interface Props {
  /** Weighted average annual return of the portfolio (e.g. 7 for 7%) */
  avgReturn: number;
}

interface YearPoint {
  year: number;
  deposits: number;
  value: number;
}

function simulate(
  startAmount: number,
  monthly: number,
  years: number,
  annualReturn: number
): YearPoint[] {
  const monthlyRate = annualReturn / 100 / 12;
  const points: YearPoint[] = [{ year: 0, deposits: startAmount, value: startAmount }];
  let value = startAmount;
  let deposits = startAmount;

  for (let month = 1; month <= years * 12; month++) {
    value = value * (1 + monthlyRate) + monthly;
    deposits += monthly;
    if (month % 12 === 0) {
      points.push({
        year: month / 12,
        deposits: Math.round(deposits),
        value: Math.round(value),
      });
    }
  }
  return points;
}

function formatEuro(value: number): string {
  return value.toLocaleString("de-DE", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
}

export function SparplanSimulator({ avgReturn }: Props) {
  const [startAmount, setStartAmount] = useState(10000);
  const [monthly, setMonthly] = useState(500);
  const [years, setYears] = useState(20);
  const [annualReturn, setAnnualReturn] = useState(avgReturn || 7);

  const data = useMemo(
    () => simulate(startAmount, monthly, years, annualReturn),
    [startAmount, monthly, years, annualReturn]
  );

  const endValue = data[data.length - 1]?.value ?? 0;
  const totalDeposits = data[data.length - 1]?.deposits ?? 0;
  const gains = endValue - totalDeposits;

  return (
    <div className="chart-card sparplan-card">
      <h3>Sparplan-Simulator</h3>

      <div className="sparplan-inputs">
        <div className="sparplan-field">
          <label>Startbetrag</label>
          <div className="input-group">
            <input
              type="number"
              value={startAmount}
              onChange={(e) => setStartAmount(Number(e.target.value) || 0)}
              min={0}
              step={1000}
            />
            <span className="unit">€</span>
          </div>
        </div>
        <div className="sparplan-field">
          <label>Monatlich</label>
          <div className="input-group">
            <input
              type="number"
              value={monthly}
              onChange={(e) => setMonthly(Number(e.target.value) || 0)}
              min={0}
              step={50}
            />
            <span className="unit">€</span>
          </div>
        </div>
        <div className="sparplan-field">
          <label>Haltedauer</label>
          <div className="input-group">
            <input
              type="number"
              value={years}
              onChange={(e) => setYears(Math.max(1, Number(e.target.value) || 1))}
              min={1}
              max={50}
            />
            <span className="unit">Jahre</span>
          </div>
        </div>
        <div className="sparplan-field">
          <label>Rendite p.a.</label>
          <div className="input-group">
            <input
              type="number"
              value={annualReturn}
              onChange={(e) => setAnnualReturn(Number(e.target.value) || 0)}
              min={0}
              max={30}
              step={0.5}
            />
            <span className="unit">%</span>
          </div>
        </div>
      </div>

      <div className="sparplan-summary">
        <div className="summary-item">
          <span className="summary-label">Eingezahlt</span>
          <span className="summary-value">{formatEuro(totalDeposits)}</span>
        </div>
        <div className="summary-item">
          <span className="summary-label">Rendite</span>
          <span className="summary-value gains">{formatEuro(gains)}</span>
        </div>
        <div className="summary-item">
          <span className="summary-label">Endsumme</span>
          <span className="summary-value total">{formatEuro(endValue)}</span>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={280}>
        <AreaChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey="year"
            tickFormatter={(v) => `${v}J`}
          />
          <YAxis
            tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
          />
          <Tooltip
            formatter={(value, name) => [
              formatEuro(Number(value)),
              name === "value" ? "Portfoliowert" : "Eingezahlt",
            ]}
            labelFormatter={(label) => `Jahr ${label}`}
          />
          <Area
            type="monotone"
            dataKey="deposits"
            stackId="1"
            stroke="#94a3b8"
            fill="#e2e8f0"
            name="deposits"
          />
          <Area
            type="monotone"
            dataKey="value"
            stroke="#2563eb"
            fill="#bfdbfe"
            name="value"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
