#!/usr/bin/env python3
"""
Slide Renderer for Video Publisher

Renders Scene objects into a self-contained HTML file with vertical (1080x1920) slides.
Adapted from frontend-slides Swiss Modern style for video export.

Each slide is a .slide element sized at 1080x1920, rendered with Google Fonts
and clean typography suitable for knowledge-sharing video content.
"""

import re
from typing import Optional

try:
    from md_splitter import Scene
except ImportError:
    from scripts.md_splitter import Scene


# ============================================================
# Style Definitions (vertical video adapted)
# ============================================================

_STYLES = {
    "swiss": {
        "name": "Swiss Modern",
        "font_display": "Archivo",
        "font_body": "Nunito",
        "font_weights": "400;700;800",
        "bg_primary": "#ffffff",
        "bg_title": "#1a1a1a",
        "text_primary": "#1a1a1a",
        "text_secondary": "#555555",
        "text_on_dark": "#ffffff",
        "accent": "#ff3300",
        "accent_light": "rgba(255, 51, 0, 0.08)",
        "border_color": "#e0e0e0",
    },
    "ink": {
        "name": "Paper & Ink",
        "font_display": "Cormorant Garamond",
        "font_body": "Source Serif 4",
        "font_weights": "400;600;700",
        "bg_primary": "#faf9f7",
        "bg_title": "#1a1a1a",
        "text_primary": "#1a1a1a",
        "text_secondary": "#555555",
        "text_on_dark": "#faf9f7",
        "accent": "#c41e3a",
        "accent_light": "rgba(196, 30, 58, 0.08)",
        "border_color": "#e8e4df",
    },
    "editorial": {
        "name": "Vintage Editorial",
        "font_display": "Fraunces",
        "font_body": "Work Sans",
        "font_weights": "400;500;700;900",
        "bg_primary": "#f5f3ee",
        "bg_title": "#1a1a1a",
        "text_primary": "#1a1a1a",
        "text_secondary": "#555555",
        "text_on_dark": "#f5f3ee",
        "accent": "#d4783c",
        "accent_light": "rgba(212, 120, 60, 0.08)",
        "border_color": "#e8d4c0",
    },
}

DEFAULT_STYLE = "swiss"


def _get_style(name: str) -> dict:
    """Get style config by name, fallback to swiss."""
    return _STYLES.get(name, _STYLES[DEFAULT_STYLE])


def _md_to_slide_html(text: str) -> str:
    """Convert simple Markdown body text to HTML for slide display."""
    lines = text.split('\n')
    html_parts: list[str] = []
    in_list = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            continue

        # List items
        list_match = re.match(r'^[-*+]\s+(.+)', stripped)
        if list_match:
            if not in_list:
                html_parts.append('<ul>')
                in_list = True
            item_html = _inline_md(list_match.group(1))
            html_parts.append(f'  <li>{item_html}</li>')
            continue

        # Numbered list
        num_match = re.match(r'^\d+\.\s+(.+)', stripped)
        if num_match:
            if not in_list:
                html_parts.append('<ul>')
                in_list = True
            item_html = _inline_md(num_match.group(1))
            html_parts.append(f'  <li>{item_html}</li>')
            continue

        if in_list:
            html_parts.append('</ul>')
            in_list = False

        # Blockquote
        if stripped.startswith('>'):
            quote_text = _inline_md(stripped.lstrip('> '))
            html_parts.append(f'<blockquote>{quote_text}</blockquote>')
            continue

        # Regular paragraph
        html_parts.append(f'<p>{_inline_md(stripped)}</p>')

    if in_list:
        html_parts.append('</ul>')

    return '\n'.join(html_parts)


def _inline_md(text: str) -> str:
    """Convert inline Markdown (bold, italic, code, links) to HTML."""
    # Bold
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'__(.+?)__', r'<strong>\1</strong>', text)
    # Italic
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    text = re.sub(r'_(.+?)_', r'<em>\1</em>', text)
    # Inline code
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    # Links
    text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
    return text


def _render_title_slide(scene: Scene, style: dict) -> str:
    """Render the title slide HTML."""
    author_html = f'<div class="author">{scene.body.replace("**", "")}</div>' if scene.body else ''
    return f'''<div class="slide title-slide">
  <div class="slide-content">
    <div class="accent-bar"></div>
    <h1>{scene.title}</h1>
    {author_html}
  </div>
</div>'''


def _render_content_slide(scene: Scene, style: dict, index: int) -> str:
    """Render a content slide HTML."""
    title_html = f'<h2>{scene.title}</h2>' if scene.title else ''
    body_html = _md_to_slide_html(scene.body)
    return f'''<div class="slide content-slide">
  <div class="slide-content">
    <div class="slide-number">{index:02d}</div>
    {title_html}
    <div class="body">{body_html}</div>
  </div>
</div>'''


def _render_closing_slide(scene: Scene, style: dict) -> str:
    """Render the closing slide HTML."""
    return f'''<div class="slide closing-slide">
  <div class="slide-content">
    <h1>{scene.title}</h1>
    <div class="subtitle">{scene.body}</div>
  </div>
</div>'''


