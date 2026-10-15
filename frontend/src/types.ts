// TypeScript types mirroring the FastAPI Pydantic models.

export interface Asset {
  id: number;
  display_name: string;
  file_reference: string | null;
  media_type: string | null;
  title: string | null;
  description: string | null;
  keywords: string[];
  category: string | null;
  metadata_origin: "manual" | "imported" | "ai_suggested";
  archived: boolean;
  created_at: string;
  updated_at: string;
}

export interface AssetList {
  items: Asset[];
  total: number;
  page: number;
  page_size: number;
}

export interface AssetInput {
  display_name: string;
  file_reference?: string | null;
  media_type?: string | null;
  title?: string | null;
  description?: string | null;
  keywords?: string[];
  category?: string | null;
  archived?: boolean;
}

export type SubmissionStatus =
  | "draft"
  | "submitted"
  | "accepted"
  | "rejected"
  | "withdrawn"
  | "unknown";

export const SUBMISSION_STATUSES: SubmissionStatus[] = [
  "draft",
  "submitted",
  "accepted",
  "rejected",
  "withdrawn",
  "unknown",
];

export interface Submission {
  id: number;
  asset_id: number;
  platform: string;
  status: SubmissionStatus;
  submitted_at: string | null;
  reviewed_at: string | null;
  rejection_note: string | null;
  rejection_category: string | null;
  created_at: string;
}

export interface SubmissionList {
  items: Submission[];
  total: number;
  page: number;
  page_size: number;
}

export interface SubmissionInput {
  asset_id: number;
  platform: string;
  status?: SubmissionStatus;
  submitted_at?: string | null;
  reviewed_at?: string | null;
  rejection_note?: string | null;
  rejection_category?: string | null;
}

export interface InsightsSummary {
  total_assets: number;
  archived_assets: number;
  total_submissions: number;
  submissions_by_status: Record<string, number>;
  submissions_by_platform: Record<string, number>;
  rejections_by_category: Record<string, number>;
  sample_size: number;
  period_start: string | null;
  period_end: string | null;
}

export interface AiStatus {
  ai_configured: boolean;
  message: string;
}
