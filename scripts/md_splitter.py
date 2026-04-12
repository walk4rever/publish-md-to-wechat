#!/usr/bin/env python3
"""
Markdown Splitter for Video Publisher

Splits a Markdown file into scenes suitable for video slides.
Each scene has a title, body content (for rendering), and narration text (for TTS).

Splitting strategy:
  1. Title slide: extracted from frontmatter/H1
  2. H2 headings create new scenes
  3. Long sections are split by paragraph density (max ~150 chars per slide)
"""

import re
import yaml
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Scene:
    """A single video slide scene."""
    title: str
    body: str  # Markdown body for rendering on slide
    narration: str  # Plain text for TTS
    scene_type: str = "content"  # "title", "content", "closing"


# Max characters per slide body before splitting
_MAX_BODY_CHARS = 200
# Max characters per narration segment (Volcengine TTS limit is ~1000)
_MAX_NARRATION_CHARS = 800


def _strip_frontmatter(md: str) -> tuple[dict, str]:
    """Remove YAML frontmatter, return (metadata, body)."""
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', md, re.DOTALL)
    if not match:
        return {}, md
    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        meta = {}
    body = md[match.end():]
    return meta, body


def _extract_title(meta: dict, body: str, provided_title: Optional[str] = None) -> tuple[str, str]:
    """Extract title and return (title, body_without_h1).

    Priority: provided_title > frontmatter title > first H1 > first line
    """
    if provided_title:
        return provided_title, body

    if meta.get("title"):
        return str(meta["title"]).strip(), body

    h1_match = re.match(r'^#\s+(.+)\s*\n', body)
    if h1_match:
        title = h1_match.group(1).strip()
        remaining = body[h1_match.end():]
        return title, remaining

    lines = [l.strip() for l in body.split('\n') if l.strip()]
    if lines:
        return lines[0], body
    return "Untitled", body


def _clean_for_narration(text: str) -> str:
    """Strip Markdown syntax to produce plain text for TTS."""
    # Remove images
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    text = re.sub(r'!\[\[.*?\]\]', '', text)
    # Remove links, keep text
    text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)
    # Remove bold/italic markers
    text = re.sub(r'\*{1,3}(.*?)\*{1,3}', r'\1', text)
    text = re.sub(r'_{1,3}(.*?)_{1,3}', r'\1', text)
    # Remove inline code
    text = re.sub(r'`([^`]*)`', r'\1', text)
    # Remove code blocks entirely (not good for narration)
    text = re.sub(r'```[\s\S]*?```', '', text)
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Remove heading markers
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Remove list markers
    text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
    # Remove blockquote markers
    text = re.sub(r'^\s*>\s*', '', text, flags=re.MULTILINE)
    # Collapse whitespace
    text = re.sub(r'\n{2,}', '\n', text)
    text = re.sub(r' {2,}', ' ', text)
    return text.strip()


def _clean_for_slide(text: str) -> str:
    """Clean markdown body for slide display — keep structure but remove images/code blocks."""
    # Remove images
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    text = re.sub(r'!\[\[.*?\]\]', '', text)
    # Remove code blocks (too detailed for video slides)
    text = re.sub(r'```[\s\S]*?```', '', text)
    # Collapse excessive blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _split_section_by_density(title: str, body: str) -> list[Scene]:
    """Split a long section into multiple scenes by paragraph density."""
    paragraphs = re.split(r'\n{2,}', body.strip())
    scenes: list[Scene] = []
    current_body_parts: list[str] = []
    current_char_count = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        para_len = len(para)

        # If adding this paragraph would exceed limit, flush current
        if current_body_parts and (current_char_count + para_len > _MAX_BODY_CHARS):
            slide_body = '\n\n'.join(current_body_parts)
            narration = _clean_for_narration(slide_body)
            if narration:
                scenes.append(Scene(
                    title=title,
                    body=_clean_for_slide(slide_body),
                    narration=narration,
                ))
            current_body_parts = []
            current_char_count = 0

        current_body_parts.append(para)
        current_char_count += para_len

    # Flush remaining
    if current_body_parts:
        slide_body = '\n\n'.join(current_body_parts)
        narration = _clean_for_narration(slide_body)
        if narration:
            scenes.append(Scene(
                title=title,
                body=_clean_for_slide(slide_body),
                narration=narration,
            ))

    return scenes


def split_md_to_scenes(
    md_content: str,
    provided_title: Optional[str] = None,
    author: Optional[str] = None,
) -> list[Scene]:
    """Split Markdown content into a list of Scenes for video generation.

    Returns:
        List of Scene objects, starting with a title scene and ending with a closing scene.
    """
    meta, body = _strip_frontmatter(md_content)
    title, body = _extract_title(meta, body, provided_title)
    author = author or meta.get("author", "")

    scenes: list[Scene] = []

    # Title slide
    description = meta.get("description", "")
    title_narration = title
    if description:
        title_narration = f"{title}。{description}"
    scenes.append(Scene(
        title=title,
        body=f"**{author}**" if author else "",
        narration=title_narration,
        scene_type="title",
    ))

    # Split body by H2 headings
    # Pattern: split on lines starting with ## (but not ### or more)
    sections = re.split(r'^(?=##\s+[^#])', body, flags=re.MULTILINE)

    for section in sections:
        section = section.strip()
        if not section:
            continue

        # Extract section heading
        heading_match = re.match(r'^##\s+(.+)\s*\n', section)
        if heading_match:
            section_title = heading_match.group(1).strip()
            section_body = section[heading_match.end():]
        else:
            # Content before first H2 (intro paragraph)
            section_title = ""
            section_body = section

        section_body = section_body.strip()
        if not section_body:
            # H2 with no content — skip
            continue

        # Check if section needs splitting
        clean_body = _clean_for_slide(section_body)
        if len(clean_body) > _MAX_BODY_CHARS:
            sub_scenes = _split_section_by_density(section_title, section_body)
            scenes.extend(sub_scenes)
        else:
            narration = _clean_for_narration(section_body)
            if section_title:
                narration = f"{section_title}。{narration}"
            if narration:
                scenes.append(Scene(
                    title=section_title,
                    body=clean_body,
                    narration=narration,
                ))

    # Closing slide
    closing_text = "感谢阅读" if any('\u4e00' <= c <= '\u9fff' for c in title) else "Thank you"
    scenes.append(Scene(
        title=closing_text,
        body=title,
        narration=closing_text,
        scene_type="closing",
    ))

    return scenes


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 md_splitter.py <markdown-file>")
        sys.exit(1)

    with open(sys.argv[1], 'r', encoding='utf-8') as f:
        content = f.read()

    for i, scene in enumerate(split_md_to_scenes(content)):
        print(f"\n{'='*60}")
        print(f"Scene {i+1} [{scene.scene_type}]")
        print(f"Title: {scene.title}")
        print(f"Body:\n{scene.body[:100]}...")
        print(f"Narration: {scene.narration[:100]}...")
