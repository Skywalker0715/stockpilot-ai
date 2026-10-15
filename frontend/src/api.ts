// Thin typed client for the StockPilot API. All requests go through here.

import type {
  AiStatus,
  Asset,
  AssetInput,
  AssetList,
  InsightsSummary,
  Submission,
  SubmissionInput,
  SubmissionList,
  SubmissionStatus,
} from "./types";

// In dev, Vite proxies /api to the backend, so relative paths work
// without CORS round-trips. Override with VITE_API_BASE for other setups.
const API_BASE: string = import.meta.env.VITE_API_BASE ?? "";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    throw new ApiError(
      0,
      "Cannot reach the backend. Is it running on port 8000?",
    );
  }
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") {
        detail = body.detail;
      } else if (Array.isArray(body.detail)) {
        // FastAPI validation errors: [{loc, msg}, ...]
        detail = body.detail
          .map((d) => (typeof d === "object" && d !== null && "msg" in d ? String((d as { msg: unknown }).msg) : JSON.stringify(d)))
          .join("; ");
      }
    } catch {
      // keep default detail
    }
    throw new ApiError(response.status, detail);
  }
  return (await response.json()) as T;
}

export const api = {
  aiStatus: () => request<AiStatus>("/api/v1/ai/status"),
  insights: () => request<InsightsSummary>("/api/v1/insights/summary"),

  listAssets: (params: { q?: string; category?: string; archived?: boolean; page?: number; page_size?: number }) => {
    const search = new URLSearchParams();
    if (params.q) search.set("q", params.q);
    if (params.category) search.set("category", params.category);
    if (params.archived !== undefined) search.set("archived", String(params.archived));
    if (params.page) search.set("page", String(params.page));
    if (params.page_size) search.set("page_size", String(params.page_size));
    const qs = search.toString();
    return request<AssetList>(`/api/v1/assets${qs ? `?${qs}` : ""}`);
  },
  getAsset: (id: number) => request<Asset>(`/api/v1/assets/${id}`),
  createAsset: (input: AssetInput) =>
    request<Asset>("/api/v1/assets", { method: "POST", body: JSON.stringify(input) }),
  updateAsset: (id: number, input: Partial<AssetInput>) =>
    request<Asset>(`/api/v1/assets/${id}`, { method: "PATCH", body: JSON.stringify(input) }),

  listSubmissions: (params: { asset_id?: number; status?: SubmissionStatus; page?: number; page_size?: number }) => {
    const search = new URLSearchParams();
    if (params.asset_id) search.set("asset_id", String(params.asset_id));
    if (params.status) search.set("status", params.status);
    if (params.page) search.set("page", String(params.page));
    if (params.page_size) search.set("page_size", String(params.page_size));
    const qs = search.toString();
    return request<SubmissionList>(`/api/v1/submissions${qs ? `?${qs}` : ""}`);
  },
  createSubmission: (input: SubmissionInput) =>
    request<Submission>("/api/v1/submissions", { method: "POST", body: JSON.stringify(input) }),
  updateSubmission: (id: number, input: Partial<SubmissionInput>) =>
    request<Submission>(`/api/v1/submissions/${id}`, { method: "PATCH", body: JSON.stringify(input) }),
};
