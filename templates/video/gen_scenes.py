#!/usr/bin/env python3
"""Editable WeChat Channels scene generator. Customize brand, colors, and labels here."""

from pathlib import Path
import html

DEFAULT_BRAND = "深度研究"
DEFAULT_TAGLINE = "关注公众号，阅读完整内容"
BACKGROUND = "#0B0D0F"
ACCENT = "#E63946"
TEXT = "#F5F5F0"
MUTED = "#9A9A94"

ROOT = Path(__file__).resolve().parent

CSS = f"""
* {{ box-sizing: border-box; }} body {{ margin: 0; width: 1080px; height: 1920px; overflow: hidden;
background: {BACKGROUND}; color: {TEXT}; font-family: 'PingFang SC', Arial, sans-serif; }}
.brand {{ position: absolute; top: 72px; left: 72px; color: {ACCENT}; font-size: 24px; font-weight: 700; letter-spacing: 6px; }}
.page {{ position: absolute; top: 72px; right: 72px; color: {MUTED}; font-size: 22px; letter-spacing: 3px; }}
.stage {{ position: absolute; inset: 0 72px 72px; display: flex; flex-direction: column; justify-content: center; }}
.kicker {{ color: {ACCENT}; font-size: 28px; font-weight: 700; letter-spacing: 4px; margin-bottom: 30px; }}
h1 {{ margin: 0; font-size: 122px; line-height: 1.12; letter-spacing: -3px; }}
p {{ color: {MUTED}; font-size: 42px; line-height: 1.45; margin: 42px 0 0; }}
.bar {{ position: absolute; bottom: 0; width: 100%; height: 72px; padding: 0 72px; display: flex; align-items: center;
justify-content: space-between; background: #000; color: {MUTED}; font-size: 18px; letter-spacing: 2px; }}
.bar strong {{ color: {ACCENT}; }}
"""


def scenes() -> list[tuple[str, str]]:
    result = []
    for line in (ROOT / "scenes.txt").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        scene_id, spoken, *display = [part.strip() for part in line.split("|", maxsplit=2)]
        result.append((scene_id, display[0] if display else spoken))
    return result


def render(scene_id: str, copy: str, index: int, total: int) -> str:
    title = html.escape(copy)
    return f"""<!doctype html><html><head><meta charset=\"utf-8\"><style>{CSS}</style></head><body>
<div class=\"brand\">{DEFAULT_BRAND}</div><div class=\"page\">{index:02} / {total:02}</div>
<main class=\"stage\"><div class=\"kicker\">{scene_id}</div><h1>{title}</h1></main>
<footer class=\"bar\"><span><strong>{DEFAULT_BRAND}</strong> VIDEO</span><span>{DEFAULT_TAGLINE}</span></footer>
</body></html>"""


if __name__ == "__main__":
    output = ROOT / "scenes"
    output.mkdir(exist_ok=True)
    items = scenes()
    for index, (scene_id, copy) in enumerate(items, start=1):
        (output / f"{scene_id}.html").write_text(render(scene_id, copy, index, len(items)), encoding="utf-8")
