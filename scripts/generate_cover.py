#!/usr/bin/env python3
"""
Cover Image Generator for WeChat Publisher
With Error Handling, Logging, and Local Generation via Pillow
"""

import argparse
import os
import urllib.parse
import urllib.request
import urllib.error
import ssl
import sys
import logging
import textwrap

# Try to import Pillow
try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

# ============================================================
# Logging Configuration
# ============================================================

def setup_logging(verbose: bool = False) -> logging.Logger:
    """Setup logging with console handler."""
    logger = logging.getLogger("CoverGenerator")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.handlers.clear()
    
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    formatter = logging.Formatter('%(asctime)s | %(levelname)-8s | %(message)s', datefmt='%H:%M:%S')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger

logger = None


# ============================================================
# Style Configurations
# ============================================================

def get_styles() -> dict:
    """Get style configurations with accent colors for cover decorations."""
    return {
        "swiss":     {"bg": "#ffffff", "text": "#000000", "accent": "#e62e2e", "fontsize": 52},
        "terminal":  {"bg": "#0d1117", "text": "#39d353", "accent": "#39d353", "fontsize": 48},
        "cyber":     {"bg": "#0a0f1c", "text": "#00ffcc", "accent": "#00ffcc", "fontsize": 48},
        "bold":      {"bg": "#1a1a1a", "text": "#ff5722", "accent": "#ff5722", "fontsize": 56},
        "botanical": {"bg": "#0f0f0f", "text": "#d4a574", "accent": "#d4a574", "fontsize": 46},
        "notebook":  {"bg": "#f8f6f1", "text": "#1a1a1a", "accent": "#98d4bb", "fontsize": 46},
        "voltage":   {"bg": "#0066ff", "text": "#ffffff", "accent": "#d4ff00", "fontsize": 48},
        "geometry":  {"bg": "#faf9f7", "text": "#1a1a1a", "accent": "#f0b4d4", "fontsize": 46},
        "editorial": {"bg": "#f5f3ee", "text": "#1a1a1a", "accent": "#1a1a1a", "fontsize": 46},
        "ink":       {"bg": "#faf9f7", "text": "#c41e3a", "accent": "#c41e3a", "fontsize": 46},
    }


# ============================================================
# Font Helpers
# ============================================================

def get_font(size: int, bold: bool = False):
    """
    Try to load a high-quality font.
    Returns an ImageFont instance.
    When bold=True, prefer bold/medium weight fonts.
    """
    # Bold-preferred candidates (tried first when bold=True)
    bold_candidates = [
        # macOS bold/semibold
        "/System/Library/Fonts/PingFang.ttc",          # index 1 = Medium, but truetype uses index 0
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/Library/Fonts/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        # Linux bold
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        # Windows bold
        "C:\\Windows\\Fonts\\msyhbd.ttc",   # Microsoft YaHei Bold
        "C:\\Windows\\Fonts\\simhei.ttf",   # SimHei (already bold-ish)
    ]

    # Regular candidates
    regular_candidates = [
        # macOS
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        # Linux
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        # Windows
        "C:\\Windows\\Fonts\\msyh.ttc",
        "C:\\Windows\\Fonts\\simhei.ttf",
        "C:\\Windows\\Fonts\\simsun.ttc",
        "C:\\Windows\\Fonts\\arial.ttf",
    ]

    candidates = (bold_candidates + regular_candidates) if bold else regular_candidates

    for path in candidates:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, size)
                logger.debug(f"Loaded font: {path} (bold={bold})")
                return font
            except Exception as e:
                logger.debug(f"Failed to load font {path}: {e}")
                continue
                
    # Fallback to default
    logger.warning("No system fonts found, using default bitmap font (Chinese will likely be garbled).")
    return ImageFont.load_default()


def wrap_text(text: str, font, max_width: int, draw) -> list:
    """
    Wrap text to fit within max_width.
    Handles CJK characters better than textwrap.
    """
    lines = []
    
    # First, split by existing newlines
    paragraphs = text.split('\n')
    
    for paragraph in paragraphs:
        if not paragraph:
            lines.append("")
            continue
            
        # If textwrap works (mostly English), try it first
        # But textwrap doesn't account for font width accurately for variable width fonts
        # So we do a manual measure loop
        
        current_line = ""
        for char in paragraph:
            test_line = current_line + char
            # bbox returns (left, top, right, bottom)
            # length = right - left
            bbox = draw.textbbox((0, 0), test_line, font=font)
            width = bbox[2] - bbox[0]
            
            if width <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = char
        
        if current_line:
            lines.append(current_line)
            
    return lines


