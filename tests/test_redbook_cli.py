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
    assert prefix[1].replace("\\", "/").endswith(
        "node_modules/@lucasygu/redbook/dist/cli.js"
    )


def test_informational_cookie_log_is_not_mapped_to_unauthorized():
    cli = make_cli()

    error = cli._map_cli_error(
        "Using saved cookie file: cookies.chrome.json\n"
        "'xsec_source' is not recognized as an internal or external command"
    )

    assert error.code == "REDBOOK_COMMAND_FAILED"
    assert error.status_code == 502


def test_captcha_is_mapped_to_rate_limit_response():
    cli = make_cli()

    error = cli._map_cli_error("Error: Captcha required: type=216, uuid=fixture")

    assert error.code == "CAPTCHA_REQUIRED"
    assert error.status_code == 429


@pytest.mark.asyncio
async def test_configured_cookie_file_is_passed_to_redbook(monkeypatch, tmp_path):
    cookie_file = tmp_path / "cookies.json"
    cookie_file.write_text('{"version":1,"platform":"xhs","cookies":{}}', encoding="utf-8")
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


@pytest.mark.asyncio
async def test_missing_configured_cookie_file_is_reported(tmp_path):
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


@pytest.mark.asyncio
async def test_run_uses_threaded_subprocess_and_parses_json(monkeypatch):
    cli = make_cli()
    captured: list[list[str]] = []

    def fake_run(command: list[str], env: dict[str, str]):
        captured.append(command)
        assert env["NO_COLOR"] == "1"
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


@pytest.mark.asyncio
async def test_timeout_is_mapped_to_api_error(monkeypatch):
    cli = make_cli()

    def fake_run(command: list[str], env: dict[str, str]):
        raise subprocess.TimeoutExpired(command, timeout=1)

    monkeypatch.setattr(cli, "_run_process", fake_run)

    with pytest.raises(RedbookError) as error:
        await cli.whoami()

    assert error.value.code == "REDBOOK_TIMEOUT"
    assert error.value.status_code == 504
