import { useState } from "react";
import { usePortfolioStore } from "../stores/portfolio";

export function ShareButton() {
  const getShareURL = usePortfolioStore((s) => s.getShareURL);
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    const url = getShareURL();
    await navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button className="share-btn" onClick={handleCopy}>
      {copied ? "Kopiert!" : "Link kopieren"}
    </button>
  );
}
