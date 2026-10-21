// Library: saved images with their metadata; reopening loads an item into
// the Generate view (single editor implementation, no duplication).

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { Asset, AssetList } from "../types";
import { AssetsView } from "./AssetsView";
import {
  ConfirmDialog,
  EmptyState,
  ErrorPanel,
  LoadingBlock,
  PageHeader,
  Pagination,
} from "../ui";

export function LibraryView({
  reloadToken,
  onOpenAsset,
  onViewInsights,
}: {
  /** Bump to refetch (e.g. after a save in the Generate view). */
  reloadToken: number;
  onOpenAsset: (id: number) => void;
  /** Navigate to Vision Insights with this asset pre-selected. */
  onViewInsights: (id: number) => void;
}) {
  const [manageAssets, setManageAssets] = useState(false);
  const [list, setList] = useState<AssetList | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  // Archive ("Remove from Library") flow — recoverable, never a delete.
  const [archiveTarget, setArchiveTarget] = useState<Asset | null>(null);
  const [archiving, setArchiving] = useState(false);
  const [archiveError, setArchiveError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    api
      .listAssets({ has_image: true, page, page_size: 12 })
      .then((l) => {
        setList(l);
        setError(null);
      })
      .catch((e: unknown) =>
        setError(e instanceof ApiError ? e.message : "Failed to load library"),
      )
      .finally(() => setLoading(false));
  }, [page]);

  useEffect(load, [load, reloadToken]);

  if (manageAssets) {
    return (
      <div>
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => setManageAssets(false)}>
          Back to Library
        </button>
        <AssetsView />
      </div>
    );
  }

  const pageSize = list?.page_size ?? 12;
  const totalPages = list ? Math.max(1, Math.ceil(list.total / pageSize)) : 1;

  const closeArchive = () => {
    if (!archiving) setArchiveTarget(null);
  };

  // Archive = PATCH archived=true on the existing endpoint. The item leaves
  // the Library (the default list hides archived rows) but its metadata,
  // uploaded file, and submission history are untouched, and the Assets page
  // can restore it via "Show archived" -> "Unarchive".
  const confirmArchive = async () => {
    if (!archiveTarget || archiving) return; // no repeated submissions
    setArchiving(true);
    setArchiveError(null);
    try {
      const name = archiveTarget.display_name;
      await api.updateAsset(archiveTarget.id, { archived: true });
      setArchiveTarget(null);
      setNotice(
        `“${name}” was archived and removed from the Library. Nothing was deleted — restore it any time from the Assets page (“Show archived” → “Unarchive”).`,
      );
      load();
    } catch (e: unknown) {
      if (e instanceof ApiError && e.status === 404) {
        setArchiveTarget(null);
        setNotice("That item no longer exists; the Library has been refreshed.");
        load();
      } else {
        setArchiveError(e instanceof ApiError ? e.message : "Failed to archive item");
      }
    } finally {
      setArchiving(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Library"
        subtitle="Images you have uploaded, with their saved metadata."
      />

      <button type="button" className="btn btn-ghost btn-sm" onClick={() => setManageAssets(true)}>
        Manage assets, archives, and deletions
      </button>

      <p className="note">
        Archiving removes an image from the Library but keeps everything:
        metadata, the uploaded file, and submission history. Restore any item
        from the Assets page (“Show archived” → “Unarchive”).
      </p>

      {notice && (
        <div className="success-panel" role="status">
          <p>{notice}</p>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => setNotice(null)}
            aria-label="Dismiss success message"
          >
            Dismiss
          </button>
        </div>
      )}

      {error && <ErrorPanel message={error} onRetry={load} />}
      {loading && !list && <LoadingBlock label="Loading library…" />}

      {list && list.items.length === 0 && !error && (
        <div className="panel">
          <div className="panel__body">
            <EmptyState
              message="No images yet"
              hint="Upload your first image on the Generate page."
            />
          </div>
        </div>
      )}

      {list && list.items.length > 0 && (
        <div className="panel">
          <div className="panel__header">
            <h3 className="panel__title">Images</h3>
            <span className="panel__meta">{list.total} total</span>
          </div>
          <div className="panel__body">
            <ul className="library-grid">
              {list.items.map((asset) => (
                <li key={asset.id} className="library-card">
                  <button
                    type="button"
                    className="library-card__open"
                    onClick={() => onOpenAsset(asset.id)}
                    aria-label={`Open ${asset.display_name} in the editor`}
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
                    <span className="badge badge-neutral">
                      {asset.keywords.length} keywords
                    </span>
                    {asset.category && (
                      <span className="badge badge-neutral">{asset.category}</span>
                    )}
                    <span className="hint">
                      {asset.metadata_origin === "ai_suggested"
                        ? "AI assisted"
                        : asset.metadata_origin}
                    </span>
                  </div>
                  <div className="library-card__actions">
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() => {
                        setArchiveTarget(asset);
                        setArchiveError(null);
                        setNotice(null);
                      }}
                      disabled={archiving}
                      aria-label={`Archive ${asset.title || asset.display_name} — remove from Library (keeps data)`}
                    >
                      Archive
                    </button>
                      <button
                        type="button"
                        className="btn btn-ghost btn-sm"
                        onClick={() => void onViewInsights(asset.id)}
                        aria-label={`View vision insights for ${asset.title || asset.display_name}`}
                      >
                        Insights
                      </button>
                    </div>
                </li>
              ))}
            </ul>
            <Pagination
              page={list.page}
              total={list.total}
              totalPages={totalPages}
              onPage={setPage}
            />
          </div>
        </div>
      )}

      {archiveTarget && (
        <ConfirmDialog
          title="Remove from Library (Archive)"
          confirmLabel="Archive"
          busy={archiving}
          onConfirm={() => void confirmArchive()}
          onCancel={closeArchive}
        >
          <p>
            <strong>{archiveTarget.display_name}</strong> will be hidden from
            the Library.
          </p>
          <p>
            Nothing is deleted: its metadata, uploaded image, and submission
            history are kept.
          </p>
          <p className="hint">
            Restore it any time from the Assets page: enable “Show archived”,
            then choose “Unarchive”.
          </p>
          {archiveError && <ErrorPanel message={archiveError} />}
        </ConfirmDialog>
      )}
    </div>
  );
}
