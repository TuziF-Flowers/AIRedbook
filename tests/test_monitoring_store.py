from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.models import InteractionSnapshot, MonitoringTask
from app.services.monitoring_store import MonitoringArchiveError, MonitoringStore


def make_task() -> MonitoringTask:
    now = datetime(2026, 7, 25, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    return MonitoringTask(
        task_id="task-1",
        note_id="note-1",
        web_url="https://www.xiaohongshu.com/explore/note-1",
        title="测试笔记",
        created_at=now,
        monitoring_starts_at=now,
        monitoring_ends_on=now.date(),
        snapshots=[InteractionSnapshot(collected_at=now, likes=12, collects=3, comments=1)],
    )


def test_store_creates_versioned_archive_and_reloads_task(tmp_path):
    store = MonitoringStore(tmp_path / "monitoring.json")
    store.upsert(make_task())

    assert (tmp_path / "monitoring.json").exists()
    loaded = store.load()
    assert loaded.version == 1
    assert loaded.tasks[0].note_id == "note-1"
    assert loaded.tasks[0].snapshots[0].likes == 12


def test_store_upsert_replaces_same_task_without_duplicate(tmp_path):
    store = MonitoringStore(tmp_path / "monitoring.json")
    task = make_task()
    store.upsert(task)
    task.last_error = "登录失效"
    store.upsert(task)

    assert len(store.load().tasks) == 1
    assert store.load().tasks[0].last_error == "登录失效"


def test_store_upsert_keeps_one_task_for_the_same_note_id(tmp_path):
    store = MonitoringStore(tmp_path / "monitoring.json")
    original = make_task()
    duplicate = original.model_copy(update={"task_id": "task-2"})

    store.upsert(original)
    stored = store.upsert(duplicate)

    assert stored.task_id == "task-1"
    assert [task.task_id for task in store.load().tasks] == ["task-1"]


def test_monitoring_models_reject_naive_timestamps():
    with pytest.raises(ValueError, match="时区"):
        InteractionSnapshot(
            collected_at=datetime(2026, 7, 25, 10, 0),
            likes=12,
            collects=3,
            comments=1,
        )


def test_store_deletes_task(tmp_path):
    store = MonitoringStore(tmp_path / "monitoring.json")
    store.upsert(make_task())

    assert store.delete("task-1") is True
    assert store.load().tasks == []
    assert store.delete("task-1") is False


def test_store_rejects_corrupt_existing_archive(tmp_path):
    path = tmp_path / "monitoring.json"
    path.write_text("not-json", encoding="utf-8")

    with pytest.raises(MonitoringArchiveError, match="本地监测档案"):
        MonitoringStore(path).load()
