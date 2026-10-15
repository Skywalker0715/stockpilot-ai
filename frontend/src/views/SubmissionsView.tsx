import { FormEvent, useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../api";
import {
  SUBMISSION_STATUSES,
  type Asset,
  type Submission,
  type SubmissionList,
  type SubmissionStatus,
} from "../types";

interface FormState {
  id: number | null; // null = creating
  asset_id: string; // select values are strings in the form
  platform: string;
  status: SubmissionStatus;
  submitted_at: string;
  rejection_note: string;
  rejection_category: string;
}

const EMPTY_FORM: FormState = {
  id: null,
  asset_id: "",
  platform: "",
  status: "submitted",
  submitted_at: "",
  rejection_note: "",
  rejection_category: "",
};

export function SubmissionsView() {
  const [list, setList] = useState<SubmissionList | null>(null);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [statusFilter, setStatusFilter] = useState<SubmissionStatus | "">("");
  const [page, setPage] = useState(1);
  const [form, setForm] = useState<FormState | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [listError, setListError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // The create form needs the asset list for its dropdown.
  useEffect(() => {
    api
      .listAssets({ page_size: 200 })
      .then((l) => setAssets(l.items))
      .catch(() => setAssets([]));
  }, []);

  const load = useCallback(() => {
    setLoading(true);
    api
      .listSubmissions({
        status: statusFilter || undefined,
        page,
        page_size: 20,
      })
      .then((l) => {
        setList(l);
        setListError(null);
      })
      .catch((e: unknown) =>
        setListError(e instanceof ApiError ? e.message : "Failed to load submissions"),
      )
      .finally(() => setLoading(false));
  }, [statusFilter, page]);

  useEffect(load, [load]);

  const startCreate = () => {
    setForm({ ...EMPTY_FORM });
    setFormError(null);
  };

  const startEdit = (s: Submission) => {
    setForm({
      id: s.id,
      asset_id: String(s.asset_id),
      platform: s.platform,
      status: s.status,
      submitted_at: s.submitted_at ?? "",
      rejection_note: s.rejection_note ?? "",
      rejection_category: s.rejection_category ?? "",
    });
    setFormError(null);
  };

  const submitForm = async (event: FormEvent) => {
    event.preventDefault();
    if (!form) return;
    setSaving(true);
    setFormError(null);
    try {
      if (form.id === null) {
        await api.createSubmission({
          asset_id: Number(form.asset_id),
          platform: form.platform,
          status: form.status,
          submitted_at: form.submitted_at || null,
          rejection_note: form.rejection_note || null,
          rejection_category: form.rejection_category || null,
        });
      } else {
        // SubmissionUpdate rejects explicit null for platform/status,
        // so send the current form values (they are required fields).
        await api.updateSubmission(form.id, {
          platform: form.platform,
          status: form.status,
          submitted_at: form.submitted_at || null,
          rejection_note: form.rejection_note || null,
          rejection_category: form.rejection_category || null,
        });
      }
      setForm(null);
      load();
    } catch (e: unknown) {
      setFormError(e instanceof ApiError ? e.message : "Failed to save submission");
    } finally {
      setSaving(false);
    }
  };

  const pageSize = list?.page_size ?? 20;
  const totalPages = list ? Math.max(1, Math.ceil(list.total / pageSize)) : 1;

  const assetLabel = (id: number) => {
    const found = assets.find((a) => a.id === id);
    return found ? `#${id} ${found.display_name}` : `#${id}`;
  };

  return (
    <div>
      <div className="toolbar">
        <label htmlFor="status-filter">Status</label>
        <select
          id="status-filter"
          value={statusFilter}
          onChange={(e) => {
            setPage(1);
            setStatusFilter(e.target.value as SubmissionStatus | "");
          }}
        >
          <option value="">All</option>
          {SUBMISSION_STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <button type="button" className="primary" onClick={startCreate}>
          Record submission
        </button>
      </div>

      {form && (
        <form className="card form" onSubmit={submitForm}>
          <h3>{form.id === null ? "Record submission" : `Edit submission #${form.id}`}</h3>
          {formError && (
            <p className="error" role="alert">
              {formError}
            </p>
          )}
          <div className="field">
            <label htmlFor="s-asset">Asset</label>
            <select
              id="s-asset"
              required
              disabled={form.id !== null}
              value={form.asset_id}
              onChange={(e) => setForm({ ...form, asset_id: e.target.value })}
            >
              <option value="">Choose an asset…</option>
              {assets.map((a) => (
                <option key={a.id} value={a.id}>
                  #{a.id} {a.display_name}
                </option>
              ))}
            </select>
            {assets.length === 0 && (
              <p className="hint">No assets available. Create an asset first.</p>
            )}
          </div>
          <div className="field">
            <label htmlFor="s-platform">
              Platform <span aria-hidden="true">*</span>
            </label>
            <input
              id="s-platform"
              required
              maxLength={100}
              value={form.platform}
              onChange={(e) => setForm({ ...form, platform: e.target.value })}
              placeholder="Adobe Stock"
            />
          </div>
          <div className="field">
            <label htmlFor="s-status">Status</label>
            <select
              id="s-status"
              value={form.status}
              onChange={(e) =>
                setForm({ ...form, status: e.target.value as SubmissionStatus })
              }
            >
              {SUBMISSION_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="s-submitted-at">Submitted date</label>
            <input
              id="s-submitted-at"
              type="date"
              value={form.submitted_at}
              onChange={(e) => setForm({ ...form, submitted_at: e.target.value })}
            />
          </div>
          <div className="field">
            <label htmlFor="s-rejection-category">Rejection category</label>
            <input
              id="s-rejection-category"
              maxLength={100}
              value={form.rejection_category}
              onChange={(e) =>
                setForm({ ...form, rejection_category: e.target.value })
              }
              placeholder="duplicate, quality, technical…"
            />
          </div>
          <div className="field">
            <label htmlFor="s-rejection-note">Rejection note</label>
            <textarea
              id="s-rejection-note"
              maxLength={4000}
              rows={3}
              value={form.rejection_note}
              onChange={(e) => setForm({ ...form, rejection_note: e.target.value })}
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

      {loading && !list && <p role="status">Loading submissions…</p>}

      {list && list.items.length === 0 && !listError && (
        <p className="empty">
          {statusFilter
            ? `No submissions with status “${statusFilter}”.`
            : "No submissions recorded yet. Use “Record submission” to add one."}
        </p>
      )}

      {list && list.items.length > 0 && (
        <>
          <table>
            <thead>
              <tr>
                <th scope="col">ID</th>
                <th scope="col">Asset</th>
                <th scope="col">Platform</th>
                <th scope="col">Status</th>
                <th scope="col">Submitted</th>
                <th scope="col">Reviewed</th>
                <th scope="col">Rejection category</th>
                <th scope="col">Rejection note</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {list.items.map((s) => (
                <tr key={s.id}>
                  <td>{s.id}</td>
                  <td>{assetLabel(s.asset_id)}</td>
                  <td>{s.platform}</td>
                  <td>{s.status}</td>
                  <td>{s.submitted_at ?? "—"}</td>
                  <td>{s.reviewed_at ?? "—"}</td>
                  <td>{s.rejection_category ?? "—"}</td>
                  <td>{s.rejection_note ?? "—"}</td>
                  <td>
                    <button type="button" onClick={() => startEdit(s)}>
                      Edit
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
