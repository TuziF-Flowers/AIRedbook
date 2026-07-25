# 发布效果监测 3.5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local 30-day Xiaohongshu/RedNote post monitoring feature with JSON persistence, scheduled interaction snapshots, and an interactive ECharts dashboard.

**Architecture:** Add a focused file store and monitoring service beside the existing redbook services. FastAPI owns the service lifecycle and exposes task CRUD/refresh APIs; the existing CLI and normalizer remain the only upstream reader. The existing vanilla JavaScript page gains a monitoring workspace that loads a locally served ECharts bundle.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, asyncio, JSON file storage, pytest, vanilla JavaScript/CSS, Apache ECharts.

## Global Constraints

- Persist all monitoring tasks and snapshots only in `data/monitoring.json`; replace the file atomically.
- A task represents exactly one public Xiaohongshu or RedNote note, uniquely identified by its note ID.
- Collect immediately on creation, then once per Asia/Shanghai calendar day at 10:00 for 30 days; startup may only fill a missing current-day snapshot.
- Store only likes, collects and comments. Do not create competitor, AI, share, view, rate or conversion features.
- On upstream failure, retain all old snapshots, record a readable error and allow future automatic/manual retries.
- Reuse `RedbookCLI.read_note` and `normalize_detail`; do not introduce Spring, Vue, a database or a CDN.
- Preserve the existing Chinese UI and light purple-blue visual system; new interactions must respect `prefers-reduced-motion`.

---

## File Structure

- `app/models.py` — API and persisted monitoring Pydantic models.
- `app/config.py` — configurable local monitoring JSON path.
- `app/services/monitoring_store.py` — versioned JSON archive load/save/delete, with atomic replacement.
- `app/services/monitoring_service.py` — note collection, error state transitions, due-task selection and scheduler lifecycle.
- `app/main.py` — monitoring lifecycle wiring, local ECharts static mount and five monitoring routes.
- `tests/test_monitoring_store.py` — persistence behavior and corrupt-file coverage.
- `tests/test_monitoring_service.py` — collection, retry, expiry and same-day behavior.
- `tests/test_api.py` — monitoring API integration with the existing fake redbook reader.
- `package.json`, `package-lock.json` — local ECharts dependency.
- `app/templates/index.html`, `app/static/app.js`, `app/static/styles.css` — task list and ECharts dashboard.
- `tests/test_monitoring_ui_assets.py` — regression checks for locally loaded chart assets and dashboard hooks.

## Task 1: Versioned monitoring models and JSON archive

**Files:**
- Create: `app/services/monitoring_store.py`
- Create: `tests/test_monitoring_store.py`
- Modify: `app/models.py`
- Modify: `app/config.py`

**Interfaces:**
- Produces `InteractionSnapshot`, `MonitoringTask`, `MonitoringTaskCreate`, `MonitoringArchive` and `MonitoringTaskStatus` models.
- Produces `MonitoringStore(path: Path)` with `load() -> MonitoringArchive`, `save(archive: MonitoringArchive) -> None`, `find_by_note_id(note_id: str) -> MonitoringTask | None`, `upsert(task: MonitoringTask) -> MonitoringTask`, and `delete(task_id: str) -> bool`.
- Produces `MonitoringArchiveError` for unreadable or invalid existing archives.

- [ ] **Step 1: Write failing archive tests**

Create `tests/test_monitoring_store.py` with a complete first behavior set:

```python
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
```

- [ ] **Step 2: Run the new tests and verify the expected red failure**

Run: `pytest tests/test_monitoring_store.py -v`

Expected: collection fails with `ModuleNotFoundError: No module named 'app.services.monitoring_store'`.

- [ ] **Step 3: Implement the models, configurable path and archive store**

Add the following model shape to `app/models.py`; timestamps must be timezone-aware ISO-8601 values in serialization:

