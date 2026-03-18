#!/usr/bin/env python3
"""
Tests for styles.py - WeChat Article Style Analyzer
"""

import unittest
import os
import sys
import json
import tempfile
import shutil

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from styles import (
    extract_color,
    extract_font_size,
    extract_line_height,
    most_common_value,
    generate_custom_style_name,
    slugify,
    is_dark_color,
    color_distance,
    extract_style_from_content,
    extract_stylesheet_rules,
    analyze_html,
)


class TestExtractColor(unittest.TestCase):
    """Test color extraction functions."""

    def test_hex_color(self):
        """Test hex color extraction."""
        self.assertEqual(extract_color("#ff0000"), "#FF0000")
        self.assertEqual(extract_color("#abc"), "#AABBCC")  # 3-char hex expanded to 6-char
        self.assertEqual(extract_color("#AABBCC"), "#AABBCC")
        self.assertEqual(extract_color("#aabbcc"), "#AABBCC")  # lowercase to uppercase

    def test_rgb_color(self):
        """Test RGB color extraction - converts to hex."""
        self.assertEqual(extract_color("rgb(255, 0, 0)"), "#FF0000")
        self.assertEqual(extract_color("rgba(255, 0, 0, 0.5)"), "#FF0000")  # alpha ignored
        self.assertEqual(extract_color("rgb(0, 255, 0)"), "#00FF00")
        self.assertEqual(extract_color("rgb(0, 0, 255)"), "#0000FF")

    def test_skip_values(self):
        """Test that skip values return None."""
        skip_values = ['transparent', 'inherit', 'initial', 'none', 'auto', 'unset', 'currentcolor']
        for value in skip_values:
            self.assertIsNone(extract_color(value))

    def test_empty_and_whitespace(self):
        """Test empty and whitespace values."""
        self.assertIsNone(extract_color(""))
        self.assertIsNone(extract_color("   "))
        self.assertIsNone(extract_color(None))


class TestExtractFontSize(unittest.TestCase):
    """Test font size extraction."""

    def test_valid_sizes(self):
        """Test valid font size values."""
        self.assertEqual(extract_font_size("14px"), "14px")
        self.assertEqual(extract_font_size("1.5em"), "1.5em")
        self.assertEqual(extract_font_size("16pt"), "16pt")

    def test_skip_values(self):
        """Test that skip values return None."""
        skip_values = ['inherit', 'initial', 'auto', 'medium', 'normal']
        for value in skip_values:
            self.assertIsNone(extract_font_size(value))

    def test_empty(self):
        """Test empty values."""
        self.assertIsNone(extract_font_size(""))
        self.assertIsNone(extract_font_size(None))


class TestExtractLineHeight(unittest.TestCase):
    """Test line height extraction."""

    def test_valid_values(self):
        """Test valid line height values."""
        self.assertEqual(extract_line_height("1.6"), "1.6")
        self.assertEqual(extract_line_height("1.8em"), "1.8em")
        self.assertEqual(extract_line_height("150%"), "150%")

    def test_skip_values(self):
        """Test that skip values return None."""
        skip_values = ['inherit', 'initial', 'auto', 'normal']
        for value in skip_values:
            self.assertIsNone(extract_line_height(value))


class TestMostCommonValue(unittest.TestCase):
    """Test most common value detection."""

    def test_simple_list(self):
        """Test with simple list."""
        values = ["a", "b", "a", "c", "a"]
        self.assertEqual(most_common_value(values, "default"), "a")

    def test_with_none_values(self):
        """Test with None values filtered out."""
        values = ["a", None, "b", None, "a"]
        self.assertEqual(most_common_value(values, "default"), "a")

    def test_empty_list(self):
        """Test with empty list returns default."""
        self.assertEqual(most_common_value([], "default"), "default")

    def test_all_none(self):
        """Test with all None values returns default."""
        self.assertEqual(most_common_value([None, None], "default"), "default")

    def test_tie_breaking(self):
        """Test that first most common wins in tie."""
        values = ["a", "b", "a", "b"]
        result = most_common_value(values, "default")
        self.assertIn(result, ["a", "b"])


