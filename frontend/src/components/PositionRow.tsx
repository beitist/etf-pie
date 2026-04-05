import { usePortfolioStore } from "../stores/portfolio";
import type { Position } from "../types";

interface Props {
  position: Position;
}

export function PositionRow({ position }: Props) {
  const { setEuroAmount, removePosition } = usePortfolioStore();

  return (
    <div className="position-row">
      <div className="position-info">
        <span className="position-name">
          {position.etfData ? position.etfData.name : position.name}
        </span>
        <span className="position-isin">{position.isin}</span>
        {position.etfData && (
          <span className="position-ter">
            TER {position.etfData.ter}%
          </span>
        )}
        {!position.etfData && (
          <span className="position-loading">Laden...</span>
        )}
      </div>
      <div className="position-controls">
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
  );
}