```python
class MonitoringTaskStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ERROR = "error"


class InteractionSnapshot(BaseModel):
    collected_at: datetime
    likes: int = Field(ge=0)
    collects: int = Field(ge=0)
    comments: int = Field(ge=0)


class MonitoringTask(BaseModel):
    task_id: str
    note_id: str
    web_url: str
    title: str
    cover_url: str | None = None
    created_at: datetime
    monitoring_starts_at: datetime
    monitoring_ends_on: date
    snapshots: list[InteractionSnapshot] = Field(default_factory=list)
    last_collected_at: datetime | None = None
    last_error: str | None = None
    last_error_at: datetime | None = None


class MonitoringArchive(BaseModel):
    version: Literal[1] = 1
    tasks: list[MonitoringTask] = Field(default_factory=list)
```

In `app/config.py`, add `monitoring_data_file: Path = PROJECT_ROOT / "data" / "monitoring.json"`, overridden by `MONITORING_DATA_FILE` when set. In `MonitoringStore.save`, create the parent directory, serialize with `model_dump(mode="json")`, write UTF-8 JSON to `path.with_suffix(".json.tmp")`, then call `replace(self.path)`. `load` returns `MonitoringArchive()` for a missing file and converts `OSError`, `json.JSONDecodeError`, and Pydantic `ValidationError` into `MonitoringArchiveError("本地监测档案无法读取，请先备份并检查 data/monitoring.json。")` without writing the original.

- [ ] **Step 4: Run the focused tests and verify green**

Run: `pytest tests/test_monitoring_store.py -v`

Expected: all four tests pass.

- [ ] **Step 5: Run formatting/lint for the changed Python files**

Run: `ruff check app/models.py app/config.py app/services/monitoring_store.py tests/test_monitoring_store.py`

Expected: exit code 0.

- [ ] **Step 6: Commit the persistence slice**

```bash
git add app/models.py app/config.py app/services/monitoring_store.py tests/test_monitoring_store.py
git commit -m "feat: persist monitoring tasks in json"
```

## Task 2: Monitoring collection, retry and due-task service

**Files:**
- Create: `app/services/monitoring_service.py`
- Create: `tests/test_monitoring_service.py`
- Modify: `app/models.py`

**Interfaces:**
- Consumes `MonitoringStore`, `RedbookCLI`, `normalize_detail`, `MonitoringTask` and `InteractionSnapshot` from Task 1.
- Produces `MonitoringService(client, store, now)` with `create(web_url: str)`, `refresh(task_id: str)`, `list_tasks()`, `get(task_id: str)`, `delete(task_id: str)`, `collect_due()`, `start_scheduler()` and `stop_scheduler()`.
- `create` returns `(task, created)` where `created` is false for an existing note ID.

- [ ] **Step 1: Write failing monitoring service tests**

Create `tests/test_monitoring_service.py` with deterministic Asia/Shanghai time and a fake CLI:

```python
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
            "interact_info": {"liked_count": str(self.likes), "collected_count": "20", "comment_count": "5"},
        }


@pytest.mark.asyncio
async def test_create_collects_first_snapshot_and_deduplicates_note(tmp_path):
    now = datetime(2026, 7, 25, 9, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    service = MonitoringService(FakeReader(), MonitoringStore(tmp_path / "monitoring.json"), now=lambda: now)

    task, created = await service.create("https://www.xiaohongshu.com/explore/note-fixture")
    repeated, repeated_created = await service.create("https://www.xiaohongshu.com/explore/note-fixture")

    assert created is True
    assert task.snapshots[0].likes == 100
    assert repeated_created is False
    assert repeated.task_id == task.task_id


@pytest.mark.asyncio
async def test_failed_creation_keeps_task_without_zero_snapshot(tmp_path):
    now = datetime(2026, 7, 25, 9, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    reader = FakeReader(error=RuntimeError("登录失效"))
    service = MonitoringService(reader, MonitoringStore(tmp_path / "monitoring.json"), now=lambda: now)

    task, created = await service.create("https://www.xiaohongshu.com/explore/note-fixture")

    assert created is True
    assert task.snapshots == []
    assert task.last_error == "登录失效"


@pytest.mark.asyncio
async def test_refresh_keeps_one_snapshot_per_beijing_day(tmp_path):
    now = datetime(2026, 7, 25, 9, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    reader = FakeReader()
    service = MonitoringService(reader, MonitoringStore(tmp_path / "monitoring.json"), now=lambda: now)
    task, _ = await service.create("https://www.xiaohongshu.com/explore/note-fixture")
    reader.likes = 130

    refreshed = await service.refresh(task.task_id)

    assert len(refreshed.snapshots) == 1
    assert refreshed.snapshots[0].likes == 130


@pytest.mark.asyncio
async def test_collect_due_skips_expired_task_and_fills_missing_current_day(tmp_path):
    day_one = datetime(2026, 7, 1, 9, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    now = day_one + timedelta(days=1)
    service = MonitoringService(FakeReader(), MonitoringStore(tmp_path / "monitoring.json"), now=lambda: now)
    task, _ = await service.create("https://www.xiaohongshu.com/explore/note-fixture")
    task.monitoring_ends_on = day_one.date()
    service.store.upsert(task)

    await service.collect_due()

    assert len(service.get(task.task_id).snapshots) == 1
```

