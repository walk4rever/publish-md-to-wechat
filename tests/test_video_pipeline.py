#!/usr/bin/env python3
"""Unit tests for video generation core modules (no external services)."""

import gzip
import json
import os
import struct
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from md_splitter import generate_slidev_content
from volcengine_tts import _parse_tts_frame, load_tts_config


class TestLLMSlidePlanner(unittest.TestCase):
    def test_generate_slidev_content_structure(self):
        md = """---
title: 测试文章
author: Rafael
---

## 第一部分
这是第一段。

## 第二部分
这是第二段。"""

        plan = {
            "outline": ["第一部分", "第二部分"],
            "slides": [
                {
                    "title": "项目概览",
                    "body_md": "- 目标\n- 核心问题",
                    "narration": "这部分介绍项目目标和核心问题。",
                },
                {
                    "title": "关键结论",
                    "body_md": "- 结论一\n- 结论二",
                    "narration": "这部分给出两个关键结论。",
                },
            ],
        }

        scenes, slides_md, meta = generate_slidev_content(
            md,
            style_name="swiss",
            duration_seconds=60,
            tone="专业",
            audience="产品经理",
            llm_plan_override=plan,
        )

        self.assertEqual(scenes[0].scene_type, "title")
        self.assertEqual(scenes[-1].scene_type, "closing")
        self.assertEqual(len(scenes), 4)
        self.assertIn("# 测试文章", slides_md)
        self.assertIn("## 项目概览", slides_md)
        self.assertIn("## 关键结论", slides_md)
        self.assertIn("theme: seriph", slides_md)
        self.assertIn("estimated_duration_seconds", meta)


class TestVolcengineFrameParser(unittest.TestCase):
    def test_parse_audio_frame_done(self):
        header = bytes([0x11, 0xB0, 0x11, 0x00])
        seq = struct.pack(">i", -1)
        reserved = struct.pack(">I", 0)
        payload = b"FAKEAUDIO"
        payload_size = struct.pack(">I", len(payload))
        frame = header + seq + reserved + payload_size + payload

        parsed = _parse_tts_frame(frame)
        self.assertEqual(parsed["audio"], payload)
        self.assertTrue(parsed["done"])
        self.assertIsNone(parsed["error"])

    def test_parse_audio_ack_frame_not_done(self):
        header = bytes([0x11, 0xB0, 0x11, 0x00])
        seq = struct.pack(">i", 0)
        reserved = struct.pack(">I", 0)
        frame = header + seq + reserved

        parsed = _parse_tts_frame(frame)
        self.assertIsNone(parsed["audio"])
        self.assertFalse(parsed["done"])
        self.assertIsNone(parsed["error"])

    def test_parse_error_frame(self):
        header = bytes([0x11, 0xF0, 0x11, 0x00])
        error_obj = {"code": 123, "message": "bad request"}
        payload = gzip.compress(json.dumps(error_obj).encode("utf-8"))
        error_code = struct.pack(">i", error_obj["code"])
        payload_size = struct.pack(">I", len(payload))
        frame = header + error_code + payload_size + payload

        parsed = _parse_tts_frame(frame)
        self.assertIsNotNone(parsed["error"])
        self.assertTrue(parsed["done"])


class TestVolcengineConfig(unittest.TestCase):
    def test_load_tts_config_verify_ssl_false(self):
        with mock.patch.dict(os.environ, {
            "VOLCANO_TTS_APPID": "test-appid",
            "VOLCANO_TTS_ACCESS_TOKEN": "test-token",
            "VOLCANO_TTS_VERIFY_SSL": "0",
        }, clear=True):
            config = load_tts_config()
            self.assertFalse(config.verify_ssl)


if __name__ == "__main__":
    unittest.main()
