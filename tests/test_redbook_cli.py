from __future__ import annotations

import subprocess

import pytest

from app.config import PROJECT_ROOT, Settings
from app.services.redbook_cli import RedbookCLI, RedbookError


def make_cli(*, timeout: float = 1) -> RedbookCLI:
    return RedbookCLI(
        Settings(
            redbook_executable="redbook",
            redbook_platform="xhs",
            command_timeout_seconds=timeout,
            max_concurrency=1,
        )
    )


def test_windows_cmd_wrapper_is_replaced_with_direct_node_command():
    """验证 Windows .cmd 包装器被替换为直接 node 调用"""
    print("\n🔍 测试: Windows .cmd 包装器 → 直接 node 命令替换")
    wrapper = PROJECT_ROOT / "node_modules" / ".bin" / "redbook.cmd"
    cli = RedbookCLI(
        Settings(
            redbook_executable=str(wrapper),
            redbook_platform="xhs",
            command_timeout_seconds=1,
            max_concurrency=1,
        )
    )

    prefix = cli._command_prefix()

    assert prefix[0].lower().endswith(("node", "node.exe"))
    print(f"  ✅ 命令前缀可执行文件: {prefix[0]}")
    assert prefix[1].replace("\\", "/").endswith(
        "node_modules/@lucasygu/redbook/dist/cli.js"
    )
    print(f"  ✅ 命令前缀脚本路径: ...{prefix[1][-50:]}")


def test_informational_cookie_log_is_not_mapped_to_unauthorized():
    """验证信息性 cookie 日志不会被错误映射为未授权错误"""
    print("\n🔍 测试: 信息性 cookie 日志不映射为 unauthorized")
    cli = make_cli()

    error = cli._map_cli_error(
        "Using saved cookie file: cookies.chrome.json\n"
        "'xsec_source' is not recognized as an internal or external command"
    )

    assert error.code == "REDBOOK_COMMAND_FAILED"
    assert error.status_code == 502
    print(f"  ✅ 错误码: {error.code} (预期: REDBOOK_COMMAND_FAILED)")
    print(f"  ✅ HTTP 状态码: {error.status_code} (预期: 502)")


def test_captcha_is_mapped_to_rate_limit_response():
    """验证验证码错误被正确映射为 429 限流响应"""
    print("\n🔍 测试: 验证码错误 → 429 限流响应映射")
    cli = make_cli()

    error = cli._map_cli_error("Error: Captcha required: type=216, uuid=fixture")

    assert error.code == "CAPTCHA_REQUIRED"
    assert error.status_code == 429
    print(f"  ✅ 错误码: {error.code} (预期: CAPTCHA_REQUIRED)")
    print(f"  ✅ HTTP 状态码: {error.status_code} (预期: 429)")


@pytest.mark.asyncio
async def test_configured_cookie_file_is_passed_to_redbook(monkeypatch, tmp_path):
    """验证配置的 cookie 文件被正确传递给 redbook 子进程"""
    print("\n🔍 测试: cookie 文件正确传递给 redbook 子进程")
    cookie_file = tmp_path / "cookies.json"
    cookie_file.write_text('{"version":1,"platform":"xhs","cookies":{}}', encoding="utf-8")
    print(f"  📁 创建临时 cookie 文件: {cookie_file.name}")
    cli = RedbookCLI(
        Settings(
            redbook_executable="redbook",
            redbook_cookie_file=str(cookie_file),
            redbook_platform="xhs",
            command_timeout_seconds=1,
            max_concurrency=1,
        )
    )

    def fake_run(command: list[str], env: dict[str, str]):
        assert env["REDBOOK_COOKIE_FILE"] == str(cookie_file)
        print("  ✅ 子进程环境变量 REDBOOK_COOKIE_FILE 已设置")
        return subprocess.CompletedProcess(
            command,
            returncode=0,
            stdout=b'{"nickname":"edge-user"}',
            stderr=b"",
        )

    monkeypatch.setattr(cli, "_run_process", fake_run)

    result = await cli.whoami()

    assert result == {"nickname": "edge-user"}
    assert cli.has_cookie_file is True
    print(f"  ✅ whoami 返回: {result}")
    print(f"  ✅ has_cookie_file = {cli.has_cookie_file}")


@pytest.mark.asyncio
async def test_missing_configured_cookie_file_is_reported(tmp_path):
    """验证缺失的 cookie 文件被正确报告为 503 错误"""
    print("\n🔍 测试: 缺失 cookie 文件 → 503 错误报告")
    cli = RedbookCLI(
        Settings(
            redbook_executable="redbook",
            redbook_cookie_file=str(tmp_path / "missing.json"),
            redbook_platform="xhs",
            command_timeout_seconds=1,
            max_concurrency=1,
        )
    )

    with pytest.raises(RedbookError) as error:
        await cli.whoami()

    assert error.value.code == "COOKIE_FILE_NOT_FOUND"
    assert error.value.status_code == 503
    print(f"  ✅ 捕获异常: {error.value.code} (预期: COOKIE_FILE_NOT_FOUND)")
    print(f"  ✅ HTTP 状态码: {error.value.status_code} (预期: 503)")


@pytest.mark.asyncio
async def test_run_uses_threaded_subprocess_and_parses_json(monkeypatch):
    """验证 CLI 使用线程化子进程执行并正确解析 JSON 输出"""
    print("\n🔍 测试: 线程化子进程执行 + JSON 解析")
    cli = make_cli()
    captured: list[list[str]] = []

    def fake_run(command: list[str], env: dict[str, str]):
        captured.append(command)
        assert env["NO_COLOR"] == "1"
        print(f"  📦 捕获命令: {' '.join(command)}")
        return subprocess.CompletedProcess(
            command,
            returncode=0,
            stdout=b'{"nickname":"fixture-user"}',
            stderr=b"",
        )

    monkeypatch.setattr(cli, "_run_process", fake_run)

    result = await cli.whoami()

    assert result == {"nickname": "fixture-user"}
    assert captured == [["redbook", "whoami", "--json", "--platform", "xhs"]]
    print(f"  ✅ whoami 返回: {result}")
    print(f"  ✅ 命令参数: {captured[0]}")


@pytest.mark.asyncio
async def test_timeout_is_mapped_to_api_error(monkeypatch):
    """验证子进程超时被映射为 504 API 错误"""
    print("\n🔍 测试: 子进程超时 → 504 API 错误映射")
    cli = make_cli()

    def fake_run(command: list[str], env: dict[str, str]):
        print(f"  ⏱️ 模拟超时: 命令 {' '.join(command)}")
        raise subprocess.TimeoutExpired(command, timeout=1)

    monkeypatch.setattr(cli, "_run_process", fake_run)

    with pytest.raises(RedbookError) as error:
        await cli.whoami()

    assert error.value.code == "REDBOOK_TIMEOUT"
    assert error.value.status_code == 504
    print(f"  ✅ 捕获异常: {error.value.code} (预期: REDBOOK_TIMEOUT)")
    print(f"  ✅ HTTP 状态码: {error.value.status_code} (预期: 504)")
