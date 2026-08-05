"""HTML scene, audio, subtitle, and FFmpeg helpers for WeChat short videos."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import re
import shutil
import subprocess
import sys
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Scene:
    id: str
    spoken_text: str
    display_text: str


@dataclass(frozen=True)
class TimedScene:
    scene: Scene
    start: float
    duration: float


def parse_scenes(content: str) -> list[Scene]:
    """Parse `S1|spoken text|optional subtitle text` lines."""
    scenes: list[Scene] = []
    seen: set[str] = set()
    for line_number, line in enumerate(content.splitlines(), start=1):
        if not line.strip():
            continue
        parts = [part.strip() for part in line.split("|", maxsplit=2)]
        if len(parts) < 2 or not re.fullmatch(r"S[1-9]\d*", parts[0]) or not parts[1]:
            raise ValueError(f"Invalid scenes.txt line {line_number}; use S1|spoken text|optional subtitle text")
        if parts[0] in seen:
            raise ValueError(f"Duplicate scene id: {parts[0]}")
        seen.add(parts[0])
        scenes.append(Scene(parts[0], parts[1], parts[2] if len(parts) == 3 and parts[2] else parts[1]))
    if not scenes:
        raise ValueError("scenes.txt contains no scenes")
    expected = [f"S{i}" for i in range(1, len(scenes) + 1)]
    if [scene.id for scene in scenes] != expected:
        raise ValueError(f"Scene ids must be sequential: {', '.join(expected)}")
    return scenes


def validate_scene_html(scene_dir: str | Path, scenes: list[Scene]) -> list[Path]:
    paths = [Path(scene_dir) / f"{scene.id}.html" for scene in scenes]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise ValueError(f"Missing generated scene HTML: {', '.join(missing)}")
    return paths


def create_video_project(project_dir: str | Path) -> Path:
    """Create an editable video project from the bundled HTML scene template."""
    project = Path(project_dir)
    project.mkdir(parents=True, exist_ok=True)
    scenes_file = project / "scenes.txt"
    generator = project / "gen_scenes.py"
    if not scenes_file.exists():
        scenes_file.write_text("S1|一句话钩子\nS2|核心观点\nS3|关注公众号，阅读完整内容\n", encoding="utf-8")
    if not generator.exists():
        shutil.copy2(PROJECT_ROOT / "templates" / "video" / "gen_scenes.py", generator)
    return project


def build_timeline(scenes: list[Scene], audio_durations: list[float], breathing_seconds: float = 0.5) -> list[TimedScene]:
    if len(scenes) != len(audio_durations):
        raise ValueError("Scene and audio counts must match")
    start = 0.0
    timeline: list[TimedScene] = []
    for scene, audio_duration in zip(scenes, audio_durations):
        if audio_duration <= 0:
            raise ValueError(f"Audio duration for {scene.id} must be positive")
        duration = audio_duration + breathing_seconds
        timeline.append(TimedScene(scene, start, duration))
        start += duration
    return timeline


def validate_target_duration(timeline: list[TimedScene], target_seconds: int, tolerance: float = 0.15) -> bool:
    """Return whether audio-derived duration is close enough to the requested runtime."""
    actual = sum(item.duration for item in timeline)
    return abs(actual - target_seconds) <= target_seconds * tolerance


def _ass_time(seconds: float) -> str:
    centiseconds = round(seconds * 100)
    hours, remainder = divmod(centiseconds, 360000)
    minutes, remainder = divmod(remainder, 6000)
    return f"{hours}:{minutes:02}:{remainder // 100:02}.{remainder % 100:02}"


def _subtitle_lines(text: str, limit: int = 24) -> str:
    text = text.replace("\n", " ").replace("{", "\\{").replace("}", "\\}")
    if len(text) <= limit:
        return text
    midpoint = len(text) // 2
    whitespace = [index for index, character in enumerate(text) if character.isspace()]
    punctuation = [index for index, character in enumerate(text) if character in "，。！？；、"]
    candidates = whitespace or punctuation
    split_at = min(candidates, key=lambda index: abs(index - midpoint)) + 1 if candidates else midpoint
    return f"{text[:split_at]}\\N{text[split_at:]}"


def render_ass(timeline: list[TimedScene]) -> str:
    header = """[Script Info]
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Sub,PingFang SC,44,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,2,2,70,70,180,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    lines = []
    for item in timeline:
        start = item.start + 0.2
        end = item.start + item.duration - 0.3
        lines.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Sub,,0,0,0,,{_subtitle_lines(item.scene.display_text)}")
    return header + "\n".join(lines) + "\n"


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True, capture_output=True, text=True)


def audio_duration(path: Path) -> float:
    result = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)], check=True, capture_output=True, text=True)
    return float(json.loads(result.stdout)["format"]["duration"])


def generate_audio(scenes: list[Scene], output_dir: Path, voice: str, rate: str) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for scene in scenes:
        output = output_dir / f"{scene.id}.mp3"
        _run([sys.executable, "-m", "edge_tts", "--voice", voice, "--rate", rate, "--text", scene.spoken_text, "--write-media", str(output)])
        paths.append(output)
    return paths


def capture_html(html_paths: list[Path], output_dir: Path) -> list[Path]:
    from playwright.sync_api import sync_playwright

    output_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1920}, device_scale_factor=1)
        paths = []
        for html_path in html_paths:
            output = output_dir / f"{html_path.stem}.png"
            page.goto(html_path.resolve().as_uri(), wait_until="networkidle")
            page.screenshot(path=str(output))
            paths.append(output)
        browser.close()
    return paths


def compose_video(images: list[Path], audio: list[Path], timeline: list[TimedScene], output: Path, subtitle_path: Path) -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise RuntimeError("ffmpeg and ffprobe are required")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="wechat_video_") as temporary:
        work = Path(temporary)
        video_list, audio_list = [], []
        for image, audio_path, item in zip(images, audio, timeline):
            video = work / f"{item.scene.id}.mp4"
            sound = work / f"{item.scene.id}.m4a"
            frames = round(item.duration * 30)
            zoom = f"zoompan=z='min(zoom+0.0009,1.07)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps=30,format=yuv420p"
            _run(["ffmpeg", "-y", "-loop", "1", "-i", str(image), "-filter_complex", zoom, "-t", str(item.duration), "-c:v", "libx264", "-preset", "fast", "-crf", "20", str(video)])
            _run(["ffmpeg", "-y", "-i", str(audio_path), "-af", f"apad,atrim=0:{item.duration}", "-c:a", "aac", "-b:a", "128k", str(sound)])
            video_list.append(f"file '{video}'")
            audio_list.append(f"file '{sound}'")
        (work / "video.txt").write_text("\n".join(video_list) + "\n", encoding="utf-8")
        (work / "audio.txt").write_text("\n".join(audio_list) + "\n", encoding="utf-8")
        video_output, audio_output = work / "video.mp4", work / "audio.m4a"
        _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(work / "video.txt"), "-c", "copy", str(video_output)])
        _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(work / "audio.txt"), "-c:a", "aac", "-b:a", "128k", str(audio_output)])
        _run(["ffmpeg", "-y", "-i", str(video_output), "-i", str(audio_output), "-vf", f"ass={subtitle_path}", "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-c:a", "aac", "-b:a", "128k", "-shortest", str(output)])
