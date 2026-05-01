#!/usr/bin/env python3
"""
Style Manager for publish-md-to-wechat

Built-in style definitions (single source of truth) + CLI for:
  - Listing all styles (--list)
  - Analyzing WeChat articles to create custom styles (--url / --file)
  - Renaming custom styles (--rename)

Usage:
    python3 scripts/styles.py --list
    python3 scripts/styles.py --url <wechat-article-url> --no-verify-ssl
    python3 scripts/styles.py --rename custom-old custom-new
    python3 scripts/styles.py --file <local-html-file>
"""

import argparse
import sys
import os
import re
import json
import urllib.request
import urllib.error
from typing import Optional, Dict, Any
from collections import Counter

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

# ============================================================
# Playwright JS extraction (computed styles + structural hints)
# ============================================================

_PLAYWRIGHT_EXTRACT_JS = """
() => {
  const $ = sel => document.querySelector(sel);
  const $$ = sel => [...document.querySelectorAll(sel)];
  const gs = el => window.getComputedStyle(el);

  const toHex = rgb => {
    const m = String(rgb).match(/rgba?\\(\\s*(\\d+)[,\\s]+(\\d+)[,\\s]+(\\d+)/);
    if (!m) return null;
    const am = String(rgb).match(/,\\s*([\\d.]+)\\s*\\)$/);
    if (am && parseFloat(am[1]) < 0.05) return null;
    return '#' + [+m[1],+m[2],+m[3]].map(x => x.toString(16).padStart(2,'0').toUpperCase()).join('');
  };

  const isBlank = c => !c || c === 'rgba(0, 0, 0, 0)' || c === 'transparent';

  const freq = arr => {
    const counts = arr.reduce((a,c)=>{a[c]=(a[c]||0)+1;return a;},{});
    return Object.entries(counts).sort((a,b)=>b[1]-a[1]);
  };

  const content = $('#js_content') || $('.rich_media_content') || document.body;

  // --- Background ---
  const rawBg = gs(content).backgroundColor;
  const rawBodyBg = gs(document.body).backgroundColor;
  const bg = (!isBlank(rawBg) && toHex(rawBg))
    || (!isBlank(rawBodyBg) && toHex(rawBodyBg))
    || '#FFFFFF';

  // --- Text color (modal paragraph color) ---
  const pColors = $$('p').slice(0, 20)
    .map(p => toHex(gs(p).color)).filter(Boolean);
  const text = pColors.length ? freq(pColors)[0][0] : '#1A1A1A';

  // --- Font / size / line-height ---
  const baseEl = content.querySelector('p') || content;
  const baseS = gs(baseEl);
  const font = baseS.fontFamily;
  const fontSize = baseS.fontSize;
  const lineHeight = baseS.lineHeight;

  // --- Heading structure helper ---
  const analyzeHeading = el => {
    const s = gs(el);
    const par = el.parentElement;
    const ps = par ? gs(par) : null;
    const elBg  = !isBlank(s.backgroundColor)  ? toHex(s.backgroundColor)  : null;
    const parBg = ps && !isBlank(ps.backgroundColor) ? toHex(ps.backgroundColor) : null;
    const blockBg = parBg || elBg;
    const borderLeft  = parseFloat(ps ? ps.borderLeftWidth  : s.borderLeftWidth)  || 0;
    const borderRight = parseFloat(ps ? ps.borderRightWidth : 0) || 0;
    const borderBottom = parseFloat(s.borderBottomWidth) || 0;
    let type = 'plain';
    if (blockBg && blockBg.toUpperCase() !== bg.toUpperCase()) type = 'bg-block';
    else if (borderLeft > 0 && borderRight === 0) type = 'left-border';
    else if (borderBottom > 0) type = 'underline';
    const borderColor = borderLeft > 0
      ? toHex((ps || s).borderLeftColor) : null;
    return {
      type,
      bg: type === 'bg-block' ? blockBg : null,
      color: toHex(s.color),
      borderColor
    };
  };

  const h2s = $$('h2').slice(0,6).map(analyzeHeading);
  const h3s = $$('h3').slice(0,6).map(analyzeHeading);
  const dominant = arr => arr.length ? freq(arr.map(h=>h.type))[0][0] : 'plain';

  const h2Style = dominant(h2s);
  const h2Bg = (h2s.find(h=>h.bg) || {}).bg || null;
  const h2BorderColor = (h2s.find(h=>h.borderColor) || {}).borderColor || null;
  const h2Color = (h2s.find(h=>h.color) || {}).color || null;
  const h3Style = dominant(h3s);
  const h3BorderColor = (h3s.find(h=>h.borderColor) || {}).borderColor || null;

  // --- Blockquote structure ---
  const bqEls = $$('blockquote').slice(0,3);
  const bqInfo = bqEls.map(el => {
    const s = gs(el);
    const bl = parseFloat(s.borderLeftWidth)  || 0;
    const br = parseFloat(s.borderRightWidth) || 0;
    const bt = parseFloat(s.borderTopWidth)   || 0;
    const bqBg = !isBlank(s.backgroundColor) ? toHex(s.backgroundColor) : null;
    const borderColor = bl > 0 ? toHex(s.borderLeftColor) : null;
    let type = 'plain';
    if (bl > 0 && br === 0 && bt === 0) type = 'left-border';
    else if (bl > 0 || bqBg) type = 'full-box';
    return { type, bg: bqBg, borderColor };
  });
  const bqStyle = bqInfo.length ? bqInfo[0].type : 'left-border';
  const bqBg = ((bqInfo.find(b=>b.bg) || {}).bg) || null;
  const bqBorderColor = ((bqInfo.find(b=>b.borderColor) || {}).borderColor) || null;

  // --- Accent (most distinctive color: border/link colors, not heading bgs) ---
  // Exclude browser-default link colors and colors too close to bg
  const BROWSER_DEFAULTS = new Set(['#0000EE','#0000FF','#551A8B','#000080']);
  const hexDist = (a, b) => {
    const p = h => [parseInt(h.slice(1,3),16), parseInt(h.slice(3,5),16), parseInt(h.slice(5,7),16)];
    const [r1,g1,b1] = p(a), [r2,g2,b2] = p(b);
    return Math.sqrt((r1-r2)**2+(g1-g2)**2+(b1-b2)**2);
  };
  const accentPool = [
    h2BorderColor, h3BorderColor, bqBorderColor,
    ...(h2Color && h2Color !== h2Bg ? [h2Color] : []),
    ...$$('a').slice(0,8).map(a => toHex(gs(a).color))
  ].filter(Boolean).filter(c =>
    c.toUpperCase() !== text.toUpperCase() &&
    c.toUpperCase() !== bg.toUpperCase() &&
    !BROWSER_DEFAULTS.has(c.toUpperCase()) &&
    hexDist(c.toUpperCase(), bg.toUpperCase()) > 60
  );
  const accent = accentPool.length ? freq(accentPool)[0][0] : text;

  // --- Secondary ---
  const secPool = $$('span').slice(0,30)
    .map(el => toHex(gs(el).color)).filter(Boolean)
    .filter(c => c !== text && c !== accent && c !== bg);
  const secondary = secPool.length ? freq(secPool)[0][0] : '#666666';

  return {
    bg, text, accent, secondary,
    font, font_size: fontSize, line_height: lineHeight,
    heading_style: h2Style,
    heading_bg: h2Bg,
    heading_border_color: h2BorderColor,
    heading_color: h2Color,
    h3_style: h3Style,
    h3_border_color: h3BorderColor,
    blockquote_style: bqStyle,
    blockquote_bg: bqBg,
    blockquote_border_color: bqBorderColor,
  };
}
"""

