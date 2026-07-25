from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def find_command(*names: str) -> str | None:
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    return None


def version(command: list[str]) -> str:
    try:
        result = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            capture_output=True,
            check=False,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "不可用"
    return (result.stdout or result.stderr).strip().splitlines()[0]


def main() -> int:
    local_redbook = PROJECT_ROOT / "node_modules" / ".bin" / (
        "redbook.cmd" if sys.platform == "win32" else "redbook"
    )
    redbook = str(local_redbook) if local_redbook.is_file() else find_command(
        "redbook", "redbook.cmd"
    )
    node = find_command("node", "node.exe")

    checks = [
        ("Python", sys.executable, sys.version.split()[0]),
        ("Node.js", node, version([node, "--version"]) if node else "未找到"),
        (
            "redbook",
            redbook,
            version([redbook, "--version"]) if redbook else "未找到，请执行 npm install",
        ),
    ]

    width = max(len(label) for label, _, _ in checks)
    print("红研 Demo 环境检查")
    print("-" * 44)
    for label, path, detected_version in checks:
        marker = "[OK]" if path else "[--]"
        print(f"{marker} {label:<{width}}  {detected_version}")

    return 0 if node and redbook else 1


if __name__ == "__main__":
    raise SystemExit(main())

