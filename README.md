# 红研 AI · 小红书竞品分析 Demo

一个本地运行的 Python Web Demo。输入产品、品牌或话题关键词后，通过
[`lucasygu/redbook`](https://github.com/lucasygu/redbook) 搜索小红书笔记，并在网页中展示封面、
标题、作者、互动信息、正文和图集，再生成结构化竞品内容分析报告。

## 功能

- 关键词搜索
- 固定热门图文搜索
- 按“点赞数 + 收藏数”展示互动最高的前 20 篇
- Top 20 互动图文卡片和缩略图补全
- 笔记详情和多图浏览
- 标题关键词、标题模板和标题特点分析
- 正文结构与文案内容分析
- 图片结构和互动数据分析
- AI 深度总结或本地规则降级分析
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
