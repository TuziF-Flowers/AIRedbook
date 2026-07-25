from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any
from urllib.parse import urlencode, urlsplit, urlunsplit

from app.models import Author, NoteDetail, NoteStats, NoteSummary, SearchResponse


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _first(mapping: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value is not None and value != "":
            return value
    return default


def _text(value: Any, default: str = "") -> str:
    return default if value is None else str(value).strip()


def _normalize_image_url(value: str) -> str | None:
    if not value.startswith(("http://", "https://")):
        return None
    parsed = urlsplit(value)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme == "http" and (
        hostname == "xhscdn.com"
        or hostname.endswith(".xhscdn.com")
        or hostname == "xiaohongshu.com"
        or hostname.endswith(".xiaohongshu.com")
    ):
        return urlunsplit(("https", parsed.netloc, parsed.path, parsed.query, parsed.fragment))
    return value


def parse_count(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return max(0, int(value))
    text = _text(value).replace(",", "").replace("+", "")
    if not text:
        return 0
    match = re.match(r"^([\d.]+)\s*([万千wk]?)", text, flags=re.IGNORECASE)
    if not match:
        return 0
    number = float(match.group(1))
    unit = match.group(2).lower()
    multiplier = {"万": 10_000, "千": 1_000, "w": 10_000, "k": 1_000}.get(unit, 1)
    return max(0, int(number * multiplier))


def _url_from_image(value: Any) -> str | None:
    if isinstance(value, str):
        return _normalize_image_url(value)
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, Mapping)):
        for candidate in value:
            url = _url_from_image(candidate)
            if url:
                return url
        return None

    image = _dict(value)
    direct = _first(
        image,
        "url_default",
        "urlDefault",
        "url_pre",
        "urlPre",
        "url",
        "trace_id",
    )
    if isinstance(direct, str):
        return _normalize_image_url(direct)

    for list_key in ("info_list", "infoList", "url_list", "urlList"):
        candidates = image.get(list_key)
        if isinstance(candidates, Iterable) and not isinstance(candidates, (str, bytes)):
            for candidate in candidates:
                url = _url_from_image(candidate)
                if url:
                    return url
    return None


def _note_type(card: Mapping[str, Any]) -> str:
    raw = _text(_first(card, "type", "note_type", "noteType")).lower()
    if raw in {"normal", "image", "images", "图文"}:
        return "image"
    if raw in {"video", "视频"}:
        return "video"
    if card.get("video"):
        return "video"
    return "unknown"


def _author(card: Mapping[str, Any]) -> Author:
    user = _dict(_first(card, "user", "author", default={}))
    return Author(
        id=_text(_first(user, "user_id", "userId", "id")),
        nickname=_text(_first(user, "nickname", "nick_name", "name"), "未知作者"),
        avatar_url=_url_from_image(_first(user, "avatar", "avatar_url", "avatarUrl")),
    )


def _stats(card: Mapping[str, Any]) -> NoteStats:
    info = _dict(_first(card, "interact_info", "interactInfo", "stats", default={}))
    return NoteStats(
        likes=parse_count(_first(info, "liked_count", "likedCount", "likes")),
        comments=parse_count(_first(info, "comment_count", "commentCount", "comments")),
        collects=parse_count(
            _first(info, "collected_count", "collectedCount", "collects", "favorites")
        ),
        shares=parse_count(
            _first(info, "share_count", "shared_count", "shareCount", "shares")
        ),
    )


def _web_url(item: Mapping[str, Any], card: Mapping[str, Any], note_id: str) -> str:
    existing = _first(
        item,
        "webUrl",
        "web_url",
        default=_first(card, "webUrl", "web_url"),
    )
    if isinstance(existing, str) and existing.startswith(("http://", "https://")):
        return existing

    token = _text(_first(item, "xsec_token", "xsecToken", default=card.get("xsec_token")))
    base = f"https://www.xiaohongshu.com/explore/{note_id}"
    if not token:
        return base
    return f"{base}?{urlencode({'xsec_token': token, 'xsec_source': 'pc_search'})}"


def normalize_summary(item: Mapping[str, Any]) -> NoteSummary | None:
    card = _dict(_first(item, "note_card", "noteCard", "note", default=item))
    note_id = _text(
        _first(
            card,
            "note_id",
            "noteId",
            "id",
            default=_first(item, "id", "note_id", "noteId"),
        )
    )
    if not note_id:
        return None

    cover = _first(card, "cover", "cover_url", "coverUrl")
    cover_url = _url_from_image(cover) or _url_from_image(
        _first(card, "image_list", "imageList", "images")
    )
    title = _text(_first(card, "display_title", "displayTitle", "title"), "无标题")
    return NoteSummary(
        note_id=note_id,
        title=title,
        note_type=_note_type(card),
        cover_url=cover_url,
        web_url=_web_url(item, card, note_id),
        author=_author(card),
        stats=_stats(card),
    )


def normalize_search(raw: Any, *, keyword: str, page: int) -> SearchResponse:
    payload = _dict(raw)
    raw_items = _first(payload, "items", "notes", default=[])
    summaries: list[NoteSummary] = []
    if isinstance(raw_items, list):
        for raw_item in raw_items:
            if not isinstance(raw_item, Mapping):
                continue
            model_type = _text(_first(raw_item, "model_type", "modelType")).lower()
            if model_type and model_type not in {"note", "note_card"}:
                continue
            summary = normalize_summary(raw_item)
            if summary:
                summaries.append(summary)

    return SearchResponse(
        keyword=keyword,
        page=page,
        page_size=20,
        has_more=bool(_first(payload, "has_more", "hasMore", default=len(summaries) >= 20)),
        items=summaries,
    )


def normalize_detail(raw: Any, *, requested_url: str) -> NoteDetail:
    payload = _dict(raw)
    card = _dict(_first(payload, "note_card", "noteCard", "note", default=payload))
    summary = normalize_summary({**payload, "note_card": card})
    if not summary:
        raise ValueError("笔记详情缺少 note_id")

    image_values = _first(card, "image_list", "imageList", "images", default=[])
    image_urls: list[str] = []
    if isinstance(image_values, list):
        for image in image_values:
            url = _url_from_image(image)
            if url and url not in image_urls:
                image_urls.append(url)
    if not image_urls and summary.cover_url:
        image_urls.append(summary.cover_url)

    tag_values = _first(card, "tag_list", "tagList", "tags", default=[])
    tags: list[str] = []
    if isinstance(tag_values, list):
        for tag in tag_values:
            name = _text(_first(tag, "name", "title")) if isinstance(tag, Mapping) else _text(tag)
            if name and name not in tags:
                tags.append(name)

    return NoteDetail(
        **summary.model_dump(exclude={"web_url"}),
        web_url=requested_url or summary.web_url,
        description=_text(_first(card, "desc", "description", "content")),
        image_urls=image_urls,
        tags=tags,
        published_at=_first(card, "time", "publish_time", "publishedAt"),
        ip_location=_text(_first(card, "ip_location", "ipLocation")) or None,
    )
