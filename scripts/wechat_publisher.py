#!/usr/bin/env python3
"""
WeChat Official Account Markdown Publisher
With Error Handling and Logging
"""

__version__ = "0.7.1"

import urllib.request
import urllib.error
import json
import re
import os
import sys
import ssl
import argparse
import logging
import urllib.parse
import hashlib
import time
import yaml
from datetime import datetime
from typing import Optional, Any, Dict

# Ensure scripts/ directory is on sys.path so `from styles import ...` works
# regardless of which directory the user invokes the script from.
_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)
from styles import BUILTIN_STYLES

try:
    from dotenv import load_dotenv
    # 1. Load from current working directory (User Project) - Priority: High
    load_dotenv()
    
    # 2. Load from global config (User Home) - Priority: Low
    global_config_dir = os.path.expanduser("~/.config/publish-md-to-wechat")
    global_env = os.path.join(global_config_dir, ".env")
    
    # Common typo fallback: .evn
    global_evn_typo = os.path.join(global_config_dir, ".evn")
    
    if os.path.exists(global_env):
        load_dotenv(global_env)
    elif os.path.exists(global_evn_typo):
        # Fallback for typo, but warn user
        print(f"Warning: Found configuration at '{global_evn_typo}'. Please rename it to '.env' for standard compliance.", file=sys.stderr)
        load_dotenv(global_evn_typo)
         
except ImportError:
    # Warn user if dotenv is missing (but continue, as env vars might be set in shell)
    print("Warning: python-dotenv not installed. .env files will not be loaded.", file=sys.stderr)
    pass

try:
    import mistune
except ImportError:
    # We will handle the error if mistune is missing later in the process
    mistune = None

def clean_text_for_title(text: str) -> str:
    """Clean text for WeChat article title: remove MD, special chars, and limit length."""
    if not text:
        return ""
    
    # 1. Remove Markdown formatting
    # Remove bold/italic
    text = re.sub(r'[*_~`]', '', text)
    # Remove links but keep text: [text](url) -> text
    text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # 2. Filter special characters
    # Keep: Alphanumeric, Chinese, and basic punctuation that is visually clean
    # Remove: < > [ ] { } / \ | * # @ $ % ^ & + = ~ `
    # Allowed: ，。！？（）《》【】“”：；, . ! ? ( ) - _
    allowed_pattern = r'[^\w\s\u4e00-\u9fa5，。！？（）《》【】“”：；, . ! ? ( ) \- _]'
    text = re.sub(allowed_pattern, '', text)
    
    # 3. Collapse multiple spaces
    text = re.sub(r'\s+', ' ', text).strip()
    
    # 4. Limit length to 50 characters (WeChat limit is actually 64, but user said 50)
    # Note: User explicitly said "not exceeding 50 characters"
    if len(text) > 50:
        text = text[:47] + "..."
        
    return text


def refine_title(md_content: str, provided_title: Optional[str] = None) -> str:
    """Extract and refine article title from MD content.

    Priority: provided_title > frontmatter title > first H1 > first non-empty line
    """
    title = provided_title

    if not title:
        # 1. Try frontmatter title field
        fm_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', md_content, re.DOTALL)
        if fm_match:
            try:
                import yaml as _yaml
                fm = _yaml.safe_load(fm_match.group(1)) or {}
                title = str(fm.get("title", "")).strip() or None
            except Exception:
                pass

    if not title:
        # 2. First H1 (skip frontmatter block)
        body = re.sub(r'^---\s*\n.*?\n---\s*\n', '', md_content, count=1, flags=re.DOTALL)
        h1_match = re.search(r'^#\s+(.+)$', body, re.M)
        if h1_match:
            title = h1_match.group(1)

    if not title:
        # 3. First non-empty line of body
        body = re.sub(r'^---\s*\n.*?\n---\s*\n', '', md_content, count=1, flags=re.DOTALL)
        lines = [l.strip() for l in body.split('\n') if l.strip()]
        title = lines[0] if lines else "Untitled Article"

    return clean_text_for_title(title)


# ============================================================
# WeChat HTML Renderer (AST-based)
# ============================================================

def _detect_ascii_table(code: str):
    """Detect pipe-delimited ASCII tables inside a code block.

    Returns a list of "segments" where each segment is either:
      ("text", str)  — non-table lines (kept as code)
      ("table", list[list[str]])  — parsed rows, first row is header

    Detection heuristic:
      - A "table line" has at least 2 pipe characters '|' used as column separators.
      - A "separator line" is made of pipes, dashes, equals, plus, colons, spaces
        (e.g.  ---|--- or ===|=== or -+-+-).
      - A table is a consecutive run of ≥3 lines where every line is either a
        table-line or a separator-line, and at least one separator exists.
      - Box-drawing characters (┌┬┐├┼┤└┴┘│─═) are also recognized: lines
        containing them are treated as separator/border lines and skipped, while
        lines with │ as separator are parsed as data rows.
    """
    # Box-drawing border: must contain at least one actual Unicode box char (─┌┐ etc),
    # not just ASCII pipes/dashes which are plain-text table separators.
    _BOX_CHARS = r'┌┬┐├┼┤└┴┘─═┅┄╌╍┈┉╔╗╚╝╠╬╣╦╩║╒╓╕╖╘╙╛╜╞╡╤╧╟╢╥╨'
    BOX_BORDER = re.compile(r'^[\s' + _BOX_CHARS + r'+\-=|:]+$')
    BOX_UNICODE = re.compile(r'[' + _BOX_CHARS + r']')
    BOX_DATA = re.compile(r'│')

    lines = code.split('\n')
    # Strip trailing empty lines
    while lines and not lines[-1].strip():
        lines.pop()

    def _is_pipe_line(line):
        """Line uses ASCII pipe '|' as column separator (≥2 pipes)."""
        return line.count('|') >= 2

    def _is_separator(line):
        """Separator row: only dashes, pipes, plus, equals, colons, spaces."""
        stripped = line.strip()
        if not stripped:
            return False
        return bool(re.match(r'^[\s|+\-=:]+$', stripped)) and ('--' in stripped or '==' in stripped)

    def _is_box_border(line):
        """Box-drawing border line (┌──┬──┐ etc). Must contain Unicode box chars."""
        stripped = line.strip()
        return (bool(stripped) and bool(BOX_BORDER.match(stripped))
                and bool(BOX_UNICODE.search(stripped)) and not BOX_DATA.search(line))

    def _is_box_data(line):
        """Box-drawing data line (│ cell │ cell │)."""
        return bool(BOX_DATA.search(line))

    def _parse_pipe_row(line):
        """Split a pipe-delimited row into cell texts."""
        # Remove leading/trailing pipe if present
        stripped = line.strip()
        if stripped.startswith('|'):
            stripped = stripped[1:]
        if stripped.endswith('|'):
            stripped = stripped[:-1]
        return [cell.strip() for cell in stripped.split('|')]

    def _parse_box_row(line):
        """Split a box-drawing data row (│ cell │ cell │) into cell texts."""
        stripped = line.strip()
        if stripped.startswith('│'):
            stripped = stripped[1:]
        if stripped.endswith('│'):
            stripped = stripped[:-1]
        return [cell.strip() for cell in stripped.split('│')]

    # --- Scan for table regions ---
    segments = []
    i = 0

    while i < len(lines):
        # Try to match a box-drawing table starting at line i
        if _is_box_border(lines[i]) or _is_box_data(lines[i]):
            j = i
            data_rows = []
            has_border = False
            while j < len(lines):
                if _is_box_border(lines[j]):
                    has_border = True
                    j += 1
                elif _is_box_data(lines[j]):
                    data_rows.append(_parse_box_row(lines[j]))
                    j += 1
                else:
                    break
            if has_border and len(data_rows) >= 2:
                segments.append(("table", data_rows))
                i = j
                continue

        # Try to match a pipe-delimited table starting at line i
        if _is_pipe_line(lines[i]) or _is_separator(lines[i]):
            j = i
            run_lines = []
            has_sep = False
            while j < len(lines):
                if _is_separator(lines[j]):
                    # Check separator BEFORE pipe-line: separators also contain '|'
                    has_sep = True
                    run_lines.append(("sep", lines[j]))
                    j += 1
                elif _is_pipe_line(lines[j]):
                    run_lines.append(("data", lines[j]))
                    j += 1
                elif not lines[j].strip():
                    # Allow one blank line inside a table block (gap between sub-tables)
                    # but only if the next non-blank is still table-like
                    peek = j + 1
                    while peek < len(lines) and not lines[peek].strip():
                        peek += 1
                    if peek < len(lines) and (_is_pipe_line(lines[peek]) or _is_separator(lines[peek])):
                        run_lines.append(("blank", lines[j]))
                        j += 1
                    else:
                        break
                else:
                    break
            data_count = sum(1 for t, _ in run_lines if t == "data")
            if has_sep and data_count >= 2:
                # Split into sub-tables on blank lines
                current_rows = []
                for kind, content in run_lines:
                    if kind == "data":
                        current_rows.append(_parse_pipe_row(content))
                    elif kind == "blank" and current_rows:
                        segments.append(("table", current_rows))
                        current_rows = []
                if current_rows:
                    segments.append(("table", current_rows))
                i = j
                continue

        # Not a table line — collect as text
        text_start = i
        i += 1
        while i < len(lines):
            if _is_pipe_line(lines[i]) or _is_separator(lines[i]) or _is_box_border(lines[i]) or _is_box_data(lines[i]):
                break
            i += 1
        segments.append(("text", '\n'.join(lines[text_start:i])))

    # Only return segments if at least one table was found
    has_table = any(kind == "table" for kind, _ in segments)
    return segments if has_table else None


