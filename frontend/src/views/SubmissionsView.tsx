import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api";
import {
  SUBMISSION_STATUSES,
  type Asset,
  type Submission,
  type SubmissionList,
  type SubmissionStatus,
} from "../types";
import {
  ConfirmDialog,
  EmptyState,
  ErrorPanel,
  LoadingBlock,
  PageHeader,
  Pagination,
  StatusBadge,
} from "../ui";

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
  // Delete flow for a single submission record (confirmation dialog).
  const [deleteTarget, setDeleteTarget] = useState<Submission | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  // Asset dropdown loading (errors surfaced with a retry).
  const [assetsError, setAssetsError] = useState<string | null>(null);
  const assetsLoadingRef = useRef(false);

  // The create form needs the asset list for its dropdown. Re-runs on demand
  // (form open) so assets created/archived in another view are picked up; the
  // ref guard prevents duplicate concurrent requests. Archived assets are
  // included so existing submissions still resolve a proper asset name.
  const loadAssets = useCallback(async () => {
    if (assetsLoadingRef.current) return;
    assetsLoadingRef.current = true;
    try {
      const [active, archived] = await Promise.all([
        api.listAssets({ archived: false, page_size: 100 }),
        api.listAssets({ archived: true, page_size: 100 }),
      ]);
      setAssets([...active.items, ...archived.items]);
      setAssetsError(null);
    } catch (e: unknown) {
      setAssetsError(
        e instanceof ApiError ? e.message : "Failed to load assets",
      );
    } finally {
      assetsLoadingRef.current = false;
    }
  }, []);

  useEffect(() => {
    void loadAssets();
  }, [loadAssets]);

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
    setNotice(null);
    // Refresh assets: another view/tab may have added or archived some.
    void loadAssets();
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

  const closeDelete = () => {
    if (!deleting) setDeleteTarget(null);
  };

  const confirmDelete = async () => {
    // Guard against repeated submissions while a delete is in flight.
    if (!deleteTarget || deleting) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      const result = await api.deleteSubmission(deleteTarget.id);
      setDeleteTarget(null);
      setNotice(
        `Submission #${result.id} (${result.platform}, ${result.status}) deleted. The asset, its image and metadata, and other submissions are unchanged.`,
      );
      load();
    } catch (e: unknown) {
      if (e instanceof ApiError && e.status === 404) {
        setDeleteTarget(null);
        setNotice(
          "That submission no longer exists; the list has been refreshed.",
        );
        load();
      } else {
        setDeleteError(
          e instanceof ApiError ? e.message : "Failed to delete submission",
        );
      }
    } finally {
      setDeleting(false);
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
      <PageHeader
        title="Submissions"
        subtitle="Track where each asset has been submitted and how it was received."
        actions={
          <button type="button" className="btn btn-primary" onClick={startCreate}>
            Record submission
          </button>
        }
      />

      <div className="toolbar">
        <div className="toolbar__field">
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
        </div>
      </div>

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

      {deleteTarget && (
        <ConfirmDialog
          title="Delete submission record?"
          destructive
          busy={deleting}
          confirmLabel="Delete submission"
          onConfirm={() => void confirmDelete()}
          onCancel={closeDelete}
        >
          <p>
            Submission <strong>#{deleteTarget.id}</strong> —{" "}
            <strong>{assetLabel(deleteTarget.asset_id)}</strong>,{" "}
            {deleteTarget.platform} ({deleteTarget.status}).
          </p>
          <p>
            Only this submission record is deleted. The asset, its image and
            metadata, and any other submissions are not affected.
          </p>
          <p className="hint">This cannot be undone.</p>
          {deleteError && <ErrorPanel message={deleteError} />}
        </ConfirmDialog>
      )}

      {form && (
        <form className="panel form-panel" onSubmit={submitForm}>
          <div className="panel__header">
            <h3 className="panel__title">
              {form.id === null ? "Record submission" : `Edit submission #${form.id}`}
            </h3>
          </div>
          <div className="panel__body">
            {formError && <ErrorPanel message={formError} />}
            <div className="form-grid">
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
                      {a.archived ? " (archived)" : ""}
                    </option>
                  ))}
                </select>
                {assetsError ? (
                  <p className="hint" role="alert">
                    {assetsError}{" "}
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() => void loadAssets()}
                    >
                      Retry
                    </button>
                  </p>
                ) : assets.length === 0 ? (
                  <p className="hint">No assets available. Create an asset first.</p>
                ) : null}
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
              <div className="field field--full">
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
              <div className="field field--full">
                <label htmlFor="s-rejection-note">Rejection note</label>
                <textarea
                  id="s-rejection-note"
                  maxLength={4000}
                  rows={3}
                  value={form.rejection_note}
                  onChange={(e) => setForm({ ...form, rejection_note: e.target.value })}
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

      {loading && !list && <LoadingBlock label="Loading submissions…" />}

      {list && list.items.length === 0 && !listError && (
        <div className="panel">
          <div className="panel__body">
            <EmptyState
              message={
                statusFilter
                  ? `No submissions with status “${statusFilter}”.`
                  : "No submissions recorded yet"
              }
              hint={
                statusFilter
                  ? "Choose a different status in the filter above."
                  : "Use “Record submission” to add one."
              }
            />
          </div>
        </div>
      )}

      {list && list.items.length > 0 && (
        <div className="panel">
          <div className="panel__header">
            <h3 className="panel__title">Submissions</h3>
            <span className="panel__meta">{list.total} total</span>
          </div>
          <div className="table-scroll">
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
                    <td className="cell-id">{s.id}</td>
                    <td className="cell-truncate" title={assetLabel(s.asset_id)}>
                      {assetLabel(s.asset_id)}
                    </td>
                    <td>{s.platform}</td>
                    <td>
                      <StatusBadge status={s.status} />
                    </td>
                    <td className="cell-num">
                      {s.submitted_at ?? <span className="muted">—</span>}
                    </td>
                    <td className="cell-num">
                      {s.reviewed_at ?? <span className="muted">—</span>}
                    </td>
                    <td>
                      {s.rejection_category ?? <span className="muted">—</span>}
                    </td>
                    <td
                      className="cell-truncate"
                      title={s.rejection_note ?? undefined}
                    >
                      {s.rejection_note ?? <span className="muted">—</span>}
                    </td>
                    <td className="cell-actions">
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => startEdit(s)}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        className="btn btn-ghost btn-sm"
                        onClick={() => {
                          setDeleteTarget(s);
                          setDeleteError(null);
                          setNotice(null);
                        }}
                        disabled={deleting}
                        aria-label={`Delete submission ${s.id} for ${s.platform}`}
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
