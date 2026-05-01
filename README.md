# Publish MD to WeChat

**v0.8.2** · [English](#english) | [中文](#中文)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **The missing publishing pipeline for WeChat's 1.3 billion users.**
> Write in Markdown. Publish with one command. Beautiful articles, zero formatting pain.

---

<a name="english"></a>
## English

### The Problem

WeChat Official Accounts (公众号) power **23 million+ publishers** — brands, creators, media, enterprises — reaching the world's largest messaging audience. Yet every publisher faces the same bottleneck: WeChat's built-in editor destroys formatting, forces manual image uploads, and produces articles that all look the same.

**publish-md-to-wechat** is the open-source CLI that eliminates this friction: write in Markdown, run one command, and a professionally styled article — with images uploaded, cover generated, and formatting preserved — lands in your draft box ready to publish.

### Why It Matters

| Metric | Impact |
|--------|--------|
| **23M+ Official Accounts** | Every one needs a better publishing workflow |
| **30+ min saved per article** | Manual formatting → one command |
| **13 professional styles** | 3 core + 7 extended + unlimited custom via URL replication |
| **Zero lock-in** | MIT-licensed, your Markdown stays yours |

### How It Works

```
article.md → [Markdown AST] → [Style Engine] → [Styled HTML]
                                      ↓
                              [Image Processor]
                              · local files → WeChat CDN
                              · external URLs → WeChat CDN
                              · Obsidian ![[WikiLinks]] → resolved
                                      ↓
                              [Cover Generator]
                              · Pillow-based branded PNG
                              · title + accent color from style
                                      ↓
                              [WeChat API Client]
                              · upload media → create draft
                              · auto-retry with exponential backoff
```

### Quick Start

```bash
# 1. Setup
./install.sh
cp env.example .env   # Add WECHAT_APP_ID and WECHAT_APP_SECRET

# 2. Publish
.venv/bin/python3 scripts/wechat_publisher.py --md article.md --style swiss

# 3. Preview (no API calls)
.venv/bin/python3 scripts/wechat_publisher.py --md article.md --style ink --dry-run --out-html /tmp/preview.html

# 4. Generate vertical video (1080x1920)
# First prepare tmp/slides.md + tmp/narration.json via agent/planner
.venv/bin/python3 scripts/video_publisher.py \
  --slides tmp/slides.md \
  --narration tmp/narration.json \
  --duration 60 \
  --style swiss
```

### Features

| Category | Capability |
|----------|-----------|
| **Rendering** | AST-powered via `mistune` 3.x — nested lists, tables, code blocks, footnotes |
| **Styles** | 3 core classics + 7 extended + unlimited custom styles via URL replication (Playwright-powered: extracts computed colors + heading/blockquote structure) |
| **Images** | Local files, external URLs, Obsidian WikiLinks — auto-uploaded to WeChat CDN |
| **Covers** | Auto-generated branded PNG from title + style (Pillow) |
| **Metadata** | YAML frontmatter auto-extraction (title, author, description) |
| **Video links (article mode)** | YouTube/Bilibili links → clean text links, not broken images |
| **Video export (new)** | Markdown → LLM planning → Slidev PNG export → narration (Volcengine TTS) → MP4 |
| **Credentials** | Project `.env` → global config → env vars (multi-level priority) |
| **Preview** | `--dry-run` generates HTML locally, zero API calls |

### Styles

```bash
# List all available styles
.venv/bin/python3 scripts/styles.py --list
```

**Core Classics — recommended starting points:**

| Style | Aesthetic | Best For |
|-------|-----------|----------|
| `swiss` | White + red, grid-driven, Müller-Brockmann precision | Tech articles, reports, announcements |
| `editorial` | Warm cream, serif, NYT/New Yorker print heritage | Opinion pieces, analysis, essays |
| `ink` | Warm white, crimson accent, Chinese calligraphy meets digital | Humanities, culture, literary writing |

**Extended:** `notebook` · `geometry` · `botanical` · `terminal` · `bold` · `cyber` · `voltage`

**Custom Style Replication:**
```bash
# Analyze any WeChat article and replicate its visual style
.venv/bin/python3 scripts/styles.py --url https://mp.weixin.qq.com/s/xxx --no-verify-ssl

# Rename custom style
.venv/bin/python3 scripts/styles.py --rename custom-old custom-new

# Publish with custom style
.venv/bin/python3 scripts/wechat_publisher.py --md article.md --style custom-kimi
```

Custom styles are stored in `~/.config/publish-md-to-wechat/custom-styles/` as JSON files with `custom-` prefix.

### Video Generation (WeChat 视频号)

> Planning (outline/slides/narration) is handled by the caller/agent first.
> `video_publisher.py` is execution-only: render Slidev + TTS + compose MP4.

```bash
# 1) Prepare assets first
# - tmp/slides.md (Slidev markdown)
# - tmp/narration.json ({"scenes": [...]})

# 2) Dry run: validate inputs and pipeline setup
.venv/bin/python3 scripts/video_publisher.py \
  --slides tmp/slides.md \
  --narration tmp/narration.json \
  --duration 60 \
  --style swiss \
  --dry-run

# 3) Export MP4 without narration
.venv/bin/python3 scripts/video_publisher.py \
  --slides tmp/slides.md \
  --narration tmp/narration.json \
  --duration 60 \
  --style swiss \
  --no-tts \
  --out article.mp4

# 4) Export MP4 with Volcengine narration
export VOLCANO_TTS_APPID=xxx
export VOLCANO_TTS_ACCESS_TOKEN=xxx
.venv/bin/python3 scripts/video_publisher.py \
  --slides tmp/slides.md \
  --narration tmp/narration.json \
  --duration 90 \
  --style ink \
  --voice zh_female_qingxin_moon_bigtts \
  --out article.mp4
```

**Video dependencies:**
- `ffmpeg` (system package)
- `npx` (Node.js / npm runtime for Slidev CLI)
- `websocket-client` (only when using TTS)

### Command Reference

```bash
# Publish
.venv/bin/python3 scripts/wechat_publisher.py \
  --md article.md \          # Markdown file (required)
  --style swiss \            # Style preset (default: swiss)
  --thumb cover.png \        # Custom cover image (optional, auto-generates)
  --title "My Title" \       # Override title (auto-detects from frontmatter/H1)
  --no-verify-ssl \          # Disable SSL verification
  --dry-run --out-html /tmp/preview.html \  # Local preview
  -v                         # Verbose logging

# Style management
.venv/bin/python3 scripts/styles.py \
  --list \                   # List all styles
  --url <wechat-url> \       # Analyze article and create custom style
  --file <local.html> \      # Analyze local HTML
  --rename OLD NEW \         # Rename custom style
  --name custom-xxx \        # Specify style name
  --dry-run                  # Analyze only, don't save

# Clear all drafts
.venv/bin/python3 scripts/clear_drafts.py
```

### Credentials

Priority: CLI args → project `.env` → `~/.config/publish-md-to-wechat/.env` → shell env vars.

```bash
# Project-level (recommended)
echo 'WECHAT_APP_ID=xxx' > .env
echo 'WECHAT_APP_SECRET=xxx' >> .env

# Global (persists across updates)
mkdir -p ~/.config/publish-md-to-wechat
echo 'WECHAT_APP_ID=xxx' > ~/.config/publish-md-to-wechat/.env
```

### Error Reference

| Error | Cause | Fix |
|-------|-------|-----|
| `40164` IP whitelist | Server IP not allowed | Add IP in WeChat console |
| `40125` / `40013` | Invalid credentials | Check `.env` |
| `45009` Rate limit | Too many requests | Wait and retry |
| `45110` Author limit | Author field > 8 bytes | Auto-truncated in v0.6.0 |
| SSL errors | Corporate proxy | Add `--no-verify-ssl` |

---

<a name="中文"></a>
## 中文

### 核心问题

微信公众号覆盖 **2300 万+ 发布者**，却共享同一个痛点：自带编辑器毁格式、手动传图片、每篇文章千篇一律。

**publish-md-to-wechat** 是开源的命令行工具：用 Markdown 写作，一行命令发布，文章带着精美样式、上传好的图片、生成好的封面，直接进入草稿箱。

### 为什么重要

| 指标 | 价值 |
|------|------|
| **2300万+ 公众号** | 每一个都需要更好的发布流程 |
| **每篇节省 30+ 分钟** | 手工排版 → 一行命令 |
| **13 种专业样式** | 3 核心 + 7 扩展 + 无限自定义（URL 复刻） |
| **零锁定** | MIT 开源，Markdown 永远是你的 |

### 功能

- **AST 渲染引擎** — `mistune` 3.x 处理复杂 Markdown（嵌套列表、表格、代码块）
- **13 种视觉样式** — 3 经典核心 + 7 扩展 + 无限自定义
- **深度样式复刻** — Playwright 提取计算后样式（非 inline CSS），自动识别标题结构（色块/左边线/下划线）和引用块结构，保存为可复用预设
- **Obsidian 兼容** — 原生支持 `![[WikiLink]]` 图片语法
- **智能图片上传** — 本地图片、外部 URL 自动上传微信 CDN
- **封面自动生成** — 基于标题和样式通过 Pillow 生成品牌 PNG 封面
- **YAML Frontmatter** — 自动提取标题、作者、摘要
- **视频链接检测** — YouTube/Bilibili 链接渲染为文字链接
- **视频生成（新）** — Markdown 自动生成竖屏 MP4（切片、截图、配音、合成）
- **凭证管理** — 项目级、全局级或环境变量级凭证解析
- **本地预览** — `--dry-run` 模式生成 HTML 预览，不调用任何 API

### 快速开始

```bash
# 1. 初始化
./install.sh
cp env.example .env   # 填入 WECHAT_APP_ID 和 WECHAT_APP_SECRET

# 2. 发布
.venv/bin/python3 scripts/wechat_publisher.py --md article.md --style swiss

# 3. 本地预览（不调用 API）
.venv/bin/python3 scripts/wechat_publisher.py --md article.md --style ink --dry-run --out-html /tmp/preview.html

# 4. 生成竖屏视频（1080x1920）
# 先由 agent/planner 生成 tmp/slides.md + tmp/narration.json
.venv/bin/python3 scripts/video_publisher.py \
  --slides tmp/slides.md \
  --narration tmp/narration.json \
  --duration 60 \
  --style swiss
```

### 样式

**核心经典（推荐）：**

| 样式 | 美学 | 适用场景 |
|------|------|----------|
| `swiss` | 白底红色，网格精确 | 技术文章、报告、公告 |
| `editorial` | 暖米色，衬线字体 | 评论、分析、个人品牌 |
| `ink` | 暖白底，深红强调 | 人文、文化、深度写作 |

**扩展样式：** `notebook` · `geometry` · `botanical` · `terminal` · `bold` · `cyber` · `voltage`

**样式复刻：**
```bash
# 从微信文章复刻样式
.venv/bin/python3 scripts/styles.py --url https://mp.weixin.qq.com/s/xxx --no-verify-ssl

# 重命名
.venv/bin/python3 scripts/styles.py --rename custom-old custom-new

# 使用
.venv/bin/python3 scripts/wechat_publisher.py --md article.md --style custom-kimi
```

自定义样式存储在 `~/.config/publish-md-to-wechat/custom-styles/`。

### 凭证配置

优先级：命令行参数 → 项目 `.env` → `~/.config/publish-md-to-wechat/.env` → 系统环境变量

### 错误处理

| 错误码 | 原因 | 解决方案 |
|--------|------|----------|
| `40164` | IP 未在白名单 | 在微信后台添加 IP |
| `40125` / `40013` | 凭证错误 | 检查 `.env` |
| `45009` | 频率限制 | 等待后重试 |
| `45110` | 作者字段超限 | v0.6.0 已自动截断 |
| SSL 错误 | 企业代理 | 添加 `--no-verify-ssl` |

---

## Roadmap

| Feature | Status |
|---------|--------|
| Core publishing pipeline (AST render + image upload + draft) | ✅ Shipped |
| 10 built-in style presets | ✅ Shipped |
| Auto cover generation (Pillow) | ✅ Shipped |
| Custom style replication (Playwright computed styles + structural hints) | ✅ Shipped |
| Obsidian WikiLink support | ✅ Shipped |
| YAML frontmatter auto-extraction | ✅ Shipped |
| Style quality refinement (classic trio polish) | 🚧 In Progress |
| Parallel image upload | 📋 Planned |
| Template system for recurring formats | 📋 Planned |
| Web UI for non-technical users | 📋 Planned |
| Team collaboration & shared style libraries | 📋 Planned |

## License

[MIT](LICENSE) — free to use, modify, and distribute.

---

*Built by [Air7.fun](https://air7.fun) · Open Source*
