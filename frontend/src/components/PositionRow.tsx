import { useState } from "react";
import { usePortfolioStore } from "../stores/portfolio";
import type { Position } from "../types";

interface Props {
  position: Position;
}

function formatReturn(val: number): string {
  if (!val) return "–";
  const sign = val > 0 ? "+" : "";
  return `${sign}${val.toFixed(2)}%`;
}

function returnClass(val: number): string {
  if (!val) return "neutral";
  return val > 0 ? "positive" : "negative";
}

export function PositionRow({ position }: Props) {
  const { setEuroAmount, removePosition } = usePortfolioStore();
  const [expanded, setExpanded] = useState(false);

  const d = position.etfData;

  return (
    <div className={`position-row ${expanded ? "position-row--expanded" : ""}`}>
      <div className="position-main" onClick={() => d && setExpanded(!expanded)}>
        <div className="position-info">
          <span className="position-name">
            {d ? d.name : position.name}
            {d && <span className="expand-icon">{expanded ? "▾" : "▸"}</span>}
          </span>
          <span className="position-isin">
            {position.isin}
            {d?.wkn && ` · WKN ${d.wkn}`}
          </span>
          {d && (
            <span className="position-ter">TER {d.ter}%</span>
          )}
          {!d && <span className="position-loading">Laden...</span>}
        </div>
        <div className="position-controls" onClick={(e) => e.stopPropagation()}>
          <div className="euro-input">
            <input
              type="number"
              value={Math.round(position.euroAmount)}
              onChange={(e) =>
                setEuroAmount(position.isin, Number(e.target.value) || 0)
              }
              min={0}
              step={25}
            />
            <span>€</span>
          </div>
          <span className="weight-display">
            {position.weight.toFixed(1)}%
          </span>
          <button
            className="remove-btn"
            onClick={() => removePosition(position.isin)}
            title="Entfernen"
          >
            ✕
          </button>
        </div>
      </div>

      {expanded && d && (
        <div className="position-detail">
          <div className="detail-grid">
            <div className="detail-section">
              <h4>Fondsdaten</h4>
              <dl>
                {d.issuer && <><dt>Anbieter</dt><dd>{d.issuer}</dd></>}
                {d.asset_class && <><dt>Anlageschwerpunkt</dt><dd>{d.asset_class}</dd></>}
                {d.benchmark && <><dt>Index</dt><dd>{d.benchmark}</dd></>}
                {d.domicile && <><dt>Fondsdomizil</dt><dd>{d.domicile}</dd></>}
                {d.fund_size && <><dt>Fondsgröße</dt><dd>{d.fund_size}</dd></>}
                <dt>Replikation</dt><dd>{d.replication || "–"}</dd>
                <dt>Ausschüttung</dt><dd>{d.distribution || "–"}</dd>
                <dt>Währung</dt><dd>{d.currency}</dd>
              </dl>
            </div>
            <div className="detail-section">
              <h4>Rendite</h4>
              <dl className="returns">
                <dt>1 Monat</dt><dd className={returnClass(d.return_1m)}>{formatReturn(d.return_1m)}</dd>
                <dt>3 Monate</dt><dd className={returnClass(d.return_3m)}>{formatReturn(d.return_3m)}</dd>
                <dt>6 Monate</dt><dd className={returnClass(d.return_6m)}>{formatReturn(d.return_6m)}</dd>
                <dt>Lfd. Jahr</dt><dd className={returnClass(d.return_ytd)}>{formatReturn(d.return_ytd)}</dd>
                <dt>1 Jahr</dt><dd className={returnClass(d.return_1y)}>{formatReturn(d.return_1y)}</dd>
                <dt>3 Jahre</dt><dd className={returnClass(d.return_3y)}>{formatReturn(d.return_3y)}</dd>
                <dt>5 Jahre</dt><dd className={returnClass(d.return_5y)}>{formatReturn(d.return_5y)}</dd>
              </dl>
              {d.volatility_1y > 0 && (
                <p className="volatility">Volatilität 1J: {d.volatility_1y.toFixed(2)}%</p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
