#!/usr/bin/env python3
"""
Video Publisher — Markdown to WeChat Video (视频号)

Converts a Markdown article into an MP4 video suitable for WeChat Video Account.

Pipeline:
  1. Parse MD → split into scenes (md_splitter)
  2. Render scenes → vertical slide HTML (slide_renderer)
  3. Capture slides → PNG screenshots (slide_capture / Playwright)
  4. Synthesize narration → MP3 audio (volcengine_tts)
  5. Compose video → MP4 (video_composer / ffmpeg)

Usage:
  python3 scripts/video_publisher.py --md article.md --style swiss --out video.mp4
  python3 scripts/video_publisher.py --md article.md --style ink --voice zh_male_m191_uranus_bigtts
  python3 scripts/video_publisher.py --md article.md --dry-run  # Preview slides only
"""

__version__ = "0.1.0"

import argparse
import logging
import os
import sys
import tempfile
import shutil

# Ensure scripts/ is on sys.path
_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

from md_splitter import split_md_to_scenes
from slide_renderer import render_slides_html, available_styles

try:
    from dotenv import load_dotenv
    load_dotenv()
    # Global fallback
    global_env = os.path.expanduser("~/.config/publish-md-to-wechat/.env")
    if os.path.exists(global_env):
        load_dotenv(global_env)
except ImportError:
    pass

logger = logging.getLogger("VideoPublisher")


def setup_logging(verbose: bool = False) -> None:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s | %(name)-16s | %(levelname)-5s | %(message)s',
        datefmt='%H:%M:%S',
    )


