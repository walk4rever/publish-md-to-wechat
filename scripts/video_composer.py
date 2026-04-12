#!/usr/bin/env python3
"""
Video Composer for Video Publisher

Combines PNG slide images and MP3 audio files into a single MP4 video
using ffmpeg. Each image is shown for the duration of its corresponding audio.
Adds fade transitions between slides.

Requires: ffmpeg (system dependency)
"""

import json
import os
import logging
import subprocess
import tempfile
import shutil

logger = logging.getLogger("VideoComposer")

# Minimum duration per slide in seconds (if audio is very short or missing)
_MIN_SLIDE_DURATION = 2.0
# Fade transition duration in seconds
_FADE_DURATION = 0.5


def _resolve_ffmpeg_bin() -> str:
    """Resolve ffmpeg binary path from PATH, imageio-ffmpeg, or Playwright cache."""
    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin:
        return ffmpeg_bin

    try:
        import imageio_ffmpeg
        ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
        if ffmpeg_bin and os.path.exists(ffmpeg_bin) and os.access(ffmpeg_bin, os.X_OK):
            return ffmpeg_bin
    except Exception:
        pass

    candidates = [
        os.path.expanduser("~/Library/Caches/ms-playwright/ffmpeg-1011/ffmpeg-mac"),
    ]
    for path in candidates:
        if os.path.exists(path) and os.access(path, os.X_OK):
            return path

    raise RuntimeError(
        "ffmpeg is required but not found.\n"
        "Install: brew install ffmpeg (macOS) or apt install ffmpeg (Linux), "
        "or pip install imageio-ffmpeg"
    )


def _resolve_ffprobe_bin() -> str | None:
    """Resolve ffprobe binary path. Optional; returns None if unavailable."""
    return shutil.which("ffprobe")


def _get_audio_duration(audio_path: str, ffprobe_bin: str | None = None) -> float:
    """Get audio file duration in seconds using ffprobe (if available)."""
    if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
        return 0.0

    ffprobe = ffprobe_bin or _resolve_ffprobe_bin()
    if not ffprobe:
        return 0.0

    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                audio_path,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        info = json.loads(result.stdout)
        return float(info.get("format", {}).get("duration", 0))
    except (subprocess.CalledProcessError, json.JSONDecodeError, ValueError):
        return 0.0


def compose_video(
    image_paths: list[str],
    audio_paths: list[str],
    output_path: str,
    fade: bool = True,
    width: int = 1080,
    height: int = 1920,
) -> str:
    """Compose PNG images and MP3 audio files into an MP4 video."""
    ffmpeg_bin = _resolve_ffmpeg_bin()
    ffprobe_bin = _resolve_ffprobe_bin()

    if len(image_paths) != len(audio_paths):
        raise ValueError(
            f"Mismatch: {len(image_paths)} images vs {len(audio_paths)} audio files"
        )

    if not image_paths:
        raise ValueError("No slides to compose")

    durations: list[float] = []
    for audio_path in audio_paths:
        duration = _get_audio_duration(audio_path, ffprobe_bin=ffprobe_bin)
        durations.append(max(duration, _MIN_SLIDE_DURATION))

    logger.info(f"Slide durations: {[f'{d:.1f}s' for d in durations]}")
    total_duration = sum(durations)
    logger.info(f"Total video duration: {total_duration:.1f}s")

    tmp_dir = tempfile.mkdtemp(prefix="video_compose_")

    try:
        segment_paths: list[str] = []

        for i, (img, audio, duration) in enumerate(zip(image_paths, audio_paths, durations)):
            segment_path = os.path.join(tmp_dir, f"segment_{i:03d}.mp4")
            has_audio = os.path.exists(audio) and os.path.getsize(audio) > 0

            video_filter = (
                f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
            )

            if has_audio:
                cmd = [
                    ffmpeg_bin, "-y",
                    "-loop", "1", "-i", img,
                    "-i", audio,
                    "-c:v", "libx264",
                    "-t", str(duration),
                    "-pix_fmt", "yuv420p",
                    "-vf", video_filter,
                    "-r", "30",
                    "-preset", "medium",
                    "-crf", "23",
                    "-c:a", "aac",
                    "-b:a", "128k",
                    "-shortest",
                    segment_path,
                ]
            else:
                cmd = [
                    ffmpeg_bin, "-y",
                    "-loop", "1", "-i", img,
                    "-f", "lavfi", "-t", str(duration), "-i", "anullsrc=r=44100:cl=stereo",
                    "-c:v", "libx264",
                    "-t", str(duration),
                    "-pix_fmt", "yuv420p",
                    "-vf", video_filter,
                    "-r", "30",
                    "-preset", "medium",
                    "-crf", "23",
                    "-c:a", "aac",
                    "-b:a", "128k",
                    "-shortest",
                    segment_path,
                ]

            logger.info(f"Encoding segment {i+1}/{len(image_paths)}")
            subprocess.run(cmd, capture_output=True, check=True)
            segment_paths.append(segment_path)

        if fade and len(segment_paths) > 1:
            output = _concat_with_fade(
                segment_paths,
                output_path,
                tmp_dir,
                width,
                height,
                ffmpeg_bin,
                ffprobe_bin,
            )
        else:
            output = _concat_simple(segment_paths, output_path, tmp_dir, ffmpeg_bin)

        logger.info(f"Video saved: {output}")
        return output

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _concat_simple(segment_paths: list[str], output_path: str, tmp_dir: str, ffmpeg_bin: str) -> str:
    """Concatenate video segments without transitions."""
    concat_file = os.path.join(tmp_dir, "concat.txt")
    with open(concat_file, 'w') as f:
        for path in segment_paths:
            f.write(f"file '{path}'\n")

    cmd = [
        ffmpeg_bin, "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_file,
        "-c", "copy",
        output_path,
    ]

    subprocess.run(cmd, capture_output=True, check=True)
    return output_path


