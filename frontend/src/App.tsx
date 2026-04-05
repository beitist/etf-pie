import { useMemo } from "react";
import { usePortfolioStore } from "./stores/portfolio";
import { aggregatePortfolio, findOverlaps } from "./lib/calculations";
import { PortfolioHeader } from "./components/PortfolioHeader";
import { AddETFSearch } from "./components/AddETFSearch";
import { PositionRow } from "./components/PositionRow";
import { AllocationChart } from "./components/AllocationChart";
import { MarketCapChart } from "./components/MarketCapChart";
import { OverlapTable } from "./components/OverlapTable";
import { WarningBanner } from "./components/WarningBanner";
import "./App.css";

function App() {
  const { positions, limits } = usePortfolioStore();

  const aggregated = useMemo(() => aggregatePortfolio(positions), [positions]);
  const overlaps = useMemo(() => findOverlaps(positions), [positions]);

  const hasData = positions.some((p) => p.etfData);

  return (
    <div className="app">
      <header className="app-header">
        <h1>ETF Portfolio Analyzer</h1>
        <p>Diversifikationsanalyse deines ETF-Portfolios</p>
      </header>

      <main>
        <section className="portfolio-section">
          <PortfolioHeader />
          <AddETFSearch />
          <div className="positions-list">
            {positions.map((p) => (
              <PositionRow key={p.isin} position={p} />
            ))}
            {positions.length === 0 && (
              <p className="empty-state">
                Füge ETFs hinzu um dein Portfolio zu analysieren.
              </p>
            )}
          </div>
        </section>

        {hasData && (
          <>
            <WarningBanner
              countries={aggregated.countries}
              limits={limits}
              positions={positions}
            />

            <section className="charts-grid">
              <AllocationChart
                title="Länder-Allokation"
                data={aggregated.countries}
              />
              <AllocationChart
                title="Sektoren"
                data={aggregated.sectors}
              />
              <AllocationChart
                title="Top Holdings"
                data={aggregated.holdings}
              />
              <MarketCapChart marketCap={aggregated.marketCap} />
            </section>

            <section className="overlap-section">
              <OverlapTable overlaps={overlaps} />
            </section>
          </>
        )}
      </main>
    </div>
  );
}

export default App;
