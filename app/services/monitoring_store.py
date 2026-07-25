from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from pydantic import ValidationError

from app.models import MonitoringArchive, MonitoringTask

ARCHIVE_ERROR_MESSAGE = "本地监测档案无法读取，请先备份并检查 data/monitoring.json。"


class MonitoringArchiveError(RuntimeError):
    pass


def _is_pending_note_id(note_id: str) -> bool:
    try:
        UUID(note_id)
    except ValueError:
        return False
    return True


class MonitoringStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> MonitoringArchive:
        if not self.path.exists():
            return MonitoringArchive()

        try:
            return MonitoringArchive.model_validate_json(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValidationError) as error:
            raise MonitoringArchiveError(ARCHIVE_ERROR_MESSAGE) from error

    def save(self, archive: MonitoringArchive) -> None:
        archive = MonitoringArchive.model_validate(archive.model_dump())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_suffix(".json.tmp")
        temporary_path.write_text(
            json.dumps(archive.model_dump(mode="json"), ensure_ascii=False),
            encoding="utf-8",
        )
        temporary_path.replace(self.path)

    def find_by_note_id(self, note_id: str) -> MonitoringTask | None:
        return next((task for task in self.load().tasks if task.note_id == note_id), None)

    def upsert(self, task: MonitoringTask) -> MonitoringTask:
        archive = self.load()
        for index, existing_task in enumerate(archive.tasks):
            if existing_task.task_id == task.task_id:
                archive.tasks[index] = task
                break
            if (
                existing_task.note_id == task.note_id
                and not _is_pending_note_id(task.note_id)
            ):
                return existing_task
        else:
            archive.tasks.append(task)
        self.save(archive)
        return task

    def delete(self, task_id: str) -> bool:
        archive = self.load()
        tasks = [task for task in archive.tasks if task.task_id != task_id]
        if len(tasks) == len(archive.tasks):
            return False
        archive.tasks = tasks
        self.save(archive)
        return True
