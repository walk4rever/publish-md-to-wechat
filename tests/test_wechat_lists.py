#!/usr/bin/env python3

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


class TestWeChatListRendering(unittest.TestCase):
    def test_loose_list_items_keep_text_inline_with_bullet(self):
        html = render("- 粗略估算，大约 60 亿人几乎没接触过 LLM。\n\n- 第二条")

        self.assertIn('flex-shrink: 0;">•</span><span style="flex: 1; min-width: 0;', html)
        self.assertNotIn('<p', html)
        self.assertNotIn('<section style="flex: 1; min-width: 0;', html)

    def test_tight_list_items_use_inline_content(self):
        html = render("- 第一条\n- 第二条")

        self.assertIn('flex-shrink: 0;">•</span><span style="flex: 1; min-width: 0;', html)
        self.assertNotIn('<section style="flex: 1; min-width: 0;', html)

    def test_multiparagraph_list_item_preserves_block_content(self):
        html = render("- 第一段\n\n  第二段\n\n- 第二条")

        self.assertIn('<section style="flex: 1; min-width: 0;', html)
        self.assertIn('<p', html)


if __name__ == "__main__":
    unittest.main()
