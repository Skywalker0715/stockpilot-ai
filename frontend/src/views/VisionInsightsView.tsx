// Vision Insights analyzes an existing library image with explicit consent.
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { Asset, AssetList, VisionInsightsRecord } from "../types";
import {
  EmptyState,
  ErrorPanel,
  LoadingBlock,
  PageHeader,
  Pagination,
} from "../ui";

const PAGE_SIZE = 12;

function AssetCard({
  asset,
  selected,
  onSelect,
}: {
  asset: Asset;
  selected: boolean;
  onSelect: (asset: Asset) => void;
}) {
  return (
    <li className={`library-card${selected ? " library-card--selected" : ""}`}>
      <button
        type="button"
        className="library-card__open"
        onClick={() => onSelect(asset)}
        aria-label={`Select ${asset.display_name} for vision insights`}
      >
        <img
          src={asset.image_url ?? ""}
          alt=""
          loading="lazy"
          className="library-card__thumb"
        />
        <span className="library-card__name" title={asset.display_name}>
          {asset.title || asset.display_name}
        </span>
      </button>
      <div className="library-card__meta">
        <span className="badge badge-neutral">{asset.keywords.length} keywords</span>
        {asset.category && <span className="badge badge-neutral">{asset.category}</span>}
      </div>
    </li>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return <h3 className="panel__title">{children}</h3>;
}

function BulletList({ items }: { items: string[] }) {
  if (items.length === 0) return <span className="muted">— none —</span>;
  return (
    <ul className="insights-list">
      {items.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}
    </ul>
  );
}

export function VisionInsightsView({
  openAssetId,
  onOpened,
}: {
  openAssetId: number | null;
  onOpened: () => void;
}) {
  const [assets, setAssets] = useState<AssetList | null>(null);
  const [assetsError, setAssetsError] = useState<string | null>(null);
  const [assetsLoading, setAssetsLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [selectedAsset, setSelectedAsset] = useState<Asset | null>(null);
  const [insights, setInsights] = useState<VisionInsightsRecord | null>(null);
  const [insightsError, setInsightsError] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [applying, setApplying] = useState(false);
  const [applyError, setApplyError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [consentGiven, setConsentGiven] = useState(false);
  const [keywordsToApply, setKeywordsToApply] = useState<Set<string>>(new Set());

  const loadAssets = useCallback(async (): Promise<AssetList | null> => {
    setAssetsLoading(true);
    setAssetsError(null);
    try {
      const list = await api.listAssets({
        has_image: true,
        q: search || undefined,
        page,
        page_size: PAGE_SIZE,
      });
      setAssets(list);
      return list;
    } catch (error: unknown) {
      setAssetsError(error instanceof ApiError ? error.message : "Failed to load images");
      return null;
    } finally {
      setAssetsLoading(false);
    }
  }, [page, search]);

  const loadInsights = useCallback(async (id: number) => {
    setInsights(null);
    setInsightsError(null);
    try {
      setInsights(await api.visionInsights(id));
    } catch (error: unknown) {
      if (error instanceof ApiError && error.status === 404) {
        setInsights(null);
        setInsightsError(null);
      } else {
        setInsightsError(error instanceof ApiError ? error.message : "Failed to load insights");
      }
    }
  }, []);

  useEffect(() => { void loadAssets(); }, [loadAssets]);

  useEffect(() => {
    if (!openAssetId) return;
    onOpened();
    let cancelled = false;
    void (async () => {
      const list = assets?.items.some((asset) => asset.id === openAssetId)
        ? assets
        : await loadAssets();
      const asset = list?.items.find((item) => item.id === openAssetId);
      if (!cancelled && asset) {
        setSelectedAsset(asset);
        void loadInsights(asset.id);
      }
    })();
    return () => { cancelled = true; };
  }, [openAssetId, onOpened, assets, loadAssets, loadInsights]);

  const runAnalysis = async () => {
    if (!selectedAsset) return;
    setAnalyzing(true);
    setInsightsError(null);
    setApplyError(null);
    setNotice(null);
    try {
      setInsights(await api.visionAnalyze(selectedAsset.id, consentGiven));
      setNotice("Vision analysis complete. Review the suggestions below.");
    } catch (error: unknown) {
      setInsightsError(error instanceof ApiError ? error.message : "Vision analysis failed");
    } finally {
      setAnalyzing(false);
    }
  };

  const applySuggestedKeywords = async () => {
    if (!selectedAsset || !insights) return;
    const allowed = new Set(insights.keyword_gap_analysis.suggested_missing);
    const existing = new Set(selectedAsset.keywords.map((keyword) => keyword.trim().toLocaleLowerCase()));
    const toAdd = [...keywordsToApply].filter((keyword) =>
      allowed.has(keyword) && !existing.has(keyword.trim().toLocaleLowerCase()),
    );
    if (toAdd.length === 0) return;

    setApplying(true);
    setApplyError(null);
    try {
      await api.updateAsset(selectedAsset.id, { keywords: [...selectedAsset.keywords, ...toAdd] });
      setNotice(`Applied ${toAdd.length} keyword${toAdd.length === 1 ? "" : "s"} to “${selectedAsset.display_name}”.`);
      setKeywordsToApply(new Set());
      setSelectedAsset(await api.getAsset(selectedAsset.id));
      void loadAssets();
    } catch (error: unknown) {
      setApplyError(error instanceof ApiError ? error.message : "Failed to apply keywords");
    } finally {
      setApplying(false);
    }
  };

  const clearSelection = () => {
    setSelectedAsset(null);
    setInsights(null);
    setInsightsError(null);
    setKeywordsToApply(new Set());
    setNotice(null);
    setConsentGiven(false);
  };

  const totalPages = assets ? Math.max(1, Math.ceil(assets.total / (assets.page_size || PAGE_SIZE))) : 1;
  const existingKeywords = new Set((selectedAsset?.keywords ?? []).map((keyword) => keyword.trim().toLocaleLowerCase()));
  const suggestedMissing = insights?.keyword_gap_analysis.suggested_missing ?? [];
  const review = insights?.metadata_quality_review;
  const hasReview = Boolean(review && (
    review.title_assessment || review.description_assessment ||
    review.keyword_issues.length || review.unsupported_terms.length
  ));

  return (
    <div>
      <PageHeader
        title="Vision Insights"
        subtitle="Analyze image attributes, metadata gaps, and possible content uses."
      />
      <p className="note">
        Select an existing image. It is sent to Cohere only after you confirm consent.
        Analysis is saved separately; metadata changes only when you apply selected keywords.
      </p>
      {notice && <div className="success-panel"><p>{notice}</p></div>}

      <section className="panel">
        <div className="panel__header"><h3 className="panel__title">Choose an image</h3></div>
        <div className="panel__body">
          <label className="field-label" htmlFor="vision-image-search">Search images</label>
          <input
            id="vision-image-search"
            className="input"
            type="search"
            value={search}
            onChange={(event) => { setPage(1); setSearch(event.target.value); }}
            placeholder="Search your library"
          />
          {assetsLoading && <LoadingBlock label="Loading images…" />}
          {assetsError && <ErrorPanel message={assetsError} />}
          {assets && assets.items.length === 0 && !assetsLoading && (
            <EmptyState message="No images available" hint="Add an image from Generate or Library first." />
          )}
          {assets && assets.items.length > 0 && (
            <>
              <ul className="library-grid">
                {assets.items.map((asset) => (
                  <AssetCard
                    key={asset.id}
                    asset={asset}
                    selected={selectedAsset?.id === asset.id}
                    onSelect={(next) => {
                      setSelectedAsset(next);
                      setKeywordsToApply(new Set());
                      setNotice(null);
                      void loadInsights(next.id);
                    }}
                  />
                ))}
              </ul>
              <Pagination page={page} total={assets.total} totalPages={totalPages} onPage={setPage} />
            </>
          )}
        </div>
      </section>

      {selectedAsset && (
        <section className="panel" style={{ marginTop: "1rem" }}>
          <div className="panel__header">
            <h3 className="panel__title">Analyze: {selectedAsset.title || selectedAsset.display_name}</h3>
          </div>
          <div className="panel__body">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={consentGiven}
                onChange={(event) => setConsentGiven(event.target.checked)}
              />
              I agree to send this image to Cohere for AI analysis.
            </label>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => void runAnalysis()}
              disabled={!consentGiven || analyzing}
              style={{ marginTop: "0.75rem" }}
            >
              {analyzing ? "Analyzing…" : insights ? "Run analysis again" : "Analyze image"}
            </button>
            {analyzing && <LoadingBlock label="Analyzing image…" />}
            {insightsError && <ErrorPanel message={insightsError} />}
            {!insights && !insightsError && !analyzing && (
              <p className="hint">No saved analysis for this image yet. Confirm consent to start.</p>
            )}
          </div>
        </section>
      )}

      {insights && (
        <section className="panel" style={{ marginTop: "1rem" }}>
          <div className="panel__header">
            <h3 className="panel__title">Vision insights</h3>
            <span className="panel__meta">Model: {insights.model} · {insights.created_at}</span>
          </div>
          <div className="panel__body insights-grid">
            <div className="insights-card">
              <SectionTitle>Visual attributes</SectionTitle>
              <p className="hint">AI-described observations; verify details against the image.</p>
              <p><strong>Objects:</strong> {insights.visual_attributes.objects.join(", ") || "—"}</p>
              <p><strong>Scene:</strong> {insights.visual_attributes.scene.join(", ") || "—"}</p>
              <p><strong>Dominant colors:</strong> {insights.visual_attributes.dominant_colors.join(", ") || "—"}</p>
              <p><strong>Lighting:</strong> {insights.visual_attributes.lighting || "—"}</p>
              <p><strong>Mood:</strong> {insights.visual_attributes.mood || "—"}</p>
              <p><strong>Composition:</strong> {insights.visual_attributes.composition || "—"}</p>
              <p><strong>Orientation:</strong> {insights.visual_attributes.orientation || "—"}</p>
              <p><strong>Copy space:</strong> {insights.visual_attributes.copy_space || "—"}</p>
            </div>

            <div className="insights-card">
              <SectionTitle>Commercial use ideas</SectionTitle>
              <p className="hint">AI suggestions, not evidence of demand, sales, or ranking.</p>
              <BulletList items={insights.commercial_use_ideas.map((idea) => idea.use_case)} />
            </div>

            <div className="insights-card">
              <SectionTitle>Keyword gap analysis</SectionTitle>
              <p className="hint">Suggested keywords are compared with saved metadata; review before applying.</p>
              {insights.keyword_gap_analysis.reasoning && <p className="hint">{insights.keyword_gap_analysis.reasoning}</p>}
              {suggestedMissing.length === 0 ? <p className="muted">No missing keywords suggested.</p> : (
                <>
                  <div className="insights-keywords">
                    {suggestedMissing.map((keyword) => {
                      const alreadySaved = existingKeywords.has(keyword.trim().toLocaleLowerCase());
                      return (
                        <label key={keyword} className="checkbox-label">
                          <input
                            type="checkbox"
                            checked={keywordsToApply.has(keyword)}
                            disabled={alreadySaved || applying}
                            onChange={() => setKeywordsToApply((previous) => {
                              const next = new Set(previous);
                              if (next.has(keyword)) next.delete(keyword);
                              else next.add(keyword);
                              return next;
                            })}
                          />
                          {keyword}{alreadySaved ? " (saved)" : ""}
                        </label>
                      );
                    })}
                  </div>
                  {keywordsToApply.size > 0 && (
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      onClick={() => void applySuggestedKeywords()}
                      disabled={applying}
                    >
                      {applying ? "Applying…" : `Apply ${keywordsToApply.size} selected`}
                    </button>
                  )}
                </>
              )}
              {applyError && <ErrorPanel message={applyError} />}
            </div>

            <div className="insights-card">
              <SectionTitle>Metadata quality review</SectionTitle>
              <p className="hint">AI review of saved metadata; check its observations before editing.</p>
              {review?.title_assessment && <p><strong>Title:</strong> {review.title_assessment}</p>}
              {review?.keyword_issues.length ? <><p><strong>Keyword issues:</strong></p><BulletList items={review.keyword_issues} /></> : null}
              {review?.description_assessment && <p><strong>Description:</strong> {review.description_assessment}</p>}
              {review?.unsupported_terms.length ? <><p><strong>Potentially unsupported terms:</strong></p><BulletList items={review.unsupported_terms} /></> : null}
              {!hasReview && <p className="muted">No metadata issues were identified by the analysis.</p>}
            </div>

            <div className="insights-card">
              <SectionTitle>Actionable recommendations</SectionTitle>
              <p className="hint">Image-specific suggestions to improve metadata clarity and discoverability.</p>
              <BulletList items={insights.actionable_recommendations} />
            </div>
          </div>
        </section>
      )}

      {selectedAsset && <button type="button" className="btn btn-ghost btn-sm" onClick={clearSelection} style={{ marginTop: "1rem" }}>Choose a different image</button>}
    </div>
  );
}