class WeChatRenderer(mistune.HTMLRenderer):
    """Custom renderer for WeChat compatible HTML with inline styles."""
    
    def __init__(self, style, style_name):
        super().__init__(escape=False)
        self.style = style
        self.style_name = style_name

    def heading(self, text, level):
        s = self.style
        # Simplified Swiss style for long articles
        if self.style_name == "swiss":
            if level == 1:
                return (f'<section style="margin: 30px 0 20px; text-align: left; border-bottom: {s["border_width"]} solid {s["accent"]}; padding-bottom: 10px;">'
                        f'<h1 style="font-size: 28px; font-weight: bold; color: {s["text"]}; margin: 0;">{text}</h1></section>\n')
            elif level == 2:
                return (f'<section style="margin: 32px 0 12px;">'
                        f'<h2 style="font-size: 22px; font-weight: bold; color: {s["text"]}; margin: 0;">{text}</h2></section>\n')
            elif level == 3:
                return (f'<section style="margin: 25px 0 10px; border-left: 4px solid {s["accent"]}; padding-left: 12px;">'
                        f'<h3 style="font-size: 19px; font-weight: bold; color: {s["text"]}; margin: 0;">{text}</h3></section>\n')
        
        # Original slide-like styles for other presets
        # Added max-width to make horizontal lines shorter and more elegant
        if level == 1:
            return (f'<section style="margin-bottom: 40px; border-bottom: {s["border_width"]} '
                    f'solid {s["text"] if self.style_name != "voltage" else "#fff"}; padding-bottom: 15px; max-width: 180px;">'
                    f'<h1 style="font-size: 32px; font-weight: 900; line-height: 1.1; margin: 0; '
                    f'text-transform: uppercase;">{text}</h1></section>\n')
        elif level == 2:
            return (f'<section style="margin-top: 50px; margin-bottom: 20px; border-top: 2px solid {s["text"]}; '
                    f'padding-top: 15px; max-width: 150px;"><span style="color: {s["accent"]}; font-size: 20px; '
                    f'font-weight: 800; text-transform: uppercase;">{text}</span></section>\n')
        elif level == 3:
            return (f'<section style="margin-top: 25px; margin-bottom: 10px; border-left: 4px solid {s["accent"]}; '
                    f'padding-left: 10px;"><span style="font-size: 18px; font-weight: bold;">{text}</span></section>\n')
        return f'<h{level} style="margin: 20px 0; font-weight: bold;">{text}</h{level}>\n'

    def paragraph(self, text):
        line_height = "1.75" if self.style_name == "swiss" else "1.8"
        font_size = "15px" if self.style_name == "swiss" else "16px"
        margin = "16px 0" if self.style_name == "swiss" else "15px 0"
        return f'<p style="font-size: {font_size}; line-height: {line_height}; margin: {margin}; color: {self.style["text"]};">{text}</p>\n'

    def block_quote(self, text):
        s = self.style
        if self.style_name == "swiss":
            return (f'<section style="margin: 25px 0; padding: 20px; background-color: #f9f9f9; '
                    f'border-left: 3px solid {s["accent"]}; color: {s["secondary"]}; font-size: 15px; line-height: 1.6;">'
                    f'{text}</section>\n')

        # ink: subtle 2px line for understated elegance
        # editorial: refined 3px line for magazine feel
        # others: default 4px
        border_w = "2px" if self.style_name == "ink" else "3px" if self.style_name == "editorial" else "4px"
        bg = "#f9f9f9" if s["bg"] == "#ffffff" else "rgba(255,255,255,0.05)"
        border_color = s["accent"]
        return (f'<section style="margin: 30px 0; padding: 25px; border: 1px solid #eeeeee; '
                f'background-color: {bg}; border-left: {border_w} solid {border_color}; border-radius: 4px;">'
                f'<section style="color: {s["text"]}; font-size: 15px; line-height: 1.8; '
                f'font-style: italic; opacity: 0.9;">{text}</section></section>\n')

    def _render_ascii_table_as_html(self, rows):
        """Render parsed ASCII table rows as a styled HTML <table>.

        Reuses the same visual style as the native Markdown table renderer so
        that auto-converted tables look identical to hand-written ones.
        """
        s = self.style
        border_color = "#dddddd" if self.style_name == "swiss" else s["text"]
        border = "#dddddd" if self.style_name == "swiss" else s["secondary"]

        # Normalize column count (pad short rows)
        max_cols = max(len(r) for r in rows)
        for r in rows:
            while len(r) < max_cols:
                r.append("")

        def _esc(t):
            return t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

        # First row is header
        header = rows[0]
        body = rows[1:]

        # Header bg/color — matches table_cell(head=True) logic
        hdr_bg = "#f2f2f2"
        hdr_color = "#1a1a1a"

        thead = '<tr style="border-bottom: 1px solid #eeeeee;">'
        for cell in header:
            thead += (f'<th style="border: 1px solid {border}; padding: 12px 10px; text-align: left; '
                      f'background-color: {hdr_bg}; color: {hdr_color}; font-weight: bold;">'
                      f'{_esc(cell)}</th>')
        thead += '</tr>'

        tbody_rows = ''
        for row in body:
            tbody_rows += '<tr style="border-bottom: 1px solid #eeeeee;">'
            for cell in row:
                tbody_rows += (f'<td style="border: 1px solid {border}; padding: 10px; '
                               f'text-align: left; color: {s["text"]};">{_esc(cell)}</td>')
            tbody_rows += '</tr>\n'

        return (f'<section style="margin: 25px 0; overflow-x: auto; -webkit-overflow-scrolling: touch;">'
                f'<table style="border-collapse: collapse; width: 100%; border: 1px solid {border_color}; '
                f'background-color: {s["bg"]}; font-size: 14px;">'
                f'<thead>{thead}</thead>\n<tbody>{tbody_rows}</tbody>'
                f'</table></section>\n')

    def _render_code_block(self, code):
        """Render a plain code block (no table detection)."""
        s = self.style
        def _escape(c):
            return c.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br>')
        if self.style_name == "swiss":
            escaped_code = _escape(code)
            return (f'<section style="margin: 20px 0; padding: 15px; background-color: #f6f6f6; '
                    f'border-radius: 4px; overflow-x: auto; border: 1px solid #eeeeee;">'
                    f'<pre style="margin: 0; font-family: {s["font"]}; font-size: 13px; line-height: 1.5; '
                    f'color: #333333; white-space: pre-wrap;">{escaped_code}</pre></section>\n')

        bg = "rgba(255,255,255,0.05)" if s["bg"] != "#ffffff" else "#f6f6f6"
        border_color = s["accent"] if self.style_name in ["terminal", "cyber"] else s["secondary"]
        escaped_code = _escape(code)
        return (f'<section style="margin: 20px 0; padding: 15px; background-color: {bg}; '
                f'border: 1px solid {border_color}; border-radius: 4px; overflow-x: auto;">'
                f'<pre style="margin: 0; font-family: {s["font"]}; font-size: 14px; line-height: 1.5; '
                f'color: {s["text"]}; white-space: pre-wrap;">{escaped_code}</pre></section>\n')

    def block_code(self, code, info=None):
        # Render Mermaid diagrams as images via mermaid.ink
        if info and info.strip() == "mermaid":
            import base64
            encoded = base64.urlsafe_b64encode(code.encode()).decode()
            img_url = f"https://mermaid.ink/img/{encoded}"
            return (f'<section style="text-align: center; margin: 20px 0;">'
                    f'<img src="{img_url}" alt="Diagram" '
                    f'style="max-width: 100%; height: auto;" /></section>\n')

        # If the code block has a language hint (e.g. ```python), skip table detection —
        # it's real code, not an ASCII table.
        if info and info.strip() not in ('', 'text', 'txt', 'plain'):
            return self._render_code_block(code)

        # Detect ASCII pipe/box-drawing tables in fenced code blocks
        segments = _detect_ascii_table(code)
        if segments is None:
            return self._render_code_block(code)

        # Render mixed content: tables as <table>, remaining text as <pre>
        html_parts = []
        for kind, data in segments:
            if kind == "table":
                html_parts.append(self._render_ascii_table_as_html(data))
            else:
                text = data.strip()
                if text:
                    html_parts.append(self._render_code_block(text))
        return '\n'.join(html_parts)

    def list(self, text, ordered, **kwargs):
        margin = "16px 0" if self.style_name == "swiss" else "15px 0"
        return f'<section style="margin: {margin};">{text}</section>\n'

    def list_item(self, text, **kwargs):
        s = self.style
        # Core styles: smaller, refined bullets; extend styles: moderate default
        if self.style_name == "swiss":
            bullet, bullet_size = "•", "14px"
        elif self.style_name == "editorial":
            bullet, bullet_size = "■", "12px"
        elif self.style_name == "ink":
            bullet, bullet_size = "■", "10px"
        else:
            bullet, bullet_size = "■", "14px"
        margin_right = "8px"
        
        return (f'<section style="margin: 8px 0; display: flex; align-items: flex-start;">'
                f'<span style="color: {s["accent"]}; font-weight: bold; margin-right: {margin_right}; '
                f'font-size: {bullet_size}; line-height: 1.2;">{bullet}</span>'
                f'<section style="font-size: 15px; line-height: 1.6; color: {s["text"]};">{text}</section></section>\n')

    def thematic_break(self):
        """Render horizontal rule (--- in Markdown) as empty.
        
        H2 headings already have border-top decoration, so we skip ---
        to avoid duplicate lines when --- precedes a heading.
        """
        return ''

    def strong(self, text):
        s = self.style
        color = s["accent"] if self.style_name in ["terminal", "cyber"] else "inherit"
        return f'<strong style="font-weight: bold; color: {color};">{text}</strong>'

    def codespan(self, text):
        s = self.style
        if self.style_name == "swiss":
            return f'<code style="background: #f3f3f3; padding: 2px 4px; font-size: 13px; border-radius: 3px; color: {s["accent"]}; font-family: {s["font"]};">{text}</code>'
        bg = "rgba(255,255,255,0.1)" if s["bg"] != "#ffffff" else "#f0f0f0"
        return f'<code style="background: {bg}; padding: 2px 4px; font-size: 13px; border-radius: 3px;">{text}</code>'

    def table(self, text):
        s = self.style
        border_color = "#dddddd" if self.style_name == "swiss" else s["text"]
        return (f'<section style="margin: 25px 0; overflow-x: auto; -webkit-overflow-scrolling: touch;">'
                f'<table style="border-collapse: collapse; width: 100%; border: 1px solid {border_color}; '
                f'background-color: {s["bg"]}; font-size: 14px;">{text}</table></section>\n')

    def table_head(self, text):
        s = self.style
        # All styles: light gray header, dark text — clean and universally readable
        bg = "#f2f2f2"
        color = "#1a1a1a"
        # Store for use in table_cell (thead context)
        self._thead_bg = bg
        self._thead_color = color
        return f'<thead>{text}</thead>\n'

    def table_body(self, text):
        self._thead_bg = None
        self._thead_color = None
        return f'<tbody>{text}</tbody>\n'

    def table_row(self, text):
        return f'<tr style="border-bottom: 1px solid #eeeeee;">{text}</tr>\n'

    def table_cell(self, text, align=None, head=False):
        s = self.style
        tag = 'th' if head else 'td'
        border = "#dddddd" if self.style_name == "swiss" else s["secondary"]
        padding = "12px 10px" if head else "10px"
        if head:
            # Explicitly set bg + color on every th — WeChat does not inherit from thead
            bg = getattr(self, '_thead_bg', None) or ("#f2f2f2" if self.style_name == "swiss" else s["text"])
            color = getattr(self, '_thead_color', None) or (s["text"] if self.style_name == "swiss" else s["bg"])
            return (f'<th style="border: 1px solid {border}; padding: {padding}; text-align: {align or "left"}; '
                    f'background-color: {bg}; color: {color}; font-weight: bold;">{text}</th>')
        return f'<td style="border: 1px solid {border}; padding: {padding}; text-align: {align or "left"}; color: {s["text"]};">{text}</td>'

    def image(self, text, url, alt="", **kwargs):
        # mistune 3.x uses 'url' as the keyword for the image source
        caption = alt or text
        
        # Suppress technical filenames, Obsidian placeholders, or generic words from being displayed as captions
        generic_placeholders = ['image', 'img', '图片', 'pasted image', 'screenshot']
        is_generic = caption.lower().strip() in generic_placeholders
        is_filename = re.search(r'\.(png|jpg|jpeg|gif|webp)$', caption, re.I)
        
        if caption and (is_generic or is_filename or caption.startswith('Pasted image')):
            caption = ""
            
        return (f'<section style="margin: 25px 0; text-align: center;">'
                f'<img src="{url}" alt="{alt}" style="max-width: 100%; border-radius: 8px; '
                f'box-shadow: 0 4px 15px rgba(0,0,0,0.1); display: block; margin: 0 auto;">'
                f'{f"<p style=\"color: #888; font-size: 13px; margin-top: 10px;\">{caption}</p>" if caption else ""}'
                f'</section>\n')

