#!/usr/bin/env python3
"""Slidev export helper for video pipeline."""

from __future__ import annotations

import glob
import logging
import os
import re
import shutil
import subprocess
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

logger = logging.getLogger("SlidevRenderer")


def _natural_key(path: str) -> list[object]:
    name = os.path.basename(path)
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def ensure_slidev_available(theme: str) -> None:
    """Check required runtime tools and local node deps for Slidev PNG export."""
    if shutil.which("npx") is None:
        raise ImportError(
            "Environment missing: npx is required for Slidev export. Install Node.js (includes npm/npx)."
        )

    cli_pkg_path = os.path.join(PROJECT_ROOT, "node_modules", "@slidev", "cli")
    if not os.path.exists(cli_pkg_path):
        raise ImportError(
            "Dependency missing: @slidev/cli is not installed in project root. "
            "Run ./install.sh (or npm install) in the skill root."
        )

    theme_pkg_name = f"theme-{theme}"
    theme_pkg_path = os.path.join(PROJECT_ROOT, "node_modules", "@slidev", theme_pkg_name)
    if not os.path.exists(theme_pkg_path):
        raise ImportError(
            f"Dependency missing: @slidev/{theme_pkg_name} is not installed in project root. "
            "Run ./install.sh (or npm install) in the skill root."
        )


def export_slidev_png(
    slides_md_path: str,
    output_dir: str,
    *,
    with_clicks: bool = False,
) -> list[str]:
    """Export Slidev markdown to ordered PNG slide images."""
    os.makedirs(output_dir, exist_ok=True)

    with open(slides_md_path, "r", encoding="utf-8") as f:
        content = f.read()
    theme_match = re.search(r"^theme:\s*([a-zA-Z0-9_-]+)", content, re.MULTILINE)
    theme_name = theme_match.group(1) if theme_match else "default"

    ensure_slidev_available(theme_name)

    temp_workdir = tempfile.mkdtemp(prefix="slidev_run_", dir=PROJECT_ROOT)
    try:
        runtime_slides_path = os.path.join(temp_workdir, "slides.md")
        shutil.copy2(slides_md_path, runtime_slides_path)

        cmd = [
            "npx",
            "--no-install",
            "@slidev/cli",
            "export",
            runtime_slides_path,
            "--format",
            "png",
            "--output",
            os.path.abspath(output_dir),
        ]
        if with_clicks:
            cmd.append("--with-clicks")

        logger.info("Exporting slides with Slidev (cwd=%s)...", PROJECT_ROOT)
        subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=PROJECT_ROOT)
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        stdout = (exc.stdout or "").strip()
        detail = stderr or stdout or str(exc)
        raise RuntimeError(
            "Slidev rendering failed. Check: 1) deps installed via ./install.sh in skill root; "
            "2) export command running with skill-root cwd; 3) slides theme package exists. "
            f"Raw error: {detail}"
        ) from exc
    finally:
        shutil.rmtree(temp_workdir, ignore_errors=True)

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
