from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import (
    _filter_single_product_seeding,
    _is_allowed_image_url,
    _select_top_image,
    app,
)
from app.models import (
    GeneratedPromotionImage,
    NoteDetail,
    NoteStats,
    NoteSummary,
    PromotionCopy,
    PromotionGenerationResponse,
    SearchResponse,
)
from app.services.analysis_store import AnalysisStore
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


class FakePromotionGenerator:
    async def generate(self, product_brief, analysis, product_images):
        assert product_brief == "白色桌面产品，适合通勤人群"
        assert analysis.analysis_mode == "ai"
        assert product_images[0][2] == "image/png"
        return PromotionGenerationResponse(
            generated_at="2026-07-25T12:00:00+09:00",
            text_model="gpt-5.6",
            image_model="gpt-image-2",
            promotion_copy=PromotionCopy(
                title="通勤桌面焕新",
                body="真实产品体验正文",
                hashtags=["通勤好物", "桌面灵感", "产品分享"],
                image_brief="自然光桌面场景",
            ),
            images=[
                GeneratedPromotionImage(index=1, data_url="data:image/png;base64,YQ==")
            ],
        )

@asynccontextmanager
async def fake_lifespan(application):
    with TemporaryDirectory() as temporary_directory:
        application.state.redbook = FakeRedbookCLI()
        application.state.analyzer = CompetitorAnalyzer(
            Settings(ai_api_key=None, ai_model=None, ai_enable_vision=False)
        )
        application.state.analysis_store = AnalysisStore(Path(temporary_directory))
        application.state.promotion_generator = FakePromotionGenerator()
        application.state.note_details = {}
        yield


def test_search_and_detail_api():
    """验证搜索、详情、分析、采集 API 端到端流程"""
    print("\n🔍 测试: 搜索 → 详情 → 分析 → 采集 端到端 API 流程")
    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = fake_lifespan
    try:
        with TestClient(app) as client:
            session = client.get("/api/session")
            assert session.status_code == 200
            assert session.json()["nickname"] == "测试用户"
            print(f"  ✅ /api/session → 用户: {session.json()['nickname']}")

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
            print(f"  ✅ /api/search → 找到笔记: {note['title']}")
            print(f"     封面 URL 协议: {note['cover_url'][:5]}...")

            detail = client.post(
                "/api/notes/detail",
                json={"web_url": note["web_url"]},
            )
            assert detail.status_code == 200
            assert detail.json()["description"] == "详情正文"
            print(f"  ✅ /api/notes/detail → 描述: {detail.json()['description']}")

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
            assert report["artifact_id"]
            assert report["json_download_url"]

            saved_json = client.get(report["json_download_url"])
            assert saved_json.status_code == 200
            saved_payload = saved_json.json()
            assert saved_payload["schema_version"] == "1.1"
            assert saved_payload["analysis_id"] == report["artifact_id"]
            assert saved_payload["dimensions"]["copywriting"]["framework"]
            assert saved_payload["dimensions"]["visual"]["reference_images"]
            assert saved_payload["dimensions"]["visual"]["analysis"]["status"] == "not_requested"
            assert saved_payload["source_notes"][0]["description"] == "详情正文"

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
            print(
                f"  ✅ /api/collect → 品类: {collection_body['keyword']}, "
                f"竞品数: {len(collection_body['items'])}"
            )
    finally:
        app.router.lifespan_context = original_lifespan


def test_detail_rejects_untrusted_host():
    """验证详情 API 拒绝不受信任的主机 URL"""
    print("\n🔍 测试: 详情 API — 拒绝不信任主机 URL")
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
            print("  ✅ 拒绝 URL: https://example.com/explore/note-fixture")
            print(f"  ✅ HTTP 状态码: {response.status_code} (预期: 422)")
            print(f"  ✅ 错误码: {response.json()['code']} (预期: INVALID_NOTE_URL)")
    finally:
        app.router.lifespan_context = original_lifespan


def test_generate_promotion_accepts_product_materials_and_ai_analysis():
    """验证种草文案生成 API 接受产品素材和 AI 分析结果"""
    print("\n🔍 测试: 种草文案生成 API — 产品素材 + AI 分析")
    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = fake_lifespan
    analysis = {
        "keyword": "桌面产品",
        "source_count": 3,
        "generated_at": "2026-07-25T12:00:00+09:00",
        "analysis_mode": "ai",
        "mode_label": "AI 总结 · gpt-5.6",
    }
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/generate-promotion",
                data={
                    "product_brief": "白色桌面产品，适合通勤人群",
                    "analysis_json": json.dumps(analysis),
                },
                files={"images": ("product.png", b"valid-image", "image/png")},
            )
            assert response.status_code == 200
            payload = response.json()
            assert payload["promotion_copy"]["title"] == "通勤桌面焕新"
            assert payload["image_model"] == "gpt-image-2"
            assert len(payload["images"]) == 1
            print(f"  ✅ 文案标题: {payload['promotion_copy']['title']}")
            print(f"  ✅ 图片模型: {payload['image_model']}")
            print(f"  ✅ 生成图片数: {len(payload['images'])}")
            print(f"  ✅ HTTP 状态码: {response.status_code}")
    finally:
        app.router.lifespan_context = original_lifespan


def test_image_proxy_only_accepts_xiaohongshu_cdn_hosts():
    """验证图片代理仅接受小红书 CDN 域名"""
    print("\n🔍 测试: 图片代理 — 仅允许小红书 CDN 域名")
    assert _is_allowed_image_url("https://sns-webpic-qc.xhscdn.com/example.webp")
    print("  ✅ 允许: sns-webpic-qc.xhscdn.com (HTTPS)")
    assert _is_allowed_image_url("https://ci.xiaohongshu.com/example.jpg")
    print("  ✅ 允许: ci.xiaohongshu.com (HTTPS)")
    assert not _is_allowed_image_url("http://sns-webpic-qc.xhscdn.com/example.webp")
    print("  ✅ 拒绝: HTTP 协议")
    assert not _is_allowed_image_url("https://xhscdn.com.example.com/example.webp")
    print("  ✅ 拒绝: 伪造域名 xhscdn.com.example.com")


def test_search_selects_top_twenty_images_by_likes_and_collects():
    """验证搜索结果按点赞和收藏排序选取前 20 条图片笔记"""
    print("\n🔍 测试: 搜索结果 — 按互动量选取 Top 20 图片笔记")
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
    print(f"  ✅ 输入: {len(result.items)} 条笔记 (25 图片 + 1 视频)")
    print(f"  ✅ 输出: {len(selected.items)} 条图片笔记")
    print("  ✅ 排序: 从 image-25 到 image-6 (按互动量降序)")
    print("  ✅ 视频笔记被排除: video-high")
    print(f"  ✅ has_more = {selected.has_more}")


def test_single_product_filter_excludes_reviews_and_prioritizes_seeding():
    """验证单品种草过滤排除测评/合集，优先种草类笔记"""
    print("\n🔍 测试: 单品种草过滤 — 排除测评/合集，优先种草")
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
    print(f"  ✅ 输入: {len(notes)} 条笔记")
    print(f"  ✅ 输出: {len(filtered.items)} 条笔记")
    print("  ✅ 排除: review (测评), collection (合集)")
    print(
        f"  ✅ 保留: {filtered.items[0].note_id} (种草, 优先), "
        f"{filtered.items[1].note_id} (中性)"
    )
    print("  ✅ 排序: 种草 > 中性")
