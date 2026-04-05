import { usePortfolioStore } from "../stores/portfolio";
import type { Position } from "../types";

interface Props {
  position: Position;
}

export function PositionRow({ position }: Props) {
  const { mode, totalAmount, setWeight, removePosition } =
    usePortfolioStore();

  const handleSlider = (e: React.ChangeEvent<HTMLInputElement>) => {
    setWeight(position.isin, Number(e.target.value));
  };

  const handleEuroInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const euro = Number(e.target.value) || 0;
    const pct = totalAmount > 0 ? (euro / totalAmount) * 100 : 0;
    setWeight(position.isin, pct);
  };

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
        <input
          type="range"
          min={0}
          max={100}
          step={0.5}
          value={position.weight}
          onChange={handleSlider}
          className="weight-slider"
        />
        {mode === "percent" ? (
          <span className="weight-display">
            {position.weight.toFixed(1)}%
          </span>
        ) : (
          <div className="euro-input">
            <input
              type="number"
              value={Math.round(position.euroAmount)}
              onChange={handleEuroInput}
              min={0}
              step={10}
            />
            <span>€</span>
          </div>
        )}
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
