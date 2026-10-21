# Pydantic models (request/response) for the StockPilot AI MVP.

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MetadataOrigin(str, Enum):
    manual = "manual"
    imported = "imported"
    ai_suggested = "ai_suggested"


class SubmissionStatus(str, Enum):
    draft = "draft"
    submitted = "submitted"
    accepted = "accepted"
    rejected = "rejected"
    withdrawn = "withdrawn"
    unknown = "unknown"


def _normalize_keywords(value: list[str]) -> list[str]:
    # Trim, drop empties, and de-duplicate case-insensitively
    # while preserving the first spelling the user typed.
    seen: set[str] = set()
    result: list[str] = []
    for raw in value:
        word = raw.strip()
        if not word or len(word) > 100:
            continue
        key = word.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(word)
    return result


class AssetCreate(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=200)
    file_reference: str | None = Field(None, max_length=1024)
    media_type: str | None = Field(None, max_length=100)
    title: str | None = Field(None, max_length=300)
    description: str | None = Field(None, max_length=4000)
    keywords: list[str] = Field(default_factory=list, max_length=50)
    category: str | None = Field(None, max_length=100)

    @field_validator("keywords")
    @classmethod
    def normalize_keywords(cls, value: list[str]) -> list[str]:
        return _normalize_keywords(value)


