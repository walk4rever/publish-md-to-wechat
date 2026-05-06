#!/usr/bin/env python3
"""
AI早知道 (ai.air7.fun) Markdown Publisher
Publishes Markdown articles via the Agent API.
Uploads local images to the platform CDN before publishing.
"""

__version__ = "0.2.0"

import argparse
import json
import logging
import os
import re
import ssl
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
    _global_env = os.path.join(os.path.expanduser("~/.config/publish-md-to-wechat"), ".env")
    if os.path.exists(_global_env):
        load_dotenv(_global_env)
except ImportError:
    pass

try:
    import yaml as _yaml
except ImportError:
    _yaml = None

BASE_URL = "https://ai.air7.fun"
VALID_TYPES = ("brief", "analysis", "case", "interview")
VALID_STATUSES = ("published", "draft")
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB per API docs

logger: Optional[logging.Logger] = None


# ============================================================
# Logging
# ============================================================

def setup_logging(verbose: bool = False) -> logging.Logger:
    log = logging.getLogger("Air7Publisher")
    log.setLevel(logging.DEBUG if verbose else logging.INFO)
    log.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%H:%M:%S"
    ))
    log.addHandler(handler)
    return log


# ============================================================
# Exceptions
# ============================================================

class Air7Error(Exception):
    pass

class Air7AuthError(Air7Error):
    pass

class Air7ValidationError(Air7Error):
    pass


# ============================================================
# Helpers
# ============================================================

def slugify(text: str) -> str:
    """Convert text to a URL-safe slug (ASCII lowercase, hyphens only)."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-{2,}", "-", text)
    text = text.strip("-")
    if not text:
        text = datetime.now().strftime("%Y%m%d%H%M%S")
    return text[:80]


def _mime_type(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(ext, "application/octet-stream")


def extract_excerpt(md_content: str, max_len: int = 150) -> str:
    """Extract a plain-text excerpt from the Markdown body."""
    body = re.sub(r"^---\s*\n.*?\n---\s*\n", "", md_content, count=1, flags=re.DOTALL)
    body = re.sub(r"^#+\s+.*$", "", body, flags=re.MULTILINE)
    body = re.sub(r"!\[\[[^\]]*\]\]", "", body)
    body = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", body)
    body = re.sub(r"[*_`~]", "", body)
    body = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", body)
    body = re.sub(r"<[^>]+>", "", body)
    body = re.sub(r"\s+", " ", body).strip()
    if len(body) > max_len:
        body = body[: max_len - 1] + "…"
    return body


def parse_frontmatter(md_content: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body_without_frontmatter)."""
    fm: dict = {}
    body = md_content
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", md_content, re.DOTALL)
    if match:
        body = md_content[match.end():]
        try:
            if _yaml:
                fm = _yaml.safe_load(match.group(1)) or {}
            else:
                for line in match.group(1).split("\n"):
                    if ":" in line:
                        k, v = line.split(":", 1)
                        fm[k.strip()] = v.strip()
        except Exception:
            pass
    return fm, body