- [ ] **Step 2: Run the service tests and verify the expected red failure**

Run: `pytest tests/test_monitoring_service.py -v`

Expected: collection fails with `ModuleNotFoundError: No module named 'app.services.monitoring_service'`.

- [ ] **Step 3: Implement the service with the specified state transitions**

Implement these rules in `MonitoringService`:

```python
ASIA_SHANGHAI = ZoneInfo("Asia/Shanghai")
MONITORING_DAYS = 30

def is_due(task: MonitoringTask, now: datetime) -> bool:
    return now.astimezone(ASIA_SHANGHAI).date() <= task.monitoring_ends_on and not any(
        snapshot.collected_at.astimezone(ASIA_SHANGHAI).date()
        == now.astimezone(ASIA_SHANGHAI).date()
        for snapshot in task.snapshots
    )
```

`create` must read and normalize the note before deduplicating, so the canonical `note_id` is available. If the upstream read or normalization fails before a note ID can be identified, create a task keyed by a generated UUID with the submitted URL, title `"待获取笔记信息"`, no snapshots and `last_error`; a successful later `refresh` replaces title/note fields and deduplicates any task that then has the same note ID. `refresh` replaces the current-day snapshot rather than appending one, clears errors on success, and records `last_error`/`last_error_at` on any exception. `collect_due` catches exceptions per task so another task continues.

Start one background asyncio task only once. It must call `collect_due()` immediately, wait until the next 10:00 Asia/Shanghai using a calculated `asyncio.sleep`, then loop; `stop_scheduler` cancels and awaits the task cleanly.

- [ ] **Step 4: Run service tests and verify green**

Run: `pytest tests/test_monitoring_service.py -v`

Expected: all four tests pass.

- [ ] **Step 5: Extend the focused test with a successful retry after failure**

Add this test:

```python
@pytest.mark.asyncio
async def test_refresh_clears_failure_and_records_snapshot(tmp_path):
    now = datetime(2026, 7, 25, 9, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    reader = FakeReader(error=RuntimeError("验证码"))
    service = MonitoringService(reader, MonitoringStore(tmp_path / "monitoring.json"), now=lambda: now)
    task, _ = await service.create("https://www.xiaohongshu.com/explore/note-fixture")
    reader.error = None

    retried = await service.refresh(task.task_id)

    assert retried.last_error is None
    assert retried.snapshots[0].comments == 5
```

- [ ] **Step 6: Run tests and lint after the retry behavior**

Run: `pytest tests/test_monitoring_service.py -v && ruff check app/models.py app/services/monitoring_service.py tests/test_monitoring_service.py`

Expected: five passing tests and exit code 0.

- [ ] **Step 7: Commit the service slice**

```bash
git add app/models.py app/services/monitoring_service.py tests/test_monitoring_service.py
git commit -m "feat: collect monitoring interaction snapshots"
```

## Task 3: FastAPI lifecycle and monitoring APIs

**Files:**
- Modify: `app/main.py:56-70, 401-505`
- Modify: `tests/test_api.py`

**Interfaces:**
- Consumes `MonitoringService` from Task 2 and request model `MonitoringTaskCreate` from Task 1.
- Produces REST routes under `/api/monitoring/tasks` and attaches the service as `app.state.monitoring`.
- Returns `ApiErrorBody` for invalid URLs, missing task IDs and corrupted local archives.

- [ ] **Step 1: Write failing monitoring API tests**

Append this test and a fake monitoring lifespan to `tests/test_api.py`:

