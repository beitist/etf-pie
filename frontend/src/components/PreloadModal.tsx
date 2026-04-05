import { useEffect, useState } from "react";

interface PreloadStatus {
  total: number;
  done: number;
  status: "idle" | "loading" | "done";
  errors: string[];
  phase: string;
}

export function PreloadModal() {
  const [status, setStatus] = useState<PreloadStatus | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    // Check if user already dismissed before
    if (sessionStorage.getItem("preload-dismissed")) {
      setDismissed(true);
      return;
    }

    const poll = async () => {
      try {
        const res = await fetch("/api/preload-status");
        const data: PreloadStatus = await res.json();
        setStatus(data);
        if (data.status === "done") {
          // Auto-dismiss after 1.5s when done
          setTimeout(() => {
            setDismissed(true);
            sessionStorage.setItem("preload-dismissed", "1");
          }, 1500);
        }
      } catch {
        // API not ready yet
      }
    };

    poll();
    const interval = setInterval(poll, 2000);
    return () => clearInterval(interval);
  }, []);

  if (dismissed || !status || status.status === "idle") return null;

  const pct = status.total > 0 ? Math.round((status.done / status.total) * 100) : 0;

  return (
    <div className="preload-overlay">
      <div className="preload-modal">
        <h2>ETF-Index wird aufgebaut</h2>
        <p>
          Suchindex wird erstellt. Beim ersten Start werden ETF-Namen
          und ISINs von justETF geladen und lokal gecacht.
        </p>

        <div className="preload-progress-bar">
          <div
            className="preload-progress-fill"
            style={{ width: `${pct}%` }}
          />
        </div>
        <p className="preload-count">
          {status.phase || `${status.done} / ${status.total} (${pct}%)`}
        </p>

        {status.status === "done" && (
          <p className="preload-done">Fertig!</p>
        )}

        {status.errors.length > 0 && (
          <details className="preload-errors">
            <summary>{status.errors.length} Fehler</summary>
            <ul>
              {status.errors.map((e, i) => (
                <li key={i}>{e}</li>
              ))}
            </ul>
          </details>
        )}

        {status.status === "loading" && (
          <button
            className="preload-skip"
            onClick={() => {
              setDismissed(true);
              sessionStorage.setItem("preload-dismissed", "1");
            }}
          >
            Überspringen
          </button>
        )}
      </div>
    </div>
  );
}
