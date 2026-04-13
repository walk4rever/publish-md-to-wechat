---
name: publish-md-to-wechat
description: >
  Professional Markdown to WeChat Official Account (公众号) publisher with visual style presets.
  Use this skill whenever the user wants to: publish an article to WeChat, create a 公众号 draft,
  format a blog post or technical tutorial for WeChat, apply a visual style to Markdown, or says
  anything like "发布到微信"、"推送到公众号"、"微信文章"、"publish to WeChat"、"WeChat draft"、
  "公众号推文"、"wechat article"、"微信公众号". Also trigger when the user asks to convert Markdown
  to a styled HTML document for WeChat, even if they don't say "publish" explicitly. This skill
  handles credentials, image uploads, 11 style presets (3 core + 7 extend + custom), automatic
  cover generation, and draft creation end-to-end.
---

# publish-md-to-wechat

Publishes Markdown articles to WeChat Official Account drafts with professional visual styling,
automatic image handling, and cover generation.

## Phase 1: Environment & Credentials

**Check dependencies:**
```bash
ls .venv/bin/python 2>/dev/null || echo "MISSING"
```
If `.venv` is missing, run `./install.sh`.

**Credentials:** Loaded automatically from `.env` in the current directory, or
`~/.config/publish-md-to-wechat/.env` as global fallback. Only ask the user for credentials
if the script explicitly fails with an auth error.

---

## Phase 2: Read the Article & Select a Style

Read the Markdown file to understand the content's tone. Then pick a style.

**List all styles:**
```bash
.venv/bin/python3 scripts/styles.py --list
```

**Style selection guide:**

| Category | Styles | When to use |
|----------|--------|-------------|
| ⭐ Core | `swiss`, `editorial`, `ink` | Default choice. Covers 90% of content types. |
| 📦 Extend | `notebook`, `geometry`, `botanical`, `terminal`, `bold`, `cyber`, `voltage` | Specific scenarios only. |
| 🎨 Custom | `custom-xxx` | User-created from WeChat article analysis. |

**Core trio quick guide:**
- `swiss` — Technical articles, tutorials, reports, official announcements
- `editorial` — Opinion pieces, analysis, blog posts, personal brands
- `ink` — Humanities, culture, deep dives, literary content

Propose the style with a one-line reason. Skip if the user already specified.

---

## Phase 3: Validate First (Recommended for complex articles)

```bash
.venv/bin/python3 scripts/wechat_publisher.py \
  --md [PATH] --style [STYLE] --dry-run --out-html /tmp/preview.html
open /tmp/preview.html
```

---

## Phase 4: Publish

```bash
.venv/bin/python3 scripts/wechat_publisher.py \
  --md [PATH] --style [STYLE]
```

**Key flags:**
- `--thumb [PATH]` — Custom cover (auto-generates if omitted)
- `--title "[TITLE]"` — Override title (auto-detects from frontmatter/H1)
- `--no-verify-ssl` — For SSL cert issues
- `-v` — Verbose logging

**YAML Frontmatter:** Title, author, description auto-extracted:
```yaml
---
title: Article Title
author: Author Name
description: Short summary for WeChat article list.
---
```

---

## Phase 4B: Generate WeChat Video (视频号)

By default, ALWAYS generate video WITH TTS voice unless explicitly told not to.
Ensure `VOLCANO_TTS_APPID` and `VOLCANO_TTS_ACCESS_TOKEN` are in the `.env` file, or load them from the environment.

```bash
# 导出 MP4（默认：带配音）
.venv/bin/python3 scripts/video_publisher.py --md [PATH] --style [STYLE] --voice zh_male_m191_uranus_bigtts --out [OUTPUT.mp4]
```

```bash
# 仅生成幻灯片预览
.venv/bin/python3 scripts/video_publisher.py --md [PATH] --style [STYLE] --dry-run --out-html /tmp/slides.html
```

```bash
# 导出 MP4（无配音 - 仅在用户明确要求时使用）
.venv/bin/python3 scripts/video_publisher.py --md [PATH] --style [STYLE] --no-tts --out [OUTPUT.mp4]
```

依赖：`ffmpeg`、`playwright + chromium`，使用配音时额外需要 `websocket-client`。

---

## Phase 5: Success Output

```
## 🚀 发布成功！

| 字段 | 值 |
|------|-----|
| **标题** | [Title] |
| **风格** | `[style]` — [one-line description] |
| **Media ID** | `[MEDIA_ID]` |

**下一步：** mp.weixin.qq.com → 草稿箱 → 预览 → 发布
```

---

## Custom Styles

```bash
# Create from WeChat article
.venv/bin/python3 scripts/styles.py --url https://mp.weixin.qq.com/s/xxx --no-verify-ssl

# Rename
.venv/bin/python3 scripts/styles.py --rename custom-old custom-new

# Use
.venv/bin/python3 scripts/wechat_publisher.py --md article.md --style custom-xxx
```

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| **40164** IP whitelist | Add IP at mp.weixin.qq.com → 设置与开发 → IP白名单 |
| **40125 / 40013** Invalid credentials | Check `.env` |
| **45009** Rate limit | Auto-retries; wait if persists |
| **SSL errors** | Add `--no-verify-ssl` |
| **Image not found** | Check filename (case-sensitive), ensure image is in article directory |
| **Cover failed** | Falls back to `assets/default_thumb.png`; or use `--thumb` |
| **Missing dependencies** | Run `./install.sh` |
