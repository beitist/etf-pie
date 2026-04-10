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

type Scenario = "historical" | "conservative" | "balanced" | "optimistic";

const HISTORICAL_RETURN = 8.0; // long-term DAX/global stocks since ~1950

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
  historical:   { w1y: 0,   w3y: 0,   w5y: 0   }, // unused, fixed rate
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
  // Historical scenario uses a fixed long-term average instead of ETF data
  if (scenario === "historical") return HISTORICAL_RETURN;

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

interface SimResult {
  points: YearPoint[];
  totalTax: number;
}

function simulate(
  startAmount: number,
  monthly: number,
  years: number,
  annualReturn: number,
  annualContribIncrease: number = 0,
  withTax: boolean = false
): SimResult {
  const monthlyRate = annualReturn / 100 / 12;
  const points: YearPoint[] = [
    { year: 0, deposits: startAmount, value: startAmount },
  ];
  let value = startAmount;
  let deposits = startAmount;
  let currentMonthly = monthly;
  let totalTax = 0;

  for (let year = 1; year <= years; year++) {
    const valueStart = value;
    let yearContrib = 0;

    for (let m = 0; m < 12; m++) {
      value = value * (1 + monthlyRate) + currentMonthly;
      deposits += currentMonthly;
      yearContrib += currentMonthly;
    }

    // Yearly tax: gain = end - start - contributions
    if (withTax) {
      const yearGain = value - valueStart - yearContrib;
      if (yearGain > 0) {
        const afterTeilfreistellung = yearGain * (1 - TEILFREISTELLUNG_AKTIEN);
        const taxableGain = Math.max(0, afterTeilfreistellung - SPARERPAUSCHBETRAG);
        const tax = taxableGain * ABGELTUNGSSTEUER;
        value -= tax;
        totalTax += tax;
      }
    }

    points.push({
      year,
      deposits: Math.round(deposits),
      value: Math.round(value),
    });

    // Increase contribution at year boundary (after tax for next year)
    currentMonthly = currentMonthly * (1 + annualContribIncrease / 100);
  }

  return { points, totalTax };
}

