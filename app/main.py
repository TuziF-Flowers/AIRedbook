from __future__ import annotations

import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated
from urllib.parse import urljoin, urlparse

import httpx
from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.models import (
    AnalysisRequest,
    ApiErrorBody,
    CompetitorAnalysis,
    CompetitorCollectionRequest,
    MonitoringTask,
    MonitoringTaskCreate,
    NoteDetail,
    NoteDetailRequest,
    NoteSummary,
    SearchResponse,
)
from app.services.analysis_store import AnalysisStore
from app.services.competitor_analyzer import CompetitorAnalyzer
from app.services.monitoring_service import MonitoringService
from app.services.monitoring_store import MonitoringArchiveError, MonitoringStore
from app.services.normalizer import normalize_detail, normalize_search
from app.services.promotion_generator import (
    PromotionGenerationError,
    PromotionGenerator,
)
from app.services.redbook_cli import RedbookCLI, RedbookError

APP_DIR = Path(__file__).resolve().parent
ECHARTS_DIST_DIR = APP_DIR.parent / "node_modules" / "echarts" / "dist"
templates = Jinja2Templates(directory=APP_DIR / "templates")
IMAGE_HOST_SUFFIXES = (".xhscdn.com", ".xiaohongshu.com")
IMAGE_HOSTS = {"xhscdn.com", "xiaohongshu.com"}
MAX_IMAGE_BYTES = 12 * 1024 * 1024
MAX_PRODUCT_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_PRODUCT_UPLOADS = 6
PRODUCT_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
IMAGE_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0.0.0 Safari/537.36"
)
REVIEW_POST_PATTERN = re.compile(
    r"测评|评测|横评|对比|开箱|避雷|踩雷|优缺点|值不值得|好不好用|购买指南|怎么选",
    re.IGNORECASE,
)
MULTI_PRODUCT_PATTERN = re.compile(
    r"合集|清单|盘点|榜单|top\s*\d+|多款|几款|款.*(?:对比|横评)|\bvs\b|\bpk\b",
    re.IGNORECASE,
)
SEEDING_PATTERN = re.compile(
    r"种草|推荐|安利|好物|必买|值得入|入手|回购|真香|宝藏|闭眼入|自用|爱用|心头好",
    re.IGNORECASE,
)
SCENE_PATTERN = re.compile(
    r"通勤|上班|办公室|家里|居家|旅行|出门|日常|每天|学习|健身|约会",
    re.IGNORECASE,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redbook = RedbookCLI(settings)
    app.state.analyzer = CompetitorAnalyzer(settings)
    app.state.analysis_store = AnalysisStore(settings.analysis_storage_dir)
    app.state.promotion_generator = PromotionGenerator(settings)
    app.state.note_details = {}
    app.state.monitoring = MonitoringService(
        app.state.redbook,
        MonitoringStore(settings.monitoring_data_file),
    )
    await app.state.monitoring.start_scheduler()
    try:
        yield
    finally:
        await app.state.monitoring.stop_scheduler()


app = FastAPI(
    title="AI种草官 · 小红书产品洞察",
    version="0.1.0",
    docs_url="/api/docs",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
app.mount("/vendor/echarts", StaticFiles(directory=ECHARTS_DIST_DIR), name="echarts")


def _service(request: Request) -> RedbookCLI:
    return request.app.state.redbook


def _monitoring(request: Request) -> MonitoringService:
    return request.app.state.monitoring


def _is_allowed_note_url(url: str) -> bool:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    allowed = (
        hostname == "xiaohongshu.com"
        or hostname.endswith(".xiaohongshu.com")
        or hostname == "rednote.com"
        or hostname.endswith(".rednote.com")
    )
    return parsed.scheme == "https" and allowed


def _is_allowed_image_url(url: str) -> bool:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    return (
        parsed.scheme == "https"
        and (hostname in IMAGE_HOSTS or hostname.endswith(IMAGE_HOST_SUFFIXES))
    )


def _select_top_image(result: SearchResponse) -> SearchResponse:
    image_notes = [note for note in result.items if note.note_type == "image"]
    top_notes = sorted(
        image_notes,
        key=lambda note: (
            note.stats.likes + note.stats.collects,
            note.stats.likes,
            note.stats.collects,
        ),
        reverse=True,
    )
    result.items = top_notes[:20]
    result.has_more = False
    return result


def _filter_single_product_seeding(
    result: SearchResponse,
    detail_cache: dict[str, NoteDetail],
) -> SearchResponse:
    ranked: list[tuple[int, int, int, NoteSummary]] = []
    for note in result.items:
        detail = detail_cache.get(note.web_url)
        tags = " ".join(detail.tags) if detail else ""
        description = detail.description if detail else ""
        text = f"{note.title} {tags} {description}"

        if REVIEW_POST_PATTERN.search(text) or MULTI_PRODUCT_PATTERN.search(text):
            continue

        seeding_score = len(SEEDING_PATTERN.findall(text)) * 3
        seeding_score += len(SCENE_PATTERN.findall(text))
        if result.keyword.casefold() in text.casefold():
            seeding_score += 2
        if detail and detail.description:
            seeding_score += 1

        engagement = note.stats.likes + note.stats.collects
        ranked.append(
            (
                seeding_score,
                engagement,
                note.stats.collects,
                note,
            )
        )

    ranked.sort(
        key=lambda item: (item[0], item[1], item[2]),
        reverse=True,
    )
    result.items = [item[3] for item in ranked[:20]]
    result.has_more = False
    return result


async def _enrich_preview_images(
    client: RedbookCLI,
    result: SearchResponse,
    detail_cache: dict[str, NoteDetail] | None = None,
    *,
    fetch_details: bool = False,
) -> SearchResponse:
    for note in result.items:
        cached = detail_cache.get(note.web_url) if detail_cache is not None else None
        if cached is not None:
            note.topic_tags = cached.tags
            if not note.cover_url and cached.image_urls:
                note.cover_url = cached.image_urls[0]
            continue
        if note.cover_url and not fetch_details:
            continue
        try:
            raw_detail = await client.read_note(note.web_url)
            detail = normalize_detail(raw_detail, requested_url=note.web_url)
        except RedbookError as exc:
            if exc.code in {
                "CAPTCHA_REQUIRED",
                "SESSION_EXPIRED",
                "COOKIE_UNAVAILABLE",
            }:
                break
            continue
        except ValueError:
            continue
        detail = detail.model_copy(
            update={
                "competitor": note.competitor,
                "topic_tags": detail.tags,
            }
        )
        if detail_cache is not None:
            detail_cache[note.web_url] = detail
        note.topic_tags = detail.tags
        if detail.image_urls:
            note.cover_url = detail.image_urls[0]
    return result


@app.exception_handler(RedbookError)
async def handle_redbook_error(_: Request, exc: RedbookError) -> JSONResponse:
    body = ApiErrorBody(code=exc.code, message=exc.message, hint=exc.hint)
    return JSONResponse(status_code=exc.status_code, content=body.model_dump())


@app.exception_handler(PromotionGenerationError)
async def handle_promotion_error(
    _: Request,
    exc: PromotionGenerationError,
) -> JSONResponse:
    body = ApiErrorBody(code=exc.code, message=exc.message, hint=exc.hint)
    return JSONResponse(status_code=exc.status_code, content=body.model_dump())


def _monitoring_archive_error_response(exc: Exception) -> JSONResponse:
    body = ApiErrorBody(
        code="MONITORING_ARCHIVE_UNAVAILABLE",
        message=str(exc),
        hint="请先备份并检查本地监测档案。",
    )
    return JSONResponse(status_code=503, content=body.model_dump())


@app.exception_handler(MonitoringArchiveError)
async def handle_monitoring_archive_error(
    _: Request, exc: MonitoringArchiveError
) -> JSONResponse:
    return _monitoring_archive_error_response(exc)


@app.exception_handler(RequestValidationError)
async def handle_request_validation_error(
    request: Request, exc: RequestValidationError
) -> Response:
    if request.url.path == "/api/monitoring/tasks":
        body = ApiErrorBody(
            code="INVALID_NOTE_URL",
            message="只支持小红书或 RedNote 的 HTTPS 笔记链接。",
            hint=None,
        )
        return JSONResponse(status_code=422, content=body.model_dump())
    return await request_validation_exception_handler(request, exc)


@app.exception_handler(KeyError)
async def handle_missing_monitoring_task(_: Request, exc: KeyError) -> JSONResponse:
    body = ApiErrorBody(
        code="MONITORING_TASK_NOT_FOUND",
        message="未找到监测任务。",
        hint=None,
    )
    return JSONResponse(status_code=404, content=body.model_dump())


@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/api/health")
async def health(request: Request) -> dict[str, object]:
    cli = _service(request)
    return {
        "status": "ok",
        "redbook_installed": cli.is_installed,
        "cookie_file_available": cli.has_cookie_file,
        "platform": settings.redbook_platform,
        "ai_configured": bool(settings.ai_api_key and settings.ai_model),
        "image_generation_configured": bool(
            settings.ai_api_key and settings.ai_image_model
        ),
        "image_model": settings.ai_image_model,
    }


@app.get("/api/session")
async def session(request: Request) -> dict[str, object]:
    raw = await _service(request).whoami()
    user = raw if isinstance(raw, dict) else {}
    return {
        "connected": True,
        "nickname": user.get("nickname") or user.get("nick_name") or "已登录",
        "user_id": user.get("user_id") or user.get("userId") or "",
    }


@app.get("/api/images/proxy")
async def image_proxy(
    url: str = Query(min_length=10, max_length=4096),
) -> Response:
    current_url = url
    headers = {
        "User-Agent": IMAGE_USER_AGENT,
        "Referer": "https://www.xiaohongshu.com/",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    }

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(12, connect=5),
        follow_redirects=False,
    ) as client:
        for _ in range(4):
            if not _is_allowed_image_url(current_url):
                return JSONResponse(
                    status_code=422,
                    content={
                        "code": "INVALID_IMAGE_URL",
                        "message": "只允许代理小红书图片地址。",
                        "hint": None,
                    },
                )
            try:
                upstream = await client.get(current_url, headers=headers)
            except httpx.HTTPError:
                return JSONResponse(
                    status_code=502,
                    content={
                        "code": "IMAGE_FETCH_FAILED",
                        "message": "图片加载失败。",
                        "hint": None,
                    },
                )

            if upstream.is_redirect:
                location = upstream.headers.get("location")
                if not location:
                    break
                current_url = urljoin(current_url, location)
                continue

            content_type = upstream.headers.get("content-type", "").split(";")[0]
            if upstream.status_code != 200 or not content_type.startswith("image/"):
                return JSONResponse(
                    status_code=502,
                    content={
                        "code": "INVALID_IMAGE_RESPONSE",
                        "message": "图片源返回异常。",
                        "hint": None,
                    },
                )
            if len(upstream.content) > MAX_IMAGE_BYTES:
                return JSONResponse(
                    status_code=413,
                    content={
                        "code": "IMAGE_TOO_LARGE",
                        "message": "图片超过大小限制。",
                        "hint": None,
                    },
                )
            return Response(
                content=upstream.content,
                media_type=content_type,
                headers={
                    "Cache-Control": "public, max-age=900",
                    "X-Content-Type-Options": "nosniff",
                },
            )

    return JSONResponse(
        status_code=502,
        content={
            "code": "IMAGE_REDIRECT_FAILED",
            "message": "图片重定向次数过多。",
            "hint": None,
        },
    )


@app.get("/api/search")
async def search(
    request: Request,
    q: str = Query(min_length=1, max_length=80),
):
    keyword = q.strip()
    if not keyword:
        return JSONResponse(
            status_code=422,
            content={"code": "EMPTY_KEYWORD", "message": "请输入搜索关键词。", "hint": None},
        )
    client = _service(request)
    raw = await client.search(
        keyword,
        page=1,
        sort="popular",
        note_type="image",
    )
    result = normalize_search(raw, keyword=keyword, page=1)
    result = _select_top_image(result)
    result = await _enrich_preview_images(
        client,
        result,
        request.app.state.note_details,
    )
    return _filter_single_product_seeding(
        result,
        request.app.state.note_details,
    )


async def _collect_competitor_notes(
    client: RedbookCLI,
    competitor: str,
    quota: int,
    detail_cache: dict[str, NoteDetail],
) -> list[NoteSummary]:
    raw = await client.search(
        competitor,
        page=1,
        sort="popular",
        note_type="image",
    )
    result = normalize_search(raw, keyword=competitor, page=1)
    result = _select_top_image(result)
    result.items = [
        note
        for note in result.items
        if not REVIEW_POST_PATTERN.search(note.title)
        and not MULTI_PRODUCT_PATTERN.search(note.title)
    ][:quota]
    for note in result.items:
        note.competitor = competitor

    result = await _enrich_preview_images(
        client,
        result,
        detail_cache,
        fetch_details=True,
    )
    result = _filter_single_product_seeding(result, detail_cache)
    return result.items[:quota]


@app.post("/api/collect")
async def collect_competitors(
    request: Request,
    body: CompetitorCollectionRequest,
) -> SearchResponse:
    competitors = body.competitors
    total_limit = 20
    base_quota, remainder = divmod(total_limit, len(competitors))
    client = _service(request)
    detail_cache: dict[str, NoteDetail] = request.app.state.note_details
    collected: list[NoteSummary] = []
    seen_note_ids: set[str] = set()

    for index, competitor in enumerate(competitors):
        quota = base_quota + (1 if index < remainder else 0)
        notes = await _collect_competitor_notes(
            client,
            competitor,
            quota,
            detail_cache,
        )
        for note in notes:
            if note.note_id in seen_note_ids:
                continue
            seen_note_ids.add(note.note_id)
            collected.append(note)

    return SearchResponse(
        keyword=body.product_name,
        page=1,
        page_size=total_limit,
        has_more=False,
        items=collected[:total_limit],
    )


@app.post("/api/notes/detail")
async def note_detail(request: Request, body: NoteDetailRequest):
    web_url = str(body.web_url)
    if not _is_allowed_note_url(web_url):
        return JSONResponse(
            status_code=422,
            content={
                "code": "INVALID_NOTE_URL",
                "message": "只支持小红书或 RedNote 的 HTTPS 笔记链接。",
                "hint": None,
            },
        )

    cached = request.app.state.note_details.get(web_url)
    if cached is not None:
        return cached

    raw = await _service(request).read_note(web_url)
    try:
        detail = normalize_detail(raw, requested_url=web_url)
        request.app.state.note_details[web_url] = detail
        return detail
    except ValueError as exc:
        raise RedbookError(
            "INVALID_NOTE_DATA",
            "笔记详情数据不完整。",
            hint="该笔记可能已删除、不可见或需要重新登录。",
        ) from exc


@app.get("/api/monitoring/tasks")
async def list_monitoring_tasks(request: Request) -> list[MonitoringTask]:
    try:
        return _monitoring(request).list_tasks()
    except (MonitoringArchiveError, OSError) as exc:
        return _monitoring_archive_error_response(exc)


@app.post("/api/monitoring/tasks", status_code=201)
async def create_monitoring_task(
    request: Request, body: MonitoringTaskCreate
) -> Response:
    web_url = str(body.web_url)
    if not _is_allowed_note_url(web_url):
        body = ApiErrorBody(
            code="INVALID_NOTE_URL",
            message="只支持小红书或 RedNote 的 HTTPS 笔记链接。",
            hint=None,
        )
        return JSONResponse(status_code=422, content=body.model_dump())

    try:
        task, created = await _monitoring(request).create(web_url)
    except (MonitoringArchiveError, OSError) as exc:
        return _monitoring_archive_error_response(exc)
    return JSONResponse(
        status_code=201 if created else 200,
        content=task.model_dump(mode="json"),
    )


@app.get("/api/monitoring/tasks/{task_id}")
async def get_monitoring_task(request: Request, task_id: str) -> MonitoringTask:
    try:
        return _monitoring(request).get(task_id)
    except (MonitoringArchiveError, OSError) as exc:
        return _monitoring_archive_error_response(exc)


@app.post("/api/monitoring/tasks/{task_id}/refresh")
async def refresh_monitoring_task(request: Request, task_id: str) -> MonitoringTask:
    try:
        return await _monitoring(request).refresh(task_id)
    except (MonitoringArchiveError, OSError) as exc:
        return _monitoring_archive_error_response(exc)


@app.delete("/api/monitoring/tasks/{task_id}", status_code=204)
async def delete_monitoring_task(request: Request, task_id: str) -> Response:
    try:
        if not await _monitoring(request).delete(task_id):
            raise KeyError(task_id)
    except (MonitoringArchiveError, OSError) as exc:
        return _monitoring_archive_error_response(exc)
    return Response(status_code=204)


@app.post("/api/analyze")
async def analyze_competitors(request: Request, body: AnalysisRequest):
    keyword = body.keyword.strip()
    details: list[NoteDetail] = []
    cache: dict[str, NoteDetail] = request.app.state.note_details
    client = _service(request)
    upstream_blocked = False

    for note in body.notes:
        cached = cache.get(note.web_url)
        if cached is not None:
            details.append(
                cached.model_copy(
                    update={
                        "competitor": note.competitor,
                        "topic_tags": note.topic_tags or cached.tags,
                    }
                )
            )
            continue

        if upstream_blocked:
            details.append(
                NoteDetail(
                    **note.model_dump(),
                    description="",
                    image_urls=[note.cover_url] if note.cover_url else [],
                )
            )
            continue

        try:
            raw = await client.read_note(note.web_url)
            detail = normalize_detail(raw, requested_url=note.web_url)
            detail = detail.model_copy(
                update={
                    "competitor": note.competitor,
                    "topic_tags": detail.tags,
                }
            )
            cache[note.web_url] = detail
            details.append(detail)
        except RedbookError as exc:
            if exc.code in {
                "CAPTCHA_REQUIRED",
                "SESSION_EXPIRED",
                "COOKIE_UNAVAILABLE",
            }:
                upstream_blocked = True
            details.append(
                NoteDetail(
                    **note.model_dump(),
                    description="",
                    image_urls=[note.cover_url] if note.cover_url else [],
                )
            )
        except ValueError:
            details.append(
                NoteDetail(
                    **note.model_dump(),
                    description="",
                    image_urls=[note.cover_url] if note.cover_url else [],
                )
            )

    analyzer: CompetitorAnalyzer = request.app.state.analyzer
    analysis = await analyzer.analyze(keyword, details)
    store: AnalysisStore = request.app.state.analysis_store
    try:
        artifact = store.save(analysis, details)
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail="无法保存本地分析 JSON，请检查 data/analyses 目录权限。",
        ) from exc
    analysis.artifact_id = artifact.analysis_id
    analysis.json_download_url = f"/api/analyses/{artifact.analysis_id}/json"
    return analysis


