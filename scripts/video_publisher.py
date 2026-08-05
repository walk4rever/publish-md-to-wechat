#!/usr/bin/env python3
"""Build a verified WeChat Channels video from HTML scenes and narration."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from video_pipeline import audio_duration, build_timeline, capture_html, compose_video, create_video_project, generate_audio, parse_scenes, render_ass, validate_scene_html, validate_target_duration


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a WeChat vertical video from HTML scenes")
    parser.add_argument("--project-dir", help="Directory containing scenes.txt and gen_scenes.py")
    parser.add_argument("--init-project", help="Create a video project from the bundled HTML template")
    parser.add_argument("--out", help="Output MP4 path")
    parser.add_argument("--duration", type=int, help="Target runtime in seconds; validates against rendered narration")
    parser.add_argument("--voice", default="zh-CN-YunxiNeural", help="Edge TTS voice")
    parser.add_argument("--rate", default="+6%", help="Edge TTS speaking rate")
    parser.add_argument("--dry-run", action="store_true", help="Generate and validate scene HTML only")
    args = parser.parse_args()

    if args.init_project:
        if args.project_dir or args.out:
            parser.error("--init-project cannot be combined with --project-dir or --out")
        print(f"Created video project: {create_video_project(args.init_project)}")
        return 0
    if not args.project_dir or not args.out or not args.duration or args.duration <= 0:
        parser.error("--project-dir, --out, and a positive --duration are required")

    project = Path(args.project_dir).resolve()
    scenes_file, generator = project / "scenes.txt", project / "gen_scenes.py"
    if not scenes_file.is_file() or not generator.is_file():
        parser.error("--project-dir must contain scenes.txt and gen_scenes.py")
    scenes = parse_scenes(scenes_file.read_text(encoding="utf-8"))
    subprocess.run([sys.executable, str(generator)], cwd=project, check=True)
    html = validate_scene_html(project / "scenes", scenes)
    if args.dry_run:
        print(f"Validated {len(scenes)} scenes in {project}")
        return 0

    frames = capture_html(html, project / "frames")
    audio = generate_audio(scenes, project / "audio", args.voice, args.rate)
    timeline = build_timeline(scenes, [audio_duration(path) for path in audio])
    if not validate_target_duration(timeline, args.duration):
        actual = sum(item.duration for item in timeline)
        raise RuntimeError(f"Narration is {actual:.1f}s, outside the allowed 15% range for target {args.duration}s. Revise scenes.txt and rerun.")
    subtitle = project / "build" / "sub.ass"
    subtitle.parent.mkdir(parents=True, exist_ok=True)
    subtitle.write_text(render_ass(timeline), encoding="utf-8")
    output = Path(args.out).resolve()
    compose_video(frames, audio, timeline, output, subtitle)
    total = sum(item.duration for item in timeline)
    for label, second in (("start", 1), ("middle", total / 2), ("end", max(total - 1, 0))):
        subprocess.run(["ffmpeg", "-y", "-ss", str(second), "-i", str(output), "-frames:v", "1", "-q:v", "3", str(project / "build" / f"check_{label}.jpg")], check=True, capture_output=True)
    print(f"Video generated: {output} ({total:.1f}s). Inspect build/check_start.jpg, check_middle.jpg, and check_end.jpg.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