function formatEuro(value: number): string {
  return value.toLocaleString("de-DE", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
}

const SCENARIO_LABELS: Record<Scenario, string> = {
  historical: "Historisch (8%)",
  conservative: "Konservativ",
  balanced: "Ausgewogen",
  optimistic: "Optimistisch",
};

const SCENARIO_DESC: Record<Scenario, string> = {
  historical: "Langfristiger Schnitt globaler Aktien (DAX seit 1950: ~8% p.a.)",
  conservative: "70% 5J + 20% 3J + 10% 1J",
  balanced: "40% 5J + 40% 3J + 20% 1J",
  optimistic: "20% 5J + 30% 3J + 50% 1J",
};

// German tax constants
const SPARERPAUSCHBETRAG = 1000; // €/year per person
const ABGELTUNGSSTEUER = 0.26375; // 25% + 5.5% Soli (without church tax)
const TEILFREISTELLUNG_AKTIEN = 0.30; // 30% of equity ETF gains tax-free
// Effective tax rate on equity ETF gains: 26.375% × 70% = 18.4625%

const DEFAULT_INFLATION = 2.5;

export function SparplanSimulator({ positions, monthlyTotal }: Props) {
  const [startAmount, setStartAmount] = useState(0);
  const [years, setYears] = useState(10);
  const [scenario, setScenario] = useState<Scenario>("balanced");
  const [showInflation, setShowInflation] = useState(true);
  const [inflation, setInflation] = useState(DEFAULT_INFLATION);
  const [showTax, setShowTax] = useState(true);
  const [adjustContribution, setAdjustContribution] = useState(true);

  const DEFAULT_RETURN = 5; // conservative fallback for ETFs without data

  const withData = positions.filter((p) => p.etfData && p.weight > 0 && (p.etfData.return_1y || p.etfData.return_3y || p.etfData.return_5y));
  const withoutData = positions.filter((p) => p.etfData && p.weight > 0 && !p.etfData.return_1y && !p.etfData.return_3y && !p.etfData.return_5y);
  const missingPct = withoutData.reduce((s, p) => s + p.weight, 0);

  const annualReturn = useMemo(() => {
    const dataReturn = getWeightedReturn(positions, scenario);
    if (missingPct <= 0) return dataReturn;

    // Blend: real data for covered %, fallback for uncovered %
    const coveredPct = 100 - missingPct;
    return coveredPct > 0
      ? (dataReturn * coveredPct + DEFAULT_RETURN * missingPct) / 100
      : DEFAULT_RETURN;
  }, [positions, scenario, missingPct]);

  const hasReturnData = withData.length > 0;

  const contribIncrease = adjustContribution ? inflation : 0;

  const sim = useMemo(
    () => simulate(startAmount, monthlyTotal, years, annualReturn, contribIncrease, showTax),
    [startAmount, monthlyTotal, years, annualReturn, contribIncrease, showTax]
  );

  const data = sim.points;
  const endValue = data[data.length - 1]?.value ?? 0;
  const totalDeposits = data[data.length - 1]?.deposits ?? 0;
  const taxAmount = sim.totalTax;
  const gains = endValue + taxAmount - totalDeposits; // gross gains before tax
  const afterTax = endValue; // already tax-deducted in simulate

  // Inflation: real value = nominal / (1+inflation)^years
  const inflationFactor = showInflation
    ? Math.pow(1 + inflation / 100, years)
    : 1;
  const realValue = afterTax / inflationFactor;
  const realDeposits = totalDeposits / inflationFactor;

  return (
    <div className="chart-card sparplan-card">
      <h3>Portfolio-Projektion</h3>
      <p className="chart-subtitle">
        Hochrechnung basierend auf der tatsächlichen Performance deines Portfolios
      </p>

      {!hasReturnData && (
        <p className="chart-subtitle" style={{ color: "#f59e0b" }}>
          Rendite-Daten werden geladen... Rechne mit {DEFAULT_RETURN}% p.a. als Schätzung.
        </p>
      )}
      {hasReturnData && missingPct > 0 && (
        <p className="chart-subtitle" style={{ color: "#f59e0b" }}>
          Für {withoutData.length} ETF{withoutData.length > 1 ? "s" : ""} ({missingPct.toFixed(0)}% des Portfolios)
          fehlen Performance-Daten. Dort wird mit {DEFAULT_RETURN}% p.a. gerechnet.
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
            {(["historical", "conservative", "balanced", "optimistic"] as Scenario[]).map((s) => (
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

      <div className="sparplan-toggles">
        <label className="toggle-field">
          <input
            type="checkbox"
            checked={showTax}
            onChange={(e) => setShowTax(e.target.checked)}
          />
          <span>Kapitalertragssteuer (DE: 26.375% mit 30% Teilfreistellung)</span>
        </label>
        <label className="toggle-field">
          <input
            type="checkbox"
            checked={showInflation}
            onChange={(e) => setShowInflation(e.target.checked)}
          />
          <span>Inflation berücksichtigen</span>
          {showInflation && (
            <input
              type="number"
              value={inflation}
              onChange={(e) => setInflation(Number(e.target.value) || 0)}
              step={0.1}
              min={0}
              max={20}
              className="inflation-input"
            />
          )}
          {showInflation && <span className="unit">% p.a.</span>}
        </label>
        <label className="toggle-field">
          <input
            type="checkbox"
            checked={adjustContribution}
            onChange={(e) => setAdjustContribution(e.target.checked)}
            disabled={!showInflation}
          />
          <span>
            Sparrate jährlich an Inflation anpassen
            {adjustContribution && showInflation && ` (+${inflation}% p.a.)`}
          </span>
        </label>
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
          <span className="summary-label">Endsumme (brutto)</span>
          <span className="summary-value total">{formatEuro(endValue)}</span>
        </div>
        {showTax && (
          <div className="summary-item">
            <span className="summary-label">Steuer (DE)</span>
            <span className="summary-value negative">−{formatEuro(taxAmount)}</span>
          </div>
        )}
        {showTax && (
          <div className="summary-item">
            <span className="summary-label">Nach Steuer</span>
            <span className="summary-value total">{formatEuro(afterTax)}</span>
          </div>
        )}
        {showInflation && (
          <div className="summary-item">
            <span className="summary-label">
              Kaufkraft heute ({inflation}% Infl.)
            </span>
            <span className="summary-value total">{formatEuro(realValue)}</span>
          </div>
        )}
        {showInflation && (
          <div className="summary-item">
            <span className="summary-label">Reale Einzahlung heute</span>
            <span className="summary-value">{formatEuro(realDeposits)}</span>
          </div>
        )}
      </div>

      <ResponsiveContainer width="100%" height={280}>
        <AreaChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey="year"
            tickFormatter={(v) => {
              const d = new Date();
              d.setFullYear(d.getFullYear() + v);
              return d.toLocaleDateString("de-DE", { month: "short", year: "2-digit" });
            }}
          />
          <YAxis tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
          <Tooltip
            formatter={(value, name) => [
              formatEuro(Number(value)),
              name === "value" ? "Portfoliowert" : "Eingezahlt",
            ]}
            labelFormatter={(label) => {
              const d = new Date();
              d.setFullYear(d.getFullYear() + Number(label));
              return d.toLocaleDateString("de-DE", { month: "long", year: "numeric" });
            }}
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