def _ensure_runtime_dependencies(enable_tts: bool) -> None:
    """Fail fast with actionable messages for optional runtime dependencies."""
    import importlib.util
    import shutil as _shutil

    if importlib.util.find_spec("playwright") is None:
        raise ImportError(
            "Playwright is required for video generation.\n"
            "Install: pip install playwright && python -m playwright install chromium"
        )

    ffmpeg_ok = _shutil.which("ffmpeg") is not None
    if not ffmpeg_ok:
        try:
            import imageio_ffmpeg
            ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
            ffmpeg_ok = bool(ffmpeg_bin and os.path.exists(ffmpeg_bin) and os.access(ffmpeg_bin, os.X_OK))
        except Exception:
            ffmpeg_ok = False

    if not ffmpeg_ok:
        # Fallback: Playwright ships a minimal ffmpeg binary.
        pw_ffmpeg = os.path.expanduser("~/Library/Caches/ms-playwright/ffmpeg-1011/ffmpeg-mac")
        ffmpeg_ok = os.path.exists(pw_ffmpeg) and os.access(pw_ffmpeg, os.X_OK)

    if not ffmpeg_ok:
        raise ImportError(
            "ffmpeg is required for video composition.\n"
            "Install: brew install ffmpeg (macOS) or apt install ffmpeg (Linux)"
        )

    if enable_tts and importlib.util.find_spec("websocket") is None:
        raise ImportError(
            "websocket-client is required for Volcengine TTS.\n"
            "Install: pip install websocket-client"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert Markdown to video for WeChat Video Account (视频号)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --md article.md --style swiss
  %(prog)s --md article.md --style ink --voice zh_female_qingxin_moon_bigtts
  %(prog)s --md article.md --dry-run --out-html preview.html
  %(prog)s --md article.md --no-tts  # Skip TTS, images only
        """,
    )

    parser.add_argument("--md", required=True, help="Path to Markdown file")
    parser.add_argument("--style", default="swiss",
                        choices=available_styles(),
                        help=f"Visual style (default: swiss). Available: {', '.join(available_styles())}")
    parser.add_argument("--out", default=None, help="Output MP4 path (default: <md_name>.mp4)")
    parser.add_argument("--out-html", default=None, help="Save intermediate slides HTML to this path")
    parser.add_argument("--title", default=None, help="Override article title")
    parser.add_argument("--author", default=None, help="Author name for title slide")

    # TTS options
    parser.add_argument("--voice", default=None,
                        help="Volcengine voice_type (overrides VOLCANO_TTS_VOICE_TYPE env var)")
    parser.add_argument("--speed", type=float, default=None, help="TTS speed ratio (default: 1.0)")
    parser.add_argument("--no-tts", action="store_true",
                        help="Skip TTS — generate video with minimum 2s per slide, no narration")

    # Video options
    parser.add_argument("--width", type=int, default=1080, help="Video width (default: 1080)")
    parser.add_argument("--height", type=int, default=1920, help="Video height (default: 1920)")
    parser.add_argument("--no-fade", action="store_true", help="Disable fade transitions")

    # Debug options
    parser.add_argument("--dry-run", action="store_true",
                        help="Generate slides HTML only, do not capture or render video")
    parser.add_argument("--keep-temp", action="store_true",
                        help="Keep intermediate files (slides.html, screenshots, audio) for debugging")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")

    args = parser.parse_args()
    setup_logging(args.verbose)

    # Validate input
    if not os.path.exists(args.md):
        logger.error(f"File not found: {args.md}")
        return 1

    if args.width <= 0 or args.height <= 0:
        logger.error("--width and --height must be positive integers")
        return 1

    # Default output path
    if args.out is None:
        base = os.path.splitext(os.path.basename(args.md))[0]
        args.out = os.path.join(os.path.dirname(args.md) or '.', f"{base}.mp4")

    # ── Step 1: Parse and split MD ───────────────────────────
    logger.info(f"Reading {args.md}")
    with open(args.md, 'r', encoding='utf-8') as f:
        md_content = f.read()

    scenes = split_md_to_scenes(md_content, provided_title=args.title, author=args.author)
    logger.info(f"Split into {len(scenes)} scenes")

    for i, scene in enumerate(scenes):
        logger.debug(f"  Scene {i+1} [{scene.scene_type}]: {scene.title[:50]}")

    # ── Step 2: Render slides HTML ───────────────────────────
    logger.info(f"Rendering slides with style: {args.style}")
    html = render_slides_html(scenes, args.style)

    if args.out_html:
        with open(args.out_html, 'w', encoding='utf-8') as f:
            f.write(html)
        logger.info(f"Slides HTML saved: {args.out_html}")

    if args.dry_run:
        # Save HTML and open in browser
        if not args.out_html:
            tmp_html = tempfile.NamedTemporaryFile(suffix='.html', delete=False, mode='w')
            tmp_html.write(html)
            tmp_html.close()
            html_path = tmp_html.name
        else:
            html_path = args.out_html

        logger.info(f"Dry run — slides preview: {html_path}")
        _open_file(html_path)
        print(f"\nDry run complete. {len(scenes)} slides generated.")
        print(f"Preview: {html_path}")
        return 0

    # ── Step 3: Capture slide screenshots ────────────────────
    tmp_dir = tempfile.mkdtemp(prefix="video_pub_")
    logger.debug(f"Working directory: {tmp_dir}")

    try:
        _ensure_runtime_dependencies(enable_tts=not args.no_tts)
        # Save HTML to temp file
        html_path = os.path.join(tmp_dir, "slides.html")
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html)

        logger.info("Capturing slide screenshots...")
        from slide_capture import capture_slides
        image_paths = capture_slides(html_path, os.path.join(tmp_dir, "images"),
                                     width=args.width, height=args.height)
        logger.info(f"Captured {len(image_paths)} screenshots")

        # ── Step 4: TTS synthesis ────────────────────────────
        audio_dir = os.path.join(tmp_dir, "audio")
        os.makedirs(audio_dir, exist_ok=True)

        if args.no_tts:
            logger.info("TTS disabled — generating silent audio placeholders")
            audio_paths = []
            for i in range(len(scenes)):
                silence_path = os.path.join(audio_dir, f"scene_{i:03d}.mp3")
                # Create empty file — composer will use min duration
                with open(silence_path, 'wb') as f:
                    pass
                audio_paths.append(silence_path)
        else:
            logger.info("Synthesizing narration with Volcengine TTS...")

            # Override voice type if specified
            if args.voice:
                os.environ["VOLCANO_TTS_VOICE_TYPE"] = args.voice
            if args.speed:
                os.environ["VOLCANO_TTS_SPEED_RATIO"] = str(args.speed)

            from volcengine_tts import synthesize_scenes
            narrations = [scene.narration for scene in scenes]
            audio_paths = synthesize_scenes(narrations, audio_dir)
            logger.info(f"Synthesized {len(audio_paths)} audio files")

        # ── Step 5: Compose video ────────────────────────────
        logger.info("Composing video with ffmpeg...")
        from video_composer import compose_video
        compose_video(
            image_paths=image_paths,
            audio_paths=audio_paths,
            output_path=args.out,
            fade=not args.no_fade,
            width=args.width,
            height=args.height,
        )

        file_size = os.path.getsize(args.out)
        file_size_mb = file_size / (1024 * 1024)

        print(f"\n{'='*50}")
        print(f"  Video generated successfully!")
        print(f"{'='*50}")
        print(f"  Output:   {args.out}")
        print(f"  Size:     {file_size_mb:.1f} MB")
        print(f"  Slides:   {len(scenes)}")
        print(f"  Style:    {args.style}")
        print(f"  Resolution: {args.width}x{args.height}")
        if not args.no_tts:
            voice = args.voice or os.environ.get("VOLCANO_TTS_VOICE_TYPE", "default")
            print(f"  Voice:    {voice}")
        if args.keep_temp:
            print(f"  Temp:     {tmp_dir}")
        print(f"{'='*50}")
        print(f"\n  Next: Upload to WeChat Video Account (视频号)")

        _open_file(args.out)
        return 0

    except ImportError as e:
        logger.error(str(e))
        logger.error("Install missing dependencies and retry.")
        return 1
    except Exception as e:
        logger.error(f"Video generation failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1
    finally:
        if args.keep_temp:
            logger.info(f"Keeping temp files: {tmp_dir}")
        else:
            shutil.rmtree(tmp_dir, ignore_errors=True)


def _open_file(path: str) -> None:
    """Open a file with the system default application."""
    import subprocess as sp
    try:
        if sys.platform == "darwin":
            sp.run(["open", path], check=False)
        elif sys.platform.startswith("linux"):
            sp.run(["xdg-open", path], check=False)
    except FileNotFoundError:
        pass


if __name__ == "__main__":
    sys.exit(main())
