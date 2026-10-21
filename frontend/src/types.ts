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
  // Image-upload fields (set when the asset has an uploaded image).
  stored_path?: string | null;
  original_filename?: string | null;
  width?: number | null;
  height?: number | null;
  file_size?: number | null;
  image_url?: string | null;
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
  metadata_origin?: "manual" | "imported" | "ai_suggested";
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
  model?: string | null;
}

// Unsaved AI metadata draft — client-side only until the user saves.
export interface AiDraft {
  asset_id: number;
  title: string;
  description: string | null;
  category: string | null;
  keywords: string[];
  model: string;
}

export interface ImageUploadResult {
  asset: Asset;
  image_url: string;
}

// Result of a permanent asset deletion (DELETE /api/v1/assets/{id}).
export interface AssetDeleteResult {
  id: number;
  display_name: string;
  deleted_submissions: number;
  // null = the asset had no stored image; false = the record was deleted but
  // the app-managed file could not be removed (logged server-side).
  image_removed: boolean | null;
}

// ---- Vision Insights types -------------------------------------------------

export interface VisualAttributes {
  objects: string[];
  scene: string[];
  dominant_colors: string[];
  lighting: string | null;
  mood: string | null;
  composition: string | null;
  orientation: string | null;
  copy_space: string | null;
}

export interface CommercialUseIdea {
  use_case: string;
  fit: string | null;
}

export interface KeywordGapAnalysis {
  existing_keywords: string[];
  suggested_missing: string[];
  reasoning: string | null;
}

export interface MetadataQualityReview {
  title_assessment: string | null;
  keyword_issues: string[];
  description_assessment: string | null;
  unsupported_terms: string[];
}

export interface VisionInsights {
  asset_id: number;
  visual_attributes: VisualAttributes;
  commercial_use_ideas: CommercialUseIdea[];
  keyword_gap_analysis: KeywordGapAnalysis;
  metadata_quality_review: MetadataQualityReview;
  actionable_recommendations: string[];
  model: string;
}

export interface VisionInsightsRecord {
  id: number;
  asset_id: number;
  visual_attributes: VisualAttributes;
  commercial_use_ideas: CommercialUseIdea[];
  keyword_gap_analysis: KeywordGapAnalysis;
  metadata_quality_review: MetadataQualityReview;
  actionable_recommendations: string[];
  model: string;
  created_at: string;
}