# ============================================================
# Generators
# ============================================================

def _hex_to_rgb(hex_color: str) -> tuple:
    """Convert hex color string to RGB tuple."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def _blend_color(c1: tuple, c2: tuple, factor: float) -> tuple:
    """Blend two RGB colors. factor=0 returns c1, factor=1 returns c2."""
    return tuple(int(a + (b - a) * factor) for a, b in zip(c1, c2))


def _draw_decorations(draw, img, style_name: str, s: dict, width: int, height: int):
    """Draw style-specific background decorations to make covers visually rich."""
    bg_rgb = _hex_to_rgb(s["bg"])
    text_rgb = _hex_to_rgb(s["text"])
    accent_rgb = _hex_to_rgb(s.get("accent", s["text"]))

    if style_name == "swiss":
        # Swiss International Style: grid lines + red accent block + geometric precision
        # Subtle grid lines
        grid_color = _blend_color(bg_rgb, (200, 200, 200), 0.4)
        for x in range(0, width, 90):
            draw.line([(x, 0), (x, height)], fill=grid_color, width=1)
        for y in range(0, height, 90):
            draw.line([(0, y), (width, y)], fill=grid_color, width=1)
        # Bold red accent bar at top
        draw.rectangle([(0, 0), (width, 8)], fill=accent_rgb)
        # Red vertical stripe on left
        draw.rectangle([(0, 0), (6, height)], fill=accent_rgb)
        # Bottom-right corner block
        draw.rectangle([(width - 120, height - 50), (width, height)], fill=accent_rgb)
        # Small decorative dot
        draw.ellipse([(width - 160, height - 40), (width - 140, height - 20)], fill=accent_rgb)

    elif style_name == "terminal":
        # Terminal: scan lines + prompt
        for y in range(0, height, 4):
            draw.line([(0, y), (width, y)], fill=_blend_color(bg_rgb, (0, 0, 0), 0.15), width=1)
        # Top bar
        draw.rectangle([(0, 0), (width, 32)], fill=_blend_color(bg_rgb, (255, 255, 255), 0.08))
        # Fake window buttons
        for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
            draw.ellipse([(16 + i * 24, 10), (28 + i * 24, 22)], fill=c)
        # Cursor blink block
        draw.rectangle([(width - 60, height - 40), (width - 40, height - 20)], fill=accent_rgb)

    elif style_name == "cyber":
        # Cyber: diagonal lines + glow accents
        for i in range(-height, width, 40):
            draw.line([(i, 0), (i + height, height)],
                      fill=_blend_color(bg_rgb, accent_rgb, 0.08), width=1)
        draw.rectangle([(0, 0), (width, 4)], fill=accent_rgb)
        draw.rectangle([(0, height - 4), (width, height)], fill=accent_rgb)
        # Corner brackets
        blen = 40
        for corner in [(0, 0, blen, 0, 0, blen), (width, 0, width - blen, 0, width, blen),
                       (0, height, blen, height, 0, height - blen),
                       (width, height, width - blen, height, width, height - blen)]:
            draw.line([(corner[0], corner[1]), (corner[2], corner[3])], fill=accent_rgb, width=2)
            draw.line([(corner[0], corner[1]), (corner[4], corner[5])], fill=accent_rgb, width=2)

    elif style_name == "botanical":
        # Botanical: elegant gold border + corner ornaments
        inset = 20
        draw.rectangle([(inset, inset), (width - inset, height - inset)],
                       outline=_blend_color(accent_rgb, bg_rgb, 0.5), width=1)
        # Corner L-shapes
        cl = 30
        for cx, cy, dx, dy in [(inset, inset, 1, 1), (width - inset, inset, -1, 1),
                                (inset, height - inset, 1, -1), (width - inset, height - inset, -1, -1)]:
            draw.line([(cx, cy), (cx + cl * dx, cy)], fill=accent_rgb, width=2)
            draw.line([(cx, cy), (cx, cy + cl * dy)], fill=accent_rgb, width=2)

    elif style_name == "bold":
        # Bold: thick diagonal stripe
        draw.rectangle([(0, 0), (width, 12)], fill=accent_rgb)
        draw.rectangle([(0, height - 12), (width, height)], fill=accent_rgb)
        # Diagonal accent
        draw.polygon([(width - 180, 0), (width, 0), (width, 120)], fill=accent_rgb)

    elif style_name == "voltage":
        # Voltage: neon yellow accent shapes
        draw.rectangle([(0, 0), (width, 6)], fill=accent_rgb)
        draw.rectangle([(40, height - 50), (200, height - 46)], fill=accent_rgb)
        draw.rectangle([(width - 200, 40), (width - 40, 44)], fill=accent_rgb)

    elif style_name == "notebook":
        # Notebook: ruled lines + margin line
        for y in range(60, height, 28):
            draw.line([(0, y), (width, y)], fill=_blend_color(bg_rgb, (180, 210, 195), 0.4), width=1)
        # Red margin line
        draw.line([(80, 0), (80, height)], fill=(220, 140, 140), width=1)

    elif style_name == "ink":
        # Ink: top crimson bar + subtle underline
        draw.rectangle([(0, 0), (width, 5)], fill=accent_rgb)
        draw.rectangle([(60, height - 30), (width - 60, height - 28)], fill=accent_rgb)

    elif style_name == "editorial":
        # Editorial: thin top/bottom rules
        draw.line([(40, 30), (width - 40, 30)], fill=text_rgb, width=2)
        draw.line([(40, height - 30), (width - 40, height - 30)], fill=text_rgb, width=1)

    elif style_name == "geometry":
        # Geometry: soft circles + rounded feel
        pastel_accent = _blend_color(accent_rgb, bg_rgb, 0.5)
        draw.ellipse([(-60, -60), (120, 120)], fill=pastel_accent)
        draw.ellipse([(width - 100, height - 80), (width + 40, height + 40)], fill=pastel_accent)
        draw.ellipse([(width - 200, -40), (width - 120, 40)], fill=_blend_color(accent_rgb, bg_rgb, 0.7))


def generate_local_cover(title: str, style_name: str, output_path: str) -> bool:
    """Generate a cover image locally using Pillow."""
    global logger
    
    if not HAS_PILLOW:
        logger.warning("Pillow not installed. Skipping local generation.")
        return False
        
    try:
        styles = get_styles()
        s = styles.get(style_name, styles["swiss"])
        
        width, height = 900, 383
        bg_color = s["bg"]
        text_color = s["text"]
        font_size = int(s["fontsize"])
        
        # Create image with background
        img = Image.new('RGB', (width, height), color=bg_color)
        draw = ImageDraw.Draw(img)
        
        # Draw style-specific decorations BEFORE text
        _draw_decorations(draw, img, style_name, s, width, height)
        
        # Load fonts — use bold for title
        font = get_font(font_size, bold=True)
        
        # Calculate max width for text (swiss: left-aligned with padding; others: centered 80%)
        if style_name == "swiss":
            left_pad = 60
            max_text_width = width - left_pad - 80
        else:
            left_pad = None
            max_text_width = width * 0.8
        
        # Wrap text
        lines = wrap_text(title, font, max_text_width, draw)
        
        # Calculate total text height
        line_heights = []
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_heights.append(bbox[3] - bbox[1])
            
        # Add some line spacing
        line_spacing = font_size * 0.3
        total_text_height = sum(line_heights) + (len(lines) - 1) * line_spacing
        
        # Start Y position to center vertically
        current_y = (height - total_text_height) / 2
        
        # Draw each line
        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font)
            line_width = bbox[2] - bbox[0]
            line_height = line_heights[i]
            
            if left_pad is not None:
                x = left_pad  # Left-aligned (swiss)
            else:
                x = (width - line_width) / 2  # Centered (others)
            
            draw.text((x, current_y), line, font=font, fill=text_color)
            current_y += line_height + line_spacing
            
        # Save
        img.save(output_path, quality=95)
        logger.info(f"✓ Local cover generated: {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"Local generation failed: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return False


def generate_online_png(title: str, style_name: str, output_path: str) -> bool:
    """Generate a high-quality PNG cover using placehold.jp API."""
    global logger
    
    styles = get_styles()
    s = styles.get(style_name, styles["swiss"])
    
    # Construct placehold.jp URL
    # Strip # from colors if present for URL
    bg = s['bg'].lstrip('#')
    text = s['text'].lstrip('#')
    
    encoded_title = urllib.parse.quote(title)
    url = f"https://placehold.jp/{s['fontsize']}/{bg}/{text}/900x383.png?text={encoded_title}"
    
    logger.debug(f"Requesting: {url}")
    
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'WeChatPublisher-CoverGenerator/1.0'
        })

        with urllib.request.urlopen(req, timeout=15) as response:
            if response.status == 200:
                with open(output_path, "wb") as f:
                    f.write(response.read())
                logger.info(f"✓ Online cover generated: {output_path}")
                return True
            else:
                logger.warning(f"Unexpected response: {response.status}")
                return False
                
    except urllib.error.URLError as e:
        logger.warning(f"Online generation failed: {e.reason}")
        return False
    except Exception as e:
        logger.warning(f"Unexpected error: {e}")
        return False


def generate_fallback_svg(title: str, style_name: str, output_path: str) -> str:
    """Generate a simplified SVG cover as fallback."""
    global logger
    
    styles = get_styles()
    s = styles.get(style_name, styles["swiss"])
    
    bg = s['bg'] if s['bg'].startswith('#') else f"#{s['bg']}"
    text = s['text'] if s['text'].startswith('#') else f"#{s['text']}"
    
    # Escape special characters for SVG
    safe_title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    
    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg width="900" height="383" xmlns="http://www.w3.org/2000/svg">
    <rect width="900" height="383" fill="{bg}"/>
    <rect x="0" y="0" width="900" height="8" fill="{text}" opacity="0.3"/>
    <text x="50%" y="50%" font-family="Arial, sans-serif" font-size="{s['fontsize']}" fill="{text}" text-anchor="middle" dominant-baseline="middle">{safe_title}</text>
    <text x="50%" y="75%" font-family="Arial, sans-serif" font-size="20" fill="{text}" text-anchor="middle" opacity="0.6">Published via Agent Skill</text>
</svg>"""
    
    # Save as SVG
    svg_path = output_path.replace(".png", ".svg")
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg)
    
    logger.info(f"✓ SVG fallback created: {svg_path}")
    return svg_path