# ============================================================
# Logging Configuration
# ============================================================

class SimpleLogger:
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
    
    def info(self, msg: str):
        print(f"ℹ️  {msg}")
    
    def debug(self, msg: str):
        if self.verbose:
            print(f"🔍 {msg}")
    
    def warning(self, msg: str):
        print(f"⚠️  {msg}", file=sys.stderr)
    
    def error(self, msg: str):
        print(f"❌ {msg}", file=sys.stderr)
    
    def success(self, msg: str):
        print(f"✅ {msg}")


logger = None

# ============================================================
# WeChat Article Fetcher
# ============================================================

def fetch_wechat_article(url: str, verify_ssl: bool = True) -> str:
    """Fetch WeChat article HTML content.
    
    Args:
        url: WeChat article URL
        verify_ssl: Enable SSL verification
        
    Returns:
        HTML content as string
        
    Raises:
        ValueError: If URL is invalid
        urllib.error.URLError: If network request fails
    """
    logger.info(f"Fetching article: {url}")
    
    # Validate URL
    if not url.startswith("https://mp.weixin.qq.com/s/"):
        raise ValueError(f"Invalid WeChat article URL: {url}")
    
    # Build request with realistic User-Agent
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    }
    
    req = urllib.request.Request(url, headers=headers)
    
    # Configure SSL context
    import ssl
    if verify_ssl:
        ssl_context = ssl.create_default_context()
    else:
        logger.warning("SSL verification disabled")
        ssl_context = ssl._create_unverified_context()
    
    try:
        with urllib.request.urlopen(req, timeout=30, context=ssl_context) as response:
            html = response.read().decode('utf-8')
            logger.success(f"Successfully fetched article ({len(html)} bytes)")
            return html
    except urllib.error.HTTPError as e:
        raise urllib.error.URLError(f"HTTP {e.code}: {e.reason}")


def load_local_html(filepath: str) -> str:
    """Load HTML from local file.
    
    Args:
        filepath: Path to HTML file
        
    Returns:
        HTML content as string
    """
    logger.info(f"Loading local HTML: {filepath}")
    
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        logger.success(f"Successfully loaded HTML ({len(content)} bytes)")
        return content


# ============================================================
# Style Extraction
# ============================================================

def extract_main_content(soup: BeautifulSoup) -> Optional[Any]:
    """Extract the main content container from WeChat article.
    
    WeChat articles use #js_content as the main content container.
    
    Args:
        soup: BeautifulSoup instance
        
    Returns:
        Main content element or None
    """
    # Try #js_content first (most common)
    content = soup.find(id='js_content')
    if content:
        logger.debug("Found main content: #js_content")
        return content
    
    # Fallback: try other common selectors
    for selector in ['.rich_media_content', '#js_article', 'article']:
        content = soup.select_one(selector)
        if content:
            logger.debug(f"Found main content: {selector}")
            return content
    
    logger.warning("Could not find main content container, using body")
    return soup.body


