from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT, Settings


class RedbookError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        hint: str | None = None,
        status_code: int = 502,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint
        self.status_code = status_code


class RedbookCLI:
    def __init__(self, config: Settings) -> None:
        self.config = config
        self._semaphore = asyncio.Semaphore(max(1, config.max_concurrency))
        self.executable = self._find_executable(config.redbook_executable)
        self.cookie_file = self._find_cookie_file(config.redbook_cookie_file)

    @staticmethod
    def _find_executable(configured: str | None) -> str | None:
        if configured:
            return configured

        local_names = ["redbook.cmd", "redbook"] if os.name == "nt" else ["redbook"]
        for name in local_names:
            candidate = PROJECT_ROOT / "node_modules" / ".bin" / name
            if candidate.is_file():
                return str(candidate)

        return shutil.which("redbook") or shutil.which("redbook.cmd")

    @staticmethod
    def _find_cookie_file(configured: str | None) -> Path | None:
        if configured:
            configured_path = Path(os.path.expandvars(configured)).expanduser()
            return configured_path if configured_path.is_file() else None

        candidates = (
            Path.home() / ".redbook" / "cookies.chrome.json",
            Path.home() / ".redbook" / "cookies.json",
            PROJECT_ROOT / ".redbook" / "cookies.json",
        )
        return next((path for path in candidates if path.is_file()), None)

    @property
    def is_installed(self) -> bool:
        return bool(self.executable)

    @property
    def has_cookie_file(self) -> bool:
        return self.cookie_file is not None

    def _command_prefix(self) -> list[str]:
        executable = str(self.executable)
        if Path(executable).suffix.lower() in {".cmd", ".bat"}:
            node = shutil.which("node")
            cli_module = (
                PROJECT_ROOT
                / "node_modules"
                / "@lucasygu"
                / "redbook"
                / "dist"
                / "cli.js"
            )
            if node and cli_module.is_file():
                return [node, str(cli_module)]
        return [executable]

    def _run_process(
        self,
        command: list[str],
        env: dict[str, str],
    ) -> subprocess.CompletedProcess[bytes]:
        creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        return subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            timeout=self.config.command_timeout_seconds,
            creationflags=creation_flags,
        )

    async def _run(self, *args: str) -> Any:
        if not self.executable:
            raise RedbookError(
                "REDBOOK_NOT_INSTALLED",
                "没有找到 redbook CLI。",
                hint="请先在项目目录执行 npm install。",
                status_code=503,
            )

        self.cookie_file = self._find_cookie_file(self.config.redbook_cookie_file)
        env = os.environ.copy()
        env["NO_COLOR"] = "1"
        if self.cookie_file:
            env["REDBOOK_COOKIE_FILE"] = str(self.cookie_file)
        elif self.config.redbook_cookie_file:
            raise RedbookError(
                "COOKIE_FILE_NOT_FOUND",
                "配置的本地 Cookie 文件不存在。",
                hint="请检查 REDBOOK_COOKIE_FILE 路径。",
                status_code=503,
            )

        command = [*self._command_prefix(), *args, "--json"]
        if self.config.redbook_platform:
            command.extend(["--platform", self.config.redbook_platform])

        async with self._semaphore:
            try:
                completed = await asyncio.to_thread(self._run_process, command, env)
            except subprocess.TimeoutExpired as exc:
                raise RedbookError(
                    "REDBOOK_TIMEOUT",
                    "小红书请求超时，请稍后重试。",
                    status_code=504,
                ) from exc
            except OSError as exc:
                raise RedbookError(
                    "REDBOOK_START_FAILED",
                    "无法启动 redbook CLI。",
                    hint="请确认 Node.js 22+ 和 redbook 已正确安装。",
                    status_code=503,
                ) from exc

        stderr_text = completed.stderr.decode("utf-8", errors="replace").strip()
        stdout_text = completed.stdout.decode("utf-8", errors="replace").strip()

        if completed.returncode != 0:
            raise self._map_cli_error(stderr_text)

        if not stdout_text:
            raise RedbookError(
                "EMPTY_RESPONSE",
                "redbook 没有返回数据。",
                hint="请检查登录状态后重试。",
            )

        try:
            return json.loads(stdout_text)
        except json.JSONDecodeError as exc:
            raise RedbookError(
                "INVALID_RESPONSE",
                "redbook 返回了无法解析的数据。",
                hint="可能是 CLI 版本变化，请检查服务日志。",
            ) from exc

    def _map_cli_error(self, stderr: str) -> RedbookError:
        lower = stderr.lower()
        if "captcha required" in lower or "type=216" in lower:
            return RedbookError(
                "CAPTCHA_REQUIRED",
                "小红书要求完成验证码验证。",
                hint="请在 Chrome 打开小红书完成验证，稍后再搜索。",
                status_code=429,
            )
        if "session expired" in lower or "re-login" in lower:
            return RedbookError(
                "SESSION_EXPIRED",
                "小红书登录状态已过期。",
                hint="请在 Chrome 中重新登录小红书，并更新本地 Cookie 文件后重试。",
                status_code=401,
            )
        cookie_errors = (
            "no 'a1' cookie",
            "missing or incomplete login cookies",
            "cookie file not found",
            "could not read cookie file",
        )
        if "web_session" in lower or any(message in lower for message in cookie_errors):
            hint = (
                "本地 Cookie 文件可能已过期，请在 Chrome 登录小红书后更新该文件。"
                if self.cookie_file
                else "请将 Chrome 中的小红书登录信息保存为 redbook Cookie 文件。"
            )
            return RedbookError(
                "COOKIE_UNAVAILABLE",
                "未能读取小红书登录信息。",
                hint=hint,
                status_code=401,
            )
        return RedbookError(
            "REDBOOK_COMMAND_FAILED",
            "redbook 请求失败。",
            hint="请检查登录状态与网络连接后重试。",
        )

    async def whoami(self) -> Any:
        return await self._run("whoami")

    async def search(
        self,
        keyword: str,
        *,
        page: int,
        sort: str,
        note_type: str,
    ) -> Any:
        return await self._run(
            "search",
            keyword,
            "--page",
            str(page),
            "--sort",
            sort,
            "--type",
            note_type,
        )

    async def read_note(self, web_url: str) -> Any:
        return await self._run("read", web_url)