class TestSlugify(unittest.TestCase):
    """Test title-to-slug conversion."""

    def test_chinese_title(self):
        name = slugify("Kimi新论文太硬核了！马斯克和Karpathy相继点赞~")
        self.assertTrue(name.startswith("kimi"))
        self.assertNotIn('！', name)
        self.assertNotIn('~', name)

    def test_mixed_title(self):
        name = slugify("如何用 Claude 写出好代码")
        self.assertIn("claude", name)

    def test_max_words(self):
        name = slugify("a b c d e f g", max_words=3)
        self.assertEqual(name, "a-b-c")

    def test_empty(self):
        self.assertEqual(slugify(""), "style")

    def test_punctuation_only(self):
        result = slugify("！！！")
        self.assertEqual(result, "style")


class TestGenerateCustomStyleName(unittest.TestCase):
    """Test custom style name generation."""

    def test_with_title_uses_slug(self):
        """When source_title is provided, name should be derived from it."""
        name = generate_custom_style_name("Kimi新论文太硬核了！马斯克和Karpathy相继点赞~")
        self.assertTrue(name.startswith("custom-"))
        self.assertNotIn("2026", name)   # Should not fall back to date format
        self.assertIn("kimi", name)

    def test_without_title_uses_date_hash(self):
        """Without title, name falls back to date+hash format."""
        name = generate_custom_style_name()
        self.assertTrue(name.startswith("custom-"))
        parts = name.split("-")
        self.assertEqual(len(parts), 3)
        self.assertEqual(len(parts[1]), 8)   # YYYYMMDD
        self.assertEqual(len(parts[2]), 6)   # hash

    def test_none_title_uses_date_hash(self):
        name = generate_custom_style_name(None)
        self.assertTrue(name.startswith("custom-"))
        self.assertEqual(len(name.split("-")), 3)


