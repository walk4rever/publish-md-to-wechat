#!/usr/bin/env python3
"""
LLM Slide Planner for Video Publisher

Transforms a Markdown article into:
  1) Scene list (title/content/closing + narration)
  2) Slidev-compatible slides.md

This module is intentionally LLM-first (no deterministic fallback).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Optional

import yaml


@dataclass(frozen=True)
class Scene:
    """A single video slide scene."""

    title: str
    body: str
    narration: str
    scene_type: str = "content"  # "title", "content", "closing"


_THEME_MAP = {
    "swiss": "seriph",
    "ink": "default",
    "minimal": "default",
}


def _strip_frontmatter(md: str) -> tuple[dict, str]:
    """Remove YAML frontmatter, return (metadata, body)."""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", md, re.DOTALL)
    if not match:
        return {}, md
    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        meta = {}
    return meta, md[match.end() :]


def _extract_title(meta: dict, body: str, provided_title: Optional[str] = None) -> tuple[str, str]:
    """Extract title and return (title, body_without_h1)."""
    if provided_title:
        return provided_title, body

    if meta.get("title"):
        return str(meta["title"]).strip(), body

    h1_match = re.match(r"^#\s+(.+)\s*\n", body)
    if h1_match:
        return h1_match.group(1).strip(), body[h1_match.end() :]

    lines = [line.strip() for line in body.split("\n") if line.strip()]
    if lines:
        return lines[0], body
    return "Untitled", body


def _estimate_narration_seconds(text: str) -> float:
    """Estimate narration duration in seconds for zh/en mixed text."""
    if not text.strip():
        return 0.0

    cjk_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    en_words = len(re.findall(r"[A-Za-z0-9_]+", text))

    # Conservative rates for natural TTS pacing.
    cjk_seconds = cjk_chars / 4.8
    en_seconds = en_words / 2.8
    buffer = 0.35
    return max(cjk_seconds + en_seconds, 0.8) + buffer


def _extract_first_json_object(text: str) -> dict:
    """Parse first JSON object from model text output."""
    text = text.strip()
    if not text:
        raise ValueError("LLM returned empty content")

    # Direct JSON fast-path.
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    # Markdown fenced JSON.
    fenced = re.search(r"```json\s*(\{[\s\S]*\})\s*```", text)
    if fenced:
        return json.loads(fenced.group(1))

    # First object heuristic.
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return json.loads(text[start : end + 1])

    raise ValueError("LLM output does not contain a valid JSON object")


def _call_planner_llm(
    *,
    title: str,
    markdown: str,
    style_name: str,
    duration_seconds: int,
    tone: str,
    audience: str,
    model: str,
    target_content_slides: int,
    feedback: Optional[str],
) -> dict:
    """Call LLM and return a strict plan dict."""
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise ImportError(
            "LLM runtime is unavailable in this environment. "
            "Run this command inside an agent environment that provides model access."
        ) from exc

    system_prompt = (
        "You are an expert presentation editor for short vertical videos. "
        "Return ONLY JSON. No prose."
    )

    user_prompt = f"""
Create a concise video slide plan from this markdown.

Hard constraints:
- Target duration: {duration_seconds} seconds total narration.
- Tone: {tone}
- Audience: {audience}
- Visual style keyword: {style_name}
- Content slide count target: about {target_content_slides} slides.
- Do not include title/closing slides in output; they are added by pipeline.
- Each slide must be easy to read on mobile vertical video.
- body_md should be concise markdown bullets or short paragraph.
- narration should sound natural spoken Chinese and stay aligned with body_md.

Return JSON schema:
{{
  "outline": ["..."] ,
  "slides": [
    {{"title": "...", "body_md": "...", "narration": "..."}}
  ]
}}

