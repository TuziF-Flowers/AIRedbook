from __future__ import annotations

from app.config import Settings
from app.models import NoteDetail, NoteStats
from app.services.vision_analyzer import VisionAnalyzer


def _note(index: int) -> NoteDetail:
    return NoteDetail(
        note_id=f"note-{index}",
        title=f"测试笔记 {index}",
        note_type="image",
        cover_url=f"https://sns-webpic-qc.xhscdn.com/{index}-cover.webp",
        web_url=f"https://www.xiaohongshu.com/explore/note-{index}",
        stats=NoteStats(likes=index * 100, collects=index * 10, comments=index),
        image_urls=[
            f"https://sns-webpic-qc.xhscdn.com/{index}-cover.webp",
            f"https://sns-webpic-qc.xhscdn.com/{index}-detail.webp",
            f"https://sns-webpic-qc.xhscdn.com/{index}-scene.webp",
        ],
    )


def test_visual_sample_selection_is_ranked_and_bounded():
    analyzer = VisionAnalyzer(
        Settings(
            ai_vision_max_covers=3,
            ai_vision_max_gallery_notes=2,
            ai_vision_max_images_per_note=2,
        )
    )

    covers, galleries = analyzer._select_samples([_note(index) for index in range(1, 5)])

    assert [sample.note_id for sample in covers] == ["note-4", "note-3", "note-2"]
    assert len(galleries) == 4
    assert [sample.note_id for sample in galleries] == [
        "note-4",
        "note-4",
        "note-3",
        "note-3",
    ]
    assert [sample.image_index for sample in galleries] == [0, 1, 0, 1]