def render_slides_html(scenes: list[Scene], style_name: str = DEFAULT_STYLE) -> str:
    """Render a list of Scenes into a self-contained HTML file.

    The HTML contains vertical (1080x1920) slides, one .slide div per scene,
    designed for Playwright screenshot capture.
    """
    style = _get_style(style_name)
    style_display_name = style["name"]

    # Build individual slide HTML
    slide_htmls: list[str] = []
    content_index = 1
    for scene in scenes:
        if scene.scene_type == "title":
            slide_htmls.append(_render_title_slide(scene, style))
        elif scene.scene_type == "closing":
            slide_htmls.append(_render_closing_slide(scene, style))
        else:
            slide_htmls.append(_render_content_slide(scene, style, content_index))
            content_index += 1

    slides_joined = '\n'.join(slide_htmls)

    font_families = f"{style['font_display']},{style['font_body']}"
    font_url = f"https://fonts.googleapis.com/css2?family={style['font_display'].replace(' ', '+')}:wght@{style['font_weights']}&family={style['font_body'].replace(' ', '+')}:wght@{style['font_weights']}&display=swap"

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=1080, height=1920">
<title>Video Slides — {style_display_name}</title>
<link href="{font_url}" rel="stylesheet">
<style>
/* === RESET === */
*, *::before, *::after {{
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}}

/* === BASE === */
html, body {{
  width: 1080px;
  height: 1920px;
  overflow: hidden;
  background: {style["bg_primary"]};
  font-family: '{style["font_body"]}', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  color: {style["text_primary"]};
  -webkit-font-smoothing: antialiased;
}}

/* === SLIDE === */
.slide {{
  width: 1080px;
  height: 1920px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  position: relative;
  background: {style["bg_primary"]};
}}

.slide-content {{
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 120px 100px;
  max-height: 100%;
  overflow: hidden;
}}

/* === TITLE SLIDE === */
.title-slide {{
  background: {style["bg_title"]};
  color: {style["text_on_dark"]};
}}

.title-slide .accent-bar {{
  width: 80px;
  height: 8px;
  background: {style["accent"]};
  margin-bottom: 60px;
  border-radius: 4px;
}}

.title-slide h1 {{
  font-family: '{style["font_display"]}', serif;
  font-size: 72px;
  font-weight: 800;
  line-height: 1.2;
  letter-spacing: -0.02em;
  margin-bottom: 40px;
}}

.title-slide .author {{
  font-size: 32px;
  color: {style["text_on_dark"]};
  opacity: 0.7;
  font-weight: 400;
}}

/* === CONTENT SLIDE === */
.content-slide .slide-number {{
  font-family: '{style["font_display"]}', sans-serif;
  font-size: 28px;
  font-weight: 800;
  color: {style["accent"]};
  margin-bottom: 24px;
  letter-spacing: 0.05em;
}}

.content-slide h2 {{
  font-family: '{style["font_display"]}', serif;
  font-size: 56px;
  font-weight: 700;
  line-height: 1.25;
  margin-bottom: 48px;
  color: {style["text_primary"]};
}}

.content-slide .body {{
  font-size: 36px;
  line-height: 1.7;
  color: {style["text_secondary"]};
}}

.content-slide .body p {{
  margin-bottom: 28px;
}}

.content-slide .body p:last-child {{
  margin-bottom: 0;
}}

.content-slide .body strong {{
  color: {style["text_primary"]};
  font-weight: 700;
}}

.content-slide .body ul {{
  list-style: none;
  padding-left: 0;
}}

.content-slide .body ul li {{
  position: relative;
  padding-left: 36px;
  margin-bottom: 20px;
}}

.content-slide .body ul li::before {{
  content: '';
  position: absolute;
  left: 0;
  top: 14px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: {style["accent"]};
}}

.content-slide .body blockquote {{
  border-left: 5px solid {style["accent"]};
  padding: 24px 32px;
  margin: 28px 0;
  background: {style["accent_light"]};
  font-style: italic;
  border-radius: 0 8px 8px 0;
}}

.content-slide .body code {{
  background: {style["accent_light"]};
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 0.9em;
  font-family: 'JetBrains Mono', monospace;
}}

/* === CLOSING SLIDE === */
.closing-slide {{
  background: {style["bg_title"]};
  color: {style["text_on_dark"]};
  text-align: center;
}}

.closing-slide .slide-content {{
  align-items: center;
}}

.closing-slide h1 {{
  font-family: '{style["font_display"]}', serif;
  font-size: 64px;
  font-weight: 700;
  margin-bottom: 40px;
}}

.closing-slide .subtitle {{
  font-size: 32px;
  opacity: 0.6;
  max-width: 800px;
}}
</style>
</head>
<body>
{slides_joined}
</body>
</html>'''


def available_styles() -> list[str]:
    """Return list of available style names."""
    return list(_STYLES.keys())


if __name__ == "__main__":
    import sys
    sys.path.insert(0, '.')
    from md_splitter import split_md_to_scenes

    if len(sys.argv) < 2:
        print("Usage: python3 slide_renderer.py <markdown-file> [style]")
        print(f"Available styles: {', '.join(available_styles())}")
        sys.exit(1)

    md_path = sys.argv[1]
    style_name = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_STYLE

    with open(md_path, 'r', encoding='utf-8') as f:
        md_content = f.read()

    scenes = split_md_to_scenes(md_content)
    html = render_slides_html(scenes, style_name)

    out_path = md_path.rsplit('.', 1)[0] + '_slides.html'
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"Generated {len(scenes)} slides → {out_path}")
