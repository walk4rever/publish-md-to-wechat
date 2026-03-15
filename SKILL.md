---
name: publish-md-to-wechat
description: >
  Professional Markdown to WeChat Official Account (公众号) publisher with visual style presets.
  Use this skill whenever the user wants to: publish an article to WeChat, create a 公众号 draft,
  format a blog post or technical tutorial for WeChat, apply a visual style to Markdown, or says
  anything like "发布到微信"、"推送到公众号"、"微信文章"、"publish to WeChat"、"WeChat draft"、
  "公众号推文"、"wechat article"、"微信公众号". Also trigger when the user asks to convert Markdown
  to a styled HTML document for WeChat, even if they don't say "publish" explicitly. This skill
  handles credentials, image uploads, 10+ style presets, automatic cover generation, and draft
  creation end-to-end.
---

# publish-md-to-wechat

Publishes Markdown articles to WeChat Official Account drafts with professional visual styling,
automatic image handling, and cover generation.

## Phase 1: Environment & Credentials

Before anything else, make sure the environment is ready — users rarely think about this upfront
and it's frustrating to fail mid-way.

**Check dependencies:**
```bash
ls .venv/bin/python 2>/dev/null || echo "MISSING"
```
If `.venv` is missing, run `./install.sh` to set up the environment.

**Check credentials:** The script automatically loads `WECHAT_APP_ID` and `WECHAT_APP_SECRET`
from `.env` in the current directory, or from `~/.config/publish-md-to-wechat/.env` as a global
fallback. If `.env` exists, proceed directly without asking the user for credentials — they're
already configured. Only ask for credentials if the script explicitly fails with an auth error.

---

## Phase 2: Read the Article & Select a Style

Read the Markdown file to understand the content's tone and purpose. Then consult
`references/styles.md` to pick the most fitting preset — good style matching significantly
improves the article's visual impact on WeChat.

**Quick style guide:**
- `swiss` — Clean and editorial. Best for long-form technical writing, tutorials, and reports.
- `terminal` — Dark hacker aesthetic with green code font. Perfect for dev tools, CLI tutorials, engineering deep-dives.
- `ink` / `editorial` — Warm and humanistic. Great for opinion pieces, reflections, and news commentary.
- `botanical` / `notebook` — Premium feel. Well-suited for product launches, elegant summaries.
- `cyber` / `voltage` — Futuristic high-contrast. Works well for AI, crypto, and tech trend pieces.
- `bold` / `geometry` — High energy. Good for listicles, highlights, and short punchy pieces.

Propose the style to the user with a one-line reason ("I'll use `terminal` since this is a CLI tutorial"). Skip the proposal only if the user already specified a style.

---

## Phase 3: Validate First (Optional but Recommended)

For new users or complex articles (many images, tables, or Obsidian WikiLinks), suggest a dry-run
before the real publish. This lets the user preview the HTML output without any API calls:

```bash
source .venv/bin/activate && python3 scripts/wechat_publisher.py \
  --md [PATH_TO_MD] \
  --style [STYLE] \
  --dry-run \
  --out-html /tmp/wechat_preview.html
open /tmp/wechat_preview.html
```

This is especially helpful when the article has local images — the dry-run validates that all
images are found before the actual upload happens.

---

## Phase 4: Publish

Run the publisher using the virtual environment. The script handles everything automatically:
cover generation, image upload, and draft creation.

```bash
source .venv/bin/activate && python3 scripts/wechat_publisher.py \
  --md [PATH_TO_MD] \
  --style [STYLE]
```

**Key flags:**
- `--thumb [PATH]` — Provide a custom cover image (PNG/JPG, under 2MB). If omitted, a branded cover is auto-generated from the article title.
- `--title "[TITLE]"` — Override the title (auto-detected from H1 or frontmatter if omitted).
- `-v` — Enable verbose output for debugging.
- `--validate` — Validate-only mode: checks images and Markdown, no API calls, no output.

**YAML Frontmatter support:** If the article has frontmatter, the script automatically uses it:
```yaml
---
title: My Article Title
author: 张三
description: A short summary shown in WeChat article list.
---
```
The `author` and `description` fields populate the WeChat draft metadata automatically.

**Image handling:** Local images, Obsidian `![[image.png]]` syntax, and external URLs are all
handled automatically. Images are uploaded to WeChat's media library and their URLs replaced.

---

## Phase 5: Success Output

When the draft is created, always respond using this format:

---
## 🚀 发布成功！| Published to WeChat Drafts

| 字段 | 值 |
|------|-----|
| **标题** | [Article Title] |
| **风格** | `[style]` — [one-line vibe description] |
| **Media ID** | `[MEDIA_ID]` |
| **草稿状态** | ✅ 已创建，待审阅发布 |

**下一步 | Next Steps:**
登录 [mp.weixin.qq.com](https://mp.weixin.qq.com) → 草稿箱 → 在手机上预览 → 发布

---

## Troubleshooting

**Error 40164 (IP Whitelist):** The error message contains the blocked IP. Tell the user:
> "请将 IP `[IP]` 添加到微信公众平台白名单：登录 mp.weixin.qq.com → 设置与开发 → 基本配置 → IP白名单。"

**Error 40125 / 40013:** Invalid AppID or AppSecret. Ask the user to double-check their `.env`
credentials against the WeChat admin console.

**Error 45009 (Rate limit):** The script automatically retries with exponential backoff (up to 3
attempts). If it still fails, wait a few minutes and try again.

**SSL errors:** Add `--no-verify-ssl` if your network uses a corporate proxy with certificate
inspection. This flag disables SSL verification for that run only.

**Image not found:** The script searches recursively from the Markdown file's directory. If an
image is still not found, check that the filename matches exactly (case-sensitive) and the image
is within the project or article directory.

**Cover generation failed:** The script falls back to `assets/default_thumb.png` if cover
generation fails. You can also pass `--thumb [path]` to provide a custom cover explicitly.

**Missing mistune / dependencies:** Run `./install.sh` to recreate the virtual environment and
reinstall all dependencies.
