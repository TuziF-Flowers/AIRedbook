from __future__ import annotations

import pytest

from app.config import Settings
from app.models import Author, NoteDetail, NoteStats
from app.services.competitor_analyzer import CompetitorAnalyzer, _sampling_options


def test_gpt5_models_use_the_only_supported_default_temperature():
    """验证 GPT-5 系列模型使用默认温度（不设置额外 temperature）"""
    print("\n🔍 测试: GPT-5 系列模型使用默认温度")
    assert _sampling_options("gpt-5.6") == {}
    print("  ✅ _sampling_options('gpt-5.6') = {} (无额外参数)")
    assert _sampling_options("gpt-5.6-sol") == {}
    print("  ✅ _sampling_options('gpt-5.6-sol') = {} (无额外参数)")


def test_other_models_keep_low_temperature_for_stable_json():
    """验证非 GPT-5 模型使用低温度以获得稳定 JSON 输出"""
    print("\n🔍 测试: 非 GPT-5 模型使用低温度参数")
    result = _sampling_options("gpt-4.1-mini")
    assert result == {"temperature": 0.2}
    print(f"  ✅ _sampling_options('gpt-4.1-mini') = {result}")


@pytest.mark.asyncio
async def test_rule_analysis_generates_structured_report():
    """验证规则分析模式生成完整的结构化竞品报告"""
    print("\n🔍 测试: 规则分析 → 结构化竞品报告生成")
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

    print(f"  📊 输入: 关键词='AI 眼镜', 笔记数={len(details)}")
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
    print(f"  ✅ 分析模式: {result.analysis_mode}")
    print(f"  ✅ 平均互动量: {result.metrics.average_engagement}")
    print(f"  ✅ 关键词数量: {len(result.keywords)}")
    print(f"  ✅ 标题模板数量: {len(result.title_templates)}")
    print(f"  ✅ 内容洞察数量: {len(result.content_insights)}")
    print(f"  ✅ 文案洞察数量: {len(result.copywriting_insights)}")
    print(f"  ✅ 竞品洞察数量: {len(result.competitor_insights)}")
    print("  ✅ 报告包含 '小红书竞品分析报告' 标题")
