// Generate: the primary product workflow.
// Upload -> preview -> consent -> Cohere analysis -> editable draft -> save.

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api";
import {
  draftEquals,
  draftFromAsset,
  emptyDraft,
  MetadataDraft,
  MetadataEditor,
} from "../MetadataEditor";
import type { AiStatus, Asset } from "../types";
import { ErrorPanel, LoadingBlock, PageHeader } from "../ui";

const ACCEPTED_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp"];
const MAX_UPLOAD_BYTES = 10 * 1024 * 1024; // mirrors backend default

function fileError(file: File): string | null {
  const lower = file.name.toLowerCase();
  if (!ACCEPTED_EXTENSIONS.some((ext) => lower.endsWith(ext))) {
    return "Unsupported file type. Use JPG, JPEG, PNG, or WebP.";
  }
  if (file.size === 0) return "The selected file is empty.";
  if (file.size > MAX_UPLOAD_BYTES) {
    return "File is too large (limit 10 MB).";
  }
  return null;
}

type Phase = "empty" | "uploading" | "ready" | "analyzing" | "draft";

export function GenerateView({
  onSaved,
  openAssetId,
  onOpened,
}: {
  /** Called after a successful save so Library can refresh. */
  onSaved: () => void;
  /** Asset id to load (e.g. after picking an item in the Library). */
  openAssetId: number | null;
  /** Reports that openAssetId has been consumed. */
  onOpened: () => void;
}) {
  const [phase, setPhase] = useState<Phase>("empty");
  const [asset, setAsset] = useState<Asset | null>(null);
  const [draft, setDraft] = useState<MetadataDraft>(emptyDraft);
  const [savedDraft, setSavedDraft] = useState<MetadataDraft>(emptyDraft);
  const [draftOrigin, setDraftOrigin] = useState<"ai" | "manual" | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved">("idle");
  const [aiStatus, setAiStatus] = useState<AiStatus | null>(null);
  // Explicit consent (ADR-010): the image is not sent to Cohere until the
  // user ticks this box. Same gate as the Vision Insights screen.
  const [consentGiven, setConsentGiven] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api
      .aiStatus()
      .then(setAiStatus)
      .catch(() => setAiStatus(null));
  }, []);

  const dirty = !draftEquals(draft, savedDraft);

  const reset = useCallback(() => {
    setPhase("empty");
    setAsset(null);
    setDraft(emptyDraft());
    setSavedDraft(emptyDraft());
    setDraftOrigin(null);
    setUploadError(null);
    setAnalysisError(null);
    setSaveError(null);
    setSaveState("idle");
    setConsentGiven(false);
  }, []);

  const handleUpload = useCallback(
    async (file: File) => {
      const localError = fileError(file);
      if (localError) {
        setUploadError(localError);
        return;
      }
      setUploadError(null);
      setAnalysisError(null);
      setSaveError(null);
      setSaveState("idle");
      // A new image needs its own consent decision.
      setConsentGiven(false);
      setPhase("uploading");
      try {
        const result = await api.uploadImage(file);
        setAsset(result.asset);
        setDraft(draftFromAsset(result.asset));
        setSavedDraft(draftFromAsset(result.asset));
        setDraftOrigin(null);
        setPhase("ready");
      } catch (e: unknown) {
        setPhase("empty");
        setUploadError(
          e instanceof ApiError ? e.message : "Upload failed. Try again.",
        );
      }
    },
    [],
  );

  // Load an asset chosen from the Library (reopen saved image + metadata).
  useEffect(() => {
    if (openAssetId === null) return;
    let cancelled = false;
    setUploadError(null);
    setAnalysisError(null);
    setSaveError(null);
    setSaveState("idle");
    // A different image needs its own consent decision.
    setConsentGiven(false);
    setPhase("uploading");
    api
      .getAsset(openAssetId)
      .then((loaded) => {
        if (cancelled) return;
        if (!loaded.image_url) {
          setUploadError("That asset has no uploaded image.");
          setPhase("empty");
          return;
        }
        setAsset(loaded);
        const fromAsset = draftFromAsset(loaded);
        setDraft(fromAsset);
        setSavedDraft(fromAsset);
        setDraftOrigin(null);
        setPhase("ready");
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setPhase("empty");
        setUploadError(
          e instanceof ApiError ? e.message : "Could not load the asset.",
        );
      })
      .finally(() => {
        if (!cancelled) onOpened();
      });
    return () => {
      cancelled = true;
    };
  }, [openAssetId, onOpened]);

  const handleAnalyze = useCallback(async () => {
    if (!asset) return;
    // Guard: the image must never leave the machine without explicit consent.
    if (!consentGiven) return;
    setAnalysisError(null);
    setSaveError(null);
    setSaveState("idle");
    setPhase("analyzing");
    try {
      const result = await api.analyzeImage(asset.id, consentGiven);
      // Draft lives only in component state until the user saves.
      setDraft({
        title: result.title,
        description: result.description ?? "",
        category: result.category ?? "",
        keywords: [...result.keywords],
      });
      setDraftOrigin("ai");
      setPhase("draft");
    } catch (e: unknown) {
      setPhase(asset ? (draftOrigin ? "draft" : "ready") : "empty");
      setAnalysisError(
        e instanceof ApiError
          ? e.message
          : "Analysis failed. Check your connection and try again.",
      );
    }
  }, [asset, draftOrigin, consentGiven]);

  const handleSave = useCallback(async () => {
    if (!asset) return;
    setSaveError(null);
    setSaveState("saving");
    try {
      await api.updateAsset(asset.id, {
        title: draft.title.trim() || null,
        description: draft.description.trim() || null,
        category: draft.category.trim() || null,
        keywords: draft.keywords,
        metadata_origin: draftOrigin === "ai" ? "ai_suggested" : "manual",
      });
      setSavedDraft(draft);
      setSaveState("saved");
      onSaved();
    } catch (e: unknown) {
      setSaveState("idle");
      setSaveError(
        e instanceof ApiError ? e.message : "Save failed. Try again.",
      );
    }
  }, [asset, draft, draftOrigin, onSaved]);

  const onPickFiles = (files: FileList | null) => {
    const file = files?.[0];
    if (file) void handleUpload(file);
  };

  const showEditor = asset && (phase === "ready" || phase === "draft" || (phase === "analyzing" && draftOrigin));

  return (
    <div>
      <PageHeader
        title="Generate metadata"
        subtitle="Upload an image, analyze it with AI, review the draft, and save when it looks right."
        actions={
          asset ? (
            <button type="button" className="btn btn-secondary" onClick={reset}>
              Start over
            </button>
          ) : undefined
        }
      />

      {uploadError && (
        <ErrorPanel message={uploadError} onRetry={reset} />
      )}

      {/* ---- Step 1: upload / dropzone ---- */}
      {!asset && (
        <div
          className={`dropzone${dragActive ? " dropzone--active" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragActive(true);
          }}
          onDragLeave={() => setDragActive(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragActive(false);
            onPickFiles(e.dataTransfer.files);
          }}
        >
          <input
            ref={inputRef}
            id="generate-file-input"
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="sr-only"
            onChange={(e) => {
              onPickFiles(e.target.files);
              e.target.value = ""; // allow re-picking the same file
            }}
          />
          {phase === "uploading" ? (
            <LoadingBlock label="Uploading image…" />
          ) : (
            <>
              <p className="dropzone__title">
                Drop an image here, or{" "}
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  onClick={() => inputRef.current?.click()}
                >
                  choose a file
                </button>
              </p>
              <p className="hint">
                JPG, JPEG, PNG, or WebP · up to 10 MB · stored only on this
                machine
              </p>
            </>
          )}
        </div>
      )}

      {/* ---- Step 2: preview + consent + generate ---- */}
      {asset && (
        <div className="generate-grid">
          <section className="panel preview-panel" aria-label="Image preview">
            <div className="panel__header">
              <h3 className="panel__title">Preview</h3>
              <span className="panel__meta">{asset.display_name}</span>
            </div>
            <div className="panel__body">
              <img
                className="preview-img"
                src={asset.image_url ?? ""}
                alt={`Preview of ${asset.display_name}`}
              />
              <p className="hint">
                {asset.width && asset.height
                  ? `${asset.width} × ${asset.height} px`
                  : null}
                {asset.file_size
                  ? ` · ${(asset.file_size / 1024).toFixed(0)} KB`
                  : null}
              </p>
            </div>
          </section>

          <section className="panel" aria-label="Metadata draft editor">
            <div className="panel__header">
              <h3 className="panel__title">Metadata</h3>
              <span className="panel__meta">
                {saveState === "saved" && !dirty
                  ? "Saved ✓"
                  : dirty
                    ? draftOrigin === "ai"
                      ? "Unsaved AI draft"
                      : "Unsaved changes"
                    : draftOrigin === "ai"
                      ? "AI draft saved"
                      : draftEquals(draft, emptyDraft())
                        ? "No metadata yet"
                        : "Saved metadata"}
              </span>
            </div>
            <div className="panel__body">
              {/* Consent notice: shown before any image leaves this machine. */}
              <div className="consent" role="note">
                <strong>Before you generate:</strong> analysis sends this
                image to Cohere for AI analysis. Image content is processed
                by Cohere under its AI terms — it is not sent anywhere
                else.
                Nothing is saved until you press Save.
              </div>

              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={consentGiven}
                  onChange={(event) => setConsentGiven(event.target.checked)}
                />
                I agree to send this image to Cohere for AI analysis.
              </label>

              {analysisError && (
                <ErrorPanel
                  message={analysisError}
                  onRetry={() => void handleAnalyze()}
                />
              )}

              <div className="generate-actions">
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => void handleAnalyze()}
                  disabled={!consentGiven || phase === "analyzing"}
                >
                  {phase === "analyzing"
                    ? "Analyzing…"
                    : phase === "draft"
                      ? "Re-generate"
                      : "Generate metadata"}
                </button>
                {phase === "analyzing" && (
                  <span className="muted" role="status">
                    Sending image to {aiStatus?.model ?? "Cohere"}…
                  </span>
                )}
                {!aiStatus?.ai_configured && (
                  <span className="hint" role="status">
                    {aiStatus?.message ??
                      "AI status unknown — check the backend."}
                  </span>
                )}
              </div>

              {phase === "analyzing" && (
                <LoadingBlock label="Analyzing image with Cohere…" />
              )}

              {showEditor && (
                <>
                  <MetadataEditor draft={draft} onChange={setDraft} />
                  {saveError && <ErrorPanel message={saveError} />}
                  <div className="form-actions">
                    <button
                      type="button"
                      className="btn btn-primary"
                      onClick={() => void handleSave()}
                      disabled={!dirty || saveState === "saving"}
                    >
                      {saveState === "saving"
                        ? "Saving…"
                        : saveState === "saved" && !dirty
                          ? "Saved ✓"
                          : "Save metadata"}
                    </button>
                    {!dirty && saveState === "saved" && (
                      <span className="hint" role="status">
                        Saved to your library.
                      </span>
                    )}
                    {dirty && saveState !== "saving" && (
                      <span className="hint">Unsaved changes</span>
                    )}
                  </div>
                </>
              )}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

