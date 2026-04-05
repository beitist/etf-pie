import { usePortfolioStore } from "../stores/portfolio";

export function PortfolioHeader() {
  const { totalAmount, setTotalAmount, mode, toggleMode } =
    usePortfolioStore();

  return (
    <div className="portfolio-header">
      <div className="amount-input">
        <label>Gesamtsumme</label>
        <div className="input-group">
          <input
            type="number"
            value={totalAmount}
            onChange={(e) => setTotalAmount(Number(e.target.value) || 0)}
            min={0}
            step={100}
          />
          <span className="unit">€/Monat</span>
        </div>
      </div>
      <button className="mode-toggle" onClick={toggleMode}>
        {mode === "percent" ? "%" : "€"} → Wechseln zu{" "}
        {mode === "percent" ? "€" : "%"}
      </button>
    </div>
  );
}
