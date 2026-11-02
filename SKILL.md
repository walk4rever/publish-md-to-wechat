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
  source article is in English and the user wants to publish it to WeChat. Also trigger for
  "视频号"、"短视频"、"竖屏视频"、"生成视频"、"video"、"short video"、or "WeChat Channels".
  This skill handles
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
- Inputs: source article plus duration, tone, audience, visual style, and optional Edge TTS voice
- Output: local `.mp4`
- Command family: `scripts/video_publisher.py`
- **Important:** The agent plans the video and creates the project files; the script renders, narrates, subtitles, composes, and captures validation frames.

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

## Phase 1C: Frontmatter Adaptation (Vault Articles)

**Before publishing any Vault article, verify the frontmatter contains the fields WeChat publisher
needs to render the article header correctly.**

The publisher renders a metadata block at the top of every article using these specific keys:

| WeChat key | Renders as | Common Vault alias | Action |
|---|---|---|---|
| `author` | 作者 | same | ✅ usually present |
| `published` | 发布日期 | `date` | ⚠️ add `published:` if only `date:` exists |
| `tags` | 标签列表 | — | ⚠️ add if missing |
| `description` | 摘要 | `excerpt` | ⚠️ add `description:` if only `excerpt:` exists |
| `source` | 来源 | — | ⚠️ add `source: AI-DIVE · ai.air7.fun` for Vault articles |

**Script fallbacks (built-in):** The publisher script automatically falls back:
- `published` → `date` → `created` (first present wins)
- `description` → `excerpt` if `description` is absent

The metadata box labels are rendered in Chinese (来源/作者/发布/标签/摘要), and when the
frontmatter carries a title, the first in-body H1 is dropped (WeChat already shows the
title above the article).

So these alias pairs do not need to be manually patched before publishing. The remaining three
(`author`, `tags`, `source`) have no automatic alias — add them to frontmatter if missing.

**Minimal complete frontmatter for a Vault → WeChat article:**
```yaml
---
title: 文章标题
slug: type-YYYY-MM-DD-topic          # ai-dive API
date: YYYY-MM-DD                     # ai-dive API
published: YYYY-MM-DD                # WeChat header display
type: analysis                       # ai-dive API
author: Rafa
tags: [标签1,标签2, 标签3]           # WeChat header display
excerpt: 摘要文字                     # ai-dive API
description: 摘要文字                 # WeChat header display (same content as excerpt)
source: AI-DIVE · ai.air7.fun       # WeChat header display
og_image: https://...               # ai-dive cover (fill after upload)
cover: assets/topic-cover.png       # local preview
---
```

**Note:** `date` and `published` carry the same value; `excerpt` and `description` carry the same
content — the two systems use different keys for the same concept.

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

## Phase 3B: 敏感词扫描（必做，2026-08-31 血泪教训）

**发布到微信公众号草稿箱之前，必须先跑敏感词扫描。** 微信审核红线「不得不当使用国家机关、国家机关工作人员的名义或形象」
会拦截直呼国家领导人姓名或具体国家机关实名的内容（VC20260817 因 Harry 一句调侃"我觉得习近平不会给你发月度最佳员工奖"被拒）。

```bash
.venv/bin/python3 scripts/sensitive_scan.py --md [PATH]
```

- 退出码 **0** = 无红线词，可继续发布。
- 退出码 **1** = 发现 🔴 红线词，发布前必须改写（见下）。
- `--strict` 连广义词（"中国政府""国家形象"等）也打印完整语境，供人工判断。

**红线词处理规则：**
- 用「国家/官方/通用主体」等中性词替代领导人姓名或具名机构；
- 或删除整句调侃、改用无具体指向的表述。
- 源文件保持纯净（保留忠实原文），只在微信临时构建文件里改写——同 aidive_url/wechat_media_id 适配边界。

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
**Important:** Before generating the video, you MUST ask the user for the following preferences if they haven't provided them explicitly in their request:
1. **Target Duration** (e.g., 30s, 60s, 90s)
2. **Narration Tone** (e.g., 专业克制, 轻松幽默, 热情洋溢)
3. **Target Audience** (e.g., AI开发者, 产品经理, 大众)
4. **Visual Style** (e.g., swiss, ink, minimal)
5. **TTS Voice** (optional; default `zh-CN-YunxiNeural`)

