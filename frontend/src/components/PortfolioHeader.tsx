import { usePortfolioStore } from "../stores/portfolio";

export function PortfolioHeader() {
  const { totalAmount } = usePortfolioStore();

  return (
    <div className="portfolio-header">
      <div className="amount-input">
        <label>Gesamtsumme</label>
        <div className="input-group">
          <span className="total-display">
            {totalAmount.toLocaleString("de-DE")} €/Monat
          </span>
        </div>
      </div>
    </div>
  );
}