class AssetUpdate(BaseModel):
    # All fields optional: PATCH updates only what is provided.
    # Explicit null clears a nullable field; display_name and keywords
    # are not nullable, so null is rejected here (422, not a DB error).
    display_name: str | None = Field(None, min_length=1, max_length=200)
    file_reference: str | None = Field(None, max_length=1024)
    media_type: str | None = Field(None, max_length=100)
    title: str | None = Field(None, max_length=300)
    description: str | None = Field(None, max_length=4000)
    keywords: list[str] | None = Field(None, max_length=50)
    category: str | None = Field(None, max_length=100)
    archived: bool | None = None
    # Origin of the metadata being saved (e.g. 'ai_suggested' after an AI
    # draft is explicitly saved). Omit to keep the current value.
    metadata_origin: MetadataOrigin | None = None

    @field_validator("display_name", "archived", "metadata_origin")
    @classmethod
    def display_name_not_null(cls, value: object) -> object:
        if value is None:
            raise ValueError(
                "value cannot be null; omit the field to keep it"
            )
        return value

    @field_validator("keywords")
    @classmethod
    def normalize_keywords(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            raise ValueError("keywords cannot be null; send [] to clear them")
        return _normalize_keywords(value)


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str
    file_reference: str | None
    media_type: str | None
    title: str | None
    description: str | None
    keywords: list[str]
    category: str | None
    metadata_origin: MetadataOrigin
    archived: bool
    created_at: str
    updated_at: str
    # Image-upload fields (002 migration). image_url is populated by the
    # service layer when a stored image exists; null for record-only assets.
    stored_path: str | None = None
    original_filename: str | None = None
    width: int | None = None
    height: int | None = None
    file_size: int | None = None
    image_url: str | None = None


class AssetListOut(BaseModel):
    items: list[AssetOut]
    total: int
    page: int
    page_size: int


class ImageUploadOut(BaseModel):
    """Response for POST /api/v1/uploads: the created asset plus its image URL."""

    asset: AssetOut
    image_url: str


class AssetDeleteOut(BaseModel):
    """Response for DELETE /api/v1/assets/{id}.

    image_removed is null when the asset had no stored image; false means the
    database deletion succeeded but the app-managed file could not be removed
    (the failure is logged server-side and does not roll back the deletion).
    """

    id: int
    display_name: str
    deleted_submissions: int
    image_removed: bool | None


class SubmissionCreate(BaseModel):
    asset_id: int = Field(..., gt=0)
    platform: str = Field(..., min_length=1, max_length=100)
    status: SubmissionStatus = SubmissionStatus.draft
    submitted_at: str | None = Field(None, max_length=40)
    rejection_note: str | None = Field(None, max_length=4000)
    rejection_category: str | None = Field(None, max_length=100)


class SubmissionUpdate(BaseModel):
    # platform and status are NOT NULL in the schema: reject explicit null
    # (422) instead of letting the DB raise a 500.
    platform: str | None = Field(None, min_length=1, max_length=100)
    status: SubmissionStatus | None = None
    submitted_at: str | None = Field(None, max_length=40)
    reviewed_at: str | None = Field(None, max_length=40)
    rejection_note: str | None = Field(None, max_length=4000)
    rejection_category: str | None = Field(None, max_length=100)

    @field_validator("platform", "status")
    @classmethod
    def not_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("cannot be null; omit the field to keep it")
        return value


class SubmissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_id: int
    platform: str
    status: SubmissionStatus
    submitted_at: str | None
    reviewed_at: str | None
    rejection_note: str | None
    rejection_category: str | None
    created_at: str


class SubmissionListOut(BaseModel):
    items: list[SubmissionOut]
    total: int
    page: int
    page_size: int


class InsightsSummaryOut(BaseModel):
    # Aggregates over user-recorded data only (PRD "Personal insights").
    total_assets: int
    archived_assets: int
    total_submissions: int
    submissions_by_status: dict[str, int]
    submissions_by_platform: dict[str, int]
    rejections_by_category: dict[str, int]
    sample_size: int
    period_start: str | None
    period_end: str | None


class AiStatusOut(BaseModel):
    # Honest indicator (approved scope Q6): reports whether a Cohere key is
    # actually configured; manual entry always works either way.
    ai_configured: bool
    message: str
    # Active vision model (informational; config.STOCKPILOT_AI_MODEL).
    model: str | None = None


class AiAnalyzeRequest(BaseModel):
    """Analyze an uploaded image. The result is a DRAFT only: nothing is
    persisted until the user explicitly saves via PATCH /assets/{id}."""

    asset_id: int = Field(..., gt=0)
    # Explicit consent: the frontend shows a consent notice before sending
    # image data to the AI provider; the API refuses to call Cohere without it.
    consent: bool = False

    @field_validator("consent")
    @classmethod
    def consent_required(cls, value: bool) -> bool:
        if not value:
            raise ValueError(
                "consent is required: confirm that the image may be sent "
                "to Cohere for AI analysis"
            )
        return value


class AiDraftOut(BaseModel):
    """Unsaved AI metadata draft for one asset."""

    asset_id: int
    title: str
    description: str | None
    category: str | None
    keywords: list[str] = Field(..., max_length=50)
    # Model that actually produced this draft (honesty: never guess).
    model: str



# ---------------------------------------------------------------------------
# Vision Insights models (image analysis beyond Generate's metadata draft)
# ---------------------------------------------------------------------------

class VisualAttributesOut(BaseModel):
    """Observable visual attributes of an image.

    Described as observations of image content, not as measured market
    performance, search volume, or sales data.
    """

    objects: list[str] = Field(default_factory=list, max_length=20)
    scene: list[str] = Field(default_factory=list, max_length=10)
    dominant_colors: list[str] = Field(default_factory=list, max_length=8)
    lighting: str | None = None
    mood: str | None = None
    composition: str | None = None
    orientation: str | None = None
    copy_space: str | None = None


class CommercialUseIdeaOut(BaseModel):
    """A plausible commercial use case for the image.

    Labeled as an AI suggestion: never presented as guaranteed demand or a
    sales forecast.
    """

    use_case: str = Field(..., max_length=120)
    fit: str | None = Field(None, max_length=200)


class KeywordGapAnalysisOut(BaseModel):
    """Comparison of existing metadata keywords against visual attributes.

    Suggests missing relevant keywords without duplicates and without
    unsupported claims.
    """

    existing_keywords: list[str] = Field(default_factory=list, max_length=50)
    suggested_missing: list[str] = Field(default_factory=list, max_length=30)
    reasoning: str | None = Field(None, max_length=1000)


class MetadataQualityReviewOut(BaseModel):
    """Honest review of existing metadata quality.

    Flags vague titles, repetitive keywords, unsupported terms, and
    descriptions that may not accurately represent the image.
    """

    title_assessment: str | None = Field(None, max_length=500)
    keyword_issues: list[str] = Field(default_factory=list, max_length=20)
    description_assessment: str | None = Field(None, max_length=1000)
    unsupported_terms: list[str] = Field(default_factory=list, max_length=20)


class VisionInsightsOut(BaseModel):
    """Complete vision-insights analysis for one asset.

    All fields are AI-generated inferences/observations and are labeled as
    such in the UI.
    """

    asset_id: int
    visual_attributes: VisualAttributesOut
    commercial_use_ideas: list[CommercialUseIdeaOut] = Field(
        default_factory=list, max_length=10
    )
    keyword_gap_analysis: KeywordGapAnalysisOut
    metadata_quality_review: MetadataQualityReviewOut
    actionable_recommendations: list[str] = Field(
        default_factory=list, max_length=15
    )
    model: str


class VisionInsightsRequest(BaseModel):
    """Analyze an uploaded image for vision insights.

    The result is AI-generated and is NOT persisted to the asset's editable
    metadata until the user explicitly applies keyword suggestions.
    """

    asset_id: int = Field(..., gt=0)
    consent: bool = False

    @field_validator("consent")
    @classmethod
    def consent_required(cls, value: bool) -> bool:
        if not value:
            raise ValueError(
                "consent is required: confirm that the image may be sent "
                "to Cohere for AI vision analysis"
            )
        return value


class VisionInsightsRecordOut(BaseModel):
    """A persisted vision-insights record, served to the UI."""

    id: int
    asset_id: int
    visual_attributes: dict
    commercial_use_ideas: list
    keyword_gap_analysis: dict
    metadata_quality_review: dict
    actionable_recommendations: list[str]
    model: str
    created_at: str

