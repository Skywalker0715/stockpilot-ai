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

    @field_validator("display_name", "archived")
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


class AssetListOut(BaseModel):
    items: list[AssetOut]
    total: int
    page: int
    page_size: int


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
    # Honest indicator required by the approved scope (Q6):
    # the MVP has no AI provider; manual entry always works.
    ai_configured: bool
    message: str

