# Publish MD to WeChat Skill | 微信公众号 Markdown 极速发布

**Current Version: v0.2.0**

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
- **Comprehensive Error Handling**: Clear error messages with actionable solutions.
- **Verbose Logging**: Debug mode with `-v` flag for troubleshooting.

### Getting Started
1. Get your `AppID` and `AppSecret` from the [WeChat Admin Console](https://mp.weixin.qq.com).
2. Add your current IP to the **Whitelist**.
3. Use your favorite Agent to run the command described in `SKILL.md`.

### Command Line Options

```bash
python3 scripts/wechat_publisher.py \
  --id YOUR_APP_ID \
  --secret YOUR_APP_SECRET \
  --md path/to/article.md \
  --thumb path/to/cover.png \
  --style swiss \
  --verify-ssl \
  -v  # Enable verbose logging
```

| Option | Description |
|--------|-------------|
| `--id` | WeChat AppID (required) |
| `--secret` | WeChat AppSecret (required) |
| `--md` | Path to Markdown file (required) |
| `--thumb` | Path to thumbnail image (optional, auto-generates if missing) |
| `--style` | Style preset: swiss, terminal, bold, botanical, notebook, cyber, voltage, geometry, editorial, ink (default: swiss) |
| `--title` | Article title (auto-detects from MD if omitted) |
| `--verify-ssl` | Enable SSL verification (disabled by default) |
| `-v, --verbose` | Enable verbose debug logging |

### Error Handling

The publisher provides clear error messages for common issues:

| Error | Cause | Solution |
|-------|-------|----------|
| `Validation Error: Markdown file not found` | MD file doesn't exist | Check file path |
| `Auth Error: IP not whitelisted` | Server IP not in whitelist | Add IP to WeChat console |
| `Auth Error: Invalid AppID` | Wrong credentials | Verify AppID and AppSecret |
| `Upload Error: Image too large` | File > 2MB | Compress or resize image |
| `Upload Error: Unsupported format` | Wrong image type | Use PNG, JPG, or GIF |

### Debug Mode

Use `-v` flag for detailed logging:
```bash
python3 scripts/wechat_publisher.py -v --id ... --secret ... --md ...
```

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
- **完善错误处理**：清晰的错误提示和可操作的解决方案。
- **详细日志**：使用 `-v` 参数启用调试模式。

### 快速开始
1. 从 [微信公众平台](https://mp.weixin.qq.com) 获取你的 `AppID` 和 `AppSecret`。
2. 将你当前的服务器/本地 IP 添加到 **IP 白名单**。
3. 参考 `SKILL.md` 中的指令，让你的 AI Agent 自动完成转换与推送。

### 命令行参数

```bash
python3 scripts/wechat_publisher.py \
  --id 你的APPID \
  --secret 你的APPSECRET \
  --md 文章.md \
  --thumb 封面.png \
  --style swiss \
  --verify-ssl \
  -v  # 启用详细日志
```

| 参数 | 说明 |
|------|------|
| `--id` | 微信公众号 AppID（必填） |
| `--secret` | 微信公众号 AppSecret（必填） |
| `--md` | Markdown 文件路径（必填） |
| `--thumb` | 封面图片路径（可选，不提供则自动生成） |
| `--style` | 风格预设：swiss, terminal, bold, botanical, notebook, cyber, voltage, geometry, editorial, ink（默认：swiss） |
| `--title` | 文章标题（省略则自动从 MD 检测） |
| `--verify-ssl` | 启用 SSL 验证（默认关闭） |
| `-v, --verbose` | 启用详细调试日志 |

### 错误处理

发布器为常见问题提供清晰的错误提示：

| 错误 | 原因 | 解决方案 |
|------|------|----------|
| `Validation Error: Markdown file not found` | 文件不存在 | 检查文件路径 |
| `Auth Error: IP not whitelisted` | IP 未在白名单 | 在微信后台添加 IP |
| `Auth Error: Invalid AppID` | 凭证错误 | 检查 AppID 和 AppSecret |
| `Upload Error: Image too large` | 图片超过 2MB | 压缩或缩小图片 |
| `Upload Error: Unsupported format` | 格式不支持 | 使用 PNG、JPG 或 GIF |

### 调试模式

使用 `-v` 参数查看详细日志：
```bash
python3 scripts/wechat_publisher.py -v --id ... --secret ... --md ...
```

### 下一步优化计划
- [ ] **长图自动切片**：支持超长内容自动切分为多张图片，解决微信加载限制。
- [ ] **本地绘图引擎集成**：增加 `Pillow` 驱动，支持在无网络环境下生成更复杂的封面。
- [ ] **本地交互预览**：支持在推送前生成一个本地 HTML 预览文件进行效果确认。
- [ ] **多平台矩阵**：扩展引擎以支持知乎、掘金等平台的自动同步。

### 致谢
本项目中的所有视觉预设均改编自 **[frontend-slides](https://github.com/walk4rever/frontend-slides)** 项目，致以诚挚感谢。

---
*Developed by **Air7.fun**. Open-source under MIT.*