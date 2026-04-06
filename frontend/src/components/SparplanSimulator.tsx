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
import type { Position } from "../types";

type Period = "1y" | "3y" | "5y";

interface Props {
  positions: Position[];
  monthlyTotal: number;
}

interface YearPoint {
  year: number;
  deposits: number;
  value: number;
}

function getWeightedReturn(positions: Position[], period: Period): number {
  let weightedReturn = 0;

  for (const p of positions) {
    if (!p.etfData || p.weight <= 0) continue;
    const w = p.weight / 100; // weight is 0-100, normalize to 0-1

    let annualized = 0;
    if (period === "1y") {
      annualized = p.etfData.return_1y || 0; // already % p.a.
    } else if (period === "3y") {
      // return_3y is cumulative %, annualize: (1 + r/100)^(1/3) - 1
      const cum = (p.etfData.return_3y || 0) / 100;
      annualized = cum !== 0 ? (Math.pow(1 + cum, 1 / 3) - 1) * 100 : 0;
    } else {
      const cum = (p.etfData.return_5y || 0) / 100;
      annualized = cum !== 0 ? (Math.pow(1 + cum, 1 / 5) - 1) * 100 : 0;
    }

    weightedReturn += w * annualized; // w is 0-1, annualized is %, result is %
  }

  return weightedReturn; // already weighted sum in %
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

const PERIOD_LABELS: Record<Period, string> = {
  "1y": "Letzte 12 Monate",
  "3y": "Letzte 3 Jahre",
  "5y": "Letzte 5 Jahre",
};

export function SparplanSimulator({ positions, monthlyTotal }: Props) {
  const [startAmount, setStartAmount] = useState(0);
  const [years, setYears] = useState(10);
  const [period, setPeriod] = useState<Period>("3y");

  const returns = useMemo(() => ({
    "1y": getWeightedReturn(positions, "1y"),
    "3y": getWeightedReturn(positions, "3y"),
    "5y": getWeightedReturn(positions, "5y"),
  }), [positions]);

  const annualReturn = returns[period];
  const hasReturnData = positions.some((p) => p.etfData && (p.etfData.return_1y || p.etfData.return_3y || p.etfData.return_5y));

  const data = useMemo(
    () => simulate(startAmount, monthlyTotal, years, annualReturn),
    [startAmount, monthlyTotal, years, annualReturn]
  );

  const endValue = data[data.length - 1]?.value ?? 0;
  const totalDeposits = data[data.length - 1]?.deposits ?? 0;
  const gains = endValue - totalDeposits;

  return (
    <div className="chart-card sparplan-card">
      <h3>Portfolio-Projektion</h3>
      <p className="chart-subtitle">
        Hochrechnung basierend auf der tatsächlichen Performance deines Portfolios
      </p>

      {!hasReturnData && (
        <p className="chart-subtitle" style={{ color: "#f59e0b" }}>
          Rendite-Daten werden geladen...
        </p>
      )}

      <div className="sparplan-inputs">
        <div className="sparplan-field">
          <label>Bestehendes Portfolio</label>
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
          <label>Monatliche Sparrate</label>
          <div className="input-group">
            <span className="total-display-sm">{monthlyTotal} €</span>
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
          <label>Basis</label>
          <div className="period-buttons">
            {(["1y", "3y", "5y"] as Period[]).map((p) => (
              <button
                key={p}
                className={`period-btn ${period === p ? "period-btn--active" : ""}`}
                onClick={() => setPeriod(p)}
              >
                {PERIOD_LABELS[p]}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="sparplan-summary">
        <div className="summary-item">
          <span className="summary-label">Gew. Rendite p.a.</span>
          <span className={`summary-value ${annualReturn >= 0 ? "gains" : "negative"}`}>
            {annualReturn >= 0 ? "+" : ""}{annualReturn.toFixed(2)}%
          </span>
        </div>
        <div className="summary-item">
          <span className="summary-label">Eingezahlt</span>
          <span className="summary-value">{formatEuro(totalDeposits)}</span>
        </div>
        <div className="summary-item">
          <span className="summary-label">Rendite</span>
          <span className={`summary-value ${gains >= 0 ? "gains" : "negative"}`}>
            {formatEuro(gains)}
          </span>
        </div>
        <div className="summary-item">
          <span className="summary-label">Endsumme</span>
          <span className="summary-value total">{formatEuro(endValue)}</span>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={280}>
        <AreaChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="year" tickFormatter={(v) => `${v}J`} />
          <YAxis tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
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