def _resolve_local_image(raw_path: str, md_dir: str) -> Optional[str]:
    """Try to find a local image file, returning its absolute path or None."""
    decoded = urllib.parse.unquote(raw_path)
    candidates = [
        os.path.join(md_dir, decoded),
        os.path.join(md_dir, os.path.basename(decoded)),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return os.path.abspath(c)
    return None


def collect_local_images(md_content: str, md_dir: str) -> list[tuple[str, str]]:
    """Return list of (raw_ref, abs_path) for local images found in the Markdown.

    Handles:
      - Standard:  ![alt](path)
      - Obsidian:  ![[path]] or ![[path|alias]]
    Skips http/https URLs.
    """
    found: list[tuple[str, str]] = []
    seen: set[str] = set()

    # Standard Markdown images: ![alt](path)
    for raw in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", md_content):
        raw = raw.strip()
        if raw.startswith(("http://", "https://")):
            continue
        if raw in seen:
            continue
        abs_path = _resolve_local_image(raw, md_dir)
        if abs_path:
            found.append((raw, abs_path))
            seen.add(raw)
        else:
            logger.warning(f"Image not found locally, skipping: {raw}")

    # Obsidian wikilink images: ![[path]] or ![[path|alias]]
    for raw in re.findall(r"!\[\[([^|\]]+)(?:\|[^\]]*)?\]\]", md_content):
        raw = raw.strip()
        if raw.startswith(("http://", "https://")):
            continue
        if raw in seen:
            continue
        abs_path = _resolve_local_image(raw, md_dir)
        if abs_path:
            found.append((raw, abs_path))
            seen.add(raw)
        else:
            logger.warning(f"Obsidian image not found locally, skipping: {raw}")

    return found


# ============================================================
# API Client
# ============================================================

def _api_request(
    method: str,
    path: str,
    api_key: str,
    payload: Optional[dict] = None,
    ssl_context: Optional[ssl.SSLContext] = None,
) -> dict:
    url = BASE_URL + path
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", f"Air7Publisher/{__version__}")

    ctx = ssl_context or ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        if e.code in (401, 403):
            raise Air7AuthError(f"HTTP {e.code}: {body}")
        raise Air7Error(f"HTTP {e.code}: {body}")
    except urllib.error.URLError as e:
        raise Air7Error(f"Network error: {e.reason}")


def _upload_image(abs_path: str, api_key: str, ctx: ssl.SSLContext) -> str:
    """Upload a local image to the air7 CDN and return its public URL."""
    size = os.path.getsize(abs_path)
    if size > MAX_IMAGE_SIZE:
        raise Air7Error(f"Image too large ({size / 1024 / 1024:.1f} MB > 10 MB): {abs_path}")

    with open(abs_path, "rb") as f:
        img_data = f.read()

    filename = os.path.basename(abs_path)
    mime = _mime_type(abs_path)
    boundary = "----Air7PublisherBoundary"

    parts = [
        f"--{boundary}".encode(),
        f'Content-Disposition: form-data; name="file"; filename="{filename}"'.encode(),
        f"Content-Type: {mime}".encode(),
        b"",
        img_data,
        f"--{boundary}--".encode(),
        b"",
    ]
    body = b"\r\n".join(parts)

    req = urllib.request.Request(BASE_URL + "/api/upload", data=body, method="POST")
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("User-Agent", f"Air7Publisher/{__version__}")

    try:
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        if e.code in (401, 403):
            raise Air7AuthError(f"Upload auth error HTTP {e.code}: {body_text}")
        raise Air7Error(f"Upload failed HTTP {e.code}: {body_text}")
    except urllib.error.URLError as e:
        raise Air7Error(f"Upload network error: {e.reason}")

    # Try common URL field names
    cdn_url = result.get("url") or result.get("cdn_url") or result.get("src") or result.get("path")
    if not cdn_url:
        raise Air7Error(f"Upload response missing URL field: {result}")
    return cdn_url


def upload_images_and_rewrite(
    md_content: str,
    md_dir: str,
    api_key: str,
    ctx: ssl.SSLContext,
) -> str:
    """Upload all local images to CDN and return MD with URLs replaced.

    Does not modify any files on disk — operates purely on the string.
    """
    local_images = collect_local_images(md_content, md_dir)
    if not local_images:
        logger.info("No local images found in Markdown.")
        return md_content

    logger.info(f"Found {len(local_images)} local image(s) to upload.")
    rewritten = md_content

    for raw_ref, abs_path in local_images:
        logger.info(f"Uploading: {os.path.basename(abs_path)}")
        try:
            cdn_url = _upload_image(abs_path, api_key, ctx)
            logger.info(f"  → {cdn_url}")
        except Air7Error as e:
            logger.warning(f"  Failed to upload {abs_path}: {e} — leaving original ref")
            continue

        # Replace in standard Markdown images: ![alt](raw_ref)
        escaped = re.escape(raw_ref)
        rewritten = re.sub(
            rf"(!\[[^\]]*\]\()({escaped})(\))",
            lambda m, url=cdn_url: m.group(1) + url + m.group(3),
            rewritten,
        )
        # Replace in Obsidian wikilinks: ![[raw_ref]] or ![[raw_ref|alias]]
        rewritten = re.sub(
            rf"(!\[\[)({escaped})(\|[^\]]*)?\]\]",
            lambda m, url=cdn_url: f"![]({url})",
            rewritten,
        )

    return rewritten


# ============================================================
# Core Publish Logic
# ============================================================

def _build_meta_header(fm: dict) -> str:
    """Generate a Markdown blockquote with frontmatter metadata.

    Displays all present fields in order: title, author, description, source, tags.
    Returns empty string if no relevant fields exist.
    """
    lines = []

    title = str(fm.get("title", "")).strip()
    if title:
        lines.append(f"**标题**：{title}")

    raw_author = fm.get("author", "")
    if raw_author:
        if isinstance(raw_author, list):
            raw_author = "、".join(str(a) for a in raw_author)
        # Strip Obsidian wikilink syntax: [[@nicbstme]] → @nicbstme, [[name]] → name
        raw_author = re.sub(r"\[\[(@?[^\]]+)\]\]", r"\1", str(raw_author)).strip()
        if raw_author:
            lines.append(f"**原文作者**：{raw_author}")

    description = str(fm.get("description", "")).strip()
    if description:
        lines.append(f"**简介**：{description}")

    source = str(fm.get("source", "")).strip()
    if source:
        lines.append(f"**原文链接**：[{source}]({source})")

    tags = fm.get("tags") or fm.get("keywords")
    if tags:
        if isinstance(tags, list):
            tags = "、".join(str(t) for t in tags)
        lines.append(f"**标签**：{tags}")

    if not lines:
        return ""

    block = "\n".join(f"> {line}  " for line in lines)
    return block + "\n\n---\n\n"


def build_payload(
    md_content: str,
    md_path: str,
    article_type: str,
    status: str,
    slug_override: Optional[str] = None,
    title_override: Optional[str] = None,
    author_override: Optional[str] = None,
) -> dict:
    if not md_content.strip():
        raise Air7ValidationError("Markdown content is empty")

    fm, body = parse_frontmatter(md_content)

    # Title: override → frontmatter → first H1 → filename
    title: str = title_override or str(fm.get("title", "")).strip()
    if not title:
        h1 = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
        title = h1.group(1) if h1 else os.path.splitext(os.path.basename(md_path))[0]
    title = re.sub(r"[*_`~\[\]]", "", title).strip()

    # Type (resolved before slug so slug can embed it)
    fm_type = str(fm.get("type", "")).strip()
    resolved_type = fm_type if fm_type in VALID_TYPES else article_type
    if article_type != "analysis":
        resolved_type = article_type

    # Date (resolved before slug so slug can embed it)
    date_val = fm.get("date") or fm.get("published") or datetime.now().strftime("%Y-%m-%d")
    if hasattr(date_val, "strftime"):
        date_val = date_val.strftime("%Y-%m-%d")
    else:
        date_val = str(date_val)[:10]

    # Slug — format: {type}-{YYYY-MM-DD}-{topic} (brief adds agent name)
    fm_slug = str(fm.get("slug", "")).strip()
    if slug_override or fm_slug:
        slug = slug_override or fm_slug
    else:
        topic = slugify(title) or slugify(os.path.splitext(os.path.basename(md_path))[0]) or "untitled"
        if resolved_type == "brief":
            agent_name = str(fm.get("agent", "neo")).strip() or "neo"
            slug = f"brief-{date_val}-{agent_name}-{topic}"
        else:
            slug = f"{resolved_type}-{date_val}-{topic}"
        slug = slug[:120]

    # Excerpt
    excerpt = str(fm.get("description") or fm.get("excerpt") or "").strip()
    if not excerpt:
        excerpt = extract_excerpt(md_content)
    if not excerpt:
        excerpt = title

    meta_header = _build_meta_header(fm)
    content = meta_header + body if meta_header else body

    payload: dict = {
        "slug": slug,
        "title": title,
        "type": resolved_type,
        "content": content,
        "excerpt": excerpt,
        "date": date_val,
        "status": status,
    }
    if author_override in ("agent", "user"):
        payload["author"] = author_override
    return payload


def publish(
    md_path: str,
    api_key: str,
    article_type: str = "analysis",
    status: str = "draft",
    slug_override: Optional[str] = None,
    title_override: Optional[str] = None,
    author_override: Optional[str] = None,
    patch_slug: Optional[str] = None,
    dry_run: bool = False,
    verify_ssl: bool = True,
    skip_images: bool = False,
) -> int:
    if not os.path.exists(md_path):
        logger.error(f"File not found: {md_path}")
        return 1

    with open(md_path, "r", encoding="utf-8") as f:
        md_content = f.read()

    md_dir = os.path.dirname(os.path.abspath(md_path))
    ctx = ssl.create_default_context() if verify_ssl else ssl._create_unverified_context()

    # Upload local images and rewrite refs (skipped in dry-run or if --skip-images)
    if not dry_run and not skip_images and api_key:
        md_content = upload_images_and_rewrite(md_content, md_dir, api_key, ctx)
    elif dry_run:
        local_imgs = collect_local_images(md_content, md_dir)
        if local_imgs:
            logger.info(f"Dry-run: would upload {len(local_imgs)} image(s): "
                        + ", ".join(os.path.basename(p) for _, p in local_imgs))

    try:
        payload = build_payload(
            md_content, md_path, article_type, status,
            slug_override, title_override, author_override,
        )
    except Air7ValidationError as e:
        logger.error(str(e))
        return 1

    logger.info(f"Title:   {payload['title']}")
    logger.info(f"Slug:    {payload['slug']}")
    logger.info(f"Type:    {payload['type']}")
    logger.info(f"Status:  {payload['status']}")
    excerpt_preview = payload["excerpt"]
    logger.info(f"Excerpt: {excerpt_preview[:80]}{'...' if len(excerpt_preview) > 80 else ''}")

    if dry_run:
        logger.info("Dry-run: payload ready (no API call made)")
        # Print payload without full content to keep output readable
        preview = {k: (v[:200] + "…" if k == "content" and len(v) > 200 else v)
                   for k, v in payload.items()}
        print(json.dumps(preview, ensure_ascii=False, indent=2))
        return 0

    if not api_key:
        logger.error("API key is required. Set API_KEY_MONICA or use --key.")
        return 1

    if patch_slug:
        logger.info(f"Patching existing post: {patch_slug}")
        result = _api_request("PATCH", f"/api/posts/{patch_slug}", api_key, payload, ctx)
    else:
        logger.info("Publishing new post...")
        result = _api_request("POST", "/api/posts", api_key, payload, ctx)

    logger.info("✓ Success!")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


# ============================================================
# CLI
# ============================================================

def main() -> int:
    global logger

    parser = argparse.ArgumentParser(
        description="Publish Markdown to ai.air7.fun",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --md article.md
  %(prog)s --md article.md --type brief --status published
  %(prog)s --md article.md --patch my-existing-slug
  %(prog)s --md article.md --dry-run
  %(prog)s --md article.md --skip-images
        """,
    )
    parser.add_argument("--md", required=True, help="Path to Markdown file")
    parser.add_argument(
        "--key",
        default=os.environ.get("AIR7_API_KEY"),
        help="Agent API Key (or set AIR7_API_KEY env var)",
    )
    parser.add_argument(
        "--type", choices=VALID_TYPES, default="analysis",
        help="Article type (default: analysis)",
    )
    parser.add_argument(
        "--status", choices=VALID_STATUSES, default="draft",
        help="Status (default: draft)",
    )
    parser.add_argument("--slug", help="Override slug (auto-generated from title if omitted)")
    parser.add_argument("--title", help="Override title (auto-detected from Markdown)")
    parser.add_argument(
        "--author", choices=("agent", "user"),
        help="Author role: 'agent' or 'user'",
    )
    parser.add_argument(
        "--patch", metavar="SLUG",
        help="PATCH an existing post by slug instead of creating a new one",
    )
    parser.add_argument(
        "--skip-images", action="store_true",
        help="Skip image upload; publish Markdown as-is",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print payload without making API call",
    )
    parser.add_argument(
        "--no-verify-ssl", dest="verify_ssl", action="store_false",
        help="Disable SSL verification (use only in dev/local environments)",
    )
    parser.set_defaults(verify_ssl=True)
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose debug output")

    args = parser.parse_args()
    logger = setup_logging(args.verbose)
    logger.info("=" * 50)
    logger.info("AI早知道 Publisher")
    logger.info("=" * 50)

    if not args.key and not args.dry_run:
        parser.error("API key required. Set AIR7_API_KEY env var or use --key.")

    try:
        return publish(
            md_path=args.md,
            api_key=args.key or "",
            article_type=args.type,
            status=args.status,
            slug_override=args.slug,
            title_override=args.title,
            author_override=args.author,
            patch_slug=args.patch,
            dry_run=args.dry_run,
            verify_ssl=args.verify_ssl,
            skip_images=args.skip_images,
        )
    except Air7AuthError as e:
        logger.error(f"Auth Error: {e}")
        logger.info("Check your AIR7_API_KEY in .env")
        return 1
    except Air7Error as e:
        logger.error(f"API Error: {e}")
        return 1
    except KeyboardInterrupt:
        logger.info("\nCancelled")
        return 130
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