```python
from contextlib import asynccontextmanager

from app.services.monitoring_service import MonitoringService
from app.services.monitoring_store import MonitoringStore


def make_fake_monitoring_lifespan(tmp_path):
    @asynccontextmanager
    async def lifespan(application):
        application.state.redbook = FakeRedbookCLI()
        application.state.analyzer = CompetitorAnalyzer(settings)
        application.state.note_details = {}
        application.state.monitoring = MonitoringService(
            application.state.redbook,
            MonitoringStore(tmp_path / "monitoring.json"),
        )
        yield

    return lifespan


def test_monitoring_task_api_creates_lists_refreshes_and_deletes(tmp_path):
    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = make_fake_monitoring_lifespan(tmp_path)
    try:
        with TestClient(app) as client:
            created = client.post(
                "/api/monitoring/tasks",
                json={"web_url": "https://www.xiaohongshu.com/explore/note-fixture"},
            )
            assert created.status_code == 201
            task_id = created.json()["task_id"]
            assert created.json()["snapshots"][0]["likes"] == 100

            duplicate = client.post(
                "/api/monitoring/tasks",
                json={"web_url": "https://www.xiaohongshu.com/explore/note-fixture"},
            )
            assert duplicate.status_code == 200
            assert duplicate.json()["task_id"] == task_id

            assert client.get("/api/monitoring/tasks").json()[0]["task_id"] == task_id
            assert client.post(f"/api/monitoring/tasks/{task_id}/refresh").status_code == 200
            assert client.delete(f"/api/monitoring/tasks/{task_id}").status_code == 204
            assert client.get(f"/api/monitoring/tasks/{task_id}").status_code == 404
    finally:
        app.router.lifespan_context = original_lifespan


def test_monitoring_task_api_rejects_untrusted_url():
    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = make_fake_monitoring_lifespan(tmp_path)
    try:
        with TestClient(app) as client:
            response = client.post("/api/monitoring/tasks", json={"web_url": "https://example.com/note"})
        assert response.status_code == 422
        assert response.json()["code"] == "INVALID_NOTE_URL"
    finally:
        app.router.lifespan_context = original_lifespan
```

- [ ] **Step 2: Run the API tests and verify the expected red failure**

Run: `pytest tests/test_api.py -k monitoring -v`

Expected: tests fail with 404 because the monitoring routes do not exist.

- [ ] **Step 3: Wire the service into app lifecycle and add routes**

Refactor the repeated host validation in `note_detail` into `_is_allowed_note_url(url: str) -> bool`; use it both there and in monitoring creation. In `lifespan`, construct `MonitoringStore(settings.monitoring_data_file)` and `MonitoringService(app.state.redbook, store)`, assign it to `app.state.monitoring`, await `start_scheduler()` after initialization, and await `stop_scheduler()` in `finally` before ending lifespan.

Add exactly these route signatures:

```python
@app.get("/api/monitoring/tasks")
async def list_monitoring_tasks(request: Request) -> list[MonitoringTask]:
    return _monitoring(request).list_tasks()

@app.post("/api/monitoring/tasks", status_code=201)
async def create_monitoring_task(request: Request, body: MonitoringTaskCreate) -> Response:
    task, created = await _monitoring(request).create(str(body.web_url))
    return JSONResponse(status_code=201 if created else 200, content=task.model_dump(mode="json"))

@app.get("/api/monitoring/tasks/{task_id}")
async def get_monitoring_task(request: Request, task_id: str) -> MonitoringTask:
    return _monitoring(request).get(task_id)

@app.post("/api/monitoring/tasks/{task_id}/refresh")
async def refresh_monitoring_task(request: Request, task_id: str) -> MonitoringTask:
    return await _monitoring(request).refresh(task_id)

@app.delete("/api/monitoring/tasks/{task_id}", status_code=204)
async def delete_monitoring_task(request: Request, task_id: str) -> Response:
    _monitoring(request).delete(task_id)
    return Response(status_code=204)
```

For duplicate creation, return the existing task with status 200 instead of 201. Convert store failures into status 503 and missing task IDs into status 404, both using `ApiErrorBody`.

- [ ] **Step 4: Run the focused API tests and verify green**

