#!/usr/bin/env python3
"""
Video Publisher — Slidev + Narration to WeChat Video (视频号)

Pipeline:
  1) Validate pre-generated Slidev markdown + narration JSON
  2) Render Slidev markdown and export PNG slides
  3) Synthesize narration to MP3 (Volcengine TTS)
  4) Compose final MP4 with ffmpeg
"""

from __future__ import annotations

__version__ = "0.2.1"

import argparse
import json
import logging
import os
import shutil
import sys
import tempfile

# Ensure scripts/ is on sys.path
_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

try:
    from dotenv import load_dotenv

    load_dotenv()
    global_env = os.path.expanduser("~/.config/publish-md-to-wechat/.env")
    if os.path.exists(global_env):
        load_dotenv(global_env)
except ImportError:
    pass

logger = logging.getLogger("VideoPublisher")


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(name)-16s | %(levelname)-5s | %(message)s",
        datefmt="%H:%M:%S",
    )


def _ensure_runtime_dependencies(enable_tts: bool) -> None:
    """Fail fast for runtime dependencies."""
    import importlib.util
    import shutil as _shutil

    if _shutil.which("npx") is None:
        raise ImportError("npx is required for Slidev export. Install Node.js (includes npm/npx).")

    if _shutil.which("ffmpeg") is None:
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
        description="Render WeChat vertical video from pre-generated Slidev + narration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --slides tmp/slides.md --narration tmp/narration.json --duration 60 --style swiss
  %(prog)s --slides tmp/slides.md --narration tmp/narration.json --duration 90 --no-tts
        """,
    )

    parser.add_argument("--md", help="Optional source markdown path (used only for output naming)")
    parser.add_argument("--slides", help="Path to pre-generated slides.md")
    parser.add_argument("--narration", help="Path to pre-generated narration.json")
    parser.add_argument("--duration", required=True, type=int, help="Target narration duration in seconds")
    parser.add_argument("--style", help="Optional style label for reporting")
    parser.add_argument("--tone", help="Optional tone label for reporting")
    parser.add_argument("--audience", help="Optional audience label for reporting")

    parser.add_argument("--out", default=None, help="Output MP4 path (default: <md_name>.mp4)")
    parser.add_argument("--out-slides", default=None, help="Copy input Slidev markdown to a target path")
    parser.add_argument("--voice", default=None, help="Volcengine voice_type override")
    parser.add_argument("--speed", type=float, default=None, help="TTS speed ratio (default: 1.0)")
    parser.add_argument("--no-verify-ssl", action="store_true", help="Disable SSL verification for TTS WebSocket")
    parser.add_argument("--no-tts", action="store_true", help="Skip TTS and produce silent per-slide audio placeholders")

    parser.add_argument("--width", type=int, default=1080, help="Video width (default: 1080)")
    parser.add_argument("--height", type=int, default=1920, help="Video height (default: 1920)")
    parser.add_argument("--no-fade", action="store_true", help="Disable fade transitions")

    parser.add_argument("--dry-run", action="store_true", help="Validate inputs and stop before rendering/TTS/composition")
    parser.add_argument("--keep-temp", action="store_true", help="Keep intermediate files for debugging")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")

    args = parser.parse_args()
    setup_logging(args.verbose)

    if args.md and not os.path.exists(args.md):
        logger.error(f"File not found: {args.md}")
        return 1

    if not args.slides or not args.narration:
        logger.error(
            "Input error: --slides and --narration are required. "
            "Planning is handled by the caller/agent before invoking this script."
        )
        return 1

    if not os.path.exists(args.slides):
        logger.error(f"File not found: {args.slides}")
        return 1

    if not os.path.exists(args.narration):
        logger.error(f"File not found: {args.narration}")
        return 1

    if args.duration <= 0:
        logger.error("--duration must be a positive integer")
        return 1

    if args.width <= 0 or args.height <= 0:
        logger.error("--width and --height must be positive integers")
        return 1

    if args.out is None:
        if args.md:
            base = os.path.splitext(os.path.basename(args.md))[0]
            args.out = os.path.join(os.path.dirname(args.md) or ".", f"{base}.mp4")
        else:
            base = os.path.splitext(os.path.basename(args.slides))[0]
            args.out = os.path.join(os.path.dirname(args.slides) or ".", f"{base}.mp4")

    tmp_dir = tempfile.mkdtemp(prefix="video_pub_")
    logger.debug(f"Working directory: {tmp_dir}")

    try:
        _ensure_runtime_dependencies(enable_tts=not args.no_tts)

        logger.info("Using pre-generated slides and narration...")
        slides_path = os.path.join(tmp_dir, "slides.md")
        shutil.copy(args.slides, slides_path)

        with open(args.narration, "r", encoding="utf-8") as f:
            narration_data = json.load(f)

        class Scene:
            def __init__(self, narration: str, title: str = "", scene_type: str = "content"):
                self.narration = narration
                self.title = title
                self.scene_type = scene_type

        raw_scenes = narration_data.get("scenes", [])
        if not isinstance(raw_scenes, list) or not raw_scenes:
            logger.error("Input error: narration.json must contain a non-empty 'scenes' array")
            return 1

        scenes = []
        for i, scene in enumerate(raw_scenes):
            if not isinstance(scene, dict):
                logger.error(f"Input error: scenes[{i}] must be an object")
                return 1
            if "narration" not in scene or not str(scene.get("narration", "")).strip():
                logger.error(f"Input error: scenes[{i}].narration is required and must be non-empty")
                return 1
            scenes.append(
                Scene(
                    narration=str(scene["narration"]),
                    title=str(scene.get("title", "")),
                    scene_type=str(scene.get("scene_type", "content")),
                )
            )

        plan_meta = narration_data.get("meta") if isinstance(narration_data.get("meta"), dict) else {}

        narration_json_path = os.path.join(tmp_dir, "narration.json")
        shutil.copy(args.narration, narration_json_path)

        if args.out_slides:
            shutil.copy(slides_path, args.out_slides)
            logger.info(f"Saved slides markdown copy: {args.out_slides}")

        if args.dry_run:
            print("\n" + "=" * 50)
            print("  Dry run completed")
            print("=" * 50)
            print(f"  Slides:    {slides_path}")
            print(f"  Narration: {narration_json_path}")
            print(f"  Scenes:    {len(scenes)}")
            if plan_meta:
                print(f"  Model:     {plan_meta.get('model', 'unknown')}")
                print(f"  Est time:  {plan_meta.get('estimated_duration_seconds', '?')}s")
            print("=" * 50)
            return 0

        # Step 2: Slidev export to PNG.
        from slidev_renderer import export_slidev_png

        logger.info("Exporting PNG slides with Slidev...")
        image_dir = os.path.join(tmp_dir, "images")
        image_paths = export_slidev_png(slides_path, image_dir, with_clicks=False)
        logger.info(f"Exported {len(image_paths)} PNG slides")

        if len(image_paths) != len(scenes):
            raise RuntimeError(
                f"Slide count mismatch: {len(image_paths)} images vs {len(scenes)} scenes"
            )

        # Step 3: TTS audio generation.
        audio_dir = os.path.join(tmp_dir, "audio")
        os.makedirs(audio_dir, exist_ok=True)

        if args.no_tts:
            logger.info("TTS disabled — generating silent placeholders")
            audio_paths = []
            for i in range(len(scenes)):
                silence_path = os.path.join(audio_dir, f"scene_{i:03d}.mp3")
                with open(silence_path, "wb") as f:
                    pass
                audio_paths.append(silence_path)
        else:
            if args.voice:
                os.environ["VOLCANO_TTS_VOICE_TYPE"] = args.voice
            if args.speed:
                os.environ["VOLCANO_TTS_SPEED_RATIO"] = str(args.speed)
            if args.no_verify_ssl:
                os.environ["VOLCANO_TTS_VERIFY_SSL"] = "0"

            logger.info("Synthesizing narration with Volcengine TTS...")
            from volcengine_tts import synthesize_scenes

            narrations = [scene.narration for scene in scenes]
            audio_paths = synthesize_scenes(narrations, audio_dir)
            logger.info(f"Synthesized {len(audio_paths)} audio files")

        # Step 4: Compose final video.
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

        file_size_mb = os.path.getsize(args.out) / (1024 * 1024)
        print("\n" + "=" * 50)
        print("  Video generated successfully!")
        print("=" * 50)
        print(f"  Output:   {args.out}")
        print(f"  Size:     {file_size_mb:.1f} MB")
        print(f"  Scenes:   {len(scenes)}")
        if args.style:
            print(f"  Style:    {args.style}")
        if args.tone:
            print(f"  Tone:     {args.tone}")
        if args.audience:
            print(f"  Audience: {args.audience}")
        if not args.no_tts:
            print(f"  Voice:    {args.voice or os.environ.get('VOLCANO_TTS_VOICE_TYPE', 'default')}")
        if args.keep_temp:
            print(f"  Temp:     {tmp_dir}")
        print("=" * 50)

        _open_file(args.out)
        return 0

    except ImportError as e:
        logger.error(str(e))
        return 1
    except Exception as e:
        logger.error(f"Video generation failed: {e}")
        if "CERTIFICATE_VERIFY_FAILED" in str(e):
            logger.error("SSL verification failed for TTS. Retry with --no-verify-ssl if behind a proxy.")
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
