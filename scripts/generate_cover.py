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
    """Get style configurations."""
    return {
        "swiss": {"bg": "#ffffff", "text": "#000000", "fontsize": 60},
        "terminal": {"bg": "#0d1117", "text": "#39d353", "fontsize": 50},
        "cyber": {"bg": "#0a0f1c", "text": "#00ffcc", "fontsize": 50},
        "bold": {"bg": "#1a1a1a", "text": "#ff5722", "fontsize": 60},
        "botanical": {"bg": "#0f0f0f", "text": "#d4a574", "fontsize": 50},
        "notebook": {"bg": "#f8f6f1", "text": "#1a1a1a", "fontsize": 50},
        "voltage": {"bg": "#0066ff", "text": "#ffffff", "fontsize": 50},
        "geometry": {"bg": "#faf9f7", "text": "#1a1a1a", "fontsize": 50},
        "editorial": {"bg": "#f5f3ee", "text": "#1a1a1a", "fontsize": 50},
        "ink": {"bg": "#faf9f7", "text": "#c41e3a", "fontsize": 50}
    }


# ============================================================
# Font Helpers
# ============================================================

def get_font(size: int):
    """
    Try to load a high-quality font.
    Returns an ImageFont instance.
    """
    # Common font paths on macOS/Linux/Windows
    font_candidates = [
        # macOS
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
        # Linux
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        # Windows
        "C:\\Windows\\Fonts\\arial.ttf",
        "C:\\Windows\\Fonts\\msyh.ttc",
    ]
    
    for path in font_candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
                
    # Fallback to default
    logger.warning("No system fonts found, using default bitmap font (ugly).")
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
        
        # Create image
        img = Image.new('RGB', (width, height), color=bg_color)
        draw = ImageDraw.Draw(img)
        
        # Load font
        font = get_font(font_size)
        
        # Calculate max width for text (80% of image width)
        max_text_width = width * 0.8
        
        # Wrap text
        lines = wrap_text(title, font, max_text_width, draw)
        
        # Calculate total text height
        line_heights = []
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_heights.append(bbox[3] - bbox[1])
            
        # Add some line spacing
        line_spacing = font_size * 0.2
        total_text_height = sum(line_heights) + (len(lines) - 1) * line_spacing
        
        # Start Y position to center vertically
        current_y = (height - total_text_height) / 2
        
        # Draw each line centered horizontally
        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font)
            line_width = bbox[2] - bbox[0]
            line_height = line_heights[i]
            
            x = (width - line_width) / 2
            
            # Draw text
            draw.text((x, current_y), line, font=font, fill=text_color)
            
            current_y += line_height + line_spacing
            
        # Save
        img.save(output_path)
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