Run: `pytest tests/test_api.py -k monitoring -v`

Expected: both monitoring API tests pass.

- [ ] **Step 5: Run the existing API regression suite**

Run: `pytest tests/test_api.py -v`

Expected: all existing search, collection, detail and analysis tests still pass.

- [ ] **Step 6: Commit the API slice**

```bash
git add app/main.py tests/test_api.py
git commit -m "feat: expose monitoring task api"
```

## Task 4: Local ECharts monitoring workspace

**Files:**
- Modify: `package.json`
- Modify: `package-lock.json`
- Modify: `app/main.py`
- Modify: `app/templates/index.html`
- Modify: `app/static/app.js`
- Modify: `app/static/styles.css`
- Create: `tests/test_monitoring_ui_assets.py`

**Interfaces:**
- Consumes the Task 3 routes and global browser `echarts` from `/vendor/echarts/echarts.min.js`.
- Produces a task list, creation form, detail dashboard, range/metric controls, manual refresh and delete actions.
- Produces `renderMonitoringChart(task)` and `loadMonitoringTasks()` functions in `app/static/app.js`.

- [ ] **Step 1: Write failing static UI asset tests**

Create `tests/test_monitoring_ui_assets.py`:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_monitoring_page_loads_local_echarts_and_exposes_dashboard_hooks():
    template = (ROOT / "app/templates/index.html").read_text(encoding="utf-8")
    script = (ROOT / "app/static/app.js").read_text(encoding="utf-8")

    assert "/vendor/echarts/echarts.min.js" in template
    assert 'id="monitoring"' in template
    assert "function renderMonitoringChart" in script
    assert "function loadMonitoringTasks" in script


def test_monitoring_styles_respect_reduced_motion():
    styles = (ROOT / "app/static/styles.css").read_text(encoding="utf-8")

    assert ".monitoring-chart" in styles
    assert "prefers-reduced-motion: reduce" in styles
```

- [ ] **Step 2: Run the UI asset tests and verify the expected red failure**

Run: `pytest tests/test_monitoring_ui_assets.py -v`

Expected: both tests fail because the monitoring section and hooks are absent.

- [ ] **Step 3: Add ECharts as a local dependency and serve its exact distribution folder**

Run: `npm install echarts`

In `app/main.py`, mount `PROJECT_ROOT / "node_modules" / "echarts" / "dist"` at `/vendor/echarts` using `StaticFiles`, after the existing `/static` mount. In the template head, load ECharts before deferred `app.js`:

```html
<script src="/vendor/echarts/echarts.min.js"></script>
<script defer src="{{ url_for('static', path='/app.js') }}"></script>
```

- [ ] **Step 4: Build the monitoring list and dashboard markup**

Add a `发布效果监测` sidebar link with `href="#monitoring"` and `data-nav-key="monitoring"`. Add a new `section#monitoring` after the existing report section containing:

```html
<section id="monitoring" class="monitoring-section">
  <div class="monitoring-heading">
    <div>
      <p class="eyebrow">POST PERFORMANCE</p>
      <h2>发布效果监测</h2>
      <p>每日记录已发布笔记的公开互动数据，连续监测 30 天。</p>
    </div>
  </div>
  <form id="monitoring-create-form" class="monitoring-create-form">
    <label for="monitoring-url">已发布笔记链接</label>
    <input id="monitoring-url" name="web_url" type="url" required placeholder="粘贴小红书或 RedNote 笔记链接" />
    <button class="gradient-button" type="submit">新建监测任务</button>
  </form>
  <div id="monitoring-message" role="status" hidden></div>
  <div id="monitoring-task-list" class="monitoring-task-list"></div>
  <article id="monitoring-dashboard" class="monitoring-dashboard" hidden>
    <div id="monitoring-metric-cards"></div>
    <div id="monitoring-metric-tabs" role="tablist">
      <button data-monitoring-metric="likes" type="button">点赞</button>
      <button data-monitoring-metric="collects" type="button">收藏</button>
      <button data-monitoring-metric="comments" type="button">评论</button>
    </div>
    <div id="monitoring-range-tabs" role="tablist">
      <button data-monitoring-range="7d" type="button">近 7 天</button>
      <button data-monitoring-range="30d" type="button">近 30 天</button>
      <button data-monitoring-range="all" type="button">全部监测期</button>
    </div>
    <button id="monitoring-refresh" type="button">立即更新</button>
    <button id="monitoring-delete" type="button">删除任务</button>
    <div id="monitoring-chart" class="monitoring-chart" aria-label="互动趋势图"></div>
  </article>
</section>
```

