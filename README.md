# Publish MD to WeChat Skill | 微信公众号 Markdown 极速发布

**Current Version: v0.1.0**

[English](#english) | [中文](#chinese)

---

<a name="english"></a>
## English

A specialized AI Agent skill to bridge the gap between Markdown and WeChat Official Account publishing.

### Core Features
- **Zero-Dependency Core**: Pure Python implementation that works in any environment.
- **Agent-Ready Design**: Optimized for CLI tools and AI agents (Claude Code, Cursor, Gemini CLI).
- **10+ Professional Styles**: Visual presets inherited from `frontend-slides`.
- **Auto Cover Generation**: Dynamically creates a branded PNG cover based on your title and selected style.
- **Native Compatibility**: Uses `section` tags and inline CSS for maximum reliability in WeChat.

### Getting Started
1. Get your `AppID` and `AppSecret` from the [WeChat Admin Console](https://mp.weixin.qq.com).
2. Add your current IP to the **Whitelist**.
3. Use your favorite Agent to run the command described in `SKILL.md`.

### Roadmap (Next Steps)
- [ ] **Image Auto-Slicing**: Support for long images by automatic slicing to bypass WeChat size limits.
- [ ] **Local Rendering Engine**: Integrated `Pillow` support for offline cover generation.
- [ ] **Interactive Style Preview**: Command to generate a local HTML preview before pushing.
- [ ] **Multi-Platform Support**: Extending the engine to support Zhihu and Juejin.

### Credits
Special thanks to the **[frontend-slides](https://github.com/walk4rever/frontend-slides)** project for the design DNA.

---

<a name="chinese"></a>
## 中文

专门为 AI Agent 打造的微信公众号 Markdown 发布技能。

### 核心功能
- **零依赖核心**：纯 Python 实现，无需安装复杂库，在任何受限环境下都能运行。
- **Agent 优先设计**：专门为 Claude Code、Cursor、Gemini CLI 等 AI 驱动工具优化。
- **10+ 专业风格**：继承自 `frontend-slides` 的精美预设（Swiss, Cyber, Botanical 等）。
- **封面自动生成**：若未提供封面图，系统将根据标题和所选风格，自动生成一张高颜值的品牌标题卡 (PNG)。
- **原生兼容性**：利用微信支持的 `section` 标签和 100% 内联 CSS，确保排版不走样。

### 快速开始
1. 从 [微信公众平台](https://mp.weixin.qq.com) 获取你的 `AppID` 和 `AppSecret`。
2. 将你当前的服务器/本地 IP 添加到 **IP 白名单**。
3. 参考 `SKILL.md` 中的指令，让你的 AI Agent 自动完成转换与推送。

### 下一步优化计划
- [ ] **长图自动切片**：支持超长内容自动切分为多张图片，解决微信加载限制。
- [ ] **本地绘图引擎集成**：增加 `Pillow` 驱动，支持在无网络环境下生成更复杂的封面。
- [ ] **本地交互预览**：支持在推送前生成一个本地 HTML 预览文件进行效果确认。
- [ ] **多平台矩阵**：扩展引擎以支持知乎、掘金等平台的自动同步。

### 致谢
本项目中的所有视觉预设均改编自 **[frontend-slides](https://github.com/walk4rever/frontend-slides)** 项目，致以诚挚感谢。

---
*Developed by **Air7.fun**. Open-source under MIT.*
