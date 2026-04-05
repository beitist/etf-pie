import { useEffect, useMemo } from "react";
import { usePortfolioStore } from "./stores/portfolio";
import { aggregatePortfolio, findOverlaps } from "./lib/calculations";
import { PortfolioHeader } from "./components/PortfolioHeader";
import { AddETFSearch } from "./components/AddETFSearch";
import { PositionRow } from "./components/PositionRow";
import { AllocationChart } from "./components/AllocationChart";
import { MarketCapChart } from "./components/MarketCapChart";
import { OverlapTable } from "./components/OverlapTable";
import { WarningBanner } from "./components/WarningBanner";
import { ShareButton } from "./components/ShareButton";
import { CountryMap } from "./components/CountryMap";
import { SparplanSimulator } from "./components/SparplanSimulator";
import { PreloadModal } from "./components/PreloadModal";
import "./App.css";

function App() {
  const { positions, limits, totalAmount, loadFromURL, getShareURL } =
    usePortfolioStore();

  // Load portfolio from URL on first render
  useEffect(() => {
    loadFromURL();
  }, [loadFromURL]);

  // Sync state to URL hash on changes
  useEffect(() => {
    if (positions.length > 0) {
      const hash = getShareURL().split("#")[1];
      window.location.hash = hash || "";
    }
  }, [positions, totalAmount, getShareURL]);

  const aggregated = useMemo(() => aggregatePortfolio(positions), [positions]);
  const overlaps = useMemo(() => findOverlaps(positions), [positions]);

  const hasData = positions.some((p) => p.etfData);

  return (
    <div className="app">
      <PreloadModal />
      <header className="app-header">
        <h1>ETF Portfolio Analyzer</h1>
        <p>Diversifikationsanalyse deines ETF-Portfolios</p>
        {positions.length > 0 && <ShareButton />}
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

            <section className="full-width-section">
              <CountryMap countries={aggregated.countries} />
            </section>

            <section className="overlap-section">
              <OverlapTable overlaps={overlaps} />
            </section>

            <section className="full-width-section">
              <SparplanSimulator avgReturn={7} />
            </section>
          </>
        )}
      </main>
    </div>
  );
}

export default App;
