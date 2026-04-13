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

**Important:** Before generating the video, you MUST ask the user for the following preferences if they haven't provided them explicitly in their request:
1. **Target Duration** (e.g., 30s, 60s, 90s)
2. **Narration Tone** (e.g., 专业克制, 轻松幽默, 热情洋溢)
3. **Target Audience** (e.g., AI开发者, 产品经理, 大众)
4. **Visual Style** (e.g., swiss, ink, minimal)
5. **TTS Voice** (Optional, default to `zh_male_m191_uranus_bigtts` or let user pick)

**Do not guess or assume these 5 parameters.** If the user simply says "convert to video", you MUST stop and ask them to specify duration, tone, audience, and style first.

**Step 1: Agent Plans Outline and Narration (DO NOT use python scripts for LLM calls)**
Read the Markdown file. Act as an expert presentation editor. You (the Agent) MUST natively generate the `tmp/slides.md` (Slidev format) and `tmp/narration.json` based on the user's requested duration, tone, audience, and style.

- `tmp/slides.md` must be valid Slidev markdown. Use `theme: seriph` for `swiss`, `default` for others. Add `aspectRatio: 9/16` and `canvasWidth: 1080`.
- `tmp/narration.json` must align with the scenes in the slides.
  ```json
  {
    "scenes": [
      { "title": "Title", "narration": "大家好...", "scene_type": "title" },
      { "title": "Point 1", "narration": "第一点...", "scene_type": "content" }
    ]
  }
  ```

**Step 2: Render and Compose**
Use the script to export slides, synthesize TTS, and compose the final MP4.

```bash
# 导出 MP4
.venv/bin/python3 scripts/video_publisher.py \
  --slides tmp/slides.md \
  --narration tmp/narration.json \
  --duration 60 \
  --style [STYLE] \
  --voice zh_male_m191_uranus_bigtts \
  --no-verify-ssl \
  --out [OUTPUT.mp4]
```

依赖：`ffmpeg`、`npx`（Node.js）用于 Slidev 导出，使用配音时额外需要 `websocket-client`。

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
