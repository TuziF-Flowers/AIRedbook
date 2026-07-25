from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi.testclient import TestClient

from app.config import settings
from app.main import (
    _filter_single_product_seeding,
    _is_allowed_image_url,
    _select_top_image,
    app,
)
from app.models import NoteDetail, NoteStats, NoteSummary, SearchResponse
from app.services.competitor_analyzer import CompetitorAnalyzer


class FakeRedbookCLI:
    is_installed = True

    async def whoami(self):
        return {"nickname": "测试用户", "user_id": "user-fixture"}

    async def search(self, keyword: str, *, page: int, sort: str, note_type: str):
        return {
            "items": [
                {
                    "model_type": "note",
                    "id": f"note-{keyword}",
                    "xsec_token": f"fixture-token-{keyword}",
                    "note_card": {
                        "type": "normal",
                        "display_title": f"{keyword}使用体验",
                        "user": {"nickname": "测试作者"},
                        "interact_info": {"liked_count": "100"},
                    },
                }
            ],
            "has_more": False,
        }

    async def read_note(self, web_url: str):
        return {
            "note_id": "note-fixture",
            "title": "详情",
            "desc": "详情正文",
            "type": "normal",
            "user": {"nickname": "测试作者"},
            "image_list": [
                {
                    "url_default": "http://sns-webpic-qc.xhscdn.com/preview.webp"
                }
            ],
        }


@asynccontextmanager
async def fake_lifespan(application):
    application.state.redbook = FakeRedbookCLI()
    application.state.analyzer = CompetitorAnalyzer(settings)
    application.state.note_details = {}
    yield


def test_search_and_detail_api():
    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = fake_lifespan
    try:
        with TestClient(app) as client:
            session = client.get("/api/session")
            assert session.status_code == 200
            assert session.json()["nickname"] == "测试用户"

            search = client.get(
                "/api/search",
                params={"q": "测试产品", "sort": "popular", "type": "image"},
            )
            assert search.status_code == 200
            note = search.json()["items"][0]
            assert note["title"] == "测试产品使用体验"
            assert note["cover_url"] == (
                "https://sns-webpic-qc.xhscdn.com/preview.webp"
            )

            detail = client.post(
                "/api/notes/detail",
                json={"web_url": note["web_url"]},
            )
            assert detail.status_code == 200
            assert detail.json()["description"] == "详情正文"

            analysis = client.post(
                "/api/analyze",
                json={
                    "keyword": "测试产品",
                    "notes": [note],
                },
            )
            assert analysis.status_code == 200
            report = analysis.json()
            assert report["source_count"] == 1
            assert report["analysis_mode"] == "rules"
            assert report["summary"]
            assert "# 测试产品 · 小红书竞品分析报告" in report["report_markdown"]

            collection = client.post(
                "/api/collect",
                json={
                    "product_name": "测试品类",
                    "competitors": ["竞品甲", "竞品乙"],
                },
            )
            assert collection.status_code == 200
            collection_body = collection.json()
            assert collection_body["keyword"] == "测试品类"
            assert len(collection_body["items"]) == 2
            assert {
                item["competitor"] for item in collection_body["items"]
            } == {"竞品甲", "竞品乙"}
    finally:
        app.router.lifespan_context = original_lifespan


def test_detail_rejects_untrusted_host():
    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = fake_lifespan
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/notes/detail",
                json={"web_url": "https://example.com/explore/note-fixture"},
            )
            assert response.status_code == 422
            assert response.json()["code"] == "INVALID_NOTE_URL"
    finally:
        app.router.lifespan_context = original_lifespan


def test_image_proxy_only_accepts_xiaohongshu_cdn_hosts():
    assert _is_allowed_image_url("https://sns-webpic-qc.xhscdn.com/example.webp")
    assert _is_allowed_image_url("https://ci.xiaohongshu.com/example.jpg")
    assert not _is_allowed_image_url("http://sns-webpic-qc.xhscdn.com/example.webp")
    assert not _is_allowed_image_url("https://xhscdn.com.example.com/example.webp")


def test_search_selects_top_twenty_images_by_likes_and_collects():
    image_notes = [
        NoteSummary(
            note_id=f"image-{index}",
            note_type="image",
            web_url=f"https://www.xiaohongshu.com/explore/image-{index}",
            stats=NoteStats(likes=index * 100, collects=index * 10),
        )
        for index in range(1, 26)
    ]
    result = SearchResponse(
        keyword="测试",
        page=1,
        items=[
            *image_notes,
            NoteSummary(
                note_id="video-high",
                note_type="video",
                web_url="https://www.xiaohongshu.com/explore/video-high",
                stats=NoteStats(likes=10_000, collects=10_000),
            ),
        ],
    )

    selected = _select_top_image(result)

    assert len(selected.items) == 20
    assert [note.note_id for note in selected.items] == [
        f"image-{index}" for index in range(25, 5, -1)
    ]
    assert selected.has_more is False


def test_single_product_filter_excludes_reviews_and_prioritizes_seeding():
    notes = [
        NoteSummary(
            note_id="review",
            title="AI 眼镜深度测评",
            note_type="image",
            web_url="https://www.xiaohongshu.com/explore/review",
            stats=NoteStats(likes=10_000, collects=5_000),
        ),
        NoteSummary(
            note_id="collection",
            title="5 款 AI 眼镜横向对比合集",
            note_type="image",
            web_url="https://www.xiaohongshu.com/explore/collection",
            stats=NoteStats(likes=8_000, collects=4_000),
        ),
        NoteSummary(
            note_id="neutral",
            title="AI 眼镜日常使用记录",
            note_type="image",
            web_url="https://www.xiaohongshu.com/explore/neutral",
            stats=NoteStats(likes=3_000, collects=1_000),
        ),
        NoteSummary(
            note_id="seeding",
            title="通勤离不开的 AI 眼镜",
            note_type="image",
            web_url="https://www.xiaohongshu.com/explore/seeding",
            stats=NoteStats(likes=1_000, collects=600),
        ),
    ]
    result = SearchResponse(keyword="AI 眼镜", page=1, items=notes)
    detail_cache = {
        notes[2].web_url: NoteDetail(
            **notes[2].model_dump(),
            description="记录每天使用的感受。",
        ),
        notes[3].web_url: NoteDetail(
            **notes[3].model_dump(),
            description="通勤场景真香好物，值得入手，推荐给上班族。",
            tags=["单品种草"],
        ),
    }

    filtered = _filter_single_product_seeding(result, detail_cache)

    assert [note.note_id for note in filtered.items] == ["seeding", "neutral"]
