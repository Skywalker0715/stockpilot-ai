# Application-managed image upload storage.
#
# Security rules enforced here:
# - Clients never supply storage paths; the server generates filenames.
# - Only .jpg/.jpeg/.png/.webp are accepted, and the file's magic bytes and
#   full Pillow decode must both agree with the claimed extension.
# - Reads/writes are confined to config.UPLOAD_DIR (path traversal blocked).

import io
import uuid
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from app import config

# extension -> (magic-byte check name, Pillow format, media type)
_ALLOWED_FORMATS: dict[str, tuple[str, str, str]] = {
    ".jpg": ("jpeg", "JPEG", "image/jpeg"),
    ".jpeg": ("jpeg", "JPEG", "image/jpeg"),
    ".png": ("png", "PNG", "image/png"),
    ".webp": ("webp", "WEBP", "image/webp"),
}

# Reject absurd pixel counts early (decompression-bomb guard). 50 MP is far
# above any legitimate 10 MiB stock photo after JPEG/WebP compression.
MAX_IMAGE_PIXELS = 50_000_000


class UploadValidationError(ValueError):
    """User-actionable upload rejection (mapped to HTTP 400)."""


@dataclass(frozen=True)
class ValidatedImage:
    extension: str  # normalized, including dot (e.g. ".png")
    media_type: str  # detected from content, not client trust
    width: int
    height: int


def _magic_ok(fmt: str, data: bytes) -> bool:
    if fmt == "jpeg":
        return data.startswith(b"\xff\xd8\xff")
    if fmt == "png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if fmt == "webp":
        return len(data) >= 12 and data[0:4] == b"RIFF" and data[8:12] == b"WEBP"
    return False


def validate_image(filename: str | None, data: bytes) -> ValidatedImage:
    """Validate upload bytes: extension, size, magic, and full decode.

    Raises UploadValidationError with an actionable message on any failure.
    """
    if not filename or "." not in filename:
        raise UploadValidationError(
            "File must have an extension (.jpg, .jpeg, .png, or .webp)."
        )
    ext = "." + filename.rsplit(".", 1)[-1].lower()
    if ext not in _ALLOWED_FORMATS:
        raise UploadValidationError(
            "Unsupported file type. Use JPG, JPEG, PNG, or WebP."
        )

    if not data:
        raise UploadValidationError("The uploaded file is empty.")
    if len(data) > config.MAX_UPLOAD_BYTES:
        limit_mb = config.MAX_UPLOAD_BYTES / (1024 * 1024)
        raise UploadValidationError(
            f"File is too large (limit {limit_mb:.1f} MB)."
        )

    magic_name, pillow_format, media_type = _ALLOWED_FORMATS[ext]
    if not _magic_ok(magic_name, data):
        raise UploadValidationError(
            "File content does not match its extension "
            "(the file is not a real image of that type)."
        )

    try:
        Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
        with Image.open(io.BytesIO(data)) as img:
            img.load()  # force a full decode; catches truncated/corrupt files
            width, height = img.size
            detected = img.format
    except Image.DecompressionBombError:
        raise UploadValidationError(
            "Image resolution is too large to process."
        ) from None
    except (UnidentifiedImageError, OSError):
        raise UploadValidationError(
            "The file could not be decoded as an image. "
            "It may be corrupt."
        ) from None

    if detected != pillow_format:
        raise UploadValidationError(
            "File content does not match its extension "
            f"(decoded as {detected}, expected {pillow_format})."
        )

    return ValidatedImage(extension=ext, media_type=media_type, width=width, height=height)


def save_image(data: bytes, extension: str) -> str:
    """Persist bytes under a server-generated filename; return the stored
    filename (relative to UPLOAD_DIR, no directories)."""
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{extension}"
    (config.UPLOAD_DIR / stored_name).write_bytes(data)
    return stored_name


def resolve_stored_path(stored_name: str) -> Path:
    """Resolve a stored filename to an absolute path inside UPLOAD_DIR.

    Rejects any name that could escape the directory (separators, '..', or
    a resolved path outside UPLOAD_DIR). Callers must 404 on this error.
    """
    if not stored_name or Path(stored_name).name != stored_name:
        raise FileNotFoundError(stored_name)
    base = config.UPLOAD_DIR.resolve()
    path = (base / stored_name).resolve()
    if path.parent != base:
        raise FileNotFoundError(stored_name)
    return path
