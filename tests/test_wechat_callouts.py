#!/usr/bin/env python3
"""
Tests for the Obsidian-style callout rendering in wechat_publisher.py.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import mistune
from styles import BUILTIN_STYLES
from wechat_publisher import WeChatRenderer


def render(markdown_text, style_name="swiss"):
    renderer = WeChatRenderer(BUILTIN_STYLES[style_name], style_name)
    md = mistune.create_markdown(renderer=renderer, plugins=['strikethrough', 'table'])
    return md(markdown_text)


class TestHighlightsCallout(unittest.TestCase):
    def test_highlights_uses_gold_border_and_red_label(self):
        html = render("> [!HIGHLIGHTS] 核心看点\n> 这是重点内容")

        self.assertIn("border-top: 6px solid #d4a017", html)
        self.assertIn("color: #dc2626", html)
        self.assertIn(">Highlights<", html)
        self.assertIn("核心看点", html)
        self.assertIn("这是重点内容", html)

    def test_highlights_falls_back_to_default_title(self):
        html = render("> [!HIGHLIGHTS]\n>\n> 无标题内容")

        self.assertIn("高光金句", html)
        self.assertIn("无标题内容", html)

    def test_existing_callout_type_still_works(self):
        html = render("> [!TIPS] 知识点\n> 提示内容")

        self.assertIn("border-left: 6px solid #1e88e5", html)
        self.assertIn(">Tips<", html)


if __name__ == "__main__":
    unittest.main()
