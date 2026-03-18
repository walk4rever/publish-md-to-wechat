# Publish MD to WeChat

**v0.6.0** · [English](#english) | [中文](#中文)

---

<a name="english"></a>
## English

Publish Markdown articles to WeChat Official Account (公众号) drafts with professional styling, automatic image handling, and cover generation.

### Features

- **AST-Powered Rendering** — `mistune` 3.x for reliable conversion of complex Markdown (nested lists, tables, code blocks)
- **11 Visual Styles** — 3 core + 7 extend + unlimited custom styles
- **Custom Style Replication** — Analyze any WeChat article URL, extract its visual style, save as reusable preset
- **Obsidian Ready** — Native `![[WikiLink]]` image syntax support
- **Smart Image Upload** — Local images, external URLs auto-uploaded to WeChat CDN
- **Auto Cover Generation** — Branded PNG cover from title + style via Pillow
- **YAML Frontmatter** — Auto-extracts title, author, description from frontmatter
- **Video URL Detection** — YouTube/Bilibili links rendered as text links, not broken images

### Quick Start

```bash
# 1. Setup
./install.sh
cp env.example .env   # Add WECHAT_APP_ID and WECHAT_APP_SECRET

# 2. Publish
.venv/bin/python3 scripts/wechat_publisher.py --md article.md --style swiss

# 3. Preview (no API calls)
.venv/bin/python3 scripts/wechat_publisher.py --md article.md --style ink --dry-run --out-html /tmp/preview.html
```

### Styles

```bash
# List all styles with descriptions
.venv/bin/python3 scripts/styles.py --list
```

**Core (recommended):**

| Style | Description |
|-------|-------------|
| `swiss` | Swiss International. White + red, grid-driven, professional. Technical articles, reports. |
| `editorial` | Magazine editorial. Warm cream, serif, wide spacing. Opinion pieces, analysis. |
| `ink` | Eastern ink. Warm white, crimson accent, max line-height. Humanities, deep writing. |

**Extend (7 more):** `notebook`, `geometry`, `botanical`, `terminal`, `bold`, `cyber`, `voltage`

**Custom:** Analyze any WeChat article and replicate its style:
```bash
# Create custom style from article
.venv/bin/python3 scripts/styles.py --url https://mp.weixin.qq.com/s/xxx --no-verify-ssl

# Rename
.venv/bin/python3 scripts/styles.py --rename custom-old custom-new

# Use it
.venv/bin/python3 scripts/wechat_publisher.py --md article.md --style custom-kimi
```

Custom styles are stored in `~/.config/publish-md-to-wechat/custom-styles/` as JSON files with `custom-` prefix.

### Command Reference

```bash
.venv/bin/python3 scripts/wechat_publisher.py \
  --md article.md \          # Markdown file (required)
  --style swiss \            # Style preset (default: swiss)
  --thumb cover.png \        # Custom cover image (optional, auto-generates)
  --title "My Title" \       # Override title (auto-detects from frontmatter/H1)
  --no-verify-ssl \          # Disable SSL verification
  --dry-run --out-html /tmp/preview.html \  # Local preview
  -v                         # Verbose logging
```

```bash
.venv/bin/python3 scripts/styles.py \
  --list \                   # List all styles
  --url <wechat-url> \       # Analyze article and create custom style
  --file <local.html> \      # Analyze local HTML
  --rename OLD NEW \         # Rename custom style
  --name custom-xxx \        # Specify style name
  --dry-run                  # Analyze only, don't save
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

### Caching

Token and image caches stored at:
- macOS: `~/Library/Caches/publish-md-to-wechat/`
- Linux: `~/.cache/publish-md-to-wechat/`

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

将 Markdown 文章发布到微信公众号草稿箱，支持专业视觉样式、自动图片处理和封面生成。

### 功能

- **AST 渲染引擎** — `mistune` 3.x 处理复杂 Markdown（嵌套列表、表格、代码块）
- **11 种视觉样式** — 3 核心 + 7 扩展 + 无限自定义
- **样式复刻** — 分析任意微信文章 URL，提取视觉风格，保存为可复用预设
- **Obsidian 兼容** — 原生支持 `![[WikiLink]]` 图片语法
- **智能图片上传** — 本地图片、外部 URL 自动上传微信 CDN
- **封面自动生成** — 基于标题和样式通过 Pillow 生成品牌 PNG 封面
- **YAML Frontmatter** — 自动提取标题、作者、摘要
- **视频链接检测** — YouTube/Bilibili 链接渲染为文字链接，不会当图片处理

### 快速开始

```bash
# 1. 初始化
./install.sh
cp env.example .env   # 填入 WECHAT_APP_ID 和 WECHAT_APP_SECRET

# 2. 发布
.venv/bin/python3 scripts/wechat_publisher.py --md article.md --style swiss

# 3. 本地预览（不调用 API）
.venv/bin/python3 scripts/wechat_publisher.py --md article.md --style ink --dry-run --out-html /tmp/preview.html
```

### 样式管理

```bash
# 查看所有样式
.venv/bin/python3 scripts/styles.py --list

# 从微信文章复刻样式
.venv/bin/python3 scripts/styles.py --url https://mp.weixin.qq.com/s/xxx --no-verify-ssl

# 重命名
.venv/bin/python3 scripts/styles.py --rename custom-old custom-new
```

**核心样式（推荐）：**

| 样式 | 说明 |
|------|------|
| `swiss` | 瑞士国际主义。白底红色，网格感强。适合技术文章、产品更新。 |
| `editorial` | 杂志编辑。暖米色，衬线字体。适合观点文章、深度分析。 |
| `ink` | 东方水墨。暖白底，深红强调。适合人文历史、深度长文。 |

**扩展样式（7 种）：** `notebook`、`geometry`、`botanical`、`terminal`、`bold`、`cyber`、`voltage`

自定义样式存储在 `~/.config/publish-md-to-wechat/custom-styles/`。

### 凭证配置

优先级：命令行参数 → 项目 `.env` → `~/.config/publish-md-to-wechat/.env` → 系统环境变量

### 错误处理

| 错误码 | 原因 | 解决方案 |
|--------|------|----------|
| `40164` | IP 未在白名单 | 在微信后台添加 IP |
| `40125` / `40013` | 凭证错误 | 检查 `.env` |
| `45110` | 作者字段超限 | v0.6.0 已自动截断 |
| SSL 错误 | 企业代理 | 添加 `--no-verify-ssl` |

---

*Developed by **Air7.fun** · Open-source under MIT*
