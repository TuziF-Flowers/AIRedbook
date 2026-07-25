from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_project_path(value: str | None, default: Path) -> Path:
    if not value:
        return default
    candidate = Path(value).expanduser()
    return candidate if candidate.is_absolute() else PROJECT_ROOT / candidate


@dataclass(frozen=True, slots=True)
class Settings:
    redbook_executable: str | None = os.getenv("REDBOOK_EXECUTABLE") or None
    redbook_cookie_file: str | None = os.getenv("REDBOOK_COOKIE_FILE") or None
    redbook_platform: str = os.getenv("REDBOOK_PLATFORM", "xhs")
    command_timeout_seconds: float = float(
        os.getenv("REDBOOK_COMMAND_TIMEOUT_SECONDS", "30")
    )
    max_concurrency: int = int(os.getenv("REDBOOK_MAX_CONCURRENCY", "2"))
    app_host: str = os.getenv("APP_HOST", "127.0.0.1")
    app_port: int = int(os.getenv("APP_PORT", "8000"))
    app_reload: bool = _as_bool(os.getenv("APP_RELOAD"), True)
    ai_api_key: str | None = os.getenv("AI_API_KEY") or None
    ai_base_url: str = os.getenv("AI_BASE_URL", "https://api.openai.com/v1")
    ai_model: str | None = os.getenv("AI_MODEL") or None
    ai_timeout_seconds: float = float(os.getenv("AI_TIMEOUT_SECONDS", "60"))
    ai_enable_vision: bool = _as_bool(os.getenv("AI_ENABLE_VISION"), True)
    ai_vision_max_covers: int = int(os.getenv("AI_VISION_MAX_COVERS", "20"))
    ai_vision_max_gallery_notes: int = int(
        os.getenv("AI_VISION_MAX_GALLERY_NOTES", "6")
    )
    ai_vision_max_images_per_note: int = int(
        os.getenv("AI_VISION_MAX_IMAGES_PER_NOTE", "4")
    )
    ai_vision_max_image_bytes: int = int(
        os.getenv("AI_VISION_MAX_IMAGE_BYTES", "550000")
    )
    ai_vision_image_detail: str = os.getenv("AI_VISION_IMAGE_DETAIL", "low")
    analysis_storage_dir: Path = _as_project_path(
        os.getenv("ANALYSIS_STORAGE_DIR"),
        PROJECT_ROOT / "data" / "analyses",
    )


settings = Settings()
