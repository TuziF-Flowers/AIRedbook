# AI种草官 · 小红书产品洞察

一个本地运行的 FastAPI Web 应用。它通过
[`lucasygu/redbook`](https://github.com/lucasygu/redbook) 读取小红书公开笔记，完成竞品图文采集、
文本与视觉分析、宣传文案及图片生成，并对已发布笔记进行 30 天互动效果监测。

应用默认只监听 `127.0.0.1`。Cookie 和 AI 密钥只由本地服务读取，不通过网页录入。

## 核心工作流

### 1. 信息录入

- 填写产品或品类名称。
- 添加最多 3 个竞品品牌或型号。
- 填写最多 1200 字的产品信息，包括卖点、目标人群、场景和品牌语气。
- 上传 1 至 6 张产品参考图，支持 JPG、PNG 和 WebP，单张不超过 8MB。

产品说明和参考图只保留在当前浏览器页面中，不会作为独立素材持久化。

### 2. 竞品采集

- 分别搜索竞品关键词并统一去重，合计最多展示 20 篇图文笔记。
- 优先保留高互动的单品种草内容。
- 排除测评、横向对比、避雷、合集和视频内容。
- 展示封面、作者、标签、点赞、收藏和评论数据。
- 支持查看完整正文与多图详情。

### 3. AI 分析

- 先通过本地规则计算关键词、标题模板、正文结构、互动指标和竞品表现。
- 配置文本模型后，生成标题、正文、文案框架、互动和综合策略洞察。
- 默认启用视觉分析：分析高互动笔记的封面构图、色彩、光影、图内文字和配图风格。
- 生成 Markdown 报告，并自动将结构化分析、来源笔记和视觉引用保存为本地 JSON。
- 支持复制报告、导出 Markdown 和下载分析 JSON。

文本或视觉模型暂时不可用时，第 3 步会保留本地规则结果并继续生成报告。

### 4. AI 创作

- 将第 1 步的产品资料与第 3 步的真实 AI 分析结果组合起来。
- 生成可直接编辑或发布的标题、正文和话题标签。
- 根据竞品视觉规律生成图片创意说明。
- 使用上传的产品图片作为身份与外观参考，生成两张竖版宣传图。
- 支持复制文案、下载图片和重新生成。

第 4 步不使用本地模拟结果。它要求第 3 步的 `analysis_mode` 为 `ai`，并且文本与图片模型均可用。

### 发布效果监测

- 粘贴已发布的小红书或 RedNote 笔记链接创建任务。
- 记录点赞、收藏和评论公开数据，监测期为 30 天。
- 展示近 7 天、近 30 天或全部监测期的互动趋势。
- 支持立即更新和删除任务。
- 服务运行时每天北京时间 10:00 自动采集一次；同一天不会重复写入定时快照。

监测任务和历史快照保存在本地 JSON 中。自动采集依赖应用进程持续运行。

## 环境要求

- Windows PowerShell
- Python 3.11+
- Node.js 22+
- Chrome 中已登录[小红书网页版](https://www.xiaohongshu.com/)，或已有可用的 redbook Cookie 文件
- 如需 AI 功能：兼容 OpenAI Chat Completions 的文本/视觉模型服务
- 如需 AI 生图：兼容 OpenAI Images Edit API 的图片模型服务

## 安装

在项目目录打开 PowerShell：

```powershell
cd D:\AIRedbook

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"

npm install
```

`npm install` 会安装固定版本的 redbook CLI 和 ECharts，并执行项目所需的本地兼容补丁。

检查 Python、Node.js 和 redbook：

```powershell
python scripts\check_environment.py
```

## 小红书登录状态

验证当前登录状态：

```powershell
.\node_modules\.bin\redbook.cmd whoami
```

项目优先使用以下本地 Cookie 文件：

```text
C:\Users\<你的用户名>\.redbook\cookies.chrome.json
C:\Users\<你的用户名>\.redbook\cookies.json
```

也可以在 `.env` 中显式指定：

```dotenv
REDBOOK_COOKIE_FILE=C:\secure\redbook-cookies.json
```

从 Chrome 更新登录态前，需要先关闭所有 Chrome 窗口，避免 Cookie 数据库被锁定：

```powershell
npm run auth:chrome
```

如果自动导出失败，可以从 Chrome 开发者工具获取新的 `a1` 和 `web_session`，再通过隐藏输入脚本保存：

```powershell
npm run auth:manual
```

Cookie 是登录凭据。不要把 Cookie 内容写入 `.env`、代码、截图或 Git。

## 配置

复制配置模板：

```powershell
Copy-Item .env.example .env
```

### 应用与采集

```dotenv
REDBOOK_EXECUTABLE=
REDBOOK_COOKIE_FILE=
REDBOOK_PLATFORM=xhs
REDBOOK_COMMAND_TIMEOUT_SECONDS=30
REDBOOK_MAX_CONCURRENCY=2

APP_HOST=127.0.0.1
APP_PORT=8000
APP_RELOAD=true
```

通常不需要配置 `REDBOOK_EXECUTABLE`。应用会优先寻找项目内的
`node_modules/.bin/redbook`，然后寻找全局命令。

### AI 文本与视觉分析

```dotenv
AI_API_KEY=你的密钥
AI_BASE_URL=https://api.openai.com/v1
AI_MODEL=gpt-5.6
AI_TIMEOUT_SECONDS=60

AI_ENABLE_VISION=true
AI_VISION_MAX_COVERS=20
AI_VISION_MAX_GALLERY_NOTES=6
AI_VISION_MAX_IMAGES_PER_NOTE=4
AI_VISION_MAX_IMAGE_BYTES=550000
AI_VISION_IMAGE_DETAIL=low
```

启用视觉分析时，`AI_MODEL` 必须支持 Chat Completions 多模态图片输入。如果服务只支持文本，可以设置：

```dotenv
AI_ENABLE_VISION=false
```

采集范围仍然是 Top 20；视觉配置只控制其中多少张封面和配图会发送给模型。图片会先在本地缩放、压缩，
并且只接受小红书 CDN 的 HTTPS 地址。

### AI 图片生成

```dotenv
AI_IMAGE_MODEL=gpt-image-2
AI_IMAGE_COUNT=2
AI_IMAGE_SIZE=1024x1536
AI_IMAGE_QUALITY=high
AI_IMAGE_TIMEOUT_SECONDS=240
```

宣传图使用 `/images/edits`，产品参考图通过 multipart `image[]` 上传给模型。当前默认生成两张高质量 PNG，
因此请求可能需要数分钟。

### 本地数据

```dotenv
ANALYSIS_STORAGE_DIR=data/analyses
MONITORING_DATA_FILE=data/monitoring.json
```

- `data/analyses/`：每次分析生成一份带来源笔记和视觉引用的结构化 JSON。
- `data/monitoring.json`：监测任务与每日互动快照。

这两个默认路径已加入 `.gitignore`。如需迁移或清理数据，请先备份。

## 启动与重启

启动开发服务：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

打开：

- 应用：[http://127.0.0.1:8000](http://127.0.0.1:8000)
- API 文档：[http://127.0.0.1:8000/api/docs](http://127.0.0.1:8000/api/docs)
- 健康检查：[http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

修改前端或后端后通常只需在浏览器按 `Ctrl + R`。如需重启服务，在终端按 `Ctrl + C`，再执行上面的启动命令。

## API 概览

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/api/health` | 检查 redbook、Cookie、AI 和图片模型配置 |
| `GET` | `/api/session` | 检查小红书登录状态 |
| `GET` | `/api/search?q=...` | 搜索并筛选高互动图文 |
| `POST` | `/api/collect` | 按产品和竞品批量采集 |
| `POST` | `/api/notes/detail` | 读取单篇笔记正文和图集 |
| `GET` | `/api/images/proxy?url=...` | 代理允许的小红书 CDN 图片 |
| `POST` | `/api/analyze` | 生成文本、视觉和互动分析，并保存 JSON |
| `GET` | `/api/analyses/{analysis_id}/json` | 下载指定分析 JSON |
| `POST` | `/api/generate-promotion` | 生成宣传文案与产品宣传图 |
| `GET` | `/api/monitoring/tasks` | 列出监测任务 |
| `POST` | `/api/monitoring/tasks` | 创建 30 天监测任务 |
| `GET` | `/api/monitoring/tasks/{task_id}` | 读取单个监测任务 |
| `POST` | `/api/monitoring/tasks/{task_id}/refresh` | 立即采集互动快照 |
| `DELETE` | `/api/monitoring/tasks/{task_id}` | 删除任务及历史快照 |

## 验证与测试

自动化测试使用脱敏 fixture 和模拟 AI 客户端，不会访问小红书或消耗真实 AI 额度：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check app tests
node --check app\static\app.js
```

需要单独检查真实小红书链路时，可以运行：

```powershell
.\.venv\Scripts\python.exe scripts\check_live_flow.py "AI眼镜"
```

该命令会真实访问小红书，要求有效登录态，并可能触发平台风控或验证码。

## 项目结构

```text
app/
├─ main.py                         FastAPI 页面、API 与服务生命周期
├─ config.py                       环境变量和本地路径配置
├─ models.py                       API、分析和监测数据模型
├─ services/
│  ├─ redbook_cli.py               安全调用 redbook CLI
│  ├─ normalizer.py                标准化搜索与详情数据
│  ├─ competitor_analyzer.py       本地规则与文本 AI 竞品分析
│  ├─ vision_analyzer.py           竞品封面和配图视觉分析
│  ├─ analysis_store.py            分析 JSON 本地存储与下载
│  ├─ promotion_generator.py       宣传文案与图片生成
│  ├─ monitoring_service.py        30 天采集规则与每日调度
│  └─ monitoring_store.py          监测 JSON 原子读写
├─ static/
│  ├─ app.js                       主工作流交互
│  ├─ monitoring_view.js           监测视图数据计算
│  └─ styles.css                   桌面与移动端样式
└─ templates/
   └─ index.html                   单页应用结构

scripts/
├─ check_environment.py            检查本地运行环境
├─ check_live_flow.py              检查真实搜索、详情和图片代理
├─ save_chrome_cookies.py          安全保存手动 Cookie
└─ patch-redbook-cdp.mjs           redbook 本地兼容补丁

data/
├─ analyses/                       本地分析 JSON，默认忽略提交
└─ monitoring.json                 监测任务与快照，默认忽略提交
```

## 安全和使用边界

`redbook` 使用小红书非官方接口，接口可能变化或受到平台限制。本项目遵循以下边界：

- 仅用于本地、低频、只读的竞品研究和内容策划。
- 不提供网页 Cookie 输入框，不把 Cookie 或 AI 密钥返回给浏览器。
- 不使用 `shell=True`，用户输入不会作为 Shell 脚本执行。
- 图片代理只允许小红书与 `xhscdn.com` 的 HTTPS 地址，并限制响应大小和重定向次数。
- 竞品笔记、标题和图内文字均按不可信输入处理，不执行其中可能包含的指令。
- AI 文案只允许使用产品说明中明确提供的事实，避免虚构功效、参数、认证、价格或销量。
- 宣传图片以用户上传图片作为产品身份参考，不复制竞品图片。
- 分析 JSON 和监测数据会持久化在本机；产品上传图和生成图片默认不单独落盘。
- 不建议将该项目直接改造成公开、高频抓取或无人值守发布服务。

遇到验证码、会话过期或平台限制时，应停止采集并重新检查登录状态，不要尝试绕过平台安全机制。

## 常见问题

### 页面可以打开，但无法采集

先运行：

```powershell
.\node_modules\.bin\redbook.cmd whoami
```

如果失败，请更新 Cookie 文件，并检查 `.env` 中的 `REDBOOK_COOKIE_FILE`。

### 报告显示“本地规则分析”

说明文本和视觉 AI 调用都没有成功。检查 `AI_API_KEY`、`AI_BASE_URL`、`AI_MODEL` 和模型权限。
第 3 步仍会保留本地分析结果。

### “生成宣传内容”按钮不可用

需要同时满足：产品信息非空、至少上传一张产品图片，以及第 3 步生成了真实 AI 分析结果。

### 文案成功，但图片生成失败

确认 `AI_IMAGE_MODEL` 支持 OpenAI Images Edit API，并适当增加 `AI_IMAGE_TIMEOUT_SECONDS`。
兼容 Chat Completions 不代表同时兼容图片编辑接口。

### 监测任务没有自动更新

自动任务只在应用进程运行时执行，每天北京时间 10:00 检查一次。也可以在页面中点击“立即更新”。
