---
name: publish-md-to-wechat
description: >
  Professional Markdown to WeChat Official Account (公众号) publisher with visual style presets.
  Use this skill whenever the user wants to: publish an article to WeChat, create a 公众号 draft,
  format a blog post or technical tutorial for WeChat, apply a visual style to Markdown, or says
  anything like "发布到微信"、"推送到公众号"、"微信文章"、"publish to WeChat"、"WeChat draft"、
  "公众号推文"、"wechat article"、"微信公众号". Also trigger when the user asks to convert Markdown
  to a styled HTML document for WeChat, even if they don't say "publish" explicitly. Also trigger
  for translation/repost requests: "全文翻译"、"转载"、"translate and publish"、"repost"、or when the
  source article is in English and the user wants to publish it to WeChat. This skill handles
  credentials, image uploads, 13 style presets (3 core + 7 extend + unlimited custom), automatic
  cover generation, full-article translation, and draft creation end-to-end.
---

# publish-md-to-wechat

Publishes Markdown articles to WeChat Official Account drafts with professional visual styling,
automatic image handling, and cover generation.

## Operating Modes (strict boundary)

### Mode A — Article Publish (公众号图文)
Use when user wants Markdown -> WeChat draft publishing.
- Inputs: `--md`, style, optional thumb/title
- Output: WeChat draft media id
- Command family: `scripts/wechat_publisher.py`

### Mode B — Video Render (视频号)
Use when user wants vertical MP4 generation.
- Inputs (required): pre-generated `tmp/slides.md` + `tmp/narration.json`
- Output: local `.mp4`
- Command family: `scripts/video_publisher.py`
- **Important:** This mode is execution-only. Planning (outline/slide content/narration writing) is done by caller/agent before invoking the script.

### Mode C — Translation & Repost (全文翻译/转载)
Use when user wants to translate a foreign-language article and publish it to WeChat.
- Trigger: "全文翻译"、"转载"、"translate"、"repost"、or source article is in English/other language.
- Inputs: source Markdown file (English or other language)
- Output: WeChat draft media id (same as Mode A)
- Workflow: Agent translates natively (no Python script) → saves to `/tmp/translated_article.md` → proceeds as Mode A.
- **Important:** Translation is done by the agent itself, not by any script. Do not invoke an LLM via Python for translation.

Do not mix Mode A and Mode B steps in one flow unless user explicitly asks for both deliverables.
Mode C always ends with Mode A publishing — it is a pre-processing step, not a separate pipeline.

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

## Phase 1B: Mode C — Translation & Repost

**Do not summarize or adapt — translate the full article faithfully.**

1. Read the source Markdown file completely.
2. Translate the entire content to Chinese, preserving:
   - All Markdown structure (headings, lists, code blocks, blockquotes, images)
   - Original section order and hierarchy
   - Technical terms in English where standard (e.g. agent, token, context window, bash)
   - Code blocks verbatim — do not translate code
   - Author attribution in frontmatter: `> 本文译自：[原文标题](url)，作者：[Author]（[Publication]）`
3. Write YAML frontmatter with `title`, `author`, `description` in Chinese.
4. Save to `/tmp/translated_article.md`.
5. Proceed to Phase 2 with the translated file as `--md`.

**Do not ask for confirmation before translating** — if the user said "全文翻译/转载", just do it.

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

**CRITICAL: Narration Quality Rules (avoid filler/repetition)**
- Audience/tone are **global constraints**, not per-scene slogans. Do **not** repeatedly say phrases like `面向AI开发者` / `关键在于` in every scene.
- Each scene narration must add **new information** (fact, example, contrast, action step), not template padding.
- Ban empty framing lines: `我们来看看`, `关键在于`, `总的来说` unless they introduce concrete content right after.
- Keep narration concise and spoken: typically 1-3 short sentences per scene; avoid paragraph-long monologues.
- Avoid repeating the same sentence pattern across scenes.
- Prefer concrete wording over abstract buzzwords.

**Narration self-check before writing files:**
1. Read all scene narrations end-to-end.
2. If any phrase stem repeats in 3+ scenes (e.g., `面向…`, `关键在…`), rewrite.
3. Ensure each scene has a unique takeaway in one line.
4. Remove all non-informational filler.

**CRITICAL: Slidev Formatting for Vertical Video (9:16)**
Because the output is a mobile vertical video, default Slidev text is too small and pushed to the top. You MUST inject custom CSS and layout directives into `tmp/slides.md` to make it look professional:
- Add `aspectRatio: 9/16` and `canvasWidth: 1080` to the frontmatter.
- Use `theme: seriph` for `swiss`, `default` for others.
- Add an appealing Unsplash background to the title slide (e.g., `background: https://images.unsplash.com/photo-...`).
- Use `layout: center` and `class: text-center` for all slides to center content.
- Inject a `<style>` block in the title slide to make `h1` very large (e.g., `5rem`), `h2` large (e.g., `3rem`), and optionally add a gradient text effect.
- Inject `<style>` blocks in content slides to make `li` and `p` large enough to read on mobile (e.g., `2.5rem`, `line-height: 2`).

- `tmp/narration.json` must align with the scenes in the slides.
  ```json
  {
    "scenes": [
      { "title": "Title", "narration": "大家好...", "scene_type": "title" },
      { "title": "Point 1", "narration": "第一点...", "scene_type": "content" }
    ]
  }
  ```

**Step 2: Render and Compose (execution-only)**
Use the script to export slides, synthesize TTS, and compose the final MP4.
Do **not** pass `--md` for planning; Mode B requires pre-generated slides + narration.

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

Style replication uses Playwright `getComputedStyle()` (not inline CSS parsing) for accurate colors,
and automatically detects structural patterns:
- **Heading style**: `bg-block` (colored section bg) / `left-border` / `underline` / `plain`
- **Blockquote style**: `left-border` / `full-box` / `plain`

The renderer applies these structural hints when publishing with a custom style.

```bash
# Create from WeChat article (give it a meaningful name)
.venv/bin/python3 scripts/styles.py --url https://mp.weixin.qq.com/s/xxx --name custom-myname --no-verify-ssl

# List all styles (core / extend / custom)
.venv/bin/python3 scripts/styles.py --list

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
