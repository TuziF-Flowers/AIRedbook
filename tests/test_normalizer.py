from __future__ import annotations

import json
from pathlib import Path

from app.services.normalizer import normalize_detail, normalize_search, parse_count

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_count_supports_chinese_and_compact_units():
    """验证数字解析支持中文单位（万）和紧凑单位（k）"""
    print("\n🔍 测试: 数字解析 — 中文/紧凑单位支持")
    assert parse_count("1.2万") == 12_000
    print(f"  ✅ parse_count('1.2万') = {parse_count('1.2万')}")
    assert parse_count("2.1k") == 2_100
    print(f"  ✅ parse_count('2.1k') = {parse_count('2.1k')}")
    assert parse_count("328") == 328
    print(f"  ✅ parse_count('328') = {parse_count('328')}")
    assert parse_count(None) == 0
    print(f"  ✅ parse_count(None) = {parse_count(None)}")


def test_xiaohongshu_image_urls_are_upgraded_to_https():
    """验证小红书图片 URL 从 http 自动升级为 https"""
    print("\n🔍 测试: 小红书图片 URL http → https 升级")
    result = normalize_search(
        {
            "items": [
                {
                    "model_type": "note",
                    "id": "note-http-image",
                    "note_card": {
                        "display_title": "图片协议测试",
                        "image_list": [
                            {
                                "url_default": (
                                    "http://sns-webpic-qc.xhscdn.com/example.webp"
                                    "?imageView2/2/w/540"
                                )
                            }
                        ],
                    },
                }
            ]
        },
        keyword="测试",
        page=1,
    )

    assert result.items[0].cover_url == (
        "https://sns-webpic-qc.xhscdn.com/example.webp?imageView2/2/w/540"
    )
    print("  ✅ 封面 URL 已升级为 https:")
    print(f"     {result.items[0].cover_url}")


def test_normalize_search_filters_non_note_items():
    """验证搜索结果归一化正确过滤非笔记类型条目"""
    print("\n🔍 测试: 搜索结果归一化 — 过滤非笔记类型")
    result = normalize_search(load_fixture("search.json"), keyword="测试产品", page=1)

    assert result.keyword == "测试产品"
    assert result.has_more is True
    assert len(result.items) == 1
    note = result.items[0]
    assert note.note_id == "note-001"
    assert note.note_type == "image"
    assert note.stats.likes == 12_000
    assert note.stats.collects == 2_100
    assert "xsec_token=fixture-token" in note.web_url
    print(f"  ✅ 关键词: {result.keyword}")
    print(f"  ✅ 有更多结果: {result.has_more}")
    print(f"  ✅ 过滤后条目数: {len(result.items)}")
    print(f"  ✅ 笔记 ID: {note.note_id}, 类型: {note.note_type}")
    print(f"  ✅ 点赞: {note.stats.likes}, 收藏: {note.stats.collects}")


def test_normalize_detail_keeps_gallery_tags_and_requested_url():
    """验证详情归一化保留图库、标签和请求 URL"""
    print("\n🔍 测试: 详情归一化 — 保留图库/标签/请求 URL")
    requested_url = (
        "https://www.xiaohongshu.com/explore/note-001"
        "?xsec_token=fixture-token&xsec_source=pc_search"
    )
    result = normalize_detail(load_fixture("detail.json"), requested_url=requested_url)

    assert result.web_url == requested_url
    assert result.description.startswith("优点和不足")
    assert result.image_urls == [
        "https://sns-img.example.com/1.jpg",
        "https://sns-img.example.com/2.jpg",
    ]
    assert result.tags == ["真实测评", "产品体验"]
    assert result.stats.shares == 88
    print("  ✅ web_url 与请求 URL 一致")
    print(f"  ✅ 描述前缀: {result.description[:20]}...")
    print(f"  ✅ 图片数量: {len(result.image_urls)}")
    print(f"  ✅ 标签: {result.tags}")
    print(f"  ✅ 分享数: {result.stats.shares}")
