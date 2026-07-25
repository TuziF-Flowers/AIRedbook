from __future__ import annotations

import getpass
import json
import os
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path


def _read_secret(name: str) -> str:
    value = getpass.getpass(f"{name}: ").strip()
    if not value:
        raise ValueError(f"{name} 不能为空")
    return value


def main() -> int:
    print("请从 Chrome 开发者工具的 Application > Cookies 中复制对应值。")
    print("输入内容不会显示在终端，也不会进入命令历史。")
    try:
        a1 = _read_secret("a1")
        web_session = _read_secret("web_session")
    except (EOFError, KeyboardInterrupt, ValueError) as exc:
        print(f"\n保存取消：{exc}")
        return 1

    target_dir = Path.home() / ".redbook"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "cookies.chrome.json"
    temporary = target.with_suffix(".json.tmp")
    payload = {
        "version": 1,
        "platform": "xhs",
        "createdAt": datetime.now(UTC).isoformat(),
        "cookies": {
            "a1": a1,
            "web_session": web_session,
        },
    }

    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with suppress(OSError):
        os.chmod(temporary, 0o600)
    os.replace(temporary, target)
    print(f"已保存到：{target}")
    print("应用下次请求会自动优先使用该文件。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
