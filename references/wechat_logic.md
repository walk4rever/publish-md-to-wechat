# WeChat Publishing Logic Reference

## Authentication
Uses client_credential flow to get Access Token. 
- Endpoint: `https://api.weixin.qq.com/cgi-bin/token`
- Requirement: IP Whitelist must be configured.

## Material Upload
Images must be uploaded as "thumb" type to get `thumb_media_id`.
- Endpoint: `https://api.weixin.qq.com/cgi-bin/material/add_material`
- Type: `thumb`

## Draft Creation
The final HTML content is pushed to the Draft Box.
- Endpoint: `https://api.weixin.qq.com/cgi-bin/draft/add`

## Layout Strategy
Since WeChat filters most CSS, this skill uses:
- `<section>` tags for containers.
- Inline styles for all colors, fonts, and spacing.
- Tables with explicit background colors to override theme-specific rendering.
- Manual line-by-line block parsing to prevent empty containers.
