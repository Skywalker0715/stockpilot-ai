import { FormEvent, useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { Asset, AssetList } from "../types";

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

export function AssetsView() {
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
  };

  const startEdit = (asset: Asset) => {
    setForm(toForm(asset));
    setFormError(null);
  };

  const toggleArchived = async (asset: Asset) => {
    try {
      await api.updateAsset(asset.id, { archived: !asset.archived });
      load();
    } catch (e: unknown) {
      setListError(e instanceof ApiError ? e.message : "Failed to update asset");
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
      <div className="toolbar">
        <form
          role="search"
          onSubmit={(e) => {
            e.preventDefault();
            setPage(1);
            setSearch(q);
          }}
        >
          <label htmlFor="asset-search">Search</label>
          <input
            id="asset-search"
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="name, title, keyword, category"
          />
          <button type="submit">Search</button>
        </form>
        <label>
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
        <button type="button" className="primary" onClick={startCreate}>
          Add asset
        </button>
      </div>

      {form && (
        <form className="card form" onSubmit={submitForm}>
          <h3>{form.id === null ? "Add asset" : `Edit asset #${form.id}`}</h3>
          {formError && (
            <p className="error" role="alert">
              {formError}
            </p>
          )}
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
            <label htmlFor="f-description">Description</label>
            <textarea
              id="f-description"
              maxLength={4000}
              rows={3}
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </div>
          <div className="field">
            <label htmlFor="f-keywords">Keywords (comma-separated)</label>
            <input
              id="f-keywords"
              value={form.keywords}
              onChange={(e) => setForm({ ...form, keywords: e.target.value })}
              placeholder="sunset, city, skyline"
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
            <label htmlFor="f-file-reference">File reference</label>
            <input
              id="f-file-reference"
              maxLength={1024}
              value={form.file_reference}
              onChange={(e) => setForm({ ...form, file_reference: e.target.value })}
              placeholder="D:\images\sunset.png"
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
          <div className="actions">
            <button type="submit" className="primary" disabled={saving}>
              {saving ? "Saving…" : "Save"}
            </button>
            <button type="button" onClick={() => setForm(null)} disabled={saving}>
              Cancel
            </button>
          </div>
        </form>
      )}

      {listError && (
        <div className="error" role="alert">
          <p>{listError}</p>
          <button type="button" onClick={load}>
            Retry
          </button>
        </div>
      )}

      {loading && !list && <p role="status">Loading assets…</p>}

      {list && list.items.length === 0 && !listError && (
        <p className="empty">
          {search || includeArchived
            ? "No assets match the current filters."
            : "No assets yet. Use “Add asset” to create the first one."}
        </p>
      )}

      {list && list.items.length > 0 && (
        <>
          <table>
            <thead>
              <tr>
                <th scope="col">ID</th>
                <th scope="col">Name</th>
                <th scope="col">Title</th>
                <th scope="col">Keywords</th>
                <th scope="col">Category</th>
                <th scope="col">Origin</th>
                <th scope="col">Archived</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {list.items.map((asset) => (
                <tr key={asset.id}>
                  <td>{asset.id}</td>
                  <td>{asset.display_name}</td>
                  <td>{asset.title ?? "—"}</td>
                  <td>{asset.keywords.join(", ") || "—"}</td>
                  <td>{asset.category ?? "—"}</td>
                  <td>{asset.metadata_origin.replace("_", " ")}</td>
                  <td>{asset.archived ? "Yes" : "No"}</td>
                  <td>
                    <button type="button" onClick={() => startEdit(asset)}>
                      Edit
                    </button>{" "}
                    <button type="button" onClick={() => toggleArchived(asset)}>
                      {asset.archived ? "Unarchive" : "Archive"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="pagination">
            <button
              type="button"
              disabled={page <= 1}
              onClick={() => setPage(page - 1)}
            >
              Previous
            </button>
            <span>
              Page {list.page} of {totalPages} ({list.total} total)
            </span>
            <button
              type="button"
              disabled={page >= totalPages}
              onClick={() => setPage(page + 1)}
            >
              Next
            </button>
          </div>
        </>
      )}
    </div>
  );
}
