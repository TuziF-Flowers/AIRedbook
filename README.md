# AI种草官 · 小红书竞品内容洞察 Demo

一个本地优先、AI 驱动的小红书竞品内容洞察工作台。输入产品、品类与最多 3 个竞品后，系统通过
固定版本的 [`lucasygu/redbook`](https://github.com/lucasygu/redbook) 获取高互动图文样本，
完成内容过滤、字段标准化与本地规则分析，并可调用兼容 OpenAI Chat Completions 的模型服务，
将样本证据进一步提炼为结构化 AI 洞察与可交付报告。

## AI 核心能力

1. **面向 AI 洞察的交互工作台**：采用原生 HTML、CSS、JavaScript 搭建单页 Web 工作台，支持录入产品或品类名称、管理最多 3 个竞品标签、查看采集进度、按竞品筛选、按互动指标排序、浏览笔记详情图集，并以分栏方式查看 AI 洞察与 Markdown 报告。
2. **为 AI 准备可靠样本的数据采集**：后端使用 Python FastAPI，通过固定版本的 redbook CLI 调用小红书搜索与详情读取能力；优先复用本地 Cookie 文件保持登录态，并通过并发限制、请求超时以及验证码和会话过期提示控制采集过程。
3. **面向 AI 分析的数据理解与筛选**：统一兼容不同来源字段，标准化标题、作者、正文、图片、标签以及点赞、收藏、评论和分享数据；从热门图文中排除测评、对比、避雷与合集内容，再依据种草表达、使用场景和互动量筛选排序，最多汇总 20 篇高价值样本。
4. **规则引擎与大模型协同生成洞察**：本地规则引擎先完成关键词、标题模板、正文结构、文案框架、图片数量和互动指标分析，确保在无模型配置时也能输出完整结果；配置兼容 OpenAI Chat Completions 的模型服务后，大模型会结合样本与规则证据生成结构化 AI 洞察，调用失败时自动回退到本地规则结果。
5. **本地优先的 AI 安全与交付**：应用默认仅监听本机地址，不通过网页收集 Cookie，也不建立数据库保存搜索历史；笔记图片经受限域名代理展示，洞察结果支持网页预览、复制、Markdown 下载，并生成不含登录凭据的本地分析 JSON，便于后续工作流复用。

## 功能

- 关键词搜索
- 固定热门图文搜索
- 按“点赞数 + 收藏数”展示互动最高的前 20 篇
- Top 20 互动图文卡片和缩略图补全
- 笔记详情和多图浏览
- 标题关键词、标题模板和标题特点分析
- 正文结构与文案内容分析
- 图片结构和互动数据分析
- 本地规则基线分析与大模型增强洞察
- AI 调用失败时自动回退到完整的本地规则结果
- Markdown 报告预览、复制和下载
- 登录状态检查
- Cookie 过期、超时和空结果提示
- 小红书链接域名校验

项目默认只监听 `127.0.0.1`，不会通过网页收集或保存 Cookie。

## 环境要求

- Python 3.11+
- Node.js 22+
- Chrome 中已登录 [小红书网页版](https://www.xiaohongshu.com/)，或已有 redbook Cookie 文件

## 安装

在项目目录打开 PowerShell：

```powershell
cd D:\yxchen42\redbook-search-demo

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"

npm install
```

检查 Python、Node.js 和 redbook：

```powershell
python scripts\check_environment.py
```

验证小红书登录状态：

```powershell
.\node_modules\.bin\redbook.cmd whoami
```

项目会优先使用浏览器无关的本地 Cookie 文件：

```text
C:\Users\<你的用户名>\.redbook\cookies.json
```

也可以在 `.env` 中指定其他位置：

```dotenv
REDBOOK_COOKIE_FILE=C:\secure\redbook-cookies.json
```

应用会优先选择 `cookies.chrome.json`，然后回退到 `cookies.json`。更新 Chrome
登录态前需要先关闭所有 Chrome 窗口，避免浏览器锁住 Cookie 数据库：

```powershell
npm run auth:chrome
```

如果 Cookie 自动导出仍失败，可以按照 redbook 文档从 Chrome 开发者工具取得新的
`a1` 和 `web_session`，然后使用隐藏输入脚本保存；Cookie 不会出现在命令历史中：

```powershell
npm run auth:manual
```

网页中的封面、头像和详情图默认通过本地 `/api/images/proxy` 加载，避免小红书 CDN
的来源检查导致只有文字而没有图片。代理只接受小红书和 `xhscdn.com` 的 HTTPS 地址。

Cookie 是登录凭据，不要把 Cookie 值写入 `.env`、代码、截图或 Git。

## 启动

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

浏览器访问 `http://127.0.0.1:8000`，接口调试页为
`http://127.0.0.1:8000/api/docs`。

## 配置

复制 `.env.example` 为 `.env` 后可以覆盖默认配置。通常不需要设置
`REDBOOK_EXECUTABLE`；应用会优先寻找项目内 `node_modules/.bin/redbook`，
然后寻找全局安装的命令。

竞品分析默认使用本地规则，不需要额外密钥。需要启用 AI 深度总结时，在 `.env`
中配置任意兼容 OpenAI Chat Completions 的模型服务：

```dotenv
AI_API_KEY=你的密钥
AI_BASE_URL=https://api.openai.com/v1
AI_MODEL=你的模型名称
```

AI 服务不可用时会自动回退到本地规则分析，不影响采集和报告导出。

## 测试

测试只使用脱敏 fixture，不会访问小红书：

```powershell
pytest
ruff check .
```

## 项目结构

```text
app/
├─ main.py                 FastAPI 页面和接口
├─ config.py               本地配置
├─ models.py               对前端稳定的数据模型
├─ services/
│  ├─ redbook_cli.py       安全调用 redbook CLI
│  ├─ competitor_analyzer.py 竞品、文案和 AI 总结
│  └─ normalizer.py        兼容和标准化原始 JSON
├─ static/
│  ├─ app.js
│  └─ styles.css
└─ templates/
   └─ index.html
```

## 安全和使用边界

`redbook` 使用小红书非官方接口，接口可能变化或受到平台限制。本项目：

- 仅设计为本地、只读 Demo。
- 不提供 Cookie 输入页面。
- 不使用 `shell=True`，关键词不会作为 Shell 脚本执行。
- 默认限制并发，并为 CLI 请求设置超时。
- 不持久化笔记、图片、Cookie 或搜索记录。
- 不建议直接改造成公开、高频抓取服务。
