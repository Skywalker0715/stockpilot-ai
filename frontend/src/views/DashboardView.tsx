import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { AssetSummary } from "../types";
import {
  EmptyState,
  ErrorPanel,
  LoadingBlock,
  PageHeader,
} from "../ui";

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
  const [summary, setSummary] = useState<AssetSummary | null>(null);
  const [imageCount, setImageCount] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([
      api.insights(),
      api.listAssets({ has_image: true, page: 1, page_size: 1 }),
    ])
      .then(([assetSummary, images]) => {
        setSummary(assetSummary);
        setImageCount(images.total);
        setError(null);
      })
      .catch((e: unknown) =>
        setError(e instanceof ApiError ? e.message : "Failed to load workspace overview"),
      )
      .finally(() => setLoading(false));
  }, [refreshKey]);

  useEffect(load, [load]);

  return (
    <div>
      <PageHeader
        title="Dashboard"
        subtitle="A quick view of the assets in your StockPilot workspace."
      />
      <p className="note">
        Counts come from your saved records. Archived records stay in your library data.
      </p>

      {loading && !summary && <LoadingBlock label="Loading workspace overview…" />}

      {error && (
        <ErrorPanel message={error} onRetry={() => setRefreshKey((key) => key + 1)} />
      )}

      {summary && !error && (
        <>
          <section className="stat-grid" aria-label="Library overview">
            <StatCard
              label="Active records"
              value={Math.max(0, summary.total_assets - summary.archived_assets)}
              hint="Available in your active library"
            />
            <StatCard
              label="Uploaded images"
              value={imageCount}
              hint="Stored in the StockPilot workspace"
            />
            <StatCard
              label="Archived records"
              value={summary.archived_assets}
              hint="Kept for later restoration"
            />
          </section>

          {summary.total_assets === 0 && (
            <section className="panel">
              <div className="panel__body">
                <EmptyState
                  message="Your workspace is ready"
                  hint="Upload an image from Generate or add an existing record in Library."
                />
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
