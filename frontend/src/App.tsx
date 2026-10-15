import { useEffect, useState } from "react";
import { api } from "./api";
import { AssetsView } from "./views/AssetsView";
import { DashboardView } from "./views/DashboardView";
import { SubmissionsView } from "./views/SubmissionsView";

type Tab = "dashboard" | "assets" | "submissions";

const TABS: { id: Tab; label: string }[] = [
  { id: "dashboard", label: "Dashboard" },
  { id: "assets", label: "Assets" },
  { id: "submissions", label: "Submissions" },
];

export default function App() {
  const [tab, setTab] = useState<Tab>("assets");
  const [aiNote, setAiNote] = useState<string | null>(null);

  useEffect(() => {
    // Honest AI disclosure (Q6): shown once, applies app-wide.
    api
      .aiStatus()
      .then((s) => {
        if (!s.ai_configured) setAiNote(s.message);
      })
      .catch(() => {
        /* banner is best-effort; views show their own errors */
      });
  }, []);

  return (
    <div className="app">
      <header className="app-header">
        <h1>StockPilot AI</h1>
        <nav aria-label="Main navigation">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              className={tab === t.id ? "tab active" : "tab"}
              aria-current={tab === t.id ? "page" : undefined}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      {aiNote && (
        <div className="notice" role="status">
          {aiNote}
        </div>
      )}

      <main>
        {tab === "dashboard" && <DashboardView />}
        {tab === "assets" && <AssetsView />}
        {tab === "submissions" && <SubmissionsView />}
      </main>
    </div>
  );
}
