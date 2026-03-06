# Publish MD to WeChat Skill | 微信公众号 Markdown 极速发布

**Current Version: v0.2.0**

[English](#english) | [中文](#chinese)

---

<a name="english"></a>
## English

A specialized AI Agent skill to bridge the gap between Markdown and WeChat Official Account publishing.

### Core Features
- **AST-Powered Rendering**: Powered by `mistune` 3.x for 100% reliable conversion of complex Markdown (nested lists, tables, etc.).
- **Obsidian Ready**: Built-in support for `![[WikiLink]]` image syntax and automatic space handling.
- **Smart Image Upload**: Automatically searches local directories for images and replaces them with permanent WeChat URLs.
- **10+ Professional Styles**: Visual presets inherited from `frontend-slides`.
- **Auto Cover Generation**: Dynamically creates a branded PNG cover based on your title and selected style.

### Quick Start | 快速开始

1. **Initialize Environment**:
   ```bash
   ./install.sh
   ```
2. **Setup Credentials**: 
   ```bash
   cp .env.example .env
   # Edit .env and add your WECHAT_APP_ID and WECHAT_APP_SECRET
   ```
3. **Publish**:
   ```bash
   source .venv/bin/activate
   python3 scripts/wechat_publisher.py --md path/to/article.md --style botanical
   ```

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

### Environment Variables | 环境变量

You can provide credentials via a `.env` file (recommended) or shell environment variables:

```bash
# 1. Using .env file (recommended)
cp .env.example .env
# Edit .env and set your credentials

# 2. Using shell environment variables
export WECHAT_APP_ID="your_app_id"
export WECHAT_APP_SECRET="your_app_secret"

# Run without --id and --secret
python3 scripts/wechat_publisher.py --md path/to/article.md
```

| Variable | Description |
|----------|-------------|
| `WECHAT_APP_ID` | Your WeChat Official Account AppID |
| `WECHAT_APP_SECRET` | Your WeChat Official Account AppSecret |

**Priority**: Command line arguments (`--id`, `--secret`) > Environment variables

### SSL Verification | SSL 验证

⚠️ **SSL verification is DISABLED by default** for the following reasons:

1. **Corporate Networks**: Many corporate proxy environments use self-signed certificates
2. **Development/Testing**: Local development often uses localhost or test environments
3. **Compatibility**: Maximum compatibility across different network configurations

To enable strict SSL verification in production:

```bash
python3 scripts/wechat_publisher.py --verify-ssl --id ... --secret ... --md ...
```

**Security Note**: Only enable `--verify-ssl` when you trust the network path to WeChat servers. In most production deployments with proper CA certificates, this is recommended.

### Available Styles | 可用风格

Choose a style that matches your article's tone and content:

| Style | Vibe 风格 | Best For 适用场景 |
| :--- | :--- | :--- |
| `swiss` | Clean, high-contrast, professional 简洁高对比，专业 | Technical guides, reports 技术指南、报告 |
| `terminal` | Green text on dark, hacker aesthetic 暗黑终端，黑客风 | Dev tools, coding tips 开发工具、编程技巧 |
| `bold` | Vibrant cards on dark, high impact 暗黑霓虹，高冲击力 | Product launches, announcements 产品发布、公告 |
| `botanical` | Elegant, sophisticated, premium 优雅精致，高端 | Artistic pieces, luxury brands 艺术内容、轻奢品牌 |
| `notebook` | Cream paper with mint accents, tactile 奶油笔记本，薄荷点缀 | Study notes, diaries 学习笔记、日记 |
| `cyber` | Futuristic navy with cyan glow 未来科技感，霓虹蓝 | AI, tech, web3 topics AI、科技、Web3 |
| `voltage` | Electric blue with neon yellow 电压蓝，霓虹黄 | Energetic, creative pitches 活力创意演示 |
| `geometry` | Soft pastels with rounded cards 柔和粉彩，圆角卡片 | Friendly, approachable content 亲和力内容 |
| `editorial` | Witty, personality-driven, serif 智慧有个性，衬线体 | Opinions, blogs, personal brands 观点、博客、个人品牌 |
| `ink` | Warm cream with crimson, literary 暖奶油色，朱红点缀 | Storytelling, deep dives 故事叙述、深度内容 |

**Example | 示例**:
```bash
# Use Swiss style (default)
--style swiss

# Use Cyber style for tech articles
--style cyber

# Use Editorial for blog posts
--style editorial
```

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
- **AST 驱动渲染**：使用 `mistune` 3.x 深度解析，完美处理复杂 Markdown（嵌套列表、代码块、表格）。
- **Obsidian 友好**：原生支持 `![[WikiLink]]` 语法，并能自动处理含空格的文件名。
- **智能图片上传**：递归搜索本地目录，自动将本地图片上传至微信素材库并替换为永久 URL。
- **10+ 专业风格**：继承自 `frontend-slides` 的精美视觉预设（Swiss, Cyber, Botanical 等）。
- **封面自动生成**：系统将根据标题和风格，自动生成高清 PNG 品牌标题卡。

### 快速开始

1. **环境初始化**：
   ```bash
   ./install.sh
   ```
2. **配置凭证**：
   ```bash
   cp .env.example .env
   # 编辑 .env 文件，填入 WECHAT_APP_ID 和 WECHAT_APP_SECRET
   ```
3. **发布文章**：
   ```bash
   source .venv/bin/activate
   python3 scripts/wechat_publisher.py --md path/to/article.md --style botanical
   ```


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

### 环境变量 | Environment Variables

你可以通过 `.env` 文件（推荐）或系统环境变量提供凭证：

```bash
# 1. 使用 .env 文件 (推荐)
cp .env.example .env
# 编辑 .env 设置你的凭证

# 2. 使用 shell 环境变量
export WECHAT_APP_ID="your_app_id"
export WECHAT_APP_SECRET="your_app_secret"

# 运行时无需 --id 和 --secret
python3 scripts/wechat_publisher.py --md path/to/article.md
```


| 变量 | 说明 |
|------|------|
| `WECHAT_APP_ID` | 微信公众号 AppID |
| `WECHAT_APP_SECRET` | 微信公众号 AppSecret |

**优先级**：命令行参数 (`--id`, `--secret`) > 环境变量

### SSL 验证 | SSL Verification

⚠️ **SSL 验证默认关闭**，原因如下：

1. **企业网络**：很多企业代理环境使用自签名证书
2. **开发/测试**：本地开发环境通常使用 localhost 或测试环境
3. **兼容性**：确保在不同网络配置下的最大兼容性

在生产环境中启用严格的 SSL 验证：

```bash
python3 scripts/wechat_publisher.py --verify-ssl --id ... --secret ... --md ...
```

**安全提示**：只有在信任网络路径通往微信服务器时才启用 `--verify-ssl`。在大多数具有正确 CA 证书的生产部署中，建议启用此选项。

### 可用风格 | Available Styles

选择与文章风格和内容相匹配的样式：

| 风格 | Style | 适用场景 | Best For |
| :--- | :--- | :--- | :--- |
| `swiss` | Clean, high-contrast, professional 简洁高对比，专业 | 技术指南、报告 | Technical guides, reports |
| `terminal` | Green text on dark, hacker aesthetic 暗黑终端，黑客风 | 开发工具、编程技巧 | Dev tools, coding tips |
| `bold` | Vibrant cards on dark, high impact 暗黑霓虹，高冲击力 | 产品发布、公告 | Product launches, announcements |
| `botanical` | Elegant, sophisticated, premium 优雅精致，高端 | 艺术内容、轻奢品牌 | Artistic pieces, luxury brands |
| `notebook` | Cream paper with mint accents, tactile 奶油笔记本，薄荷点缀 | 学习笔记、日记 | Study notes, diaries |
| `cyber` | Futuristic navy with cyan glow 未来科技感，霓虹蓝 | AI、科技、Web3 | AI, tech, web3 topics |
| `voltage` | Electric blue with neon yellow 电压蓝，霓虹黄 | 活力创意演示 | Energetic, creative pitches |
| `geometry` | Soft pastels with rounded cards 柔和粉彩，圆角卡片 | 亲和力内容 | Friendly, approachable content |
| `editorial` | Witty, personality-driven, serif 智慧有个性，衬线体 | 观点、博客、个人品牌 | Opinions, blogs, personal brands |
| `ink` | Warm cream with crimson, literary 暖奶油色，朱红点缀 | 故事叙述、深度内容 | Storytelling, deep dives |

**示例 | Example**:
```bash
# 使用 Swiss 风格（默认）
--style swiss

# 科技文章使用 Cyber 风格
--style cyber

# 博客文章使用 Editorial 风格
--style editorial
```

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