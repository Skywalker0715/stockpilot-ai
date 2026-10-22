import { FormEvent, useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { Asset, AssetList } from "../types";
import { EmptyState, ErrorPanel, LoadingBlock, PageHeader, Pagination, ConfirmDialog } from "../ui";

interface FormState {
  id: number | null; // null = creating
  display_name: string;
  title: string;
  description: string;
  keywords: string; // comma-separated in the form
  category: string;
  file_reference: string;
  media_type: string;
}

const EMPTY_FORM: FormState = {
  id: null,
  display_name: "",
  title: "",
  description: "",
  keywords: "",
  category: "",
  file_reference: "",
  media_type: "",
};

function toForm(asset: Asset): FormState {
  return {
    id: asset.id,
    display_name: asset.display_name,
    title: asset.title ?? "",
    description: asset.description ?? "",
    keywords: asset.keywords.join(", "),
    category: asset.category ?? "",
    file_reference: asset.file_reference ?? "",
    media_type: asset.media_type ?? "",
  };
}

export function LibraryManagementView() {
  const [list, setList] = useState<AssetList | null>(null);
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [includeArchived, setIncludeArchived] = useState(false);
  const [page, setPage] = useState(1);
  const [form, setForm] = useState<FormState | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [listError, setListError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  // Permanent delete flow (confirmation dialog).
  const [deleteTarget, setDeleteTarget] = useState<Asset | null>(null);
  // null = still checking; the dialog cannot confirm until this resolves.
  const [linkedCount, setLinkedCount] = useState<number | null>(null);
  const [linkedCountError, setLinkedCountError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    api
      .listAssets({ q: search || undefined, archived: includeArchived, page, page_size: 20 })
      .then((l) => {
        setList(l);
        setListError(null);
      })
      .catch((e: unknown) =>
        setListError(e instanceof ApiError ? e.message : "Failed to load assets"),
      )
      .finally(() => setLoading(false));
  }, [search, includeArchived, page]);

  useEffect(load, [load]);

  const startCreate = () => {
    setForm({ ...EMPTY_FORM });
    setFormError(null);
    setSuccessMessage(null);
  };

  const startEdit = (asset: Asset) => {
    setForm(toForm(asset));
    setFormError(null);
    setSuccessMessage(null);
  };

  const toggleArchived = async (asset: Asset) => {
    try {
      await api.updateAsset(asset.id, { archived: !asset.archived });
      load();
    } catch (e: unknown) {
      setListError(e instanceof ApiError ? e.message : "Failed to update asset");
    }
  };

  // Open the delete confirmation and look up how many submission records are
  // linked to this asset, so the dialog can show the full blast radius before
  // the user is allowed to confirm.
  const openDelete = async (asset: Asset) => {
    setDeleteTarget(asset);
    setLinkedCount(null);
    setLinkedCountError(null);
    setDeleteError(null);
    setSuccessMessage(null);
    try {
      const linked = await api.listSubmissions({ asset_id: asset.id, page_size: 1 });
      setLinkedCount(linked.total);
    } catch (e: unknown) {
      setLinkedCountError(
        e instanceof ApiError ? e.message : "Failed to check linked submissions",
      );
    }
  };

  const closeDelete = () => {
    if (!deleting) setDeleteTarget(null);
  };

  const confirmDelete = async () => {
    // Guard against repeated submissions while a delete is in flight.
    if (!deleteTarget || deleting) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      const result = await api.deleteAsset(deleteTarget.id);
      let message = `Deleted “${result.display_name}”.`;
      if (result.deleted_submissions > 0) {
        const n = result.deleted_submissions;
        message += ` ${n} linked submission record${n === 1 ? "" : "s"} deleted as well.`;
      }
      if (result.image_removed === false) {
        message +=
          " The record is gone, but the image file could not be removed from disk (the failure was logged).";
      }
      setSuccessMessage(message);
      setDeleteTarget(null);
      setLinkedCount(null);
      load();
    } catch (e: unknown) {
      if (e instanceof ApiError && e.status === 404) {
        // Already deleted elsewhere (e.g. another tab): refresh instead of failing.
        setSuccessMessage(
          `“${deleteTarget.display_name}” no longer exists; the list has been refreshed.`,
        );
        setDeleteTarget(null);
        setLinkedCount(null);
        load();
      } else {
        setDeleteError(e instanceof ApiError ? e.message : "Failed to delete asset");
      }
    } finally {
      setDeleting(false);
    }
  };

  const submitForm = async (event: FormEvent) => {
    event.preventDefault();
    if (!form) return;
    setSaving(true);
    setFormError(null);
    const keywords = form.keywords
      .split(",")
      .map((k) => k.trim())
      .filter((k) => k.length > 0);
    const payload = {
      display_name: form.display_name,
      title: form.title || null,
      description: form.description || null,
      keywords,
      category: form.category || null,
      file_reference: form.file_reference || null,
      media_type: form.media_type || null,
    };
    try {
      if (form.id === null) {
        await api.createAsset(payload);
      } else {
        await api.updateAsset(form.id, payload);
      }
      setForm(null);
      load();
    } catch (e: unknown) {
      setFormError(e instanceof ApiError ? e.message : "Failed to save asset");
    } finally {
      setSaving(false);
    }
  };

  const pageSize = list?.page_size ?? 20;
  const totalPages = list ? Math.max(1, Math.ceil(list.total / pageSize)) : 1;

  return (
    <div>
      <PageHeader
        title="All library records"
        subtitle="Search and manage image records, including archived items."
        actions={
          <button type="button" className="btn btn-primary" onClick={startCreate}>
            Add asset
          </button>
        }
      />

      <div className="toolbar">
        <form
          className="toolbar__search"
          role="search"
          onSubmit={(e) => {
            e.preventDefault();
            setPage(1);
            setSearch(q);
          }}
        >
          <label className="sr-only" htmlFor="asset-search">
            Search assets
          </label>
          <input
            id="asset-search"
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search by name, title, keyword, or category"
          />
          <button type="submit" className="btn btn-secondary">
            Search
          </button>
        </form>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={includeArchived}
            onChange={(e) => {
              setPage(1);
              setIncludeArchived(e.target.checked);
            }}
          />
          Show archived
        </label>
      </div>

      {successMessage && (
        <div className="success-panel" role="status">
          <p>{successMessage}</p>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => setSuccessMessage(null)}
            aria-label="Dismiss success message"
          >
            Dismiss
          </button>
        </div>
      )}

      {deleteTarget && (
        <ConfirmDialog
          title="Delete asset permanently?"
          destructive
          busy={deleting}
          confirmLabel="Delete permanently"
          confirmDisabled={linkedCount === null}
          onConfirm={() => void confirmDelete()}
          onCancel={closeDelete}
        >
          <p>
            <strong>{deleteTarget.display_name}</strong> will be permanently
            deleted, along with its metadata and uploaded image.
          </p>
          {linkedCountError ? (
            <ErrorPanel
              message={linkedCountError}
              onRetry={() => void openDelete(deleteTarget)}
            />
          ) : linkedCount === null ? (
            <p className="hint" role="status">
              Checking linked submissions…
            </p>
          ) : (
            <p>
              {linkedCount === 0
                ? "No linked submission records are affected."
                : `${linkedCount} linked submission record${linkedCount === 1 ? "" : "s"} will also be permanently deleted.`}
            </p>
          )}
          {deleteError && <ErrorPanel message={deleteError} />}
          <p className="hint">
            This cannot be undone. To hide an item without deleting it, use
            Archive instead.
          </p>
        </ConfirmDialog>
      )}

      {form && (
        <form className="panel form-panel" onSubmit={submitForm}>
          <div className="panel__header">
            <h3 className="panel__title">
              {form.id === null ? "Add asset" : `Edit asset #${form.id}`}
            </h3>
          </div>
          <div className="panel__body">
            {formError && <ErrorPanel message={formError} />}
            <div className="form-grid">
              <div className="field">
                <label htmlFor="f-display-name">
                  Display name <span aria-hidden="true">*</span>
                </label>
                <input
                  id="f-display-name"
                  required
                  maxLength={200}
                  value={form.display_name}
                  onChange={(e) => setForm({ ...form, display_name: e.target.value })}
                />
              </div>
              <div className="field">
                <label htmlFor="f-title">Title</label>
                <input
                  id="f-title"
                  maxLength={300}
                  value={form.title}
                  onChange={(e) => setForm({ ...form, title: e.target.value })}
                />
              </div>
              <div className="field">
                <label htmlFor="f-category">Category</label>
                <input
                  id="f-category"
                  maxLength={100}
                  value={form.category}
                  onChange={(e) => setForm({ ...form, category: e.target.value })}
                />
              </div>
              <div className="field">
                <label htmlFor="f-media-type">Media type</label>
                <input
                  id="f-media-type"
                  maxLength={100}
                  value={form.media_type}
                  onChange={(e) => setForm({ ...form, media_type: e.target.value })}
                  placeholder="image"
                />
              </div>
              <div className="field field--full">
                <label htmlFor="f-keywords">Keywords (comma-separated)</label>
                <input
                  id="f-keywords"
                  value={form.keywords}
                  onChange={(e) => setForm({ ...form, keywords: e.target.value })}
                  placeholder="sunset, city, skyline"
                />
              </div>
              <div className="field field--full">
                <label htmlFor="f-file-reference">File reference</label>
                <input
                  id="f-file-reference"
                  maxLength={1024}
                  value={form.file_reference}
                  onChange={(e) => setForm({ ...form, file_reference: e.target.value })}
                  placeholder="D:\images\sunset.png"
                />
              </div>
              <div className="field field--full">
                <label htmlFor="f-description">Description</label>
                <textarea
                  id="f-description"
                  maxLength={4000}
                  rows={3}
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                />
              </div>
            </div>
            <div className="form-actions">
              <button type="submit" className="btn btn-primary" disabled={saving}>
                {saving ? "Saving…" : "Save"}
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setForm(null)}
                disabled={saving}
              >
                Cancel
              </button>
            </div>
          </div>
        </form>
      )}

      {listError && <ErrorPanel message={listError} onRetry={load} />}

      {loading && !list && <LoadingBlock label="Loading assets…" />}

      {list && list.items.length === 0 && !listError && (
        <div className="panel">
          <div className="panel__body">
            <EmptyState
              message={
                search || includeArchived
                  ? "No assets match the current filters."
                  : "No assets yet"
              }
              hint={
                search || includeArchived
                  ? "Try a different search term, or uncheck “Show archived”."
                  : "Use “Add asset” to create the first one."
              }
            />
          </div>
        </div>
      )}

      {list && list.items.length > 0 && (
        <div className="panel">
          <div className="panel__header">
            <h3 className="panel__title">Assets</h3>
            <span className="panel__meta">{list.total} total</span>
          </div>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th scope="col">ID</th>
                  <th scope="col">Name</th>
                  <th scope="col">Title</th>
                  <th scope="col">Keywords</th>
                  <th scope="col">Category</th>
                  <th scope="col">Origin</th>
                  <th scope="col">Status</th>
                  <th scope="col">Actions</th>
                </tr>
              </thead>
              <tbody>
                {list.items.map((asset) => (
                  <tr key={asset.id}>
                    <td className="cell-id">{asset.id}</td>
                    <td>{asset.display_name}</td>
                    <td className="cell-truncate" title={asset.title ?? undefined}>
                      {asset.title ?? <span className="muted">—</span>}
                    </td>
                    <td
                      className="cell-truncate"
                      title={asset.keywords.join(", ") || undefined}
                    >
                      {asset.keywords.join(", ") || <span className="muted">—</span>}
                    </td>
                    <td>{asset.category ?? <span className="muted">—</span>}</td>
                    <td className="muted">
                      {asset.metadata_origin.replace("_", " ")}
                    </td>
                    <td>
                      {asset.archived ? (
                        <span className="badge badge-archived">Archived</span>
                      ) : (
                        <span className="badge badge-active">Active</span>
                      )}
                    </td>
                    <td className="cell-actions">
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => startEdit(asset)}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        className="btn btn-ghost btn-sm"
                        onClick={() => toggleArchived(asset)}
                      >
                        {asset.archived ? "Unarchive" : "Archive"}
                      </button>
                      <button
                        type="button"
                        className="btn btn-ghost btn-sm"
                        onClick={() => void openDelete(asset)}
                        disabled={deleting}
                        aria-label={`Delete ${asset.display_name} permanently`}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination
            page={list.page}
            total={list.total}
            totalPages={totalPages}
            onPage={setPage}
          />
        </div>
      )}
    </div>
  );
}
