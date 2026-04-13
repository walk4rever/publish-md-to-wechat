#!/usr/bin/env python3
"""Slidev export helper for video pipeline."""

from __future__ import annotations

import glob
import logging
import os
import re
import shutil
import subprocess

logger = logging.getLogger("SlidevRenderer")


def _natural_key(path: str) -> list[object]:
    name = os.path.basename(path)
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def ensure_slidev_available() -> None:
    """Check required runtime tools for Slidev PNG export."""
    if shutil.which("npx") is None:
        raise ImportError(
            "npx is required for Slidev export. Install Node.js (which includes npm/npx)."
        )


def export_slidev_png(
    slides_md_path: str,
    output_dir: str,
    *,
    with_clicks: bool = False,
) -> list[str]:
    """Export Slidev markdown to ordered PNG slide images."""
    ensure_slidev_available()
    os.makedirs(output_dir, exist_ok=True)

    cmd = [
        "npx",
        "--yes",
        "@slidev/cli",
        "export",
        slides_md_path,
        "--format",
        "png",
        "--output",
        output_dir,
    ]
    if with_clicks:
        cmd.append("--with-clicks")

    logger.info("Exporting slides with Slidev...")
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        stdout = (exc.stdout or "").strip()
        detail = stderr or stdout or str(exc)
        raise RuntimeError(f"Slidev export failed: {detail}") from exc

    png_paths = glob.glob(os.path.join(output_dir, "**", "*.png"), recursive=True)
    png_paths.sort(key=_natural_key)

    if not png_paths:
        raise RuntimeError("Slidev export succeeded but produced no PNG files")

    logger.info(f"Slidev exported {len(png_paths)} PNG slides")
    return png_paths


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Export Slidev markdown to PNG files")
    parser.add_argument("slides_md", help="Path to slides.md")
    parser.add_argument("--out", required=True, help="Output directory")
    parser.add_argument("--with-clicks", action="store_true")
    args = parser.parse_args()

    paths = export_slidev_png(args.slides_md, args.out, with_clicks=args.with_clicks)
    print(f"Exported {len(paths)} PNG files")
