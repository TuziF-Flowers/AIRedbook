from __future__ import annotations

import base64

import httpx
import pytest

from app.config import Settings
from app.models import AnalysisInsight, CompetitorAnalysis
from app.services import promotion_generator as promotion_module
from app.services.promotion_generator import PromotionGenerator


@pytest.mark.asyncio
async def test_generation_uses_real_text_and_multi_image_api_shapes(monkeypatch):
    """验证种草文案生成使用真实文本 API 和多图片 API 格式"""
    print("\n🔍 测试: 种草文案生成 — 文本 API + 多图片 API 格式")
    calls: list[tuple[str, dict[str, object]]] = []
    encoded_image = base64.b64encode(b"generated-png").decode()

    class FakeAsyncClient:
        def __init__(self, **_: object) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def post(self, url: str, **kwargs: object) -> httpx.Response:
            calls.append((url, kwargs))
            request = httpx.Request("POST", url)
            if url.endswith("/chat/completions"):
                return httpx.Response(
                    200,
                    request=request,
                    json={
                        "choices": [
                            {
                                "message": {
                                    "content": (
                                        '{"title":"通勤桌面焕新","body":"真实产品体验正文",'
                                        '"hashtags":["通勤好物","桌面灵感","产品分享"],'
                                        '"image_brief":"明亮自然光下的桌面使用场景"}'
                                    )
                                }
                            }
                        ]
                    },
                )
            return httpx.Response(
                200,
                request=request,
                json={"data": [{"b64_json": encoded_image}, {"b64_json": encoded_image}]},
            )

    monkeypatch.setattr(promotion_module.httpx, "AsyncClient", FakeAsyncClient)
    settings = Settings(
        ai_api_key="test-key",
        ai_base_url="https://api.example.test/v1",
        ai_model="gpt-5.6",
        ai_image_model="gpt-image-2",
        ai_image_count=2,
    )
    analysis = CompetitorAnalysis(
        keyword="桌面产品",
        source_count=3,
        generated_at="2026-07-25T12:00:00+09:00",
        analysis_mode="ai",
        mode_label="AI 总结 · gpt-5.6",
        image_insights=[
            AnalysisInsight(title="场景明确", description="自然光与真实桌面环境")
        ],
    )

    result = await PromotionGenerator(settings).generate(
        "白色桌面产品，面向通勤上班族",
        analysis,
        [
            ("front.png", b"front", "image/png"),
            ("side.webp", b"side", "image/webp"),
        ],
    )

    assert result.promotion_copy.title == "通勤桌面焕新"
    assert len(result.images) == 2
    assert calls[0][0].endswith("/chat/completions")
    assert calls[0][1]["json"]["model"] == "gpt-5.6"
    assert "temperature" not in calls[0][1]["json"]
    assert calls[1][0].endswith("/images/edits")
    assert calls[1][1]["data"] == {
        "model": "gpt-image-2",
        "prompt": calls[1][1]["data"]["prompt"],
        "n": "2",
        "size": "1024x1536",
        "quality": "high",
        "output_format": "png",
    }
    files = calls[1][1]["files"]
    assert [field for field, _ in files] == ["image[]", "image[]"]
    assert [file[0] for _, file in files] == ["front.png", "side.webp"]
    print(f"  ✅ 文案标题: {result.promotion_copy.title}")
    print(f"  ✅ 生成图片数: {len(result.images)}")
    print(f"  ✅ 文本 API 模型: {calls[0][1]['json']['model']}")
    print("  ✅ 文本 API 无 temperature 参数 (使用模型默认)")
    print(f"  ✅ 图片 API 端点: ...{calls[1][0][-20:]}")
    print(f"  ✅ 图片模型: {calls[1][1]['data']['model']}")
    print(f"  ✅ 图片尺寸: {calls[1][1]['data']['size']}")
    print(f"  ✅ 上传文件: {[file[0] for _, file in files]}")
