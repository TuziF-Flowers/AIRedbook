import asyncio
import inspect
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.models import MonitoringTaskStatus
from app.services.monitoring_service import MonitoringService
from app.services.monitoring_store import MonitoringStore


class FakeReader:
    def __init__(self, likes=100, error=None):
        self.likes = likes
        self.error = error
        self.calls = 0

    async def read_note(self, web_url):
        self.calls += 1
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
    assert task.model_dump(mode="json")["status"] == MonitoringTaskStatus.ACTIVE
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
    assert task.status == MonitoringTaskStatus.ERROR


@pytest.mark.asyncio
async def test_repeated_failed_creation_reuses_task_by_normalized_url(tmp_path):
    now = datetime(2026, 7, 25, 9, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    reader = FakeReader(error=RuntimeError("登录失效"))
    service = MonitoringService(
        reader, MonitoringStore(tmp_path / "monitoring.json"), now=lambda: now
    )

    first, first_created = await service.create(
        "https://www.xiaohongshu.com/explore/note-fixture/"
    )
    repeated, repeated_created = await service.create(
        "https://www.xiaohongshu.com/explore/note-fixture"
    )

    assert first_created is True
    assert repeated_created is False
    assert repeated.task_id == first.task_id
    assert reader.calls == 1


@pytest.mark.asyncio
async def test_refresh_appends_a_snapshot_for_each_same_day_update(tmp_path):
    now = datetime(2026, 7, 25, 9, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    reader = FakeReader()
    service = MonitoringService(
        reader, MonitoringStore(tmp_path / "monitoring.json"), now=lambda: now
    )
    task, _ = await service.create("https://www.xiaohongshu.com/explore/note-fixture")
    reader.likes = 130

    refreshed = await service.refresh(task.task_id)

    assert len(refreshed.snapshots) == 2
    assert [snapshot.likes for snapshot in refreshed.snapshots] == [100, 130]


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
async def test_refresh_expired_task_is_a_completed_noop(tmp_path):
    day_one = datetime(2026, 7, 1, 9, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    now = day_one + timedelta(days=1)
    reader = FakeReader()
    service = MonitoringService(
        reader, MonitoringStore(tmp_path / "monitoring.json"), now=lambda: now
    )
    task, _ = await service.create("https://www.xiaohongshu.com/explore/note-fixture")
    task.monitoring_ends_on = day_one.date()
    service.store.upsert(task)

    refreshed = await service.refresh(task.task_id)

    assert refreshed.status == MonitoringTaskStatus.COMPLETED
    assert reader.calls == 1
    assert len(refreshed.snapshots) == 1


@pytest.mark.asyncio
async def test_delete_during_in_flight_refresh_never_resurrects_task(tmp_path):
    now = datetime(2026, 7, 25, 9, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    service = MonitoringService(
        FakeReader(), MonitoringStore(tmp_path / "monitoring.json"), now=lambda: now
    )
    task, _ = await service.create("https://www.xiaohongshu.com/explore/note-fixture")

    class BlockingReader(FakeReader):
        def __init__(self):
            super().__init__(likes=130)
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def read_note(self, web_url):
            self.started.set()
            await self.release.wait()
            return await super().read_note(web_url)

    reader = BlockingReader()
    service.client = reader
    refresh_operation = asyncio.create_task(service.refresh(task.task_id))
    await reader.started.wait()

    async def delete_task():
        result = service.delete(task.task_id)
        return await result if inspect.isawaitable(result) else result

    delete_operation = asyncio.create_task(delete_task())
    await asyncio.sleep(0)
    reader.release.set()
    await asyncio.gather(refresh_operation, delete_operation)

    with pytest.raises(KeyError):
        service.get(task.task_id)


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