# ============================================================
# Logging Configuration
# ============================================================

def setup_logging(verbose: bool = False) -> logging.Logger:
    """Setup logging with console handler."""
    logger = logging.getLogger("WeChatPublisher")
    
    # Set log level
    level = logging.DEBUG if verbose else logging.INFO
    logger.setLevel(level)
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Console handler with colored output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    
    logger.addHandler(console_handler)
    return logger

# Global logger (initialized in main)
logger = None

# ============================================================
# SSL Configuration
# ============================================================

def configure_ssl(verify: bool = True):
    """Configure SSL context based on verify flag."""
    if verify:
        ssl._create_default_https_context = ssl.create_default_context
    else:
        logger.warning("SSL verification disabled - use only for development")
        ssl._create_default_https_context = ssl._create_unverified_context


def _get_cache_dir() -> str:
    if sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Caches")
    else:
        base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    path = os.path.join(base, "publish-md-to-wechat")
    os.makedirs(path, exist_ok=True)
    return path


def _read_json_file(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception:
        return None


def _write_json_file_atomic(path: str, data: dict) -> None:
    tmp_path = f"{path}.tmp.{os.getpid()}"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _convert_to_wechat_format(path: str) -> str:
    """Ensure image is in a WeChat-compatible format (PNG/JPG/GIF).

    Detects the actual image format using Pillow regardless of file extension.
    Converts WebP and other unsupported formats to PNG in-place (new file).
    Returns the path to use for upload (may differ from input if converted).
    """
    try:
        from PIL import Image
    except ImportError:
        return path  # Can't check without Pillow; let upload fail naturally

    try:
        with Image.open(path) as img:
            fmt = (img.format or "").upper()
    except Exception:
        return path  # Can't open; let upload attempt proceed

    supported = {"PNG", "JPEG", "GIF"}
    if fmt in supported:
        return path

    # Convert to PNG
    base = os.path.splitext(path)[0]
    out_path = base + "_converted.png"
    try:
        with Image.open(path) as img:
            rgb = img.convert("RGBA") if img.mode in ("RGBA", "LA", "P") else img.convert("RGB")
            rgb.save(out_path, "PNG")
        logger.info(f"✓ Converted {fmt} → PNG: {out_path}")
        return out_path
    except Exception as e:
        logger.warning(f"Failed to convert {fmt} image at {path}: {e}")
        return path


def _ensure_supported_image(path: str) -> None:
    if not os.path.exists(path):
        raise UploadError(f"Image not found: {path}")
    file_size = os.path.getsize(path)
    if file_size > 2 * 1024 * 1024:
        raise UploadError(f"Image too large ({file_size / 1024 / 1024:.1f}MB). Must be under 2MB: {path}")
    ext = os.path.splitext(path)[1].lower()
    if ext not in [".png", ".jpg", ".jpeg", ".gif"]:
        raise UploadError(f"Unsupported image format: {ext}. Use PNG, JPG, or GIF: {path}")


def _mime_type_for_image(path: str) -> str:
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    if ext == "png":
        return "image/png"
    if ext in ["jpg", "jpeg"]:
        return "image/jpeg"
    if ext == "gif":
        return "image/gif"
    return "application/octet-stream"


def _format_wechat_error(errcode: Optional[int], errmsg: Optional[str]) -> str:
    code = errcode if errcode is not None else "unknown"
    msg = (errmsg or "Unknown error").strip()
    hint = None
    if errcode in [40013]:
        hint = "Invalid AppID. Verify AppID in WeChat admin console."
    elif errcode in [40125, 40001]:
        hint = "Invalid AppSecret or access token. Check credentials and try again."
    elif errcode in [40164]:
        hint = "IP not whitelisted. Add your current IP to WeChat console whitelist."
    elif errcode in [42001]:
        hint = "Access token expired. Retry; token will refresh automatically."
    elif errcode in [45009]:
        hint = "API rate limit reached. Wait and retry."
    return f"WeChat API Error {code}: {msg}" + (f" | Hint: {hint}" if hint else "")


def _raise_if_wechat_error(data: dict, exc_cls: type[WeChatPublisherError], context: str) -> None:
    if not isinstance(data, dict):
        raise exc_cls(f"{context}: Invalid response from WeChat API")
    if "errcode" in data and data.get("errcode") not in [0, None]:
        raise exc_cls(f"{context}: {_format_wechat_error(data.get('errcode'), data.get('errmsg'))}")


def _with_retry(fn, max_attempts: int = 3, context: str = "") -> Any:
    """Call fn() with exponential backoff retry on rate limit or transient network errors."""
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except AuthError:
            raise  # Never retry auth errors
        except WeChatPublisherError as e:
            is_rate_limit = "45009" in str(e)
            if not is_rate_limit or attempt >= max_attempts:
                raise
            wait = 2 ** attempt
            logger.warning(f"{context}: rate limit hit (attempt {attempt}/{max_attempts}). Retrying in {wait}s...")
            time.sleep(wait)
        except urllib.error.URLError as e:
            if attempt >= max_attempts:
                raise
            wait = 2 ** attempt
            logger.warning(f"{context}: network error (attempt {attempt}/{max_attempts}): {e}. Retrying in {wait}s...")
            time.sleep(wait)


# ============================================================
# Custom Exceptions
# ============================================================

class WeChatPublisherError(Exception):
    """Base exception for WeChatPublisher."""
    pass

class AuthError(WeChatPublisherError):
    """Authentication failed."""
    pass

class UploadError(WeChatPublisherError):
    """File upload failed."""
    pass

class DraftError(WeChatPublisherError):
    """Draft creation failed."""
    pass

class ValidationError(WeChatPublisherError):
    """Input validation failed."""
    pass


# ============================================================
# Main Publisher Class
# ============================================================

class WeChatPublisher:
    """WeChat Official Account Markdown Publisher with error handling."""
    
    # Styles inherited and adapted from frontend-slides project
    STYLES = {k: dict(v) for k, v in BUILTIN_STYLES.items()}

    def __init__(self, app_id: Optional[str], app_secret: Optional[str], verify_ssl: bool = True, enable_network: bool = True):
        """Initialize publisher with app credentials."""
        global logger
        
        self.app_id = app_id or ""
        self.app_secret = app_secret or ""
        self.verify_ssl = verify_ssl
        self.enable_network = enable_network
        
        # Load custom styles and merge with built-in styles
        self.STYLES = self._load_custom_styles()
        logger.info(f"✓ Loaded {len(self.STYLES)} styles ({len(self.STYLES) - 10} custom)")
        
        # Configure SSL
        configure_ssl(verify_ssl)
        self.ssl_context = ssl.create_default_context() if verify_ssl else ssl._create_unverified_context()
        
        if not enable_network:
            logger.info("Network disabled (dry-run/validate mode)")
            self.access_token = None
            return
        
        if not self.app_id or not self.app_secret:
            raise ValidationError("AppID and AppSecret are required for publish mode")
        
        logger.info(f"Initializing WeChat Publisher for AppID: {self.app_id[:8]}...")
        
        # Get access token
        self.access_token = self._get_access_token()
        logger.info("✓ Successfully obtained access token")

    def _get_custom_styles_dir(self) -> str:
        """Get the directory for custom style configurations."""
        return os.path.join(os.path.expanduser("~/.config/publish-md-to-wechat/custom-styles"))

    def _load_custom_styles(self) -> Dict[str, Dict[str, Any]]:
        """Load custom styles from user config directory and merge with built-in styles.
        
        Custom styles take precedence over built-in styles with the same name.
        Custom styles must be named with 'custom-' prefix to avoid accidental conflicts.
        """
        # Start with a copy of built-in styles
        styles = dict(self.STYLES)
        
        custom_dir = self._get_custom_styles_dir()
        if not os.path.exists(custom_dir):
            try:
                os.makedirs(custom_dir, exist_ok=True)
                logger.debug(f"Created custom styles directory: {custom_dir}")
            except Exception as e:
                logger.warning(f"Failed to create custom styles directory: {e}")
                return styles
        
        # Scan for JSON files
        try:
            for filename in os.listdir(custom_dir):
                if filename.endswith(".json") and filename.startswith("custom-"):
                    filepath = os.path.join(custom_dir, filename)
                    style_name = filename[:-5]  # Remove .json extension
                    
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            custom_style = json.load(f)
                        
                        # Validate required fields
                        required_fields = ["bg", "accent", "text", "secondary", "font"]
                        missing = [field for field in required_fields if field not in custom_style]
                        if missing:
                            logger.warning(f"Skipping {filename}: missing required fields {missing}")
                            continue
                        
                        styles[style_name] = custom_style
                        logger.debug(f"✓ Loaded custom style: {style_name}")
                        
                    except json.JSONDecodeError as e:
                        logger.warning(f"Skipping {filename}: invalid JSON - {e}")
                    except Exception as e:
                        logger.warning(f"Skipping {filename}: {e}")
                        
        except Exception as e:
            logger.warning(f"Failed to scan custom styles directory: {e}")
        
        return styles

    def _token_cache_path(self) -> str:
        safe = re.sub(r"[^a-zA-Z0-9_.-]", "_", self.app_id) if self.app_id else "unknown"
        return os.path.join(_get_cache_dir(), f"token.{safe}.json")

    def _load_cached_access_token(self) -> Optional[str]:
        data = _read_json_file(self._token_cache_path())
        if not data:
            return None
        token = data.get("access_token")
        expires_at = data.get("expires_at")
        if not token or not expires_at:
            return None
        try:
            if float(expires_at) <= time.time():
                return None
        except Exception:
            return None
        return token

    def _save_access_token(self, token: str, expires_in: int) -> None:
        skew = 300
        expires_at = time.time() + max(int(expires_in) - skew, 60)
        _write_json_file_atomic(self._token_cache_path(), {
            "access_token": token,
            "expires_in": int(expires_in),
            "expires_at": expires_at,
            "updated_at": time.time(),
            "app_id": self.app_id,
        })

    def _image_cache_path(self) -> str:
        safe = re.sub(r"[^a-zA-Z0-9_.-]", "_", self.app_id) if self.app_id else "unknown"
        return os.path.join(_get_cache_dir(), f"image_cache.{safe}.json")

    def _load_image_cache(self) -> Dict[str, Any]:
        return _read_json_file(self._image_cache_path()) or {"version": 1, "items": {}}

    def _save_image_cache(self, cache: Dict[str, Any]) -> None:
        _write_json_file_atomic(self._image_cache_path(), cache)

    def _get_cached_image_result(self, kind: str, sha256: str) -> Optional[str]:
        cache = self._load_image_cache()
        item = (cache.get("items") or {}).get(f"{kind}:{sha256}")
        if isinstance(item, dict):
            value = item.get("value")
            if isinstance(value, str) and value:
                return value
        return None

    def _set_cached_image_result(self, kind: str, sha256: str, value: str) -> None:
        cache = self._load_image_cache()
        items = cache.setdefault("items", {})
        items[f"{kind}:{sha256}"] = {"value": value, "updated_at": time.time()}
        self._save_image_cache(cache)

    def _get_access_token(self) -> str:
        """Get WeChat API access token."""
        url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={self.app_id}&secret={self.app_secret}"
        
        logger.debug(f"Requesting access token from: {url.split('?')[0]}")
        
        cached = self._load_cached_access_token()
        if cached:
            logger.debug("Using cached access token")
            return cached
        
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'WeChatPublisher/1.0'})
            with urllib.request.urlopen(req, timeout=30, context=self.ssl_context) as response:
                data = json.loads(response.read().decode())
                
                if "access_token" in data:
                    expires_in = data.get("expires_in", 7200)
                    logger.debug(f"Access token expires in {expires_in}s")
                    try:
                        self._save_access_token(data["access_token"], int(expires_in))
                    except Exception:
                        logger.debug("Failed to write token cache")
                    return data["access_token"]
                
                # Handle WeChat error codes
                errcode = data.get("errcode")
                errmsg = data.get("errmsg", "Unknown error")
                
                if errcode == 40164:
                    raise AuthError(f"IP not whitelisted. Add your server IP to WeChat console. Error: {errmsg}")
                elif errcode == 40125:
                    raise AuthError(f"Invalid AppID or AppSecret. Please check your credentials. Error: {errmsg}")
                elif errcode == 40013:
                    raise AuthError(f"Invalid AppID. Please verify in WeChat admin console. Error: {errmsg}")
                else:
                    raise AuthError(f"Failed to get access token. Error {errcode}: {errmsg}")
                    
        except urllib.error.URLError as e:
            logger.error(f"Network error: {e.reason}")
            raise AuthError(f"Network error while getting access token: {e.reason}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response: {e}")
            raise AuthError(f"Invalid response from WeChat API: {e}")

    def upload_thumb(self, img_path: str) -> str:
        """Upload thumbnail image to WeChat and return media_id."""
        logger.info(f"Uploading thumbnail: {img_path}")
        
        if not self.enable_network or not self.access_token:
            raise UploadError("Network disabled; cannot upload thumbnail in dry-run/validate mode")
        
        _ensure_supported_image(img_path)
        sha = _sha256_file(img_path)
        cached = self._get_cached_image_result("thumb", sha)
        if cached:
            logger.info("✓ Thumbnail cache hit")
            return cached
        
        url = f"https://api.weixin.qq.com/cgi-bin/material/add_material?access_token={self.access_token}&type=thumb"
        
        boundary = "----WeChatPublisherBoundary"
        
        try:
            with open(img_path, "rb") as f:
                img_data = f.read()
            
            filename = os.path.basename(img_path)
            mime_type = _mime_type_for_image(img_path)
            
            parts = [
                f"--{boundary}".encode(),
                f'Content-Disposition: form-data; name="media"; filename="{filename}"'.encode(),
                f"Content-Type: {mime_type}".encode(),
                b"",
                img_data,
                f"--{boundary}--".encode(),
                b""
            ]
            
            body = b"\r\n".join(parts)
            req = urllib.request.Request(url, data=body)
            req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
            req.add_header("User-Agent", "WeChatPublisher/1.0")
            
            with urllib.request.urlopen(req, timeout=60, context=self.ssl_context) as response:
                data = json.loads(response.read().decode())
                
                if "media_id" in data:
                    logger.info(f"✓ Thumbnail uploaded successfully, media_id: {data['media_id'][:16]}...")
                    try:
                        self._set_cached_image_result("thumb", sha, data["media_id"])
                    except Exception:
                        logger.debug("Failed to write thumbnail cache")
                    return data["media_id"]
                
                _raise_if_wechat_error(data, UploadError, "Upload thumbnail")
                raise UploadError("Failed to upload thumbnail: Unknown error")
                
        except urllib.error.HTTPError as e:
            logger.error(f"HTTP error during upload: {e.code} {e.reason}")
            raise UploadError(f"HTTP error: {e.code} {e.reason}")
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            raise UploadError(f"Failed to upload thumbnail: {e}")

    def upload_image(self, img_path: str) -> str:
        """Upload image to WeChat and return permanent URL for use in articles."""
        logger.info(f"Uploading image to WeChat: {img_path}")
        
        if not self.enable_network or not self.access_token:
            raise UploadError("Network disabled; cannot upload image in dry-run/validate mode")
        
        _ensure_supported_image(img_path)
        sha = _sha256_file(img_path)
        cached = self._get_cached_image_result("article_image", sha)
        if cached:
            logger.info("✓ Image cache hit")
            return cached
        
        url = f"https://api.weixin.qq.com/cgi-bin/media/uploadimg?access_token={self.access_token}"
        
        boundary = "----WeChatPublisherBoundary"
        with open(img_path, "rb") as f:
            img_data = f.read()
        
        filename = os.path.basename(img_path)
        mime_type = _mime_type_for_image(img_path)
        
        parts = [
            f"--{boundary}".encode(),
            f'Content-Disposition: form-data; name="media"; filename="{filename}"'.encode(),
            f'Content-Type: {mime_type}'.encode(),
            b"",
            img_data,
            f"--{boundary}--".encode(),
            b""
        ]
        body = b"\r\n".join(parts)
        
        req = urllib.request.Request(url, data=body)
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        req.add_header("User-Agent", "WeChatPublisher/1.0")
        
        try:
            with urllib.request.urlopen(req, timeout=60, context=self.ssl_context) as response:
                res_data = json.loads(response.read().decode())
                if "url" in res_data:
                    logger.info(f"✓ Image uploaded: {res_data['url']}")
                    try:
                        self._set_cached_image_result("article_image", sha, res_data["url"])
                    except Exception:
                        logger.debug("Failed to write image cache")
                    return res_data["url"]
                else:
                    _raise_if_wechat_error(res_data, UploadError, "Upload image")
                    raise UploadError(f"Failed to get URL: {res_data}")
        except Exception as e:
            logger.error(f"Image upload failed: {e}")
            raise UploadError(f"Failed to upload image: {e}")

    def render_md_table_to_html(self, table_str, style):
        """Manually convert a markdown table string to robust HTML with inline styles."""
        lines = [line.strip() for line in table_str.strip().split('\n')]
        if len(lines) < 2: return table_str
        
        # Parse headers
        headers = [c.strip() for c in lines[0].strip('|').split('|')]
        # Skip separator line (lines[1])
        rows = []
        for line in lines[2:]:
            if '|' in line:
                rows.append([c.strip() for c in line.strip('|').split('|')])
        
        # Build HTML
        html = [f'<div style="margin: 20px 0; overflow-x: auto; -webkit-overflow-scrolling: touch;">']
        table_border = "#dddddd" if style["bg"] == "#ffffff" else "#444"
        html.append(f'<table style="border-collapse: collapse; width: 100%; border: 1px solid {table_border}; font-size: 14px; line-height: 1.5; background-color: {style["bg"]};">')
        
        # Header
        head_bg = "#f2f2f2" if style["bg"] == "#ffffff" else style["text"]
        head_color = style["text"] if style["bg"] == "#ffffff" else style["bg"]
        html.append(f'<thead style="background-color: {head_bg}; color: {head_color};">')
        html.append(f'<tr>')
        for h in headers:
            html.append(f'<th style="border: 1px solid {table_border}; padding: 12px 10px; font-weight: bold; text-align: left;">{h}</th>')
        html.append(f'</tr></thead>')
        
        # Body
        html.append(f'<tbody>')
        for i, row in enumerate(rows):
            bg = "#fafafa" if i % 2 == 0 and style["bg"] == "#ffffff" else style["bg"]
            html.append(f'<tr style="background-color: {bg}; border-bottom: 1px solid #eeeeee;">')
            for cell in row:
                html.append(f'<td style="border: 1px solid {table_border}; padding: 10px; color: {style["text"]};">{cell}</td>')
            html.append(f'</tr>')
        html.append(f'</tbody></table></div>')
        
        return "".join(html)

    def convert_md_to_html(self, md_content: str, style_name: str = "swiss", md_path: Optional[str] = None, upload_images: bool = True, validate_images: bool = False) -> str:
        """Convert Markdown to WeChat-compatible HTML using mistune."""
        logger.debug(f"Converting Markdown to HTML with style: {style_name}")
        
        # Check if mistune is available
        if mistune is None:
            logger.error("mistune library not found. Please run ./install.sh")
            raise ValidationError("Missing dependency: mistune. Please install it first.")

        # 1. Parse and Extract YAML Frontmatter
        frontmatter = {}
        content_body = md_content
        fm_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', md_content, re.DOTALL)
        if fm_match:
            fm_text = fm_match.group(1)
            content_body = md_content[fm_match.end():]
            try:
                frontmatter = yaml.safe_load(fm_text) or {}
            except Exception as e:
                logger.warning(f"Failed to parse frontmatter as YAML: {e}")
                # Fallback to simple parser if YAML fails
                for line in fm_text.split('\n'):
                    if ':' in line:
                        k, v = line.split(':', 1)
                        frontmatter[k.strip()] = v.strip()

        # 2. Pre-process: Convert Obsidian WikiLink ![[img.png|alias]] to standard MD ![alias](<img.png>)
        def obsidian_repl(match):
            path_part = match.group(1).strip()
            alias_part = match.group(2).strip() if match.group(2) else path_part
            return f'![{alias_part}](<{path_part}>)'
            
        processed_md = re.sub(r'!\[\[([^|\]]+)(?:\|([^\]]+))?\]\]', obsidian_repl, content_body)
        
        # Validate style
        if style_name not in self.STYLES:
            logger.warning(f"Unknown style '{style_name}', using 'swiss'")
            style_name = "swiss"
        
        style = self.STYLES[style_name]

        # Generate Frontmatter HTML
        fm_html = ""
        if frontmatter:
            fm_items = []
            # We filter some internal or huge fields, only show relevant ones
            display_keys = ['source', 'author', 'published', 'tags', 'description']
            for k in display_keys:
                if k in frontmatter:
                    v = frontmatter[k]
                    # Handle lists (like tags or authors)
                    if isinstance(v, list):
                        v = ", ".join(map(str, v))
                    # Strip Obsidian [[wikilink]] syntax
                    v = re.sub(r'\[\[([^\]]+)\]\]', r'\1', str(v))
                    fm_items.append(f'<div style="margin: 4px 0; font-size: 13px; color: {style["secondary"]};"><strong style="color: {style["accent"]}; text-transform: uppercase;">{k}:</strong> {v}</div>')
            
            if fm_items:
                fm_html = (f'<section style="margin: 0 0 30px; padding: 20px; border: 1px solid #eeeeee; '
                           f'background-color: #fafafa; border-radius: 4px;">'
                           f'{" ".join(fm_items)}</section>')

        # ULTIMATE PROTECTION v2: Use Placeholders to bypass Markdown parser
        table_cache = {}
        def table_placeholder_replacer(match):
            quote_content = match.group(0)
            # Find the table part within the quote
            table_match = re.search(r'((?:^> *\|.*\|\s*)+(?:^> *\|[- :|]+\|\s*)(?:^> *\|.*\|\s*)*)', quote_content, re.MULTILINE)
            if table_match:
                raw_table = table_match.group(1)
                clean_table = re.sub(r'^> *', '', raw_table, flags=re.MULTILINE)
                html_table = self.render_md_table_to_html(clean_table, style)
                
                # Store HTML in cache and return a safe placeholder
                placeholder_id = f"[[WECHAT_TABLE_{len(table_cache)}]]"
                table_cache[placeholder_id] = html_table
                return quote_content.replace(raw_table, "\n" + placeholder_id + "\n")
            return quote_content

        # Apply placeholder logic
        processed_md = re.sub(r'(?:^>.*\n?)+', table_placeholder_replacer, processed_md, flags=re.MULTILINE)

        # Initialize mistune with custom renderer
        renderer = WeChatRenderer(style, style_name)
        markdown = mistune.create_markdown(
            renderer=renderer,
            plugins=['strikethrough', 'table']
        )
        
        # Convert content
        main_html = markdown(processed_md)
        
        # Post-process: Replace placeholders with real HTML
        for p_id, p_html in table_cache.items():
            # Mistune might wrap the placeholder in <p> tags, so we replace carefully
            main_html = main_html.replace(p_id, p_html)
            # Also handle if it was escaped (though unlikely inside placeholders)
            main_html = main_html.replace(p_id.replace('[', '&#91;').replace(']', '&#93;'), p_html)
        
        # 2. Post-process: Upload local images and replace URLs
        img_tags = re.findall(r'<img src="(.*?)"', main_html)
        
        md_abs = md_path or ""
        if md_abs and not os.path.isabs(md_abs):
            md_abs = os.path.join(os.getcwd(), md_abs)
        md_dir = os.path.dirname(os.path.abspath(md_abs)) if md_abs else os.getcwd()
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        for local_path in img_tags:
            # Decode URL (e.g., %20 -> space) and unescape HTML entities
            local_path_decoded = urllib.parse.unquote(local_path)
            found_path = None
            is_external = local_path.startswith(('http://', 'https://'))

            # Skip video/platform URLs — they are not images
            VIDEO_HOSTS = ('youtube.com', 'youtu.be', 'vimeo.com', 'bilibili.com', 'v.qq.com')
            if is_external and any(h in local_path for h in VIDEO_HOSTS):
                logger.info(f"Skipping video URL (not an image): {local_path}")
                # Replace entire <img ...> tag (including all attributes) with a text link
                main_html = re.sub(
                    rf'<img\s[^>]*src="{re.escape(local_path)}"[^>]*/?>',
                    f'<a href="{local_path}" style="color: {self.STYLES.get(style_name, {}).get("accent", "#1a1a1a")};">▶ 视频链接</a>',
                    main_html
                )
                continue

            if is_external:
                if not upload_images:
                    continue
                logger.info(f"Downloading external image: {local_path}")
                try:
                    tmp_dir = os.path.join(project_root, "tmp", "assets")
                    os.makedirs(tmp_dir, exist_ok=True)
                    ext = ".jpg" # Default
                    if ".png" in local_path.lower(): ext = ".png"
                    elif ".gif" in local_path.lower(): ext = ".gif"
                    
                    # Create a hash of the URL to avoid re-downloading/collisions
                    url_hash = hashlib.md5(local_path.encode()).hexdigest()
                    found_path = os.path.join(tmp_dir, f"ext_{url_hash}{ext}")
                    
                    if not os.path.exists(found_path):
                        req = urllib.request.Request(local_path, headers={'User-Agent': 'Mozilla/5.0'})
                        with urllib.request.urlopen(req, timeout=20, context=self.ssl_context) as response:
                            with open(found_path, "wb") as f:
                                f.write(response.read())
                    logger.info(f"✓ Downloaded to: {found_path}")
                    # Convert unsupported formats (e.g. WebP) to PNG before upload
                    found_path = _convert_to_wechat_format(found_path)
                except Exception as e:
                    logger.warning(f"Failed to download external image {local_path}: {e}")
                    continue
            else:
                # Local image logic
                md_abs = md_path or ""
                if md_abs and not os.path.isabs(md_abs):
                    md_abs = os.path.join(os.getcwd(), md_abs)
                md_dir = os.path.dirname(os.path.abspath(md_abs)) if md_abs else os.getcwd()
                
                # 1. Try direct path relative to MD file
                direct_rel_path = os.path.join(md_dir, local_path_decoded)
                if os.path.exists(direct_rel_path):
                    found_path = direct_rel_path
                
                # 2. Try direct path relative to project root
                if not found_path:
                    direct_root_path = os.path.join(project_root, local_path_decoded)
                    if os.path.exists(direct_root_path):
                        found_path = direct_root_path
                
                # 3. Recursive search by filename (fallback)
                if not found_path:
                    filename = os.path.basename(local_path_decoded)
                    logger.info(f"Searching for image '{filename}' recursively...")
                    
                    # Search order: MD dir then Project root
                    search_bases = [md_dir, project_root]
                    for base in search_bases:
                        if found_path: break
                        for root, dirs, files in os.walk(base):
                            if filename in files:
                                found_path = os.path.join(root, filename)
                                break
            
            if found_path:
                found_path = os.path.abspath(found_path)
                try:
                    if validate_images:
                        _ensure_supported_image(found_path)
                        logger.info(f"✓ Image OK: {found_path}")
                    if upload_images:
                        wechat_url = _with_retry(lambda p=found_path: self.upload_image(p), context=f"upload_image:{os.path.basename(found_path)}")
                        # Use replace with care, but since it's the exact src attribute value it's safe
                        main_html = main_html.replace(f'src="{local_path}"', f'src="{wechat_url}"')
                except Exception as e:
                    logger.warning(f"Failed to upload image {found_path}: {e}")
            else:
                if not is_external:
                    logger.warning(f"Image '{local_path_decoded}' not found in any search path.")
        
        # Wrap with global container
        header = f'<section style="background-color: {style["bg"]}; padding: 25px 15px; font-family: {style["font"]}; color: {style["text"]};">'
        if style_name == "swiss":
            footer = (f'<section style="margin-top: 50px; text-align: center; border-top: 1px solid #eeeeee; '
                     f'padding-top: 20px; font-size: 12px; font-weight: 600; letter-spacing: 1px; '
                     f'color: {style["secondary"]}; text-transform: uppercase;">PUBLISHED VIA AIR7.FUN | STYLE: {style_name.upper()}</section></section>')
        else:
            footer = (f'<section style="margin-top: 60px; text-align: center; border-top: 5px solid {style["text"]}; '
                     f'padding-top: 25px; font-size: 14px; font-weight: 900; letter-spacing: 2px; '
                     f'text-transform: uppercase;">PUBLISHED VIA AIR7.FUN | STYLE: {style_name.upper()}</section></section>')
        
        return header + fm_html + main_html + footer

    def create_draft(self, title: str, html_content: str, thumb_id: str, author: str = "", digest: str = "") -> dict:
        """Create a draft in WeChat Official Account."""
        logger.info(f"Creating draft: {title}")

        if not self.enable_network or not self.access_token:
            raise DraftError("Network disabled; cannot create draft in dry-run/validate mode")

        # Validate inputs
        if not title or not title.strip():
            raise DraftError("Title cannot be empty")

        if not html_content:
            raise DraftError("HTML content cannot be empty")

        if not thumb_id:
            raise DraftError("Thumbnail media_id is required")

        url = f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={self.access_token}"

        data = {
            "articles": [{
                "title": title,
                "author": author or "Agent",
                "digest": digest or "Automatically published from Markdown via Agent Skill.",
                "content": html_content,
                "thumb_media_id": thumb_id,
                "need_open_comment": 1
            }]
        }
        
        try:
            json_data = json.dumps(data, ensure_ascii=False).encode('utf-8')
            req = urllib.request.Request(url, data=json_data, method="POST")
            req.add_header("Content-Type", "application/json")
            req.add_header("User-Agent", "WeChatPublisher/1.0")
            
            with urllib.request.urlopen(req, timeout=30, context=self.ssl_context) as response:
                result = json.loads(response.read().decode())
                
                if "media_id" in result:
                    logger.info(f"✓ Draft created successfully! media_id: {result['media_id']}")
                    return result
                
                _raise_if_wechat_error(result, DraftError, "Create draft")
                raise DraftError("Failed to create draft: Unknown error")
                
        except urllib.error.HTTPError as e:
            logger.error(f"HTTP error during draft creation: {e.code}")
            raise DraftError(f"HTTP error: {e.code} {e.reason}")


