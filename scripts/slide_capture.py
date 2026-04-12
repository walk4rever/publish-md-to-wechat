#!/usr/bin/env python3
"""
Slide Capture for Video Publisher

Uses Playwright to render slide HTML and capture each .slide element
as a 1080x1920 PNG screenshot.

Requires: playwright (pip install playwright && playwright install chromium)
"""

import os
import logging
import tempfile
from typing import Optional

logger = logging.getLogger("SlideCapture")


def capture_slides(
    html_path: str,
    output_dir: str,
    width: int = 1080,
    height: int = 1920,
) -> list[str]:
    """Capture each .slide in the HTML file as a PNG screenshot.

    Args:
        html_path: Path to the slides HTML file.
        output_dir: Directory to save PNG files.
        width: Viewport width (default 1080 for vertical video).
        height: Viewport height (default 1920 for vertical video).

    Returns:
        List of PNG file paths in slide order.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise ImportError(
            "Playwright is required for slide capture.\n"
            "Install: pip install playwright && python -m playwright install chromium"
        )

    os.makedirs(output_dir, exist_ok=True)
    abs_html = os.path.abspath(html_path)
    file_url = f"file://{abs_html}"

    logger.info(f"Capturing slides from {html_path} at {width}x{height}")

    screenshot_paths: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": height})

        page.goto(file_url, wait_until="networkidle")

        # Wait for fonts to load
        page.evaluate("() => document.fonts.ready")
        page.wait_for_timeout(1500)

        # Count slides
        slide_count = page.evaluate("() => document.querySelectorAll('.slide').length")
        logger.info(f"Found {slide_count} slides")

        if slide_count == 0:
            browser.close()
            raise RuntimeError("No .slide elements found in HTML")

        for i in range(slide_count):
            # Show only the current slide, hide all others
            page.evaluate("""(index) => {
                const slides = document.querySelectorAll('.slide');
                slides.forEach((slide, idx) => {
                    if (idx === index) {
                        slide.style.display = 'flex';
                        slide.style.opacity = '1';
                        slide.style.visibility = 'visible';
                        slide.style.position = 'relative';
                    } else {
                        slide.style.display = 'none';
                    }
                });
            }""", i)

            page.wait_for_timeout(200)

            out_path = os.path.join(output_dir, f"slide_{i:03d}.png")
            page.screenshot(path=out_path, full_page=False)
            screenshot_paths.append(out_path)
            logger.info(f"Captured slide {i+1}/{slide_count}: {out_path}")

        browser.close()

    return screenshot_paths


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage: python3 slide_capture.py <slides.html> [output_dir]")
        sys.exit(1)

    html_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "./slides_output"

    paths = capture_slides(html_path, output_dir)
    print(f"Captured {len(paths)} slides to {output_dir}")
