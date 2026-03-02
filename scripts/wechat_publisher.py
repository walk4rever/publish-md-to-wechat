import urllib.request
import json
import re
import os
import sys
import ssl
import argparse

# Disable SSL verification for broader environment compatibility
ssl._create_default_https_context = ssl._create_unverified_context

class WeChatPublisher:
    # Styles inherited and adapted from frontend-slides project
    STYLES = {
        "swiss": {
            "bg": "#ffffff", "accent": "#e62e2e", "text": "#000000", "secondary": "#666666",
            "font": "Helvetica, Arial, sans-serif", "border_width": "8px"
        },
        "terminal": {
            "bg": "#0d1117", "accent": "#39d353", "text": "#e6edf3", "secondary": "#8b949e",
            "font": "JetBrains Mono, Menlo, Monaco, Courier New, monospace", "border_width": "4px"
        },
        "bold": {
            "bg": "#1a1a1a", "accent": "#FF5722", "text": "#ffffff", "secondary": "#999999",
            "font": "Archivo Black, Impact, sans-serif", "border_width": "10px"
        },
        "botanical": {
            "bg": "#0f0f0f", "accent": "#d4a574", "text": "#e8e4df", "secondary": "#9a9590",
            "font": "Cormorant, Georgia, serif", "border_width": "2px"
        },
        "notebook": {
            "bg": "#f8f6f1", "accent": "#98d4bb", "text": "#1a1a1a", "secondary": "#555555",
            "font": "Bodoni Moda, serif", "border_width": "4px"
        },
        "cyber": {
            "bg": "#0a0f1c", "accent": "#00ffcc", "text": "#ffffff", "secondary": "#9ca3af",
            "font": "Clash Display, sans-serif", "border_width": "4px"
        },
        "voltage": {
            "bg": "#0066ff", "accent": "#d4ff00", "text": "#ffffff", "secondary": "#e0e0e0",
            "font": "Syne, sans-serif", "border_width": "6px"
        },
        "geometry": {
            "bg": "#faf9f7", "accent": "#f0b4d4", "text": "#1a1a1a", "secondary": "#5a7c6a",
            "font": "Plus Jakarta Sans, sans-serif", "border_width": "4px"
        },
        "editorial": {
            "bg": "#f5f3ee", "accent": "#1a1a1a", "text": "#1a1a1a", "secondary": "#555555",
            "font": "Fraunces, serif", "border_width": "2px"
        },
        "ink": {
            "bg": "#faf9f7", "accent": "#c41e3a", "text": "#1a1a1a", "secondary": "#444444",
            "font": "Cormorant Garamond, serif", "border_width": "1px"
        }
    }

    def __init__(self, app_id, app_secret):
        self.app_id = app_id
        self.app_secret = app_secret
        self.access_token = self._get_access_token()

    def _get_access_token(self):
        url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={self.app_id}&secret={self.app_secret}"
        try:
            with urllib.request.urlopen(url) as response:
                data = json.loads(response.read().decode())
                if "access_token" in data:
                    return data["access_token"]
                raise Exception(f"Failed to get token: {data}")
        except Exception as e:
            print(f"Auth Error: {e}")
            sys.exit(1)

    def upload_thumb(self, img_path):
        url = f"https://api.weixin.qq.com/cgi-bin/material/add_material?access_token={self.access_token}&type=thumb"
        boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
        with open(img_path, "rb") as f:
            img_data = f.read()
        filename = os.path.basename(img_path)
        parts = []
        parts.append(f"--{boundary}".encode())
        parts.append(f'Content-Disposition: form-data; name="media"; filename="{filename}"'.encode())
        parts.append(b'Content-Type: image/png')
        parts.append(b"")
        parts.append(img_data)
        parts.append(f"--{boundary}--".encode())
        parts.append(b"")
        body = b"\r\n".join(parts)
        req = urllib.request.Request(url, data=body)
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            return data.get("media_id")

    def convert_md_to_html(self, md_content, style_name="swiss"):
        style = self.STYLES.get(style_name, self.STYLES["swiss"])
        
        # Pre-cleaning
        content = md_content
        content = re.sub(r'^---+\s*$', '', content, flags=re.M)
        content = re.sub(r'\*\*(.*?)\*\*', f'<strong style="font-weight: bold; color: {style["accent"] if style_name in ["terminal", "cyber"] else "inherit"};">\\1</strong>', content)
        content = re.sub(r'`(.*?)`', f'<code style="background: {"rgba(255,255,255,0.1)" if style["bg"] != "#ffffff" else "#f0f0f0"}; padding: 2px 4px; font-size: 13px; border-radius: 3px;">\\1</code>', content)
        
        lines = content.split('\n')
        html_sections = []
        i = 0
        in_table = False
        
        while i < len(lines):
            line = lines[i].strip()
            if not line: 
                i += 1; continue
            
            if line.startswith('# '):
                html_sections.append(f'<section style="margin-bottom: 40px; border-bottom: {style["border_width"]} solid {style["text"] if style_name != "voltage" else "#fff"}; padding-bottom: 15px;"><h1 style="font-size: 32px; font-weight: 900; line-height: 1.1; margin: 0; text-transform: uppercase;">{line[2:]}</h1></section>')
            elif line.startswith('## '):
                html_sections.append(f'<section style="margin-top: 50px; margin-bottom: 20px; border-top: 2px solid {style["text"]}; padding-top: 15px;"><span style="color: {style["accent"]}; font-size: 20px; font-weight: 800; text-transform: uppercase;">{line[3:]}</span></section>')
            elif line.startswith('### '):
                html_sections.append(f'<section style="margin-top: 25px; margin-bottom: 10px; border-left: 4px solid {style["accent"]}; padding-left: 10px;"><span style="font-size: 18px; font-weight: bold;">{line[4:]}</span></section>')
            elif line.startswith('> '):
                html_sections.append(f'<section style="margin: 20px 0; padding: 20px; border: 1px solid {style["secondary"]}; background-color: {"rgba(255,255,255,0.05)" if style["bg"] != "#ffffff" else "#f6f6f6"};"><p style="color: {style["secondary"]}; font-size: 15px; line-height: 1.6; margin: 0;">{line[2:]}</p></section>')
            elif line.startswith('|'):
                if not in_table:
                    html_sections.append(f'<section style="margin: 25px 0; overflow-x: auto;"><table style="border-collapse: collapse; width: 100%; border: 2px solid {style["text"]}; background-color: {style["bg"]};">')
                    in_table = True
                    is_header = True
                    while i < len(lines) and lines[i].strip().startswith('|'):
                        curr_line = lines[i].strip()
                        if '---' in curr_line: i += 1; continue
                        cells = [c.strip() for c in curr_line.split('|') if c.strip()]
                        html_sections.append('<tr>')
                        for cell in cells:
                            bg = style["text"] if is_header else "transparent"
                            color = style["bg"] if is_header else style["text"]
                            html_sections.append(f'<td style="border: 1px solid {style["secondary"]}; padding: 10px; font-size: 13px; background-color: {bg}; color: {color}; font-weight: {"bold" if is_header else "normal"};">{cell}</td>')
                        html_sections.append('</tr>')
                        is_header = False
                        i += 1
                    html_sections.append('</table></section>')
                    in_table = False
                    i -= 1
            elif line.startswith('* '):
                html_sections.append(f'<section style="margin: 10px 0; display: flex; align-items: flex-start;"><span style="color: {style["accent"]}; font-weight: bold; margin-right: 10px; font-size: 18px; line-height: 1;">■</span><span style="font-size: 15px; line-height: 1.6;">{line[2:]}</span></section>')
            elif not line.startswith('<'):
                html_sections.append(f'<p style="font-size: 16px; line-height: 1.8; margin: 15px 0;">{line}</p>')
            else:
                html_sections.append(line)
            i += 1
        
        header = f'<section style="background-color: {style["bg"]}; padding: 25px 15px; font-family: {style["font"]}; color: {style["text"]};">'
        footer = f'<section style="margin-top: 60px; text-align: center; border-top: 5px solid {style["text"]}; padding-top: 25px; font-size: 14px; font-weight: 900; letter-spacing: 2px; text-transform: uppercase;">PUBLISHED VIA AGENT SKILL | STYLE: {style_name.upper()}</section></section>'
        return header + '\n'.join(html_sections) + footer

    def create_draft(self, title, html_content, thumb_id):
        url = f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={self.access_token}"
        data = {
            "articles": [{
                "title": title,
                "author": "Agent",
                "digest": "Automatically published from Markdown via Agent Skill.",
                "content": html_content,
                "thumb_media_id": thumb_id,
                "need_open_comment": 1
            }]
        }
        json_data = json.dumps(data, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(url, data=json_data, method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())

def main():
    parser = argparse.ArgumentParser(description="Publish MD to WeChat Drafts with Frontend Slides Styles")
    parser.add_argument("--id", required=True, help="WeChat AppID")
    parser.add_argument("--secret", required=True, help="WeChat AppSecret")
    parser.add_argument("--md", required=True, help="Path to MD file")
    parser.add_argument("--thumb", help="Path to thumb image (optional, will auto-generate if missing)")
    parser.add_argument("--style", default="swiss", choices=["swiss", "terminal", "bold", "botanical", "notebook", "cyber", "voltage", "geometry", "editorial", "ink"])
    parser.add_argument("--title", help="Article Title")
    
    args = parser.parse_args()
    
    with open(args.md, "r", encoding="utf-8") as f:
        md_content = f.read()
    
    title_match = re.search(r'^# (.*)$', md_content, re.M)
    title = args.title or (title_match.group(1) if title_match else "Untitled Article")

    # Intelligent Thumb Handling
    thumb_path = args.thumb
    if not thumb_path:
        print(f"No thumb provided. Auto-generating branded PNG cover for style: {args.style}...")
        script_dir = os.path.dirname(os.path.abspath(__file__))
        gen_script = os.path.join(script_dir, "generate_cover.py")
        auto_thumb = "assets/auto_cover.png"
        
        # Command to generate cover based on style and title
        os.system(f'python3 "{gen_script}" --title "{title}" --style "{args.style}" --output "{auto_thumb}"')
        
        if os.path.exists(auto_thumb):
            thumb_path = auto_thumb
        else:
            thumb_path = "assets/default_thumb.png"
            print(f"Generation failed. Falling back to default: {thumb_path}")

    publisher = WeChatPublisher(args.id, args.secret)
    thumb_id = publisher.upload_thumb(thumb_path)
    
    html = publisher.convert_md_to_html(md_content, args.style)
    
    result = publisher.create_draft(title, html, thumb_id)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