# ============================================================
# Main Entry Point
# ============================================================

def main():
    """Main entry point with error handling."""
    global logger
    
    parser = argparse.ArgumentParser(
        description="Publish MD to WeChat Drafts with Frontend Slides Styles",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Credentials - supports command line args or environment variables
    # Priority: command line args > environment variables
    parser.add_argument("--id", 
                       default=os.environ.get("WECHAT_APP_ID"),
                       help="WeChat AppID (or set WECHAT_APP_ID env var)")
    parser.add_argument("--secret", 
                       default=os.environ.get("WECHAT_APP_SECRET"),
                       help="WeChat AppSecret (or set WECHAT_APP_SECRET env var)")
    parser.add_argument("--md", help="Path to MD file (not required for --list-styles)")
    
    # Optional arguments
    parser.add_argument("--thumb", help="Path to thumb image (optional, will auto-generate if missing)")
    parser.add_argument("--style", default="swiss",
                        help="Style preset: swiss, terminal, bold, botanical, notebook, cyber, voltage, geometry, editorial, ink, or custom-xxx (default: swiss)")
    parser.add_argument("--title", help="Article Title (optional, auto-detect from MD)")
    parser.add_argument("--verify-ssl", dest="verify_ssl", action="store_true",
                       help="Enable SSL verification (default: enabled)")
    parser.add_argument("--no-verify-ssl", dest="verify_ssl", action="store_false",
                       help="Disable SSL verification (use only for development)")
    parser.set_defaults(verify_ssl=True)
    parser.add_argument("--dry-run", action="store_true",
                       help="Render and validate locally; skip all WeChat API calls")
    parser.add_argument("--validate", action="store_true",
                       help="Only validate inputs and local images; no rendering output required")
    parser.add_argument("--out-html", help="Write rendered HTML to a file (dry-run only)")
    parser.add_argument("-v", "--verbose", action="store_true", 
                       help="Enable verbose debug logging")
    
    args = parser.parse_args()
    
    # Setup logging early
    logger = setup_logging(args.verbose)
    logger.info("=" * 50)
    logger.info("WeChat Markdown Publisher v1.3 (Hardened for Agent Runs)")
    logger.info("=" * 50)
    
    # Validate --md is required
    if not args.md:
        parser.error("--md is required")
    
    enable_network = not (args.dry_run or args.validate)
    app_id = (args.id or os.environ.get("WECHAT_APP_ID") or "") if enable_network else (args.id or os.environ.get("WECHAT_APP_ID") or "")
    app_secret = (args.secret or os.environ.get("WECHAT_APP_SECRET") or "") if enable_network else (args.secret or os.environ.get("WECHAT_APP_SECRET") or "")
    
    if enable_network and (not app_id or not app_secret):
        logger.error("Missing WeChat credentials!")
        logger.error(f"Searched in: Command line args, Shell env, Project .env, and Global config (~/.config/publish-md-to-wechat/.env)")
        parser.error("Credentials required for publish mode. Please set WECHAT_APP_ID/WECHAT_APP_SECRET.")
    
    try:
        # Validate MD file
        logger.info(f"Reading Markdown file: {args.md}")
        if not os.path.exists(args.md):
            raise ValidationError(f"Markdown file not found: {args.md}")
        
        with open(args.md, "r", encoding="utf-8") as f:
            md_content = f.read()
        
        if not md_content.strip():
            raise ValidationError("Markdown file is empty")

        # Parse YAML frontmatter for metadata (author, digest)
        frontmatter = {}
        fm_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', md_content, re.DOTALL)
        if fm_match:
            try:
                frontmatter = yaml.safe_load(fm_match.group(1)) or {}
            except Exception:
                pass
        # Clean author: unwrap lists, strip Obsidian [[links]], remove quotes
        # WeChat author field limit: 8 bytes (strictly enforced)
        raw_author = frontmatter.get("author", "")
        if isinstance(raw_author, list):
            raw_author = ", ".join(str(a) for a in raw_author)
        raw_author = str(raw_author).strip().strip("'\"")
        raw_author = re.sub(r'\[\[([^\]]+)\]\]', r'\1', raw_author)
        # Truncate to 8 bytes safely (avoid splitting multibyte chars)
        encoded = raw_author.encode('utf-8')[:8]
        fm_author = encoded.decode('utf-8', errors='ignore').strip()

        fm_digest = str(frontmatter.get("description", "") or frontmatter.get("digest", "") or frontmatter.get("summary", "")).strip()
        if fm_author:
            logger.info(f"Frontmatter author: {fm_author}")
        if fm_digest:
            logger.info(f"Frontmatter digest: {fm_digest[:60]}{'...' if len(fm_digest) > 60 else ''}")

        # Refine and clean title from MD or use provided
        title = refine_title(md_content, args.title)
        logger.info(f"Final article title: {title}")
        
        thumb_path = args.thumb
        if enable_network:
            if not thumb_path:
                logger.info(f"No thumb provided. Auto-generating cover for style: {args.style}...")
                script_dir = os.path.dirname(os.path.abspath(__file__))
                gen_script = os.path.join(script_dir, "generate_cover.py")
                auto_thumb = os.path.join(os.path.dirname(script_dir), "assets", "auto_cover.png")
                
                import subprocess
                
                if os.path.exists(auto_thumb):
                    os.remove(auto_thumb)
                    logger.debug(f"Removed old thumbnail: {auto_thumb}")
                
                python_exe = sys.executable
                cmd_args = [python_exe, gen_script, "--title", title, "--style", args.style, "--output", auto_thumb]
                if args.verbose:
                    cmd_args.append("--verbose")
                if not args.verify_ssl:
                    cmd_args.append("--no-verify-ssl")
                
                logger.debug(f"Running: {' '.join(cmd_args)}")
                
                try:
                    result = subprocess.run(cmd_args, capture_output=True, text=True)
                    if result.returncode == 0 and os.path.exists(auto_thumb):
                        thumb_path = auto_thumb
                        logger.info(f"✓ Auto-generated cover: {auto_thumb}")
                    else:
                        error_msg = result.stderr or result.stdout or "Unknown error"
                        logger.warning(f"Cover generation failed: {error_msg.strip()}")
                        default_thumb = os.path.join(os.path.dirname(script_dir), "assets", "default_thumb.png")
                        if os.path.exists(default_thumb):
                            thumb_path = default_thumb
                            logger.warning("Generation failed, using default thumbnail")
                        else:
                            raise ValidationError("No thumbnail provided and auto-generation failed")
                except Exception as e:
                    logger.warning(f"Failed to run generation script: {e}")
                    default_thumb = os.path.join(os.path.dirname(script_dir), "assets", "default_thumb.png")
                    if os.path.exists(default_thumb):
                        thumb_path = default_thumb
                    else:
                        raise ValidationError("No thumbnail provided and auto-generation failed")
        else:
            if thumb_path:
                _ensure_supported_image(thumb_path)
        
        logger.info("Initializing WeChat publisher...")
        publisher = WeChatPublisher(app_id, app_secret, verify_ssl=args.verify_ssl, enable_network=enable_network)
        
        html = publisher.convert_md_to_html(
            md_content,
            args.style,
            md_path=args.md,
            upload_images=enable_network,
            validate_images=(args.validate or args.dry_run),
        )
        logger.info(f"✓ Converted Markdown to HTML ({len(html)} bytes)")
        
        if args.out_html:
            if not args.dry_run:
                raise ValidationError("--out-html is only supported with --dry-run")
            out_dir = os.path.dirname(os.path.abspath(args.out_html))
            if out_dir and not os.path.exists(out_dir):
                os.makedirs(out_dir, exist_ok=True)
            with open(args.out_html, "w", encoding="utf-8") as f:
                f.write(html)
            logger.info(f"✓ Wrote HTML: {args.out_html}")
        
        if args.validate:
            logger.info("✓ Validation OK")
            return 0
        
        if args.dry_run:
            logger.info("✓ Dry-run complete (no WeChat API calls made)")
            return 0
        
        thumb_id = _with_retry(lambda: publisher.upload_thumb(thumb_path), context="upload_thumb")
        result = _with_retry(lambda: publisher.create_draft(title, html, thumb_id, author=fm_author, digest=fm_digest), context="create_draft")
        
        # Success
        logger.info("=" * 50)
        logger.info("🎉 Successfully published to WeChat Drafts!")
        logger.info(f"   media_id: {result.get('media_id')}")
        logger.info("=" * 50)
        
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
        
    except ValidationError as e:
        logger.error(f"Validation Error: {e}")
        logger.info("Run with --help for usage information")
        return 1
        
    except AuthError as e:
        logger.error(f"Authentication Error: {e}")
        logger.info("Please check your AppID and AppSecret, and ensure your IP is whitelisted")
        return 1
        
    except UploadError as e:
        logger.error(f"Upload Error: {e}")
        return 1
        
    except DraftError as e:
        logger.error(f"Draft Error: {e}")
        return 1
        
    except WeChatPublisherError as e:
        logger.error(f"Publisher Error: {e}")
        return 1
        
    except KeyboardInterrupt:
        logger.info("\n⚠ Cancelled by user")
        return 130
        
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        logger.info("Please run with -v flag for more details")
        return 1


if __name__ == "__main__":
    sys.exit(main())
