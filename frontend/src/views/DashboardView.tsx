import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { InsightsSummary } from "../types";
import {
  EmptyState,
  ErrorPanel,
  LoadingBlock,
  PageHeader,
  StatusBadge,
  isSubmissionStatus,
} from "../ui";

// Count rows with a proportional bar. The bar encodes only the real
// counts returned by the API (relative to the largest count).
function CountList({
  counts,
  variant,
}: {
  counts: Record<string, number>;
  variant: "status" | "plain";
}) {
  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  const max = Math.max(...entries.map(([, n]) => n), 1);
  return (
    <ul className="count-list">
      {entries.map(([key, n]) => {
        const knownStatus = variant === "status" && isSubmissionStatus(key);
        return (
          <li className="count-row" key={key}>
            <span className="count-row__label">
              {knownStatus ? <StatusBadge status={key} /> : key}
            </span>
            <span className="count-row__value">{n}</span>
            <span className="count-row__track">
              <span
                className={
                  knownStatus
                    ? `count-row__fill count-row__fill--${key}`
                    : "count-row__fill"
                }
                style={{ width: `${Math.round((n / max) * 100)}%` }}
              />
            </span>
          </li>
        );
      })}
    </ul>
  );
}

function StatCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: number;
  hint: string;
}) {
  return (
    <div className="stat-card">
      <span className="stat-card__label">{label}</span>
      <span className="stat-card__value">{value}</span>
      <p className="stat-card__hint">{hint}</p>
    </div>
  );
}

export function DashboardView() {
  const [summary, setSummary] = useState<InsightsSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);

  const load = useCallback(() => {
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
  }, [refreshKey]);

  useEffect(load, [load]);

  return (
    <div>
      <PageHeader
        title="Dashboard"
        subtitle="Overview of your asset library and submission activity."
      />
      <p className="note">
        Counts reflect only the records entered in this app. They are not
        predictions.
      </p>

      {loading && !summary && <LoadingBlock label="Loading summary…" />}

      {error && (
        <ErrorPanel message={error} onRetry={() => setRefreshKey((k) => k + 1)} />
      )}

      {summary && !error && (
        <>
          <section className="stat-grid" aria-label="Totals">
            <StatCard
              label="Active assets"
              value={Math.max(0, summary.total_assets - summary.archived_assets)}
              hint="Not archived"
            />
            <StatCard
              label="Archived assets"
              value={summary.archived_assets}
              hint="Hidden from the default list"
            />
            <StatCard
              label="Submissions"
              value={summary.total_submissions}
              hint="Across all platforms"
            />
          </section>

          <div className="breakdown-grid">
            <section className="panel">
              <div className="panel__header">
                <h3 className="panel__title">Submissions by status</h3>
              </div>
              <div className="panel__body">
                {Object.keys(summary.submissions_by_status).length === 0 ? (
                  <EmptyState
                    message="No submissions yet"
                    hint="Record one from the Submissions page."
                  />
                ) : (
                  <CountList counts={summary.submissions_by_status} variant="status" />
                )}
              </div>
            </section>

            <section className="panel">
              <div className="panel__header">
                <h3 className="panel__title">Submissions by platform</h3>
              </div>
              <div className="panel__body">
                {Object.keys(summary.submissions_by_platform).length === 0 ? (
                  <EmptyState
                    message="No platforms recorded yet"
                    hint="Platforms appear here once you record submissions."
                  />
                ) : (
                  <CountList counts={summary.submissions_by_platform} variant="plain" />
                )}
              </div>
            </section>

            <section className="panel">
              <div className="panel__header">
                <h3 className="panel__title">Rejection categories</h3>
              </div>
              <div className="panel__body">
                {Object.keys(summary.rejections_by_category).length === 0 ? (
                  <EmptyState
                    message="No rejections recorded yet"
                    hint="Rejection reasons appear here once recorded."
                  />
                ) : (
                  <CountList counts={summary.rejections_by_category} variant="plain" />
                )}
              </div>
            </section>
          </div>

          <section className="panel">
            <div className="panel__header">
              <h3 className="panel__title">Dated submissions</h3>
            </div>
            <div className="panel__body">
              <dl className="meta-rows">
                <div>
                  <dt>With a recorded date</dt>
                  <dd>{summary.sample_size}</dd>
                </div>
                <div>
                  <dt>Earliest date</dt>
                  <dd>{summary.period_start ?? "—"}</dd>
                </div>
                <div>
                  <dt>Latest date</dt>
                  <dd>{summary.period_end ?? "—"}</dd>
                </div>
              </dl>
              {summary.sample_size === 0 && (
                <p className="hint" style={{ marginTop: "0.8rem" }}>
                  No dated submissions yet.
                </p>
              )}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