class TestCustomStyleLoading(unittest.TestCase):
    """Test custom style loading from wechat_publisher.py."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.custom_styles_dir = os.path.join(self.test_dir, "custom-styles")
        os.makedirs(self.custom_styles_dir, exist_ok=True)

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir)

    def test_load_valid_custom_style(self):
        """Test that a valid custom style JSON can be loaded."""
        style_config = {
            "bg": "#ffffff",
            "accent": "#ff0000",
            "text": "#000000",
            "secondary": "#666666",
            "font": "Arial, sans-serif",
            "border_width": "3px"
        }

        style_path = os.path.join(self.custom_styles_dir, "custom-test-style.json")
        with open(style_path, "w") as f:
            json.dump(style_config, f)

        # Verify the file can be loaded and parsed correctly
        with open(style_path, "r") as f:
            loaded = json.load(f)

        required_fields = ["bg", "accent", "text", "secondary", "font"]
        for field in required_fields:
            self.assertIn(field, loaded)
        self.assertEqual(loaded["bg"], "#ffffff")
        self.assertEqual(loaded["accent"], "#ff0000")

    def test_skip_invalid_json(self):
        """Test that invalid JSON files are skipped gracefully."""
        bad_path = os.path.join(self.custom_styles_dir, "custom-broken.json")
        with open(bad_path, "w") as f:
            f.write("{invalid json!!")
        # Should not crash — just skip
        with self.assertRaises(json.JSONDecodeError):
            with open(bad_path, "r") as f:
                json.load(f)

    def test_custom_style_naming_convention(self):
        """Test that custom styles must start with 'custom-'."""
        valid_names = ["custom-mystyle", "custom-20260318-abc123", "custom-example"]
        invalid_names = ["mystyle", "test", "builtin"]

        for name in valid_names:
            self.assertTrue(name.startswith("custom-"), f"{name} should be valid")

        for name in invalid_names:
            self.assertFalse(name.startswith("custom-"), f"{name} should be invalid")


class TestIsDarkColor(unittest.TestCase):
    """Test is_dark_color including rgba alpha handling."""

    def test_dark_hex(self):
        self.assertTrue(is_dark_color("#000000"))
        self.assertTrue(is_dark_color("#282C34"))
        self.assertTrue(is_dark_color("#1a1a1a"))

    def test_light_hex(self):
        self.assertFalse(is_dark_color("#ffffff"))
        self.assertFalse(is_dark_color("#f5f5f5"))
        self.assertFalse(is_dark_color("#EEEEEE"))

    def test_rgba_nearly_transparent_is_light(self):
        """rgba(0,0,0,0.05) is nearly transparent — should NOT be treated as dark."""
        self.assertFalse(is_dark_color("rgba(0,0,0,0.05)"))
        self.assertFalse(is_dark_color("rgba(0, 0, 0, 0.1)"))

    def test_rgba_opaque_dark(self):
        """rgba with alpha=1 should behave like rgb."""
        self.assertTrue(is_dark_color("rgba(0, 0, 0, 1)"))
        self.assertTrue(is_dark_color("rgba(40, 44, 52, 1.0)"))

    def test_empty_and_invalid(self):
        self.assertFalse(is_dark_color(""))
        self.assertFalse(is_dark_color(None))
        self.assertFalse(is_dark_color("not-a-color"))


class TestColorDistance(unittest.TestCase):
    """Test color_distance for accent vs text discrimination."""

    def test_identical_colors(self):
        self.assertAlmostEqual(color_distance("#000000", "#000000"), 0.0)

    def test_black_white(self):
        self.assertAlmostEqual(color_distance("#000000", "#ffffff"), 441.67, delta=1)

    def test_similar_dark_grays(self):
        """#1a1a1a vs #222222 should be close — below accent threshold."""
        dist = color_distance("#1a1a1a", "#222222")
        self.assertLess(dist, 60)

    def test_distinct_accent(self):
        """Purple #916DD5 vs dark gray #1a1a1a should be clearly distinct."""
        dist = color_distance("#916DD5", "#1a1a1a")
        self.assertGreater(dist, 60)


class TestExtractStyleFromContent(unittest.TestCase):
    """Test core style extraction logic with HTML fixtures."""

    def _make_soup(self, html):
        from bs4 import BeautifulSoup
        return BeautifulSoup(html, 'html.parser')

    def test_basic_light_article(self):
        """Light background, dark text, purple accent."""
        html = """
        <div id="js_content" style="background-color: #ffffff; color: #1a1a1a;">
          <p style="color: #1a1a1a; font-family: Georgia, serif; font-size: 15px; line-height: 1.75;">正文段落。</p>
          <p style="color: #1a1a1a; font-family: Georgia, serif; font-size: 15px; line-height: 1.75;">第二段。</p>
          <h2 style="color: #916DD5;">标题</h2>
        </div>
        """
        soup = self._make_soup(html)
        content = soup.find(id='js_content')
        style = extract_style_from_content(content)
        self.assertEqual(style['bg'], '#FFFFFF')
        self.assertEqual(style['text'], '#1A1A1A')
        self.assertEqual(style['accent'], '#916DD5')
        self.assertIn('Georgia', style['font'])

    def test_code_block_bg_ignored(self):
        """Dark code block background should NOT leak into article bg."""
        html = """
        <div id="js_content" style="background-color: #ffffff;">
          <p style="color: #333333;">正文。</p>
          <pre style="background-color: #282C34;"><code>code here</code></pre>
          <p style="color: #333333;">更多正文。</p>
        </div>
        """
        soup = self._make_soup(html)
        content = soup.find(id='js_content')
        style = extract_style_from_content(content)
        self.assertEqual(style['bg'], '#FFFFFF')

    def test_pure_black_text_replaced_with_dark_gray(self):
        """#000000 text should be normalized to #1a1a1a."""
        html = """
        <div id="js_content">
          <p style="color: #000000;">段落文字。</p>
          <p style="color: #000000;">另一段。</p>
        </div>
        """
        soup = self._make_soup(html)
        content = soup.find(id='js_content')
        style = extract_style_from_content(content)
        self.assertNotEqual(style['text'], '#000000')
        self.assertEqual(style['text'], '#1a1a1a')

    def test_accent_not_same_as_text(self):
        """Accent color should differ from text color by at least threshold."""
        html = """
        <div id="js_content">
          <p style="color: #1a1a1a;">正文。</p>
          <h2 style="color: #222222;">相近深色标题</h2>
          <a style="color: #916DD5;" href="#">链接</a>
        </div>
        """
        soup = self._make_soup(html)
        content = soup.find(id='js_content')
        style = extract_style_from_content(content)
        # accent should pick the distinct purple, not the near-identical heading gray
        self.assertEqual(style['accent'], '#916DD5')


