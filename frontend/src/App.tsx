import { useCallback, useEffect, useState, type ReactNode } from "react";
import { api } from "./api";
import { DashboardView } from "./views/DashboardView";
import { GenerateView } from "./views/GenerateView";
import { LibraryView } from "./views/LibraryView";
import { VisionInsightsView } from "./views/VisionInsightsView";

type Tab =
  | "generate"
  | "library"
  | "dashboard"
  | "vision-insights";

const PRIMARY_TABS: { id: Tab; label: string }[] = [
  { id: "generate", label: "Generate" },
  { id: "library", label: "Library" },
];

const SECONDARY_TABS: { id: Tab; label: string }[] = [
  { id: "dashboard", label: "Dashboard" },
  { id: "vision-insights", label: "Vision Insights" },
];

// Minimal 16px inline icons for the sidebar nav (no icon dependency).
function NavIcon({ tab }: { tab: Tab }) {
  let paths: ReactNode;
  if (tab === "generate") {
    // sparkle / magic wand
    paths = (
      <>
        <path d="M8 1.5 9.4 5.1 13 6.5 9.4 7.9 8 11.5 6.6 7.9 3 6.5 6.6 5.1z" />
        <path d="M12.5 10.5l.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7z" />
      </>
    );
  } else if (tab === "library") {
    // stacked images
    paths = (
      <>
        <rect x="2.5" y="5.5" width="9" height="7.5" rx="1" />
        <path d="M4.5 3.5h7a1 1 0 0 1 1 1v5.5" />
      </>
    );
  } else if (tab === "dashboard") {
    paths = (
      <>
        <rect x="2.5" y="2.5" width="5" height="5" rx="1" />
        <rect x="8.5" y="2.5" width="5" height="5" rx="1" />
        <rect x="2.5" y="8.5" width="5" height="5" rx="1" />
        <rect x="8.5" y="8.5" width="5" height="5" rx="1" />
      </>
    );
  } else if (tab === "vision-insights") {
    // eye / analysis icon
    paths = (
      <>
        <path d="M8 2.5c-3 0-5.5 1.5-5.5 4S5 11 8 11s5.5-1.5 5.5-4-2.5-4-5.5-4" />
        <path d="M8 6a2 2 0 1 1 0 4 2 2 0 0 1 0-4" />
      </>
    );
  } else {
    paths = <path d="M13.5 2.5 7.5 13.5 6 9 2 7.5z M13.5 2.5 6 9" />;
  }
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.4"
      strokeLinejoin="round"
      strokeLinecap="round"
      aria-hidden="true"
    >
      {paths}
    </svg>
  );
}

export default function App() {
  const [tab, setTab] = useState<Tab>("generate");
  const [aiNote, setAiNote] = useState<string | null>(null);
  // Asset to open in the Generate editor (from the Library).
  const [openAssetId, setOpenAssetId] = useState<number | null>(null);
  // Bumped after each save so the Library refetches.
  const [libraryReload, setLibraryReload] = useState(0);

  useEffect(() => {
    // Honest AI disclosure (Q6): shown in the Generate view and sidebar,
    // applies app-wide. Best-effort; views show their own errors.
    api
      .aiStatus()
      .then((s) => {
        if (!s.ai_configured) setAiNote(s.message);
      })
      .catch(() => {
        /* no banner; views report their own API errors */
      });
  }, []);

  const handleSaved = useCallback(() => setLibraryReload((n) => n + 1), []);

  const openFromLibrary = useCallback((id: number) => {
    setOpenAssetId(id);
    setTab("generate");
  }, []);

  const viewInsightsFromLibrary = useCallback((id: number) => {
    setOpenAssetId(id);
    setTab("vision-insights");
  }, []);

  const renderNavItems = (tabs: { id: Tab; label: string }[]) =>
    tabs.map((t) => (
      <button
        key={t.id}
        type="button"
        className={tab === t.id ? "nav-item nav-item--active" : "nav-item"}
        aria-current={tab === t.id ? "page" : undefined}
        onClick={() => setTab(t.id)}
      >
        <NavIcon tab={t.id} />
        <span>{t.label}</span>
      </button>
    ));

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand__mark" aria-hidden="true">
            <img src="/stockpilot-%20logo.jpg" alt="" loading="eager" />
          </span>
          <span className="brand__name">
            StockPilot <span className="brand__accent">AI</span>
          </span>
        </div>

        <nav className="side-nav" aria-label="Main navigation">
          {renderNavItems(PRIMARY_TABS)}
        </nav>

        <nav className="side-nav side-nav--secondary" aria-label="Secondary navigation">
          <p className="side-nav__label">More</p>
          {renderNavItems(SECONDARY_TABS)}
        </nav>

        {aiNote && (
          <div className="sidebar-foot">
            <p className="ai-status" role="status">
              <span className="ai-status__dot" aria-hidden="true" />
              <span>{aiNote}</span>
            </p>
          </div>
        )}
      </aside>

      <main className="main">
        <div className="page">
          {tab === "generate" && (
            <GenerateView
              onSaved={handleSaved}
              openAssetId={openAssetId}
              onOpened={() => setOpenAssetId(null)}
            />
          )}
          {tab === "library" && (
            <LibraryView
              reloadToken={libraryReload}
              onOpenAsset={openFromLibrary}
              onViewInsights={viewInsightsFromLibrary}
            />
          )}
          {tab === "dashboard" && <DashboardView />}
          {tab === "vision-insights" && (
            <VisionInsightsView
              openAssetId={openAssetId}
              onOpened={() => setOpenAssetId(null)}
            />
          )}
        </div>
      </main>
    </div>
  );
}


