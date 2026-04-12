#!/usr/bin/env python3
"""Unit tests for video generation core modules (no external services)."""

import gzip
import json
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from md_splitter import split_md_to_scenes
from slide_renderer import render_slides_html
from volcengine_tts import _parse_tts_frame


class TestMarkdownSplitter(unittest.TestCase):
    def test_split_adds_title_and_closing_scene(self):
        md = """---
title: 测试文章
author: Rafael
---

## 第一部分
这是第一段。

## 第二部分
这是第二段。"""
        scenes = split_md_to_scenes(md)
        self.assertGreaterEqual(len(scenes), 4)
        self.assertEqual(scenes[0].scene_type, "title")
        self.assertEqual(scenes[-1].scene_type, "closing")
        self.assertIn("测试文章", scenes[0].title)

    def test_long_section_is_split(self):
        paragraph = "这是一段用于测试切分的文字。" * 20
        md = f"## 长章节\n\n{paragraph}\n\n{paragraph}"
        scenes = split_md_to_scenes(md)
        content_scenes = [s for s in scenes if s.scene_type == "content"]
        self.assertGreaterEqual(len(content_scenes), 2)


class TestSlideRenderer(unittest.TestCase):
    def test_render_contains_slide_markup(self):
        md = "# 标题\n\n## 小节\n内容"
        scenes = split_md_to_scenes(md)
        html = render_slides_html(scenes, "swiss")
        self.assertIn("class=\"slide title-slide\"", html)
        self.assertIn("class=\"slide content-slide\"", html)
        self.assertIn("class=\"slide closing-slide\"", html)


class TestVolcengineFrameParser(unittest.TestCase):
    def test_parse_audio_frame_done(self):
        # Build a synthetic audio-only frame matching parser assumptions.
        header = bytes([0x11, 0xB0, 0x11, 0x00])  # v1, message_type=0x0B
        seq = struct.pack(">i", -1)  # negative => last chunk
        payload = b"FAKEAUDIO"
        payload_size = struct.pack(">I", len(payload))
        frame = header + seq + payload_size + payload

        parsed = _parse_tts_frame(frame)
        self.assertEqual(parsed["audio"], payload)
        self.assertTrue(parsed["done"])
        self.assertIsNone(parsed["error"])

    def test_parse_error_frame(self):
        header = bytes([0x11, 0xF0, 0x11, 0x00])  # message_type=0x0F (error)
        error_obj = {"code": 123, "message": "bad request"}
        payload = gzip.compress(json.dumps(error_obj).encode("utf-8"))
        # Current parser expects error frames as:
        # [header][error_code(int32)][payload_size(uint32)][payload]
        error_code = struct.pack(">i", error_obj["code"])
        payload_size = struct.pack(">I", len(payload))
        frame = header + error_code + payload_size + payload

        parsed = _parse_tts_frame(frame)
        self.assertIsNotNone(parsed["error"])
        self.assertTrue(parsed["done"])


if __name__ == "__main__":
    unittest.main()
