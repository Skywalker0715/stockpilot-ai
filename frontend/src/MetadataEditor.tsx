// Editable metadata form shared by the Generate and Library views:
// title, description, category, ordered keyword chips, and copy actions.
// Business rules (50-keyword cap, de-duplication, order) live here so both
// views behave identically; persistence stays with the caller.

import { FormEvent, useEffect, useRef, useState } from "react";

export interface MetadataDraft {
  title: string;
  description: string;
  category: string;
  keywords: string[];
}

export const KEYWORD_LIMIT = 50;

export function emptyDraft(): MetadataDraft {
  return { title: "", description: "", category: "", keywords: [] };
}

export function draftFromAsset(a: {
  title: string | null;
  description: string | null;
  category: string | null;
  keywords: string[];
}): MetadataDraft {
  return {
    title: a.title ?? "",
    description: a.description ?? "",
    category: a.category ?? "",
    keywords: [...a.keywords],
  };
}

export function draftEquals(a: MetadataDraft, b: MetadataDraft): boolean {
  return (
    a.title === b.title &&
    a.description === b.description &&
    a.category === b.category &&
    a.keywords.length === b.keywords.length &&
    a.keywords.every((k, i) => k === b.keywords[i])
  );
}

function CopyButton({
  label,
  text,
  disabled,
}: {
  label: string;
  text: string;
  disabled: boolean;
}) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard unavailable: stay honest — no fake "Copied" state.
      setCopied(false);
    }
  };

  return (
    <button
      type="button"
      className="btn btn-secondary btn-sm"
      onClick={copy}
      disabled={disabled || !text}
      aria-label={copied ? `${label} copied` : `Copy ${label}`}
    >
      {copied ? "Copied ✓" : `Copy ${label}`}
    </button>
  );
}

export function MetadataEditor({
  draft,
  onChange,
}: {
  draft: MetadataDraft;
  onChange: (next: MetadataDraft) => void;
}) {
  const [newKeyword, setNewKeyword] = useState("");
  const [keywordError, setKeywordError] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState("");

  const set = (patch: Partial<MetadataDraft>) => onChange({ ...draft, ...patch });

  const addKeyword = (event: FormEvent) => {
    event.preventDefault();
    const word = newKeyword.trim();
    setKeywordError(null);
    if (!word) return;
    if (word.length > 100) {
      setKeywordError("Keyword must be 100 characters or fewer.");
      return;
    }
    if (draft.keywords.some((k) => k.toLowerCase() === word.toLowerCase())) {
      setKeywordError(`“${word}” is already in the list.`);
      return;
    }
    if (draft.keywords.length >= KEYWORD_LIMIT) {
      setKeywordError(`Limit reached: maximum ${KEYWORD_LIMIT} keywords.`);
      return;
    }
    set({ keywords: [...draft.keywords, word] });
    setNewKeyword("");
    setAnnouncement(
      `Added keyword ${word}. ${draft.keywords.length + 1} total.`,
    );
  };

  const removeKeyword = (index: number) => {
    const removed = draft.keywords[index];
    set({ keywords: draft.keywords.filter((_, i) => i !== index) });
    setAnnouncement(`Removed keyword ${removed}.`);
  };

  const moveKeyword = (index: number, delta: -1 | 1) => {
    const target = index + delta;
    if (target < 0 || target >= draft.keywords.length) return;
    const next = [...draft.keywords];
    const [word] = next.splice(index, 1);
    next.splice(target, 0, word);
    set({ keywords: next });
    setAnnouncement(
      `Moved ${word} to position ${target + 1} of ${next.length}.`,
    );
  };

  const allText = [
    draft.title && `Title: ${draft.title}`,
    draft.description && `Description: ${draft.description}`,
    draft.category && `Category: ${draft.category}`,
    draft.keywords.length > 0 && `Keywords: ${draft.keywords.join(", ")}`,
  ]
    .filter(Boolean)
    .join("\n");

  return (
    <div className="editor">
      <div className="form-grid">
        <div className="field field--full">
          <label htmlFor="editor-title">Title</label>
          <input
            id="editor-title"
            maxLength={300}
            value={draft.title}
            onChange={(e) => set({ title: e.target.value })}
            placeholder="Specific, searchable stock title"
          />
        </div>
        <div className="field">
          <label htmlFor="editor-category">Category</label>
          <input
            id="editor-category"
            maxLength={100}
            value={draft.category}
            onChange={(e) => set({ category: e.target.value })}
            placeholder="e.g. Nature"
          />
        </div>
        <div className="field field--full">
          <label htmlFor="editor-description">Description</label>
          <textarea
            id="editor-description"
            maxLength={4000}
            rows={3}
            value={draft.description}
            onChange={(e) => set({ description: e.target.value })}
            placeholder="One or two factual sentences"
          />
        </div>
      </div>

      <div className="keywords">
        <div className="keywords__head">
          <label htmlFor="editor-keyword-input">Keywords</label>
          <span
            className={`keywords__count${
              draft.keywords.length >= KEYWORD_LIMIT
                ? " keywords__count--full"
                : ""
            }`}
          >
            {draft.keywords.length} / {KEYWORD_LIMIT}
          </span>
        </div>

        <form className="keywords__add" onSubmit={addKeyword}>
          <input
            id="editor-keyword-input"
            value={newKeyword}
            maxLength={100}
            onChange={(e) => setNewKeyword(e.target.value)}
            placeholder="Add a keyword and press Enter"
            aria-describedby="editor-keyword-help"
          />
          <button
            type="submit"
            className="btn btn-secondary btn-sm"
            disabled={draft.keywords.length >= KEYWORD_LIMIT}
          >
            Add
          </button>
        </form>
        {keywordError && (
          <p className="keywords__error" role="alert">
            {keywordError}
          </p>
        )}
        <p id="editor-keyword-help" className="hint">
          Keywords are ordered by relevance (most important first). Use the
          arrow buttons to reorder — no dragging required.
        </p>

        {draft.keywords.length > 0 && (
          <ul className="keywords__list" aria-label="Keyword list">
            {draft.keywords.map((word, index) => (
              <li key={`${word}-${index}`} className="chip">
                <span className="chip__index" aria-hidden="true">
                  {index + 1}
                </span>
                <span className="chip__text">{word}</span>
                <button
                  type="button"
                  className="chip__btn"
                  onClick={() => moveKeyword(index, -1)}
                  disabled={index === 0}
                  aria-label={`Move ${word} earlier`}
                  title="Move earlier"
                >
                  ↑
                </button>
                <button
                  type="button"
                  className="chip__btn"
                  onClick={() => moveKeyword(index, 1)}
                  disabled={index === draft.keywords.length - 1}
                  aria-label={`Move ${word} later`}
                  title="Move later"
                >
                  ↓
                </button>
                <button
                  type="button"
                  className="chip__btn chip__btn--remove"
                  onClick={() => removeKeyword(index)}
                  aria-label={`Remove ${word}`}
                  title="Remove"
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        )}
        <p className="sr-only" role="status" aria-live="polite">
          {announcement}
        </p>
      </div>

      <div className="copy-row">
        <CopyButton label="Title" text={draft.title} disabled={!draft.title} />
        <CopyButton
          label="Description"
          text={draft.description}
          disabled={!draft.description}
        />
        <CopyButton
          label="Keywords"
          text={draft.keywords.join(", ")}
          disabled={draft.keywords.length === 0}
        />
        <CopyButton
          label="All"
          text={allText}
          disabled={!allText}
        />
      </div>
    </div>
  );
}

