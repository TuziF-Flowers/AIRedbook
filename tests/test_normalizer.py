from __future__ import annotations

import json
from pathlib import Path

from app.services.normalizer import normalize_detail, normalize_search, parse_count

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_count_supports_chinese_and_compact_units():
    assert parse_count("1.2万") == 12_000
    assert parse_count("2.1k") == 2_100
    assert parse_count("328") == 328
    assert parse_count(None) == 0


def test_xiaohongshu_image_urls_are_upgraded_to_https():
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


def test_normalize_search_filters_non_note_items():
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


def test_normalize_detail_keeps_gallery_tags_and_requested_url():
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