@app.get("/api/analyses/{analysis_id}/json")
async def download_analysis_json(request: Request, analysis_id: str) -> FileResponse:
    store: AnalysisStore = request.app.state.analysis_store
    path = store.get_path(analysis_id)
    if path is None:
        raise HTTPException(status_code=404, detail="未找到该分析 JSON。")
    return FileResponse(
        path,
        media_type="application/json",
        filename=path.name,
    )


@app.post("/api/generate-promotion")
async def generate_promotion(
    request: Request,
    product_brief: Annotated[str, Form(min_length=1, max_length=1200)],
    analysis_json: Annotated[str, Form(min_length=2, max_length=100_000)],
    images: Annotated[list[UploadFile], File()],
):
    cleaned_brief = product_brief.strip()
    if not cleaned_brief:
        raise PromotionGenerationError(
            "EMPTY_PRODUCT_BRIEF",
            "请先填写待宣传产品信息。",
            status_code=422,
        )
    try:
        analysis = CompetitorAnalysis.model_validate_json(analysis_json)
    except ValueError as exc:
        raise PromotionGenerationError(
            "INVALID_ANALYSIS",
            "竞品分析数据无效，请重新完成第 3 步。",
            status_code=422,
        ) from exc
    if analysis.analysis_mode != "ai":
        raise PromotionGenerationError(
            "AI_ANALYSIS_REQUIRED",
            "第 4 步需要真实 AI 竞品分析结果。",
            hint="请确认文本模型可用后重新生成第 3 步分析。",
            status_code=422,
        )
    if not images or len(images) > MAX_PRODUCT_UPLOADS:
        raise PromotionGenerationError(
            "INVALID_IMAGE_COUNT",
            f"请上传 1 至 {MAX_PRODUCT_UPLOADS} 张产品图片。",
            status_code=422,
        )

    uploaded: list[tuple[str, bytes, str]] = []
    for index, image in enumerate(images, start=1):
        content_type = (image.content_type or "").lower()
        if content_type not in PRODUCT_IMAGE_TYPES:
            raise PromotionGenerationError(
                "INVALID_PRODUCT_IMAGE",
                "产品图片仅支持 JPG、PNG 和 WebP。",
                status_code=422,
            )
        content = await image.read(MAX_PRODUCT_UPLOAD_BYTES + 1)
        await image.close()
        if not content or len(content) > MAX_PRODUCT_UPLOAD_BYTES:
            raise PromotionGenerationError(
                "INVALID_PRODUCT_IMAGE",
                "每张产品图片必须有效且不超过 8MB。",
                status_code=422,
            )
        extension = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[
            content_type
        ]
        uploaded.append((f"product-reference-{index}.{extension}", content, content_type))

    generator: PromotionGenerator = request.app.state.promotion_generator
    return await generator.generate(cleaned_brief, analysis, uploaded)
