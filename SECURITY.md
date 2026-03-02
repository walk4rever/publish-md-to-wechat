# Security Policy | 安全策略

## Reporting Security Vulnerabilities | 报告安全漏洞

If you discover a security vulnerability, please report it by opening an issue. We appreciate your help in keeping this project secure.

---

## Security Design | 安全设计

### Credential Handling | 凭据处理

This project handles sensitive credentials (WeChat AppID and AppSecret). Here's how we protect them:

#### 1. Environment Variables Support | 环境变量支持

Credentials can be provided via:
- **Command line arguments**: `--id`, `--secret`
- **Environment variables**: `WECHAT_APP_ID`, `WECHAT_APP_SECRET`

```bash
# Recommended: Use environment variables
export WECHAT_APP_ID="your_app_id"
export WECHAT_APP_SECRET="your_app_secret"

python3 scripts/wechat_publisher.py --md article.md
```

**Priority**: Command line args > Environment variables

#### 2. No Credential Logging | 不记录凭据

The script never logs or exposes credentials:
- AppID is only shown partially (first 8 characters) in initialization messages
- AppSecret is never displayed in any output
- Access tokens are not logged

#### 3. Best Practices | 最佳实践

- **Never commit credentials** to version control
- Use environment variables in production
- Rotate credentials periodically
- Use minimum required permissions for the WeChat account

---

### SSL/TLS Configuration | SSL/TLS 配置

#### Why SSL Verification is Disabled by Default | 为什么默认关闭 SSL 验证

⚠️ **This is intentional and documented.**

The script disables SSL verification (`verify_ssl=False`) by default for these reasons:

1. **Corporate Proxy Compatibility**: Many enterprise networks use transparent proxies with self-signed certificates
2. **Development Environments**: Local development often involves localhost or self-signed certs
3. **Maximum Compatibility**: Ensures the tool works across diverse network environments

#### When to Enable SSL Verification | 何时启用 SSL 验证

In production environments with proper CA-signed certificates:

```bash
python3 scripts/wechat_publisher.py --verify-ssl --id ... --secret ... --md ...
```

**Recommended Production Configuration**:
- Use `--verify-ssl` flag
- Ensure your server has proper CA certificates installed
- Use environment variables instead of command line args to avoid credential exposure in process lists

#### Security Trade-off | 安全权衡

| Scenario | SSL Setting | Rationale |
|----------|-------------|-----------|
| Development/Local | Disabled (default) | Self-signed certs, proxy issues |
| Corporate Network | Disabled | Proxy with MITM certs |
| Production/Cloud | **Enabled** (`--verify-ssl`) | Proper CA certificates |

---

### Network Security | 网络安全

- **Only connects to WeChat API**: `api.weixin.qq.com`
- **No third-party analytics**: No external tracking or telemetry
- **Timeouts**: 30s for API calls, 60s for file uploads
- **No persistent storage**: Credentials are not stored

---

### File System Access | 文件系统访问

The script only accesses:
- **Read**: Markdown files, image files (thumbnails)
- **Write**: Temporary auto-generated covers (`assets/auto_cover.png`)
- **No sensitive data** is written to disk

---

## Vulnerability Disclosure | 漏洞披露

1. Do not report security vulnerabilities through public issues
2. Email the maintainer directly (see GitHub profile)
3. Include detailed reproduction steps
4. We aim to respond within 48 hours

---

## Compliance | 合规

- **No PII collected**: The script does not collect any personal information
- **WeChat API only**: All data stays within WeChat's ecosystem
- **No external dependencies with network access** (except WeChat API)

---

## Changelog | 更新日志

### v0.2.0
- Added environment variable support (`WECHAT_APP_ID`, `WECHAT_APP_SECRET`)
- Added `.socket` configuration file documenting security design
- Updated README with SSL bypass explanation

---

*Last updated: 2026-03-03*