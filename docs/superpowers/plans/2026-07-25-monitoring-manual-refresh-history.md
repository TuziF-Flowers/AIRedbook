# 手动刷新保留同日历史 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让同一天内每次成功“立即更新”都保留独立互动快照。

**Architecture:** `MonitoringService._collect` 目前在写入快照前删除同一北京时间日期的快照。移除这段替换逻辑，使手动刷新追加快照；`is_due` 保持不变，因此定时任务仍检测当天是否已有快照并每日最多运行一次。前端已按完整时间排序快照，无需改动。

**Tech Stack:** Python 3.14、FastAPI、Pydantic、pytest。

## Global Constraints

- 仅记录点赞、收藏、评论，保留本地 JSON 存储结构。
- 手动刷新成功时追加快照；失败时不追加快照。
- `is_due` 的同日去重规则不变，定时任务每天最多采集一次。
- 使用 `.venv/bin/python -m pytest` 和 `.venv/bin/ruff check .` 验证。

---

### Task 1: 追加同日手动刷新快照

**Files:**
- Modify: `tests/test_monitoring_service.py:91-106`
- Modify: `app/services/monitoring_service.py:132-138`

**Interfaces:**
- Consumes: `MonitoringService.refresh(task_id: str) -> MonitoringTask`。
- Produces: `MonitoringTask.snapshots` 以采集顺序保留同日多次成功刷新结果。

- [x] **Step 1: Write the failing test**

将既有同日刷新用例替换为以下断言：

```python
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
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest -q tests/test_monitoring_service.py::test_refresh_appends_a_snapshot_for_each_same_day_update`

Expected: FAIL because the current service removes the first same-day snapshot before appending the refreshed value.

- [x] **Step 3: Write minimal implementation**

Delete only the current-day filtering assignment in `_collect`; keep the append operation and all error handling:

```python
task.snapshots.append(snapshot)
```

Do not modify `is_due`, because it governs scheduled collection rather than manual refresh.

- [x] **Step 4: Run focused tests to verify behavior**

Run: `.venv/bin/python -m pytest -q tests/test_monitoring_service.py`

Expected: PASS, including `test_collect_due_skips_expired_task_and_fills_missing_current_day`, which proves automatic same-day collection remains deduplicated.

- [x] **Step 5: Run full verification**

Run:

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
node --check app/static/app.js
```

Expected: all tests and checks pass.

- [x] **Step 6: Commit**

```bash
git add app/services/monitoring_service.py tests/test_monitoring_service.py
git commit -m "feat: retain same-day monitoring snapshots"
```
