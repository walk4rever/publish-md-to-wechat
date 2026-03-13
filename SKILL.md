---
name: publish-md-to-wechat
description: Automate the professional formatting and publishing of Markdown to WeChat Official Accounts. Use this skill whenever the user mentions "WeChat article", "public account draft", "publish MD to WeChat", or wants to apply styles like "Swiss" or "Terminal" to their blog posts. This skill handles credentials, image uploading, professional style conversion, and draft creation.
---

# publish-md-to-wechat

Professional Markdown to WeChat Official Account Draft publisher with style-driven HTML conversion.

## Operational Workflow

### 1. Prerequisite Check (Silent)
Before any action, ensure the environment is ready:
- **Dependencies**: Check if `.venv/bin/activate` or `mistune` is available. If missing, tell the user: "I need to set up the environment first. Running `./install.sh`..." and execute it.
- **Credentials**: The script automatically loads `WECHAT_APP_ID` and `WECHAT_APP_SECRET` from the `.env` file. 
  - If `.env` exists, **do NOT** read its content or ask the user for credentials. Just proceed with the following steps.
  - If the script fails with an "Authentication Error" or if `.env` is missing, then ask the user for credentials and save them to `.env`.

### 2. Content Preparation & Style Selection
- **Analyze Content**: Read the input Markdown file.
- **Select Style**: Read `references/styles.md` to pick the best style for the content.
  - *Tech/Code*: Suggest `terminal` or `swiss`.
  - *News/Blog*: Suggest `editorial` or `ink`.
- **Confirm Style**: Propose the style to the user unless they explicitly specified one.

### 3. Cover Image Strategy
- **Existing Cover**: If `thumb` or `cover.png` is provided/detected, use it.
- **Auto-Generate**: If no cover is available, use `scripts/generate_cover.py` to create a branded card matching the chosen style:
  ```bash
  python3 scripts/generate_cover.py --title "[TITLE]" --style [STYLE] --output tmp/auto_cover.png
  ```
- **AI Creative**: If requested, generate a high-quality prompt for an image generator (DALL-E) based on the article theme.

### 4. Execution (The Publisher)
Run the publisher script using the virtual environment (it will load credentials from `.env` automatically):
```bash
source .venv/bin/activate && python3 scripts/wechat_publisher.py \
  --md [PATH_TO_MD] \
  --style [STYLE] \
  --thumb [THUMB_PATH_OR_TMP_PATH]
```
*Note: The script recursively finds local images and uploads them automatically.*

## Success Criteria & Output Template
Upon successful draft creation, ALWAYS return a response using this format:

# 🚀 WeChat Article Published!
- **Title**: [Article Title]
- **Style Applied**: `[Style Name]` ([Vibe description])
- **Media ID**: `[MEDIA_ID]`
- **Draft Status**: Successfully created in WeChat Official Account drafts.

> **Next Steps**: Log into [mp.weixin.qq.com](https://mp.weixin.qq.com), find the draft, preview it on your phone, and hit Publish!

## Troubleshooting
- **Error 40164 (IP Whitelist)**: If seen, extract the IP from the error and tell the user: "Please add IP `[IP]` to your WeChat Whitelist (Basic Configuration -> IP Whitelist)."
- **SSL Error**: The publisher defaults to bypassing SSL to handle environment-specific issues.

---
*Created via Skill Creator*