**Do not guess or assume these 5 parameters.** If the user simply says "convert to video", you MUST stop and ask them to specify duration, tone, audience, and style first.

**Step 1: Agent Plans Scenes (DO NOT use Python scripts for LLM calls)**
Read the Markdown file. Act as an expert presentation editor. Natively create a video project directory containing `scenes.txt` and `gen_scenes.py`, based on the requested duration, tone, audience, and visual style.

Create the project first; do not start from a blank Python file:
```bash
.venv/bin/python3 scripts/video_publisher.py --init-project /tmp/video-project
```
Then edit `/tmp/video-project/scenes.txt` and `/tmp/video-project/gen_scenes.py`. The bundled generator is the visual baseline: retain its 1080×1920 canvas, brand line, page number, bottom bar, contrast, and common CSS; adapt the copy and layouts for the story.

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

**CRITICAL: HTML Scene Formatting for Vertical Video (9:16)**
- `scenes.txt` contains one ordered scene per line: `S1|spoken narration|optional written subtitle`.
- `gen_scenes.py` must generate `scenes/S1.html`, `scenes/S2.html`, and so on at 1080×1920.
- Use a shared CSS system in the generator: stable brand line, page number, bottom information bar, high-contrast text, and a restrained accent color.
- The spoken and subtitle text can differ for URLs and English terms. For example, speak `air7 点 fun` but subtitle `air7.fun`.
- Keep each scene to one idea. The script derives timing from the generated audio, adds a short breathing interval, and burns subtitles into the video.

**Step 2: Render and Compose (execution-only)**
Use the script to generate HTML, capture PNG scenes, synthesize narration, create subtitles, compose the MP4, and capture start/middle/end QA frames.

```bash
# 导出 MP4
.venv/bin/python3 scripts/video_publisher.py \
  --project-dir /tmp/video-project \
  --duration [SECONDS] \
  --voice zh-CN-YunxiNeural \
  --rate +6% \
  --out [OUTPUT.mp4]
```

依赖：`ffmpeg`、Python Playwright Chromium 和 `edge-tts`。

**Step 3: Mandatory visual QA**
Open `build/check_start.jpg`, `build/check_middle.jpg`, and `build/check_end.jpg`. Check subtitle line breaks, readable contrast, overflowing copy, spelling, and narration-to-scene alignment. If any frame fails, modify only the affected scene in `scenes.txt` / `gen_scenes.py`, then rerun the renderer. Do not report a video as complete without passing this check.

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
| **45166** invalid content (anchor links) | Article contains `href="#anchor"` links (e.g. table of contents). These are auto-stripped by the post-processor since v0.7.0. If you see this on older versions, upgrade. |
| **SSL errors** | Add `--no-verify-ssl` |
| **Image not found** | Check filename (case-sensitive), ensure image is in article directory |
| **Cover failed** | Falls back to `assets/default_thumb.png`; or use `--thumb` |
| **Missing dependencies** | Run `./install.sh` |

---

## Known WeChat Rendering Constraints

These are platform-level limitations in WeChat's HTML renderer, handled automatically by the post-processor since v0.7.0:

| Constraint | Behaviour | Automatic Fix |
|------------|-----------|---------------|
| **`data-src` required on images** | WeChat lazy-loads images using `data-src`. Images with only `src` render as blank. | Post-processor adds `data-src` to every `<img>` after URL upload. |
| **`<ol>/<li>` whitespace nodes** | Whitespace text nodes between `<li>` tags are rendered as extra blank numbered items. | Post-processor rebuilds the entire `.footnotes` section as flat `<section>` elements with inline numbering. |
| **Anchor links (`href="#"`) blocked** | Draft API returns `45166` if any `<a href="#...">` is present. | Post-processor unwraps all `#`-prefixed `<a>` tags to plain text. |
| **Footnote backlinks** | `mistune` inserts a `↩` return link at the end of each footnote which is meaningless in WeChat. | Post-processor removes all `<a class="footnote">` tags and strips residual `↩` characters. |
