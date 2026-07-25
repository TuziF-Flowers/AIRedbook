from __future__ import annotations

import asyncio
import sys
from urllib.parse import urlparse

from app.config import settings
from app.main import image_proxy
from app.services.normalizer import normalize_detail, normalize_search
from app.services.redbook_cli import RedbookCLI


async def main() -> int:
    keyword = sys.argv[1] if len(sys.argv) > 1 else "AI眼镜"
    client = RedbookCLI(settings)
    search_raw = await client.search(
        keyword,
        page=1,
        sort="general",
        note_type="all",
    )
    search = normalize_search(search_raw, keyword=keyword, page=1)
    if not search.items:
        print("Search returned no notes.")
        return 2

    note = search.items[0]
    detail_raw = await client.read_note(note.web_url)
    detail = normalize_detail(detail_raw, requested_url=note.web_url)
    image_hosts = sorted(
        {
            urlparse(url).hostname or ""
            for url in detail.image_urls
            if urlparse(url).hostname
        }
    )

    print(f"Cookie file: {client.cookie_file.name if client.cookie_file else '(browser)'}")
    print(f"Search notes: {len(search.items)}")
    print(f"Search cover available: {'yes' if note.cover_url else 'no'}")
    print(f"Detail loaded: {'yes' if detail.description else 'no'}")
    print(f"Detail images: {len(detail.image_urls)}")
    print(f"Image hosts: {', '.join(image_hosts) or '(none)'}")
    if detail.image_urls:
        image_response = await image_proxy(detail.image_urls[0])
        print(f"Image proxy status: {image_response.status_code}")
        print(f"Image proxy type: {image_response.media_type}")
        print(f"Image proxy bytes: {len(image_response.body)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
