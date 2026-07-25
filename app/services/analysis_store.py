from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Lock
from uuid import uuid4

from app.models import CompetitorAnalysis, NoteDetail

ARTIFACT_ID_PATTERN = re.compile(r"ana_\d{8}T\d{6}_[0-9a-f]{8}")


@dataclass(frozen=True, slots=True)
class AnalysisArtifact:
    analysis_id: str
    path: Path


class AnalysisStore:
    """Stores local, credential-free analysis artifacts for downstream workflows."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory.resolve()
        self._lock = Lock()

    def save(
        self,
        analysis: CompetitorAnalysis,
        source_notes: list[NoteDetail],
    ) -> AnalysisArtifact:
        self.directory.mkdir(parents=True, exist_ok=True)
        analysis_id = (
            f"ana_{datetime.now().strftime('%Y%m%dT%H%M%S')}_{uuid4().hex[:8]}"
        )
        path = self._path_for_id(analysis_id)
        payload = self._build_payload(analysis_id, analysis, source_notes)
        temporary_path = path.with_suffix(".tmp")

        with self._lock:
            temporary_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temporary_path.replace(path)

        return AnalysisArtifact(analysis_id=analysis_id, path=path)

    def get_path(self, analysis_id: str) -> Path | None:
        if not ARTIFACT_ID_PATTERN.fullmatch(analysis_id):
            return None
        path = self._path_for_id(analysis_id)
        return path if path.is_file() else None

    def _path_for_id(self, analysis_id: str) -> Path:
        path = (self.directory / f"{analysis_id}.json").resolve()
        if path.parent != self.directory:
            raise ValueError("Invalid analysis artifact path")
        return path

    @staticmethod
    def _build_payload(
        analysis_id: str,
        analysis: CompetitorAnalysis,
        source_notes: list[NoteDetail],
    ) -> dict[str, object]:
        competitors = sorted(
            {note.competitor for note in source_notes if note.competitor}
        )
        visual_references = [
            {
                "note_id": note.note_id,
                "competitor": note.competitor,
                "title": note.title,
                "cover_url": note.cover_url,
                "image_urls": note.image_urls,
                "tags": note.tags,
                "web_url": note.web_url,
            }
            for note in source_notes
            if note.cover_url or note.image_urls
        ]
        return {
            "schema_version": "1.1",
            "analysis_id": analysis_id,
            "saved_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "product": {
                "name": analysis.keyword,
                "competitors": competitors,
            },
            "overview": {
                "source_count": analysis.source_count,
                "analysis_mode": analysis.analysis_mode,
                "mode_label": analysis.mode_label,
                "metrics": analysis.metrics.model_dump(mode="json"),
                "summary": analysis.summary,
            },
            "dimensions": {
                "competitor_comparison": [
                    item.model_dump(mode="json")
                    for item in analysis.competitor_insights
                ],
                "title": {
                    "keywords": [
                        item.model_dump(mode="json") for item in analysis.keywords
                    ],
                    "templates": [
                        item.model_dump(mode="json")
                        for item in analysis.title_templates
                    ],
                    "insights": [
                        item.model_dump(mode="json")
                        for item in analysis.title_traits
                    ],
                },
                "content": [
                    item.model_dump(mode="json")
                    for item in analysis.content_insights
                ],
                "copywriting": {
                    "insights": [
                        item.model_dump(mode="json")
                        for item in analysis.copywriting_insights
                    ],
                    "framework": [
                        item.model_dump(mode="json")
                        for item in analysis.copywriting_framework
                    ],
                },
                "visual": {
                    "insights": [
                        item.model_dump(mode="json")
                        for item in analysis.image_insights
                    ],
                    "analysis": analysis.visual_analysis.model_dump(mode="json"),
                    "reference_images": visual_references,
                },
                "interaction": [
                    item.model_dump(mode="json")
                    for item in analysis.interaction_insights
                ],
            },
            "source_notes": [
                note.model_dump(mode="json") for note in source_notes
            ],
            "outputs": {"report_markdown": analysis.report_markdown},
        }
