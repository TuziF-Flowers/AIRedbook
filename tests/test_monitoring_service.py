from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.services.monitoring_service import MonitoringService
from app.services.monitoring_store import MonitoringStore


class FakeReader:
    def __init__(self, likes=100, error=None):
        self.likes = likes
        self.error = error

    async def read_note(self, web_url):
        if self.error:
            raise self.error
        return {
            "note_id": "note-fixture",
            "title": "已发布笔记",
            "type": "normal",
            "interact_info": {
                "liked_count": str(self.likes),
                "collected_count": "20",
                "comment_count": "5",
            },
        }


@pytest.mark.asyncio
async def test_create_collects_first_snapshot_and_deduplicates_note(tmp_path):
    now = datetime(2026, 7, 25, 9, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    service = MonitoringService(
        FakeReader(), MonitoringStore(tmp_path / "monitoring.json"), now=lambda: now
    )

    task, created = await service.create("https://www.xiaohongshu.com/explore/note-fixture")
    repeated, repeated_created = await service.create(
        "https://www.xiaohongshu.com/explore/note-fixture"
    )

    assert created is True
    assert task.snapshots[0].likes == 100
    assert repeated_created is False
    assert repeated.task_id == task.task_id


@pytest.mark.asyncio
async def test_failed_creation_keeps_task_without_zero_snapshot(tmp_path):
    now = datetime(2026, 7, 25, 9, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    reader = FakeReader(error=RuntimeError("登录失效"))
    service = MonitoringService(
        reader, MonitoringStore(tmp_path / "monitoring.json"), now=lambda: now
    )

    task, created = await service.create("https://www.xiaohongshu.com/explore/note-fixture")

    assert created is True
    assert task.snapshots == []
    assert task.last_error == "登录失效"


@pytest.mark.asyncio
async def test_refresh_keeps_one_snapshot_per_beijing_day(tmp_path):
    now = datetime(2026, 7, 25, 9, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    reader = FakeReader()
    service = MonitoringService(
        reader, MonitoringStore(tmp_path / "monitoring.json"), now=lambda: now
    )
    task, _ = await service.create("https://www.xiaohongshu.com/explore/note-fixture")
    reader.likes = 130

    refreshed = await service.refresh(task.task_id)

    assert len(refreshed.snapshots) == 1
    assert refreshed.snapshots[0].likes == 130


@pytest.mark.asyncio
async def test_collect_due_skips_expired_task_and_fills_missing_current_day(tmp_path):
    day_one = datetime(2026, 7, 1, 9, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    now = day_one + timedelta(days=1)
    service = MonitoringService(
        FakeReader(), MonitoringStore(tmp_path / "monitoring.json"), now=lambda: now
    )
    task, _ = await service.create("https://www.xiaohongshu.com/explore/note-fixture")
    task.monitoring_ends_on = day_one.date()
    service.store.upsert(task)

    await service.collect_due()

    assert len(service.get(task.task_id).snapshots) == 1


@pytest.mark.asyncio
async def test_refresh_clears_failure_and_records_snapshot(tmp_path):
    now = datetime(2026, 7, 25, 9, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    reader = FakeReader(error=RuntimeError("验证码"))
    service = MonitoringService(
        reader, MonitoringStore(tmp_path / "monitoring.json"), now=lambda: now
    )
    task, _ = await service.create("https://www.xiaohongshu.com/explore/note-fixture")
    reader.error = None

    retried = await service.refresh(task.task_id)

    assert retried.last_error is None
    assert retried.snapshots[0].comments == 5
