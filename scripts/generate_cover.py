#!/usr/bin/env python3
"""
Cover Image Generator for WeChat Publisher
With Error Handling and Logging
"""

import argparse
import os
import urllib.parse
import urllib.request
import urllib.error
import ssl
import sys
import logging

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
        "swiss": {"bg": "ffffff", "text": "000000", "fontsize": "55"},
        "terminal": {"bg": "0d1117", "text": "39d353", "fontsize": "50"},
        "cyber": {"bg": "0a0f1c", "text": "00ffcc", "fontsize": "50"},
        "bold": {"bg": "1a1a1a", "text": "ff5722", "fontsize": "60"},
        "botanical": {"bg": "0f0f0f", "text": "d4a574", "fontsize": "50"},
        "notebook": {"bg": "f8f6f1", "text": "1a1a1a", "fontsize": "50"},
        "voltage": {"bg": "0066ff", "text": "ffffff", "fontsize": "50"},
        "geometry": {"bg": "faf9f7", "text": "1a1a1a", "fontsize": "50"},
        "editorial": {"bg": "f5f3ee", "text": "1a1a1a", "fontsize": "50"},
        "ink": {"bg": "faf9f7", "text": "c41e3a", "fontsize": "50"}
    }


def generate_online_png(title: str, style_name: str, output_path: str) -> bool:
    """Generate a high-quality PNG cover using placehold.jp API."""
    global logger
    
    styles = get_styles()
    s = styles.get(style_name, styles["swiss"])
    
    # Construct placehold.jp URL
    encoded_title = urllib.parse.quote(title)
    url = f"https://placehold.jp/{s['fontsize']}/{s['bg']}/{s['text']}/900x383.png?text={encoded_title}"
    
    logger.debug(f"Requesting: {url}")
    
    try:
        # Create unverified context as fallback
        context = ssl._create_unverified_context()
        req = urllib.request.Request(url, headers={
            'User-Agent': 'WeChatPublisher-CoverGenerator/1.0'
        })
        
        with urllib.request.urlopen(req, timeout=15, context=context) as response:
            if response.status == 200:
                with open(output_path, "wb") as f:
                    f.write(response.read())
                logger.info(f"✓ Cover generated: {output_path}")
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
    
    bg = f"#{s['bg']}"
    text = f"#{s['text']}"
    
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
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    logger = setup_logging(args.verbose)
    
    logger.info("=" * 40)
    logger.info("Cover Generator v1.0")
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
    
    # Try online generation first
    logger.info(f"Generating cover: '{args.title}' (style: {args.style})")
    success = generate_online_png(args.title, args.style, args.output)
    
    if success and os.path.exists(args.output):
        logger.info("✓ Success!")
        return 0
    
    # Fallback to SVG
    logger.info("Online generation failed, trying SVG fallback...")
    svg_path = generate_fallback_svg(args.title, args.style, args.output)
    
    # Convert SVG to PNG using sips (macOS) or report
    if svg_path:
        try:
            # Try to convert SVG to PNG using sips (macOS built-in)
            png_from_svg = svg_path.replace(".svg", ".png")
            # Note: sips doesn't support SVG, so we just leave the SVG
            logger.info(f"✓ Cover available as: {svg_path}")
            return 0
        except Exception as e:
            logger.warning(f"Could not convert SVG: {e}")
            return 0
    
    logger.error("Failed to generate cover")
    return 1


if __name__ == "__main__":
    sys.exit(main())