Markdown source:
---
Title: {title}
---
{markdown}
""".strip()

    if feedback:
        user_prompt += "\n\nRevision feedback:\n" + feedback

    client = OpenAI()
    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    output_text = getattr(response, "output_text", None)
    if not output_text:
        # Backward-compatible fallback across SDK variants.
        output_text = str(response)

    return _extract_first_json_object(output_text)


def _validate_plan(plan: dict) -> list[dict]:
    """Validate and normalize slide list from LLM output."""
    slides = plan.get("slides")
    if not isinstance(slides, list) or not slides:
        raise ValueError("LLM plan must include non-empty 'slides' array")

    normalized: list[dict] = []
    for i, slide in enumerate(slides):
        if not isinstance(slide, dict):
            raise ValueError(f"Slide #{i+1} is not an object")

        title = str(slide.get("title", "")).strip()
        body_md = str(slide.get("body_md", "")).strip()
        narration = str(slide.get("narration", "")).strip()

        if not title:
            raise ValueError(f"Slide #{i+1} missing title")
        if not body_md:
            raise ValueError(f"Slide #{i+1} missing body_md")
        if not narration:
            raise ValueError(f"Slide #{i+1} missing narration")

        normalized.append({"title": title, "body_md": body_md, "narration": narration})

    return normalized


def _build_slidev_markdown(title: str, style_name: str, content_slides: list[dict]) -> str:
    """Build slides.md content for Slidev."""
    theme = _THEME_MAP.get(style_name, "default")

    parts: list[str] = [
        "---",
        f"theme: {theme}",
        "aspectRatio: 9/16",
        "canvasWidth: 1080",
        "title: Generated Video Slides",
        "---",
        "",
        "layout: center",
        "class: text-center",
        "---",
        "",
        f"# {title}",
    ]

    for slide in content_slides:
        parts.extend(
            [
                "",
                "---",
                "",
                f"## {slide['title']}",
                "",
                slide["body_md"],
            ]
        )

    parts.extend(
        [
            "",
            "---",
            "",
            "layout: center",
            "class: text-center",
            "---",
            "",
            "# Thank You",
        ]
    )

    return "\n".join(parts).strip() + "\n"


def generate_slidev_content(
    md_content: str,
    *,
    style_name: str,
    duration_seconds: int,
    tone: str,
    audience: str,
    provided_title: Optional[str] = None,
    model: Optional[str] = None,
    max_attempts: int = 3,
    llm_plan_override: Optional[dict] = None,
) -> tuple[list[Scene], str, dict]:
    """Generate scenes + Slidev markdown via LLM planning."""
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be > 0")

    meta, body = _strip_frontmatter(md_content)
    title, body = _extract_title(meta, body, provided_title)

    model_name = model or os.environ.get("VIDEO_LLM_MODEL", "gpt-5-mini")
    target_content_slides = max(3, min(20, round(duration_seconds / 8)))

    feedback: Optional[str] = None
    selected_plan: Optional[dict] = None
    selected_slides: Optional[list[dict]] = None

    for attempt in range(1, max_attempts + 1):
        plan = llm_plan_override or _call_planner_llm(
            title=title,
            markdown=body,
            style_name=style_name,
            duration_seconds=duration_seconds,
            tone=tone,
            audience=audience,
            model=model_name,
            target_content_slides=target_content_slides,
            feedback=feedback,
        )

        content_slides = _validate_plan(plan)

        scenes: list[Scene] = [
            Scene(title=title, body="", narration=title, scene_type="title")
        ]
        for item in content_slides:
            scenes.append(
                Scene(
                    title=item["title"],
                    body=item["body_md"],
                    narration=item["narration"],
                    scene_type="content",
                )
            )
        closing_text = "感谢观看" if any("\u4e00" <= c <= "\u9fff" for c in title) else "Thank you"
        scenes.append(Scene(title=closing_text, body=title, narration=closing_text, scene_type="closing"))

        est_seconds = sum(_estimate_narration_seconds(scene.narration) for scene in scenes)
        tolerance = max(6.0, duration_seconds * 0.12)
        if abs(est_seconds - duration_seconds) <= tolerance:
            selected_plan = plan
            selected_slides = content_slides
            break

        delta = est_seconds - duration_seconds
        direction = "shorter" if delta > 0 else "longer"
        feedback = (
            f"Estimated narration duration is {est_seconds:.1f}s, target is {duration_seconds}s. "
            f"Revise to be {abs(delta):.1f}s {direction} overall while keeping key ideas."
        )

        if llm_plan_override is not None:
            # In tests with override we cannot iterate meaningfully.
            selected_plan = plan
            selected_slides = content_slides
            break

    if selected_plan is None or selected_slides is None:
        raise RuntimeError(
            f"LLM could not satisfy duration target ({duration_seconds}s) within {max_attempts} attempts"
        )

    slides_md = _build_slidev_markdown(title, style_name, selected_slides)

    scenes_out: list[Scene] = [Scene(title=title, body="", narration=title, scene_type="title")]
    for item in selected_slides:
        scenes_out.append(
            Scene(
                title=item["title"],
                body=item["body_md"],
                narration=item["narration"],
                scene_type="content",
            )
        )
    closing_text = "感谢观看" if any("\u4e00" <= c <= "\u9fff" for c in title) else "Thank you"
    scenes_out.append(Scene(title=closing_text, body=title, narration=closing_text, scene_type="closing"))

    metadata = {
        "title": title,
        "outline": selected_plan.get("outline", []),
        "model": model_name,
        "target_duration_seconds": duration_seconds,
        "estimated_duration_seconds": round(
            sum(_estimate_narration_seconds(scene.narration) for scene in scenes_out), 2
        ),
    }

    return scenes_out, slides_md, metadata


def split_md_to_scenes(
    md_content: str,
    *,
    style_name: str,
    duration_seconds: int,
    tone: str,
    audience: str,
    provided_title: Optional[str] = None,
    model: Optional[str] = None,
) -> list[Scene]:
    """Backward-compatible wrapper returning scenes only."""
    scenes, _, _ = generate_slidev_content(
        md_content,
        style_name=style_name,
        duration_seconds=duration_seconds,
        tone=tone,
        audience=audience,
        provided_title=provided_title,
        model=model,
    )
    return scenes


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate Slidev deck + narration scenes from markdown via LLM")
    parser.add_argument("md", help="Path to markdown file")
    parser.add_argument("--style", required=True)
    parser.add_argument("--duration", required=True, type=int)
    parser.add_argument("--tone", required=True)
    parser.add_argument("--audience", required=True)
    parser.add_argument("--out", default="slides.md", help="Output slides.md path")
    args = parser.parse_args()

    with open(args.md, "r", encoding="utf-8") as f:
        content = f.read()

    scenes, slides_md, meta = generate_slidev_content(
        content,
        style_name=args.style,
        duration_seconds=args.duration,
        tone=args.tone,
        audience=args.audience,
    )

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(slides_md)

    print(json.dumps(meta, ensure_ascii=False, indent=2))
    print(f"Generated {len(scenes)} scenes -> {args.out}")
