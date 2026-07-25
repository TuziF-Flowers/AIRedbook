from __future__ import annotations

import pytest

from app.config import Settings
from app.models import Author, NoteDetail, NoteStats
from app.services.competitor_analyzer import CompetitorAnalyzer


@pytest.mark.asyncio
async def test_rule_analysis_generates_structured_report():
    analyzer = CompetitorAnalyzer(Settings(ai_api_key=None, ai_model=None))
    details = [
        NoteDetail(
            note_id="note-1",
            title="亲测 AI 眼镜，通勤真的好用吗？",
            note_type="image",
            competitor="竞品甲",
            cover_url="https://sns-webpic-qc.xhscdn.com/cover.webp",
            web_url="https://www.xiaohongshu.com/explore/note-1",
            author=Author(nickname="测试作者"),
            stats=NoteStats(likes=1200, collects=500, comments=80),
            description="通勤场景真实体验\n1. 佩戴舒适\n2. 记录方便 ✅",
            image_urls=[
                "https://sns-webpic-qc.xhscdn.com/1.webp",
                "https://sns-webpic-qc.xhscdn.com/2.webp",
            ],
            tags=["AI眼镜", "真实测评"],
        )
    ]

    result = await analyzer.analyze("AI 眼镜", details)

    assert result.analysis_mode == "rules"
    assert result.metrics.average_engagement == 1780
    assert result.keywords
    assert result.title_templates
    assert result.content_insights
    assert result.copywriting_insights
    assert result.copywriting_framework
    assert result.competitor_insights
    assert result.competitor_insights[0].title == "竞品甲"
    assert "文案内容分析" in result.report_markdown
    assert "小红书竞品分析报告" in result.report_markdown
