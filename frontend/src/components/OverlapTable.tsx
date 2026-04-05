interface Props {
  overlaps: { name: string; etfs: string[] }[];
}

export function OverlapTable({ overlaps }: Props) {
  if (overlaps.length === 0) return null;

  return (
    <div className="chart-card">
      <h3>Overlap-Analyse</h3>
      <p className="chart-subtitle">Aktien, die in mehreren ETFs vorkommen</p>
      <div className="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Aktie</th>
              <th>Enthalten in</th>
            </tr>
          </thead>
          <tbody>
            {overlaps.slice(0, 20).map((o) => (
              <tr key={o.name}>
                <td>{o.name}</td>
                <td>{o.etfs.join(", ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
