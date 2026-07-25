from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress
from datetime import datetime, time, timedelta
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.models import InteractionSnapshot, MonitoringTask
from app.services.monitoring_store import MonitoringStore
from app.services.normalizer import normalize_detail

ASIA_SHANGHAI = ZoneInfo("Asia/Shanghai")
MONITORING_DAYS = 30


def is_due(task: MonitoringTask, now: datetime) -> bool:
    today = now.astimezone(ASIA_SHANGHAI).date()
    return today <= task.monitoring_ends_on and not any(
        snapshot.collected_at.astimezone(ASIA_SHANGHAI).date() == today
        for snapshot in task.snapshots
    )


class MonitoringService:
    def __init__(
        self,
        client: Any,
        store: MonitoringStore,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.client = client
        self.store = store
        self.now = now or (lambda: datetime.now(ASIA_SHANGHAI))
        self._scheduler_task: asyncio.Task[None] | None = None
        self._task_locks: dict[str, asyncio.Lock] = {}

    async def create(self, web_url: str) -> tuple[MonitoringTask, bool]:
        existing = self.store.find_by_web_url(web_url)
        if existing:
            return existing, False

        try:
            detail = normalize_detail(
                await self.client.read_note(web_url), requested_url=web_url
            )
        except Exception as error:
            return self._create_pending_task(web_url, error), True

        existing = self.store.find_by_note_id(detail.note_id)
        if existing:
            return existing, False

        now = self.now()
        task = MonitoringTask(
            task_id=str(uuid4()),
            note_id=detail.note_id,
            web_url=web_url,
            title=detail.title,
            cover_url=detail.cover_url,
            created_at=now,
            monitoring_starts_at=now,
            monitoring_ends_on=now.astimezone(ASIA_SHANGHAI).date()
            + timedelta(days=MONITORING_DAYS - 1),
        )
        return await self._collect(task, detail=detail), True

    def _create_pending_task(self, web_url: str, error: Exception) -> MonitoringTask:
        now = self.now()
        task = MonitoringTask(
            task_id=str(uuid4()),
            note_id=str(uuid4()),
            web_url=web_url,
            title="待获取笔记信息",
            created_at=now,
            monitoring_starts_at=now,
            monitoring_ends_on=now.astimezone(ASIA_SHANGHAI).date()
            + timedelta(days=MONITORING_DAYS - 1),
            last_error=str(error),
            last_error_at=now,
        )
        return self.store.upsert(task)

    async def refresh(self, task_id: str) -> MonitoringTask:
        async with self._task_lock(task_id):
            task = self.get(task_id)
            now = self.now()
            if now.astimezone(ASIA_SHANGHAI).date() > task.monitoring_ends_on:
                return task
            return await self._collect(task)

    def list_tasks(self) -> list[MonitoringTask]:
        return sorted(self.store.load().tasks, key=lambda task: task.created_at, reverse=True)

    def get(self, task_id: str) -> MonitoringTask:
        for task in self.store.load().tasks:
            if task.task_id == task_id:
                return task
        raise KeyError(task_id)

    async def delete(self, task_id: str) -> bool:
        async with self._task_lock(task_id):
            return self.store.delete(task_id)

    def _task_lock(self, task_id: str) -> asyncio.Lock:
        if task_id not in self._task_locks:
            self._task_locks[task_id] = asyncio.Lock()
        return self._task_locks[task_id]

    async def _collect(self, task: MonitoringTask, *, detail: Any | None = None) -> MonitoringTask:
        now = self.now()
        try:
            detail = detail or normalize_detail(
                await self.client.read_note(task.web_url), requested_url=task.web_url
            )
            duplicate = self.store.find_by_note_id(detail.note_id)
            if duplicate and duplicate.task_id != task.task_id:
                self.store.delete(task.task_id)
                return duplicate

            task.note_id = detail.note_id
            task.title = detail.title
            task.cover_url = detail.cover_url
            snapshot = InteractionSnapshot(
                collected_at=now,
                likes=detail.stats.likes,
                collects=detail.stats.collects,
                comments=detail.stats.comments,
            )
            today = now.astimezone(ASIA_SHANGHAI).date()
            task.snapshots = [
                current
                for current in task.snapshots
                if current.collected_at.astimezone(ASIA_SHANGHAI).date() != today
            ]
            task.snapshots.append(snapshot)
            task.last_collected_at = now
            task.last_error = None
            task.last_error_at = None
        except Exception as error:
            task.last_error = str(error)
            task.last_error_at = now
        return self.store.upsert(task)

    async def collect_due(self) -> None:
        now = self.now()
        for task in self.list_tasks():
            if not is_due(task, now):
                continue
            try:
                await self.refresh(task.task_id)
            except Exception:
                continue

    async def start_scheduler(self) -> None:
        if self._scheduler_task is None or self._scheduler_task.done():
            self._scheduler_task = asyncio.create_task(self._run_scheduler())

    async def stop_scheduler(self) -> None:
        if self._scheduler_task is None:
            return
        self._scheduler_task.cancel()
        with suppress(asyncio.CancelledError):
            await self._scheduler_task
        self._scheduler_task = None

    async def _run_scheduler(self) -> None:
        await self.collect_due()
        while True:
            await asyncio.sleep(self._seconds_until_next_collection())
            await self.collect_due()

    def _seconds_until_next_collection(self) -> float:
        now = self.now().astimezone(ASIA_SHANGHAI)
        next_run = datetime.combine(now.date(), time(10), tzinfo=ASIA_SHANGHAI)
        if now >= next_run:
            next_run += timedelta(days=1)
        return (next_run - now).total_seconds()
