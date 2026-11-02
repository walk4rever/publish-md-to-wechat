"""swiss 样式 h3 无红竖线；图片正下方的整段斜体按图注渲染（不套引用框）。

回归来源：2026-11-02 OA 博客批次，用户目检微信草稿发现
①swiss h3 带 border-left 红竖线；②斜体图注被整段斜体=引用框规则误伤。
"""
import unittest

from scripts.wechat_publisher import WeChatRenderer


STYLE = {
    "accent": "#e62e2e",
    "text": "#1a1a1a",
    "secondary": "#555555",
    "bg": "#ffffff",
    "border_width": "3px",
}


def render(md_text):
    import mistune
    renderer = WeChatRenderer(STYLE, "swiss")
    md = mistune.Markdown(renderer)
    return md(md_text)


class TestSwissHeadingNoBorder(unittest.TestCase):
    def test_h2_no_border_left(self):
        html = render("## 二级标题")
        self.assertNotIn("border-left", html)

    def test_h3_no_border_left(self):
        html = render("### 三级标题")
        self.assertNotIn("border-left", html)
        self.assertIn("font-size: 19px", html)


class TestImageCaption(unittest.TestCase):
    def test_italic_paragraph_after_image_is_caption(self):
        html = render("![alt](https://example.com/a.png)\n\n*图 01 · 架构图（静态帧）*")
        self.assertIn("text-align: center", html)
        self.assertNotIn("border-left", html)
        self.assertIn("图 01 · 架构图（静态帧）", html)

    def test_italic_paragraph_not_after_image_stays_quote_box(self):
        html = render("前言段落。\n\n*这是一句斜体引文*")
        self.assertIn("border-left", html)

    def test_heading_between_resets_caption_detection(self):
        html = render("![alt](https://example.com/a.png)\n\n## 章节\n\n*斜体段落*")
        # 图片与斜体段之间隔了标题 → 斜体段仍是引用框
        self.assertIn("border-left", html)

    def test_normal_paragraph_after_image_not_caption(self):
        html = render("![alt](https://example.com/a.png)\n\n普通段落不居中。")
        self.assertNotIn("text-align: center; color: #888888", html)


if __name__ == "__main__":
    unittest.main()
