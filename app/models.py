from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator


def _require_timezone(value: datetime | None) -> datetime | None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise ValueError("监测时间必须包含时区信息")
    return value


class Author(BaseModel):
    id: str = ""
    nickname: str = "未知作者"
    avatar_url: str | None = None


class NoteStats(BaseModel):
    likes: int = 0
    comments: int = 0
    collects: int = 0
    shares: int = 0


class NoteSummary(BaseModel):
    note_id: str
    title: str = "无标题"
    note_type: Literal["image", "video", "unknown"] = "unknown"
    cover_url: str | None = None
    web_url: str
    competitor: str | None = None
    topic_tags: list[str] = Field(default_factory=list)
    author: Author = Field(default_factory=Author)
    stats: NoteStats = Field(default_factory=NoteStats)


class SearchResponse(BaseModel):
    keyword: str
    page: int
    page_size: int = 20
    has_more: bool = False
    items: list[NoteSummary] = Field(default_factory=list)


class NoteDetail(NoteSummary):
    description: str = ""
    image_urls: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    published_at: int | None = None
    ip_location: str | None = None


class NoteDetailRequest(BaseModel):
    web_url: HttpUrl


class AnalysisRequest(BaseModel):
    keyword: str = Field(min_length=1, max_length=80)
    notes: list[NoteSummary] = Field(min_length=1, max_length=20)


class CompetitorCollectionRequest(BaseModel):
    product_name: str = Field(min_length=1, max_length=80)
    competitors: list[str] = Field(min_length=1, max_length=3)

    @field_validator("product_name")
    @classmethod
    def clean_product_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("产品名称不能为空")
        return cleaned

    @field_validator("competitors")
    @classmethod
    def clean_competitors(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for value in values:
            item = value.strip()
            key = item.casefold()
            if item and key not in seen:
                cleaned.append(item)
                seen.add(key)
        if not cleaned:
            raise ValueError("至少需要一个竞品标签")
        return cleaned


class KeywordInsight(BaseModel):
    term: str
    count: int = 1
    weight: int = 1


class TitleTemplate(BaseModel):
    template: str
    evidence_count: int = 1
    example: str = ""


class AnalysisInsight(BaseModel):
    title: str
    description: str


class AnalysisMetrics(BaseModel):
    total_likes: int = 0
    total_collects: int = 0
    total_comments: int = 0
    average_likes: int = 0
    average_collects: int = 0
    average_comments: int = 0
    average_engagement: int = 0


class CompetitorAnalysis(BaseModel):
    keyword: str
    source_count: int
    generated_at: str
    analysis_mode: Literal["ai", "rules"] = "rules"
    mode_label: str
    keywords: list[KeywordInsight] = Field(default_factory=list)
    title_templates: list[TitleTemplate] = Field(default_factory=list)
    title_traits: list[AnalysisInsight] = Field(default_factory=list)
    content_insights: list[AnalysisInsight] = Field(default_factory=list)
    copywriting_insights: list[AnalysisInsight] = Field(default_factory=list)
    copywriting_framework: list[AnalysisInsight] = Field(default_factory=list)
    competitor_insights: list[AnalysisInsight] = Field(default_factory=list)
    image_insights: list[AnalysisInsight] = Field(default_factory=list)
    interaction_insights: list[AnalysisInsight] = Field(default_factory=list)
    summary: list[str] = Field(default_factory=list)
    metrics: AnalysisMetrics = Field(default_factory=AnalysisMetrics)
    report_markdown: str = ""


class ApiErrorBody(BaseModel):
    code: str
    message: str
    hint: str | None = None


class MonitoringTaskStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ERROR = "error"


class InteractionSnapshot(BaseModel):
    collected_at: datetime
    likes: int = Field(ge=0)
    collects: int = Field(ge=0)
    comments: int = Field(ge=0)

    @field_validator("collected_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        return _require_timezone(value)


class MonitoringTask(BaseModel):
    task_id: str
    note_id: str
    web_url: str
    title: str
    cover_url: str | None = None
    created_at: datetime
    monitoring_starts_at: datetime
    monitoring_ends_on: date
    snapshots: list[InteractionSnapshot] = Field(default_factory=list)
    last_collected_at: datetime | None = None
    last_error: str | None = None
    last_error_at: datetime | None = None

    @field_validator(
        "created_at",
        "monitoring_starts_at",
        "last_collected_at",
        "last_error_at",
    )
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        return _require_timezone(value)


class MonitoringTaskCreate(BaseModel):
    web_url: HttpUrl


class MonitoringArchive(BaseModel):
    version: Literal[1] = 1
    tasks: list[MonitoringTask] = Field(default_factory=list)