Use actual labels `点赞`, `收藏`, `评论`, `近 7 天`, `近 30 天`, `全部监测期`; the creation input must be labelled `已发布笔记链接`.

- [ ] **Step 5: Implement the browser data flow and ECharts option**

Extend `state` with `monitoringTasks`, `monitoringTask`, `monitoringMetric` defaulting to `"likes"`, `monitoringRange` defaulting to `"30d"`, and `monitoringChart`.

`loadMonitoringTasks()` fetches `GET /api/monitoring/tasks`, renders task cards ordered by API response, and automatically opens the first active task when no task is selected. Creation posts `{"web_url": link}` and opens the returned task. Refresh posts to `/refresh`; deletion calls `window.confirm("删除后将永久移除该任务及全部历史快照，确定继续吗？")`, then deletes and clears the dashboard.

`renderMonitoringChart(task)` must build an ECharts option with:

```javascript
{
  animation: !window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  tooltip: { trigger: "axis" },
  xAxis: { type: "category", data: labels },
  yAxis: { type: "value", minInterval: 1 },
  dataZoom: [{ type: "inside" }, { type: "slider", height: 18 }],
  series: [{
    type: "line",
    smooth: true,
    areaStyle: { opacity: 0.16 },
    data: values,
  }],
}
```

Filter labels and snapshots by the selected range before the option. The tooltip formatter must show Beijing date, current total and the delta from the preceding visible snapshot. Reuse one chart instance, call `setOption(option, true)`, and call `resize()` on window resize. For zero or one point, render an explanatory empty/first-snapshot message instead of an unreadable chart.

- [ ] **Step 6: Add responsive, motion-safe dashboard styles**

Add styles for `.monitoring-section`, `.monitoring-task-list`, `.monitoring-dashboard`, `.monitoring-chart`, metric cards, active segmented controls, error chips and narrow-screen stacking. Use the existing `--purple`, `--violet`, `--surface`, `--line`, and `--shadow` tokens. Add:

```css
@media (prefers-reduced-motion: reduce) {
  .monitoring-section *,
  .monitoring-section *::before,
  .monitoring-section *::after {
    animation-duration: 0.01ms !important;
    scroll-behavior: auto !important;
    transition-duration: 0.01ms !important;
  }
}
```

- [ ] **Step 7: Run static UI tests and JavaScript syntax verification**

Run: `pytest tests/test_monitoring_ui_assets.py -v && node --check app/static/app.js`

Expected: both tests pass and Node exits 0.

- [ ] **Step 8: Perform browser verification with fixture-backed API data**

Start the app with the existing fake lifespan test harness or a local logged-in session. Verify in a browser at 375px and 1440px that task creation, duplicate opening, manual refresh, deletion confirmation, metric/range switching, tooltip, slider zoom, failure display and reduced-motion mode are reachable. Record any visual correction before committing.

- [ ] **Step 9: Run the full regression suite and lint**

Run: `pytest -v && ruff check . && node --check app/static/app.js`

Expected: all tests pass, Ruff exits 0, and JavaScript syntax check exits 0.

- [ ] **Step 10: Commit the user interface slice**

```bash
git add package.json package-lock.json app/main.py app/templates/index.html app/static/app.js app/static/styles.css tests/test_monitoring_ui_assets.py
git commit -m "feat: add monitoring dashboard"
```

## Final verification

- [ ] Run `pytest -v`, `ruff check .`, and `node --check app/static/app.js` after all commits.
- [ ] Start `uvicorn app.main:app --host 127.0.0.1 --port 8000` and visit the page with a valid local login; confirm `/api/health` remains healthy.
- [ ] Inspect `data/monitoring.json` after a successful creation: it contains `version: 1`, one task, and only likes/collects/comments snapshots.
- [ ] Confirm no competitor comparison, AI optimization, shares, views, rates, Vue, Spring, database or CDN was added.