def color_distance(hex1: str, hex2: str) -> float:
    """Euclidean distance between two hex colors in RGB space (0–441).

    Used to reject accent candidates that are too close to the text color.

    Args:
        hex1, hex2: Hex color strings like #RRGGBB

    Returns:
        Distance value; 0 = identical, 441 = black vs white
    """
    def _parse(h: str):
        h = h.lstrip('#')
        if len(h) == 3:
            h = ''.join([c * 2 for c in h])
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    try:
        r1, g1, b1 = _parse(hex1)
        r2, g2, b2 = _parse(hex2)
        return ((r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2) ** 0.5
    except Exception:
        return 0.0


def rgb_to_hex(r: int, g: int, b: int) -> str:
    """Convert RGB values to hex color.
    
    Args:
        r, g, b: RGB values (0-255)
        
    Returns:
        Hex color string like #RRGGBB
    """
    return f"#{r:02X}{g:02X}{b:02X}"


def normalize_color(value: str) -> Optional[str]:
    """Normalize color to hex format.
    
    Handles: hex colors, rgb(), rgba(), named colors
    Converts RGB to hex for consistency.
    
    Args:
        value: CSS color value
        
    Returns:
        Normalized hex color string or None
    """
    if not value:
        return None
    
    value = value.strip().lower()
    
    # Skip empty after strip
    if not value:
        return None
    
    # Skip transparent/inherit/initial and other non-color values
    skip_values = ['transparent', 'inherit', 'initial', 'none', 'auto', 'unset', 'currentcolor']
    if value in skip_values:
        return None
    
    # Hex color - normalize to uppercase
    if value.startswith('#'):
        hex_val = value[1:]
        if len(hex_val) == 3:
            hex_val = ''.join([c*2 for c in hex_val])
        return f"#{hex_val.upper()}"
    
    # RGB/RGBA - convert to hex
    if value.startswith('rgb'):
        match = re.search(r'rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)', value)
        if match:
            r, g, b = int(match.group(1)), int(match.group(2)), int(match.group(3))
            return rgb_to_hex(r, g, b)
        return None
    
    # Named color - return as-is for now
    return value


def extract_color(value: str) -> Optional[str]:
    """Extract and normalize color value from CSS property.
    
    Args:
        value: CSS color value
        
    Returns:
        Normalized hex color string or None
    """
    return normalize_color(value)


def extract_font_size(value: str) -> Optional[str]:
    """Extract font size from CSS property.
    
    Args:
        value: CSS font-size value
        
    Returns:
        Font size string or None
    """
    if not value:
        return None
    
    value = value.strip().lower()
    
    # Skip inherit/initial
    if value in ['inherit', 'initial', 'auto', 'medium', 'normal']:
        return None
    
    return value


def extract_line_height(value: str) -> Optional[str]:
    """Extract line height from CSS property.
    
    Args:
        value: CSS line-height value
        
    Returns:
        Line height string or None
    """
    if not value:
        return None
    
    value = value.strip().lower()
    
    if value in ['inherit', 'initial', 'auto', 'normal']:
        return None
    
    return value


def get_computed_style(element: Any, property: str) -> Optional[str]:
    """Get style value from element's inline style attribute.
    
    Args:
        element: BeautifulSoup element
        property: CSS property name
        
    Returns:
        Style value or None
    """
    if not element or not hasattr(element, 'get'):
        return None
    
    style_attr = element.get('style', '')
    if style_attr:
        for declaration in style_attr.split(';'):
            if ':' in declaration:
                key, val = declaration.split(':', 1)
                if key.strip().lower() == property.lower():
                    return val.strip()
    
    return None


def extract_stylesheet_rules(soup: Any) -> Dict[str, Dict[str, str]]:
    """Parse <style> blocks and return a selector → {property: value} mapping.

    Only handles simple single-class and element selectors (e.g. `.rich_media_content`,
    `p`, `#js_content`) — sufficient for WeChat article theme detection.

    Args:
        soup: BeautifulSoup instance of the full page

    Returns:
        Dict mapping selector strings to their CSS property dicts
    """
    rules: Dict[str, Dict[str, str]] = {}

    for style_tag in soup.find_all('style'):
        css_text = style_tag.get_text()
        # Strip comments
        css_text = re.sub(r'/\*.*?\*/', '', css_text, flags=re.DOTALL)

        # Match selector { declarations }
        for match in re.finditer(r'([^{]+)\{([^}]+)\}', css_text):
            selector = match.group(1).strip()
            declarations = match.group(2).strip()

            props: Dict[str, str] = {}
            for decl in declarations.split(';'):
                if ':' in decl:
                    prop, val = decl.split(':', 1)
                    props[prop.strip().lower()] = val.strip()

            if props:
                rules[selector] = props

    return rules


def get_stylesheet_color(rules: Dict[str, Dict[str, str]], property: str,
                         priority_selectors: list) -> Optional[str]:
    """Look up a CSS property value from parsed stylesheet rules.

    Checks selectors in priority order and returns the first match.

    Args:
        rules: Output of extract_stylesheet_rules()
        property: CSS property name (e.g. 'color', 'background-color')
        priority_selectors: Selectors to check, in priority order

    Returns:
        Color value string or None
    """
    for sel in priority_selectors:
        props = rules.get(sel, {})
        val = props.get(property)
        if val:
            return val
    return None


def most_common_value(values: list, default: str) -> str:
    """Get most common non-None value from list.
    
    Args:
        values: List of values
        default: Default value if no valid values
        
    Returns:
        Most common value or default
    """
    filtered = [v for v in values if v]
    if not filtered:
        return default
    
    counter = Counter(filtered)
    return counter.most_common(1)[0][0]


def is_dark_color(color_str: str) -> bool:
    """Check if a color is effectively dark (for background detection).

    For rgba colors, alpha-blends against white before checking brightness,
    so rgba(0,0,0,0.05) (nearly transparent) is treated as near-white, not black.

    Args:
        color_str: Color string (hex, rgb, rgba)

    Returns:
        True if color is dark
    """
    if not color_str:
        return False

    try:
        alpha = 1.0

        # Hex color
        if color_str.startswith('#'):
            hex_val = color_str.lstrip('#')
            if len(hex_val) == 3:
                hex_val = ''.join([c * 2 for c in hex_val])
            r = int(hex_val[0:2], 16)
            g = int(hex_val[2:4], 16)
            b = int(hex_val[4:6], 16)

        # RGB / RGBA
        elif color_str.startswith('rgb'):
            match = re.search(
                r'rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*([\d.]+))?\s*\)',
                color_str
            )
            if not match:
                return False
            r, g, b = int(match.group(1)), int(match.group(2)), int(match.group(3))
            if match.group(4) is not None:
                alpha = float(match.group(4))
        else:
            return False

        # Alpha-blend against white (255, 255, 255) to get effective color
        r = int(r * alpha + 255 * (1 - alpha))
        g = int(g * alpha + 255 * (1 - alpha))
        b = int(b * alpha + 255 * (1 - alpha))

        # Perceived brightness (ITU-R BT.601)
        brightness = (r * 299 + g * 587 + b * 114) / 1000
        return brightness < 100

    except Exception:
        return False


def extract_style_from_content(content: Any,
                               stylesheet_rules: Optional[Dict[str, Dict[str, str]]] = None) -> Dict[str, Any]:
    """Extract style properties from content element.

    Strategy (in priority order):
    1. Container inline style  → most specific
    2. <style> block rules     → theme-level fallback (new)
    3. Paragraph inline styles → body text sample
    4. All-element scan        → broad fallback
    5. Hardcoded defaults      → last resort

    Args:
        content: Main content element
        stylesheet_rules: Parsed CSS rules from <style> blocks (from extract_stylesheet_rules)

    Returns:
        Style configuration dictionary
    """
    if stylesheet_rules is None:
        stylesheet_rules = {}

    # WeChat content selectors in priority order for stylesheet lookup
    WECHAT_CONTENT_SELECTORS = [
        '#js_content', '.rich_media_content', 'body', '*'
    ]

    # Step 1: Try to get background from content container inline style
    container_bg = get_computed_style(content, 'background-color') or get_computed_style(content, 'background')
    container_bg_extracted = None
    if container_bg:
        container_bg_extracted = extract_color(container_bg)

    # Step 2: Fallback to <style> block for background and text color
    if not container_bg_extracted:
        raw = get_stylesheet_color(stylesheet_rules, 'background-color', WECHAT_CONTENT_SELECTORS) \
              or get_stylesheet_color(stylesheet_rules, 'background', WECHAT_CONTENT_SELECTORS)
        if raw:
            container_bg_extracted = extract_color(raw)
            if logger:
                logger.debug(f"Background from <style> block: {container_bg_extracted}")

    stylesheet_text_color = extract_color(
        get_stylesheet_color(stylesheet_rules, 'color', WECHAT_CONTENT_SELECTORS) or ''
    )
    stylesheet_font = get_stylesheet_color(stylesheet_rules, 'font-family', WECHAT_CONTENT_SELECTORS)
    
    # Collect all elements for analysis
    all_elements = content.find_all(True)  # All tags
    
    # Extract background color
    bg_colors = []
    text_colors = []
    fonts = []
    font_sizes = []
    line_heights = []
    
    # Elements to exclude from main style detection (code blocks, etc.)
    exclude_tags = {'pre', 'code', 'kbd', 'samp', 'tt'}
    
    for elem in all_elements:
        if elem.name in exclude_tags:
            continue  # Skip code-related elements
        
        # Background color - only from block-level content elements
        if elem.name in ['p', 'section', 'div', 'span', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            bg = get_computed_style(elem, 'background-color') or get_computed_style(elem, 'background')
            if bg:
                extracted = extract_color(bg)
                if extracted and extracted not in ["transparent", "unset", "inherit"]:
                    # Skip dark backgrounds from non-code elements (likely code block containers)
                    if not is_dark_color(extracted):
                        bg_colors.append(extracted)
        
        # Text color - only from text elements
        if elem.name in ['p', 'span', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li']:
            color = get_computed_style(elem, 'color')
            if color:
                text_colors.append(extract_color(color))
        
        # Font family
        font = get_computed_style(elem, 'font-family')
        if font:
            font_clean = font.strip('"\'')
            if 'monospace' not in font_clean.lower() and 'consolas' not in font_clean.lower():
                fonts.append(font_clean)
        
        # Font size
        size = get_computed_style(elem, 'font-size')
        if size:
            font_sizes.append(extract_font_size(size))
        
        # Line height
        lh = get_computed_style(elem, 'line-height')
        if lh:
            line_heights.append(extract_line_height(lh))
    
    # Extract font from paragraphs specifically (most representative of body text)
    paragraph_fonts = []
    paragraph_colors = []
    for elem in content.find_all('p'):
        font = get_computed_style(elem, 'font-family')
        if font:
            font_clean = font.strip('"\'')
            if 'monospace' not in font_clean.lower():
                paragraph_fonts.append(font_clean)
        
        color = get_computed_style(elem, 'color')
        if color:
            paragraph_colors.append(extract_color(color))
    
    # Determine dominant styles
    # Priority: paragraph styles > all text styles > container styles > defaults
    
    # Background: prefer light colors, default to white
    # Only use dark background if explicitly set on container AND most text elements have it
    if container_bg_extracted and container_bg_extracted not in ["transparent", "unset", "inherit"]:
        if not is_dark_color(container_bg_extracted):
            bg_colors.insert(0, container_bg_extracted)  # Priority to container bg if light
    
    # Text color priority: paragraph inline > stylesheet > all-element scan > default
    # Pure black (#000000) is a browser default, replace with dark gray
    DEFAULT_TEXT = "#1a1a1a"
    raw_text = most_common_value(paragraph_colors if paragraph_colors else text_colors,
                                 stylesheet_text_color or DEFAULT_TEXT)
    if raw_text in ("#000000", "#000"):
        raw_text = DEFAULT_TEXT

    # Font priority: paragraph inline > stylesheet > all-element scan > default
    DEFAULT_FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif"
    resolved_font = most_common_value(
        paragraph_fonts if paragraph_fonts else fonts,
        stylesheet_font or DEFAULT_FONT
    )

    style = {
        "bg": most_common_value(bg_colors, "#ffffff"),
        "text": raw_text,
        "font": resolved_font,
        "font_size": most_common_value(font_sizes, "15px"),
        "line_height": most_common_value(line_heights, "1.75"),
    }
    
    # Extract accent color (from links and headings; exclude strong/b which inherit text color)
    # Require minimum color distance from text to avoid accent ≈ text
    ACCENT_MIN_DISTANCE = 60  # out of 441; filters near-identical shades
    accent_colors = []
    for elem in content.find_all(['a', 'h1', 'h2', 'h3']):
        color = get_computed_style(elem, 'color')
        if not color:
            continue
        hex_color = extract_color(color)
        if not hex_color:
            continue
        if color_distance(hex_color, style["text"]) >= ACCENT_MIN_DISTANCE:
            accent_colors.append(hex_color)

    if accent_colors:
        style["accent"] = most_common_value(accent_colors, "#e62e2e")
    else:
        style["accent"] = style["text"]
    
    # Secondary color (for less important text)
    secondary_colors = []
    for elem in content.find_all(['span', 'small', 'em']):
        color = get_computed_style(elem, 'color')
        if color and color != style["text"] and color != style["accent"]:
            secondary_colors.append(extract_color(color))
    
    style["secondary"] = most_common_value(secondary_colors, "#666666")
    
    # Border width: extract from blockquote / quote-like sections only.
    # These represent intentional decorative borders in the article theme,
    # not generic div/section borders which are often structural.
    border_widths = []
    for elem in content.find_all(['blockquote', 'section', 'div']):
        # Only consider elements with border-left (quote accent style)
        val = get_computed_style(elem, 'border-left-width') \
              or get_computed_style(elem, 'border-left')
        if val:
            # Extract just the width part if it's a shorthand like "4px solid #xxx"
            width_match = re.match(r'(\d+(?:\.\d+)?(?:px|em|rem))', val.strip())
            if width_match:
                border_widths.append(width_match.group(1))

    style["border_width"] = most_common_value(border_widths, "3px")
    
    return style


def _analyze_with_playwright(html: str) -> Dict[str, Any]:
    """Extract computed styles and structural hints using a headless browser.

    Writes html to a temp file, loads it in Playwright Chromium, and runs
    getComputedStyle() + structural analysis via _PLAYWRIGHT_EXTRACT_JS.

    Returns the raw JS result dict, or raises on failure.
    """
    import tempfile
    import os as _os

    from playwright.sync_api import sync_playwright

    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', encoding='utf-8', delete=False) as f:
        f.write(html)
        tmp_path = f.name

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(f'file://{tmp_path}', wait_until='domcontentloaded')
            try:
                page.wait_for_selector('#js_content, .rich_media_content', timeout=4000)
            except Exception:
                pass
            result = page.evaluate(_PLAYWRIGHT_EXTRACT_JS)
            browser.close()
        return result or {}
    finally:
        _os.unlink(tmp_path)


def _extract_title_from_html(html: str) -> Optional[str]:
    """Extract article title using BeautifulSoup (lightweight, no browser needed)."""
    if BeautifulSoup is None:
        return None
    soup = BeautifulSoup(html, 'html.parser')
    title_elem = soup.find('h1', id='activity-name') or soup.find('h1', class_='rich_media_title')
    if title_elem:
        return title_elem.get_text(strip=True)[:50]
    return None


def analyze_html(html: str) -> Dict[str, Any]:
    """Analyze HTML and extract style configuration.

    Tries Playwright first (computed styles + structural hints).
    Falls back to BeautifulSoup inline-style parsing if Playwright is unavailable.

    Args:
        html: HTML content

    Returns:
        Style configuration dictionary
    """
    # --- Playwright path (preferred) ---
    try:
        pw = _analyze_with_playwright(html)
        if pw:
            # Normalize line_height: browser returns px ("27.2px"), convert to ratio
            raw_lh = pw.get("line_height", "")
            font_size_px = pw.get("font_size", "15px")
            try:
                lh_px = float(str(raw_lh).replace("px", ""))
                fs_px = float(str(font_size_px).replace("px", ""))
                pw["line_height"] = f"{lh_px / fs_px:.2f}" if fs_px else "1.75"
            except (ValueError, ZeroDivisionError):
                pw["line_height"] = pw.get("line_height", "1.75")

            # Rename font_size key to match existing schema
            pw["font_size"] = pw.pop("font_size", "15px")

            # Add border_width fallback for renderers that use it
            pw.setdefault("border_width", "3px")

            # Attach article title
            title = _extract_title_from_html(html)
            if title:
                pw["source_title"] = title

            if logger:
                logger.success("Style extracted via Playwright (computed styles + structure)")
            return pw
    except ImportError:
        if logger:
            logger.debug("Playwright not available, using HTML parser")
    except Exception as e:
        if logger:
            logger.warning(f"Playwright extraction failed ({e}), falling back to HTML parser")

    # --- BeautifulSoup fallback ---
    if BeautifulSoup is None:
        raise ImportError("beautifulsoup4 is required. Install with: pip install beautifulsoup4")

    soup = BeautifulSoup(html, 'html.parser')
    stylesheet_rules = extract_stylesheet_rules(soup)
    logger.debug(f"Parsed {len(stylesheet_rules)} CSS rules from <style> blocks")

    content = extract_main_content(soup)
    if content is None:
        raise ValueError("Could not find main content in HTML")

    style = extract_style_from_content(content, stylesheet_rules)

    title_elem = soup.find('h1', id='activity-name') or soup.find('h1', class_='rich_media_title')
    if title_elem:
        style["source_title"] = title_elem.get_text(strip=True)[:50]

    return style


# ============================================================
# Style Generation
# ============================================================

def slugify(text: str, max_words: int = 4) -> str:
    """Convert article title to a readable slug.

    Chinese characters are kept as-is (pinyin conversion is a heavy dependency).
    Non-alphanumeric / non-CJK characters are replaced with hyphens.
    Takes the first max_words "words" (split on whitespace / punctuation).

    Examples:
        "Kimi新论文太硬核了！马斯克和Karpathy相继点赞~" → "kimi新论文太硬核了"
        "如何用 Claude 写出好代码" → "如何用-claude"

    Args:
        text: Source text (article title)
        max_words: Maximum number of tokens to keep

    Returns:
        Lowercase slug string
    """
    # Strip HTML entities and common punctuation
    text = re.sub(r'&[a-z]+;', '', text)
    # Split on whitespace and punctuation boundaries (ASCII + CJK punctuation + misc symbols)
    tokens = re.split(r'[\s\-_/\\~`@#%^&*+=|<>，。！？、：；\u201c\u201d\u2018\u2019【】《》…·～｜.!?,;:\'"()\[\]{}]+', text)
    tokens = [t for t in tokens if t][:max_words]
    slug = '-'.join(tokens).lower()
    # Collapse multiple hyphens
    slug = re.sub(r'-{2,}', '-', slug).strip('-')
    # Hard cap at 24 characters to keep names manageable
    slug = slug[:24].rstrip('-')
    return slug or 'style'


def generate_custom_style_name(source_title: Optional[str] = None) -> str:
    """Generate a human-readable custom style name.

    If a source_title is available, derives a slug from it so the name is
    meaningful (e.g. 'custom-kimi新论文太硬核了').
    Falls back to date+hash when no title is present.

    Args:
        source_title: Article title extracted during style analysis

    Returns:
        Style name like 'custom-kimi新论文太硬核了' or 'custom-20260317-abc123'
    """
    import hashlib
    import time

    if source_title:
        slug = slugify(source_title, max_words=3)
        if slug and slug != 'style':
            return f"custom-{slug}"

    # Fallback: date + short hash
    timestamp = str(int(time.time()))
    hash_suffix = hashlib.md5(timestamp.encode()).hexdigest()[:6]
    date = time.strftime("%Y%m%d")
    return f"custom-{date}-{hash_suffix}"


def save_style_config(style: Dict[str, Any], output_path: str) -> None:
    """Save style configuration to JSON file.
    
    Args:
        style: Style configuration dictionary
        output_path: Output file path
    """
    # Ensure output directory exists
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    # Add metadata
    style["created_at"] = __import__('datetime').datetime.now().isoformat()
    style["source"] = "styles.py"
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(style, f, ensure_ascii=False, indent=2)
    
    logger.success(f"Style config saved to: {output_path}")


def get_default_output_path(style_name: str) -> str:
    """Get default output path for custom style.
    
    Args:
        style_name: Style name
        
    Returns:
        Default output path
    """
    custom_dir = os.path.expanduser("~/.config/publish-md-to-wechat/custom-styles")
    os.makedirs(custom_dir, exist_ok=True)
    return os.path.join(custom_dir, f"{style_name}.json")


# ============================================================
# Style Management Helpers
# ============================================================

# ============================================================
# Built-in Style Definitions (single source of truth)
# Categories: core (3) — fully tested, recommended
#             extend (7) — specific scenarios
# ============================================================

BUILTIN_STYLES = {

    # ── Core ──────────────────────────────────────────────────────────────────

    "swiss": {
        "category": "core",
        "desc": "瑞士国际主义风格。白底红色，网格感强，专业克制。适合技术文章、产品更新、官方通知。",
        "bg": "#ffffff", "accent": "#e62e2e", "text": "#000000", "secondary": "#666666",
        "font": "-apple-system, BlinkMacSystemFont, 'Helvetica Neue', Helvetica, Arial, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif", "border_width": "3px",
    },
    "editorial": {
        "category": "core",
        "desc": "杂志编辑风格。暖米色背景，衬线字体，大行距。适合观点文章、深度分析、专栏内容。",
        "bg": "#f5f3ee", "accent": "#1a1a1a", "text": "#1a1a1a", "secondary": "#555555",
        "font": "Fraunces, Georgia, 'Times New Roman', 'Songti SC', 'Noto Serif CJK SC', 'SimSun', serif", "border_width": "2px",
    },
    "ink": {
        "category": "core",
        "desc": "东方水墨风格。暖白底色，深红强调，超大行距。适合人文历史、文化评论、深度长文。",
        "bg": "#faf9f7", "accent": "#c41e3a", "text": "#1a1a1a", "secondary": "#444444",
        "font": "Cormorant Garamond, 'Palatino Linotype', 'Kaiti SC', 'STKaiti', 'Kaiti', serif", "border_width": "1px",
    },

    # ── Extend ────────────────────────────────────────────────────────────────

    "notebook": {
        "category": "extend",
        "desc": "笔记本风格。米白底色，绿色强调，亲切随意。适合个人日记、读书笔记、生活记录。",
        "bg": "#f8f6f1", "accent": "#98d4bb", "text": "#1a1a1a", "secondary": "#555555",
        "font": "'Bodoni Moda', Georgia, 'Kaiti SC', 'STKaiti', 'Kaiti', serif", "border_width": "4px",
    },
    "geometry": {
        "category": "extend",
        "desc": "几何柔和风格。浅白底色，粉色强调，圆润友好。适合生活方式、教程科普、女性向内容。",
        "bg": "#faf9f7", "accent": "#f0b4d4", "text": "#1a1a1a", "secondary": "#5a7c6a",
        "font": "'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif", "border_width": "4px",
    },
    "botanical": {
        "category": "extend",
        "desc": "植物暗色风格。深黑背景，金色强调，高端典雅。适合品牌故事、艺术评论、高奢内容。",
        "bg": "#0f0f0f", "accent": "#d4a574", "text": "#e8e4df", "secondary": "#9a9590",
        "font": "Cormorant, Georgia, 'Songti SC', 'Noto Serif CJK SC', 'SimSun', serif", "border_width": "2px",
    },
    "terminal": {
        "category": "extend",
        "desc": "终端代码风格。GitHub 深色背景，绿色高亮，等宽字体。适合极客内容、开源项目介绍、技术教程。",
        "bg": "#0d1117", "accent": "#39d353", "text": "#e6edf3", "secondary": "#8b949e",
        "font": "'JetBrains Mono', Menlo, Monaco, Consolas, 'Courier New', 'PingFang SC', 'Microsoft YaHei', monospace", "border_width": "4px",
    },
    "bold": {
        "category": "extend",
        "desc": "大胆黑色风格。深黑背景，橙色强调，视觉冲击强。适合活动预告、产品发布、重要公告。",
        "bg": "#1a1a1a", "accent": "#FF5722", "text": "#ffffff", "secondary": "#999999",
        "font": "'Archivo Black', Impact, -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif", "border_width": "10px",
    },
    "cyber": {
        "category": "extend",
        "desc": "赛博朋克风格。深蓝背景，青绿强调，科技感强。适合 AI/科技话题、未来感内容。",
        "bg": "#0a0f1c", "accent": "#00ffcc", "text": "#ffffff", "secondary": "#9ca3af",
        "font": "'Clash Display', -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif", "border_width": "4px",
    },
    "voltage": {
        "category": "extend",
        "desc": "高压蓝黄风格。亮蓝背景，荧光黄强调，能量感十足。适合活动运营、促销推广。",
        "bg": "#0066ff", "accent": "#d4ff00", "text": "#ffffff", "secondary": "#e0e0e0",
        "font": "Syne, -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif", "border_width": "6px",
    },
}

CORE_STYLES   = [k for k, v in BUILTIN_STYLES.items() if v["category"] == "core"]
EXTEND_STYLES = [k for k, v in BUILTIN_STYLES.items() if v["category"] == "extend"]

CUSTOM_STYLES_DIR = os.path.expanduser("~/.config/publish-md-to-wechat/custom-styles")


def _load_custom_styles() -> Dict[str, Dict]:
    """Load custom styles from disk."""
    customs = {}
    if os.path.exists(CUSTOM_STYLES_DIR):
        for filename in sorted(os.listdir(CUSTOM_STYLES_DIR)):
            if filename.startswith("custom-") and filename.endswith(".json"):
                try:
                    with open(os.path.join(CUSTOM_STYLES_DIR, filename), "r", encoding="utf-8") as f:
                        customs[filename[:-5]] = json.load(f)
                except Exception:
                    customs[filename[:-5]] = {}
    return customs


def cmd_list_styles() -> int:
    """List all styles by category: core / extend / custom."""
    custom_styles = _load_custom_styles()

    print("\n📚 可用样式")
    print("=" * 60)

    # ── Core ──
    print("\n── Core（推荐）──────────────────────────────────────────\n")
    for name in CORE_STYLES:
        cfg = BUILTIN_STYLES[name]
        print(f"  ⭐ {name:<12}  {cfg.get('desc', '')}")

    # ── Extend ──
    print("\n── Extend（扩展）────────────────────────────────────────\n")
    for name in EXTEND_STYLES:
        cfg = BUILTIN_STYLES[name]
        print(f"  📦 {name:<12}  {cfg.get('desc', '')}")

    # ── Custom ──
    print("\n── Custom（定制）────────────────────────────────────────\n")
    if custom_styles:
        for name, cfg in custom_styles.items():
            if cfg.get("source_title"):
                desc = f"复刻自：{cfg['source_title']}"
            else:
                desc = cfg.get("desc", "")
            print(f"  🎨 {name:<24}  {desc}")
    else:
        print("  （暂无自定义样式）")
        print("  python3 scripts/styles.py --url <wechat-article-url> --no-verify-ssl")

    total = len(BUILTIN_STYLES) + len(custom_styles)
    print("\n" + "=" * 60)
    print(f"共 {len(CORE_STYLES)} core + {len(EXTEND_STYLES)} extend + {len(custom_styles)} custom = {total} 种样式")
    print()
    print("发布：  python3 scripts/wechat_publisher.py --md article.md --style <name>")
    print("复刻：  python3 scripts/styles.py --url <wechat-article-url> --no-verify-ssl")
    print("重命名：python3 scripts/styles.py --rename <old> <new>")
    return 0


def cmd_rename_style(old_name: str, new_name: str) -> int:
    """Rename a custom style."""
    if not old_name.startswith("custom-"):
        print(f"❌ '{old_name}' is a built-in style and cannot be renamed", file=sys.stderr)
        return 1
    if not new_name.startswith("custom-"):
        print(f"❌ New name '{new_name}' must start with 'custom-'", file=sys.stderr)
        return 1

    old_path = os.path.join(CUSTOM_STYLES_DIR, f"{old_name}.json")
    new_path = os.path.join(CUSTOM_STYLES_DIR, f"{new_name}.json")

    if not os.path.exists(old_path):
        print(f"❌ Style not found: {old_name}", file=sys.stderr)
        print("   Run --list to see available custom styles", file=sys.stderr)
        return 1
    if os.path.exists(new_path):
        print(f"❌ '{new_name}' already exists, choose a different name", file=sys.stderr)
        return 1

    os.rename(old_path, new_path)
    print(f"✅ Renamed: {old_name} → {new_name}")
    print(f"   Usage: python3 scripts/wechat_publisher.py --md article.md --style {new_name}")
    return 0


# ============================================================
# Main Entry Point
# ============================================================

def main():
    global logger
    logger = SimpleLogger()
    
    parser = argparse.ArgumentParser(
        description="Custom style manager — analyze articles, list and rename styles",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract style from a WeChat article
  python3 scripts/styles.py --url https://mp.weixin.qq.com/s/xxx --no-verify-ssl

  # List all styles (built-in + custom)
  python3 scripts/styles.py --list

  # Rename a custom style
  python3 scripts/styles.py --rename custom-kimi custom-kimi-purple

  # Analyze local HTML file
  python3 scripts/styles.py --file article.html
        """
    )
    
    # Input options (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--url", help="WeChat article URL to analyze")
    input_group.add_argument("--file", help="Local HTML file to analyze")
    input_group.add_argument("--list", action="store_true", help="List all available styles and exit")
    input_group.add_argument("--rename", nargs=2, metavar=("OLD", "NEW"),
                             help="Rename a custom style: --rename custom-old custom-new")

    # Output options
    parser.add_argument("--output", "-o", help="Output file path (default: ~/.config/publish-md-to-wechat/custom-styles/custom-<slug>.json)")
    parser.add_argument("--name", help="Custom style name (default: derived from article title)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    parser.add_argument("--dry-run", action="store_true", help="Analyze only, don't save file")
    parser.add_argument("--no-verify-ssl", action="store_true", help="Disable SSL verification (use only for development)")
    
    args = parser.parse_args()

    # --list and --rename don't need logging setup
    if args.list:
        return cmd_list_styles()

    if args.rename:
        return cmd_rename_style(args.rename[0], args.rename[1])

    logger = SimpleLogger(verbose=args.verbose)
    
    try:
        # Fetch/load HTML
        if args.url:
            html = fetch_wechat_article(args.url, verify_ssl=not args.no_verify_ssl)
        else:
            html = load_local_html(args.file)
        
        # Analyze style
        logger.info("Analyzing style...")
        style = analyze_html(html)
        
        # Display results
        print("\n" + "=" * 50)
        print("📊 Extracted Style Configuration:")
        print("=" * 50)
        for key, value in sorted(style.items()):
            if key not in ["created_at", "source"]:  # Skip metadata during analysis
                print(f"  {key}: {value}")
        print("=" * 50)
        
        # Generate output
        if args.dry_run:
            logger.info("Dry run - not saving file")
            return 0
        
        # Determine output path and name
        # Use source_title for a meaningful name when no --name is given
        style_name = args.name or generate_custom_style_name(style.get("source_title"))
        output_path = args.output or get_default_output_path(style_name)
        
        # Ensure name starts with 'custom-'
        if not os.path.basename(output_path).startswith("custom-"):
            dirname = os.path.dirname(output_path)
            basename = os.path.basename(output_path)
            if not basename.startswith("custom-"):
                output_path = os.path.join(dirname, f"custom-{basename}") if dirname else f"custom-{basename}"
        
        # Save style config
        save_style_config(style, output_path)
        
        # Print usage instructions
        print("\n✅ Style created successfully!")
        print(f"\nUsage:")
        print(f"  python3 scripts/wechat_publisher.py --md article.md --style {os.path.basename(output_path)[:-5]}")
        print(f"\nList all styles:")
        print(f"  python3 scripts/styles.py --list")
        
        return 0
        
    except FileNotFoundError as e:
        logger.error(str(e))
        return 1
    except ValueError as e:
        logger.error(str(e))
        return 1
    except urllib.error.URLError as e:
        logger.error(f"Network error: {e.reason}")
        return 1
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        logger.info("Install with: pip install beautifulsoup4")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
