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

type Scenario = "conservative" | "balanced" | "optimistic";

interface Props {
  positions: Position[];
  monthlyTotal: number;
}

interface YearPoint {
  year: number;
  deposits: number;
  value: number;
}

// Weights for blending return periods per scenario
const SCENARIO_WEIGHTS: Record<Scenario, { w1y: number; w3y: number; w5y: number }> = {
  conservative: { w1y: 0.1, w3y: 0.2, w5y: 0.7 },
  balanced:     { w1y: 0.2, w3y: 0.4, w5y: 0.4 },
  optimistic:   { w1y: 0.5, w3y: 0.3, w5y: 0.2 },
};

function annualize(cumReturn: number, years: number): number {
  if (!cumReturn) return 0;
  return (Math.pow(1 + cumReturn / 100, 1 / years) - 1) * 100;
}

function getBlendedReturn(d: Position["etfData"], scenario: Scenario): number {
  if (!d) return 0;

  const r1y = d.return_1y || 0;
  const r3y = d.return_3y ? annualize(d.return_3y, 3) : 0;
  const r5y = d.return_5y ? annualize(d.return_5y, 5) : 0;

  // Use available data, redistribute weights if some periods missing
  const sw = SCENARIO_WEIGHTS[scenario];
  let totalW = 0;
  let blended = 0;

  if (r1y) { blended += sw.w1y * r1y; totalW += sw.w1y; }
  if (r3y) { blended += sw.w3y * r3y; totalW += sw.w3y; }
  if (r5y) { blended += sw.w5y * r5y; totalW += sw.w5y; }

  return totalW > 0 ? blended / totalW : 0;
}

function getWeightedReturn(positions: Position[], scenario: Scenario): number {
  let weightedReturn = 0;
  let coveredWeight = 0;

  for (const p of positions) {
    if (!p.etfData || p.weight <= 0) continue;

    const blended = getBlendedReturn(p.etfData, scenario);
    if (!blended) continue;

    const w = p.weight / 100;
    weightedReturn += w * blended;
    coveredWeight += w;
  }

  return coveredWeight > 0 ? weightedReturn / coveredWeight : 0;
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

const SCENARIO_LABELS: Record<Scenario, string> = {
  conservative: "Konservativ",
  balanced: "Ausgewogen",
  optimistic: "Optimistisch",
};

const SCENARIO_DESC: Record<Scenario, string> = {
  conservative: "70% 5J + 20% 3J + 10% 1J",
  balanced: "40% 5J + 40% 3J + 20% 1J",
  optimistic: "20% 5J + 30% 3J + 50% 1J",
};

export function SparplanSimulator({ positions, monthlyTotal }: Props) {
  const [startAmount, setStartAmount] = useState(0);
  const [years, setYears] = useState(10);
  const [scenario, setScenario] = useState<Scenario>("balanced");

  const annualReturn = useMemo(
    () => getWeightedReturn(positions, scenario),
    [positions, scenario]
  );

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
          <label>Szenario</label>
          <div className="period-buttons">
            {(["conservative", "balanced", "optimistic"] as Scenario[]).map((s) => (
              <button
                key={s}
                className={`period-btn ${scenario === s ? "period-btn--active" : ""}`}
                onClick={() => setScenario(s)}
                title={SCENARIO_DESC[s]}
              >
                {SCENARIO_LABELS[s]}
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