def main():
    """Main entry point."""
    global logger
    
    parser = argparse.ArgumentParser(description="Generate Branded Article Cover")
    parser.add_argument("--title", required=True, help="Article Title")
    parser.add_argument("--style", default="swiss", help="Style preset")
    parser.add_argument("--output", default="assets/cover.png", help="Output file path")
    parser.add_argument("--no-verify-ssl", action="store_true", help="Disable SSL verification (use only for development)")
    parser.add_argument("--force-online", action="store_true", help="Force online generation (skip local Pillow)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    logger = setup_logging(args.verbose)
    
    logger.info("=" * 40)
    logger.info("Cover Generator v2.0 (Local + Online)")
    logger.info("=" * 40)
    
    # Validate title
    if not args.title or not args.title.strip():
        logger.error("Title cannot be empty")
        return 1
    
    # Create output directory
    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
        logger.debug(f"Created directory: {output_dir}")
    
    # Check style
    styles = get_styles()
    if args.style not in styles:
        logger.warning(f"Unknown style '{args.style}', using 'swiss'")
        args.style = "swiss"
    
    success = False
    
    # 1. Try Local Generation (Preferred)
    if HAS_PILLOW and not args.force_online:
        logger.info(f"Attempting local generation (Pillow)...")
        success = generate_local_cover(args.title, args.style, args.output)
    elif not HAS_PILLOW:
        logger.info("Pillow not installed, skipping local generation.")
    
    # 2. Try Online Generation (Fallback)
    if not success:
        logger.info(f"Attempting online generation (placehold.jp)...")
        if args.no_verify_ssl:
            logger.warning("SSL verification disabled - use only for development")
            ssl._create_default_https_context = ssl._create_unverified_context
        else:
            ssl._create_default_https_context = ssl.create_default_context
        success = generate_online_png(args.title, args.style, args.output)
    
    if success and os.path.exists(args.output):
        logger.info("✓ Success!")
        return 0
    
    # 3. Last Resort: SVG Fallback
    logger.warning("All PNG generation methods failed, trying SVG fallback...")
    logger.warning("Note: WeChat does NOT support SVG covers directly.")
    svg_path = generate_fallback_svg(args.title, args.style, args.output)
    
    if svg_path:
        return 0
    
    logger.error("Failed to generate cover")
    return 1


if __name__ == "__main__":
    sys.exit(main())