def _concat_with_fade(
    segment_paths: list[str],
    output_path: str,
    tmp_dir: str,
    width: int,
    height: int,
    ffmpeg_bin: str,
    ffprobe_bin: str | None,
) -> str:
    """Concatenate video segments with crossfade transitions using xfade filter."""
    if len(segment_paths) == 1:
        shutil.copy2(segment_paths[0], output_path)
        return output_path

    seg_durations: list[float] = []
    for seg in segment_paths:
        dur = _get_audio_duration(seg, ffprobe_bin=ffprobe_bin)
        seg_durations.append(dur if dur > 0 else _MIN_SLIDE_DURATION)

    cmd = [ffmpeg_bin, "-y"]

    for seg in segment_paths:
        cmd.extend(["-i", seg])

    n = len(segment_paths)
    filter_parts: list[str] = []
    audio_filter_parts: list[str] = []

    cumulative = 0.0
    offsets: list[float] = []
    for i in range(n - 1):
        cumulative += seg_durations[i]
        offset = max(0, cumulative - _FADE_DURATION)
        offsets.append(offset)

    if n == 2:
        filter_parts.append(
            f"[0:v][1:v]xfade=transition=fade:duration={_FADE_DURATION}:offset={offsets[0]}[outv]"
        )
        audio_filter_parts.append(
            f"[0:a][1:a]acrossfade=d={_FADE_DURATION}[outa]"
        )
    else:
        prev_label = "0:v"
        for i in range(n - 1):
            next_label = f"{i+1}:v"
            out_label = "outv" if i == n - 2 else f"v{i}"
            filter_parts.append(
                f"[{prev_label}][{next_label}]xfade=transition=fade:duration={_FADE_DURATION}:offset={offsets[i]}[{out_label}]"
            )
            prev_label = out_label

        prev_label = "0:a"
        for i in range(n - 1):
            next_label = f"{i+1}:a"
            out_label = "outa" if i == n - 2 else f"a{i}"
            audio_filter_parts.append(
                f"[{prev_label}][{next_label}]acrossfade=d={_FADE_DURATION}[{out_label}]"
            )
            prev_label = out_label

    filter_graph = ";".join(filter_parts + audio_filter_parts)

    cmd.extend([
        "-filter_complex", filter_graph,
        "-map", "[outv]",
        "-map", "[outa]",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "medium",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        output_path,
    ])

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.warning(f"xfade failed, falling back to simple concat: {result.stderr[:200]}")
        return _concat_simple(segment_paths, output_path, tmp_dir, ffmpeg_bin)

    return output_path


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 4:
        print("Usage: python3 video_composer.py <images_dir> <audio_dir> <output.mp4>")
        print("  images_dir: directory containing slide_000.png, slide_001.png, ...")
        print("  audio_dir: directory containing scene_000.mp3, scene_001.mp3, ...")
        sys.exit(1)

    images_dir = sys.argv[1]
    audio_dir = sys.argv[2]
    output = sys.argv[3]

    images = sorted(
        os.path.join(images_dir, f) for f in os.listdir(images_dir) if f.endswith('.png')
    )
    audios = sorted(
        os.path.join(audio_dir, f) for f in os.listdir(audio_dir) if f.endswith('.mp3')
    )

    compose_video(images, audios, output)
