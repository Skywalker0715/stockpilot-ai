import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { InsightsSummary } from "../types";

function CountMap({ title, counts }: { title: string; counts: Record<string, number> }) {
  const entries = Object.entries(counts);
  return (
    <section className="card">
      <h3>{title}</h3>
      {entries.length === 0 ? (
        <p className="empty">No records yet.</p>
      ) : (
        <dl>
          {entries.map(([key, n]) => (
            <div className="row" key={key}>
              <dt>{key}</dt>
              <dd>{n}</dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  );
}

export function DashboardView() {
  const [summary, setSummary] = useState<InsightsSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api
      .insights()
      .then((s) => {
        setSummary(s);
        setError(null);
      })
      .catch((e: unknown) =>
        setError(e instanceof ApiError ? e.message : "Failed to load summary"),
      )
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p role="status">Loading summary…</p>;
  if (error)
    return (
      <div className="error" role="alert">
        <p>{error}</p>
        <button type="button" onClick={() => window.location.reload()}>
          Retry
        </button>
      </div>
    );
  if (!summary) return null;

  return (
    <div>
      <p className="disclaimer">
        These counts reflect only the records you have entered in this app. They
        are not predictions.
      </p>

      <section className="card">
        <h3>Totals</h3>
        <dl>
          <div className="row">
            <dt>Assets (active)</dt>
            <dd>{summary.total_assets - summary.archived_assets}</dd>
          </div>
          <div className="row">
            <dt>Assets (archived)</dt>
            <dd>{summary.archived_assets}</dd>
          </div>
          <div className="row">
            <dt>Submissions</dt>
            <dd>{summary.total_submissions}</dd>
          </div>
        </dl>
      </section>

      <div className="grid">
        <CountMap title="By status" counts={summary.submissions_by_status} />
        <CountMap title="By platform" counts={summary.submissions_by_platform} />
        <CountMap title="Rejection categories" counts={summary.rejections_by_category} />
      </div>

      <section className="card">
        <h3>Sample</h3>
        <p>
          {summary.sample_size} submission{summary.sample_size === 1 ? "" : "s"} with
          a recorded date
          {summary.period_start && summary.period_end
            ? ` between ${summary.period_start} and ${summary.period_end}.`
            : ". No dated submissions yet."}
        </p>
      </section>
    </div>
  );
}