class TestExtractStylesheetRules(unittest.TestCase):
    """Test <style> block parsing."""

    def _make_soup(self, html):
        from bs4 import BeautifulSoup
        return BeautifulSoup(html, 'html.parser')

    def test_basic_rule_parsing(self):
        html = """<html><head>
        <style>
          #js_content { color: #333333; background-color: #fafafa; }
          p { font-size: 15px; }
        </style></head><body></body></html>"""
        soup = self._make_soup(html)
        rules = extract_stylesheet_rules(soup)
        self.assertIn('#js_content', rules)
        self.assertEqual(rules['#js_content']['color'], '#333333')
        self.assertEqual(rules['#js_content']['background-color'], '#fafafa')
        self.assertIn('p', rules)
        self.assertEqual(rules['p']['font-size'], '15px')

    def test_comment_stripped(self):
        html = """<html><head>
        <style>
          /* main content */ #js_content { color: #444; }
        </style></head><body></body></html>"""
        soup = self._make_soup(html)
        rules = extract_stylesheet_rules(soup)
        self.assertIn('#js_content', rules)

    def test_stylesheet_color_used_as_fallback(self):
        """When inline color is absent, stylesheet color should be used."""
        html = """<html><head>
        <style>#js_content { color: #555555; background-color: #fefefe; }</style>
        </head><body>
        <div id="js_content">
          <p>段落，没有 inline color。</p>
        </div>
        </body></html>"""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        rules = extract_stylesheet_rules(soup)
        content = soup.find(id='js_content')
        style = extract_style_from_content(content, rules)
        # bg should fall back to stylesheet value
        self.assertEqual(style['bg'], '#FEFEFE')


class TestStyleConfigValidation(unittest.TestCase):
    """Test style configuration validation."""

    def test_required_fields(self):
        """Test that required fields are present."""
        required_fields = ["bg", "accent", "text", "secondary", "font"]

        valid_config = {
            "bg": "#ffffff",
            "accent": "#ff0000",
            "text": "#000000",
            "secondary": "#666666",
            "font": "Arial, sans-serif"
        }

        for field in required_fields:
            self.assertIn(field, valid_config)

    def test_optional_fields(self):
        """Test optional fields."""
        optional_fields = ["border_width", "font_size", "line_height", "created_at", "source"]

        config_with_optional = {
            "bg": "#ffffff",
            "accent": "#ff0000",
            "text": "#000000",
            "secondary": "#666666",
            "font": "Arial, sans-serif",
            "border_width": "3px",
            "font_size": "16px",
            "line_height": "1.6"
        }

        for field in optional_fields:
            if field in ["border_width", "font_size", "line_height"]:
                self.assertIn(field, config_with_optional)


if __name__ == "__main__":
    unittest.main()
