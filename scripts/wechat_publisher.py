#!/usr/bin/env python3
"""
WeChat Official Account Markdown Publisher
With Error Handling and Logging
"""

import urllib.request
import urllib.error
import json
import re
import os
import sys
import ssl
import argparse
import logging
import urllib.parse
from datetime import datetime

try:
    import mistune
except ImportError:
    # We will handle the error if mistune is missing later in the process
    mistune = None

# ============================================================
# WeChat HTML Renderer (AST-based)
# ============================================================

class WeChatRenderer(mistune.HTMLRenderer):
    """Custom renderer for WeChat compatible HTML with inline styles."""
    
    def __init__(self, style, style_name):
        super().__init__()
        self.style = style
        self.style_name = style_name

    def heading(self, text, level):
        s = self.style
        if level == 1:
            return (f'<section style="margin-bottom: 40px; border-bottom: {s["border_width"]} '
                    f'solid {s["text"] if self.style_name != "voltage" else "#fff"}; padding-bottom: 15px;">'
                    f'<h1 style="font-size: 32px; font-weight: 900; line-height: 1.1; margin: 0; '
                    f'text-transform: uppercase;">{text}</h1></section>\n')
        elif level == 2:
            return (f'<section style="margin-top: 50px; margin-bottom: 20px; border-top: 2px solid {s["text"]}; '
                    f'padding-top: 15px;"><span style="color: {s["accent"]}; font-size: 20px; '
                    f'font-weight: 800; text-transform: uppercase;">{text}</span></section>\n')
        elif level == 3:
            return (f'<section style="margin-top: 25px; margin-bottom: 10px; border-left: 4px solid {s["accent"]}; '
                    f'padding-left: 10px;"><span style="font-size: 18px; font-weight: bold;">{text}</span></section>\n')
        return f'<h{level} style="margin: 20px 0; font-weight: bold;">{text}</h{level}>\n'

    def paragraph(self, text):
        return f'<p style="font-size: 16px; line-height: 1.8; margin: 15px 0;">{text}</p>\n'

    def block_quote(self, text):
        s = self.style
        bg = "rgba(255,255,255,0.05)" if s["bg"] != "#ffffff" else "#f6f6f6"
        return (f'<section style="margin: 20px 0; padding: 20px; border: 1px solid {s["secondary"]}; '
                f'background-color: {bg}; border-left: 4px solid {s["accent"]};">'
                f'<section style="color: {s["secondary"]}; font-size: 15px; line-height: 1.6;">{text}</section></section>\n')

    def block_code(self, code, info=None):
        s = self.style
        bg = "rgba(255,255,255,0.05)" if s["bg"] != "#ffffff" else "#f6f6f6"
        border_color = s["accent"] if self.style_name in ["terminal", "cyber"] else s["secondary"]
        escaped_code = code.replace('<', '&lt;').replace('>', '&gt;')
        return (f'<section style="margin: 20px 0; padding: 15px; background-color: {bg}; '
                f'border: 1px solid {border_color}; border-radius: 4px; overflow-x: auto;">'
                f'<pre style="margin: 0; font-family: {s["font"]}; font-size: 14px; line-height: 1.5; '
                f'color: {s["text"]}; white-space: pre;">{escaped_code}</pre></section>\n')

    def list(self, text, ordered, **kwargs):
        return f'<section style="margin: 15px 0;">{text}</section>\n'

    def list_item(self, text, **kwargs):
        s = self.style
        return (f'<section style="margin: 10px 0; display: flex; align-items: flex-start;">'
                f'<span style="color: {s["accent"]}; font-weight: bold; margin-right: 10px; '
                f'font-size: 18px; line-height: 1.2;">■</span>'
                f'<section style="font-size: 15px; line-height: 1.6;">{text}</section></section>\n')

    def strong(self, text):
        s = self.style
        color = s["accent"] if self.style_name in ["terminal", "cyber"] else "inherit"
        return f'<strong style="font-weight: bold; color: {color};">{text}</strong>'

    def codespan(self, text):
        s = self.style
        bg = "rgba(255,255,255,0.1)" if s["bg"] != "#ffffff" else "#f0f0f0"
        return f'<code style="background: {bg}; padding: 2px 4px; font-size: 13px; border-radius: 3px;">{text}</code>'

    def table(self, text):
        s = self.style
        return (f'<section style="margin: 25px 0; overflow-x: auto;">'
                f'<table style="border-collapse: collapse; width: 100%; border: 2px solid {s["text"]}; '
                f'background-color: {s["bg"]};">{text}</table></section>\n')

    def table_head(self, text):
        return f'<thead style="background-color: {self.style["text"]}; color: {self.style["bg"]};">{text}</thead>\n'

    def table_body(self, text):
        return f'<tbody>{text}</tbody>\n'

    def table_row(self, text):
        return f'<tr>{text}</tr>\n'

    def table_cell(self, text, align=None, head=False):
        s = self.style
        tag = 'th' if head else 'td'
        return f'<{tag} style="border: 1px solid {s["secondary"]}; padding: 10px; font-size: 13px;">{text}</{tag}>'

    def image(self, text, url, alt="", **kwargs):
        # mistune 3.x uses 'url' as the keyword for the image source
        caption = alt or text
        
        # Suppress technical filenames or Obsidian placeholders from being displayed as captions
        if caption and (caption.startswith('Pasted image') or re.search(r'\.(png|jpg|jpeg|gif|webp)$', caption, re.I)):
            caption = ""
            
        return (f'<section style="margin: 25px 0; text-align: center;">'
                f'<img src="{url}" alt="{alt}" style="max-width: 100%; border-radius: 8px; '
                f'box-shadow: 0 4px 15px rgba(0,0,0,0.1); display: block; margin: 0 auto;">'
                f'{f"<p style=\"color: #888; font-size: 13px; margin-top: 10px;\">{caption}</p>" if caption else ""}'
                f'</section>\n')

# ============================================================
# Logging Configuration
# ============================================================

def setup_logging(verbose: bool = False) -> logging.Logger:
    """Setup logging with console handler."""
    logger = logging.getLogger("WeChatPublisher")
    
    # Set log level
    level = logging.DEBUG if verbose else logging.INFO
    logger.setLevel(level)
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Console handler with colored output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    
    logger.addHandler(console_handler)
    return logger

# Global logger (initialized in main)
logger = None

# ============================================================
# SSL Configuration
# ============================================================

def configure_ssl(verify: bool = True):
    """Configure SSL context based on verify flag."""
    if verify:
        ssl._create_default_https_context()
    else:
        logger.warning("SSL verification disabled - use only for development")
        ssl._create_default_https_context = ssl._create_unverified_context


# ============================================================
# Custom Exceptions
# ============================================================

class WeChatPublisherError(Exception):
    """Base exception for WeChatPublisher."""
    pass

class AuthError(WeChatPublisherError):
    """Authentication failed."""
    pass

class UploadError(WeChatPublisherError):
    """File upload failed."""
    pass

class DraftError(WeChatPublisherError):
    """Draft creation failed."""
    pass

class ValidationError(WeChatPublisherError):
    """Input validation failed."""
    pass


# ============================================================
# Main Publisher Class
# ============================================================

class WeChatPublisher:
    """WeChat Official Account Markdown Publisher with error handling."""
    
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

    def __init__(self, app_id: str, app_secret: str, verify_ssl: bool = False):
        """Initialize publisher with app credentials."""
        global logger
        
        # Validate inputs
        if not app_id or not app_secret:
            raise ValidationError("AppID and AppSecret are required")
        
        self.app_id = app_id
        self.app_secret = app_secret
        self.verify_ssl = verify_ssl
        
        # Configure SSL
        configure_ssl(verify_ssl)
        
        logger.info(f"Initializing WeChat Publisher for AppID: {app_id[:8]}...")
        
        # Get access token
        self.access_token = self._get_access_token()
        logger.info("✓ Successfully obtained access token")

    def _get_access_token(self) -> str:
        """Get WeChat API access token."""
        url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={self.app_id}&secret={self.app_secret}"
        
        logger.debug(f"Requesting access token from: {url.split('?')[0]}")
        
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'WeChatPublisher/1.0'})
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode())
                
                if "access_token" in data:
                    expires_in = data.get("expires_in", 7200)
                    logger.debug(f"Access token expires in {expires_in}s")
                    return data["access_token"]
                
                # Handle WeChat error codes
                errcode = data.get("errcode")
                errmsg = data.get("errmsg", "Unknown error")
                
                if errcode == 40164:
                    raise AuthError(f"IP not whitelisted. Add your server IP to WeChat console. Error: {errmsg}")
                elif errcode == 40125:
                    raise AuthError(f"Invalid AppID or AppSecret. Please check your credentials. Error: {errmsg}")
                elif errcode == 40013:
                    raise AuthError(f"Invalid AppID. Please verify in WeChat admin console. Error: {errmsg}")
                else:
                    raise AuthError(f"Failed to get access token. Error {errcode}: {errmsg}")
                    
        except urllib.error.URLError as e:
            logger.error(f"Network error: {e.reason}")
            raise AuthError(f"Network error while getting access token: {e.reason}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response: {e}")
            raise AuthError(f"Invalid response from WeChat API: {e}")

    def upload_thumb(self, img_path: str) -> str:
        """Upload thumbnail image to WeChat and return media_id."""
        logger.info(f"Uploading thumbnail: {img_path}")
        
        # Validate file exists
        if not os.path.exists(img_path):
            raise UploadError(f"Thumbnail file not found: {img_path}")
        
        # Validate file size (WeChat limit: 2MB)
        file_size = os.path.getsize(img_path)
        if file_size > 2 * 1024 * 1024:
            raise UploadError(f"Image too large ({file_size / 1024 / 1024:.1f}MB). Must be under 2MB.")
        
        # Validate file extension
        ext = os.path.splitext(img_path)[1].lower()
        if ext not in ['.png', '.jpg', '.jpeg', '.gif']:
            raise UploadError(f"Unsupported image format: {ext}. Use PNG, JPG, or GIF.")
        
        url = f"https://api.weixin.qq.com/cgi-bin/material/add_material?access_token={self.access_token}&type=thumb"
        
        boundary = "----WeChatPublisherBoundary"
        
        try:
            with open(img_path, "rb") as f:
                img_data = f.read()
            
            filename = os.path.basename(img_path)
            
            parts = [
                f"--{boundary}".encode(),
                f'Content-Disposition: form-data; name="media"; filename="{filename}"'.encode(),
                b'Content-Type: image/png',
                b"",
                img_data,
                f"--{boundary}--".encode(),
                b""
            ]
            
            body = b"\r\n".join(parts)
            req = urllib.request.Request(url, data=body)
            req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
            req.add_header("User-Agent", "WeChatPublisher/1.0")
            
            with urllib.request.urlopen(req, timeout=60) as response:
                data = json.loads(response.read().decode())
                
                if "media_id" in data:
                    logger.info(f"✓ Thumbnail uploaded successfully, media_id: {data['media_id'][:16]}...")
                    return data["media_id"]
                
                errcode = data.get("errcode")
                errmsg = data.get("errmsg", "Unknown error")
                raise UploadError(f"Failed to upload thumbnail. Error {errcode}: {errmsg}")
                
        except urllib.error.HTTPError as e:
            logger.error(f"HTTP error during upload: {e.code} {e.reason}")
            raise UploadError(f"HTTP error: {e.code} {e.reason}")
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            raise UploadError(f"Failed to upload thumbnail: {e}")

    def upload_image(self, img_path: str) -> str:
        """Upload image to WeChat and return permanent URL for use in articles."""
        logger.info(f"Uploading image to WeChat: {img_path}")
        
        # Validate file size (WeChat limit: 2MB)
        if os.path.getsize(img_path) > 2 * 1024 * 1024:
            raise UploadError(f"Image too large (>2MB): {img_path}")
        
        url = f"https://api.weixin.qq.com/cgi-bin/media/uploadimg?access_token={self.access_token}"
        
        boundary = "----WeChatPublisherBoundary"
        with open(img_path, "rb") as f:
            img_data = f.read()
        
        filename = os.path.basename(img_path)
        ext = filename.split('.')[-1].lower()
        mime_type = "image/png" if ext == "png" else "image/jpeg"
        
        parts = [
            f"--{boundary}".encode(),
            f'Content-Disposition: form-data; name="media"; filename="{filename}"'.encode(),
            f'Content-Type: {mime_type}'.encode(),
            b"",
            img_data,
            f"--{boundary}--".encode(),
            b""
        ]
        body = b"\r\n".join(parts)
        
        req = urllib.request.Request(url, data=body)
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        req.add_header("User-Agent", "WeChatPublisher/1.0")
        
        try:
            with urllib.request.urlopen(req, context=ssl._create_unverified_context()) as response:
                res_data = json.loads(response.read().decode())
                if "url" in res_data:
                    logger.info(f"✓ Image uploaded: {res_data['url']}")
                    return res_data["url"]
                else:
                    raise UploadError(f"Failed to get URL: {res_data}")
        except Exception as e:
            logger.error(f"Image upload failed: {e}")
            raise UploadError(f"Failed to upload image: {e}")

    def convert_md_to_html(self, md_content: str, style_name: str = "swiss") -> str:
        """Convert Markdown to WeChat-compatible HTML using mistune."""
        logger.debug(f"Converting Markdown to HTML with style: {style_name}")
        
        # Check if mistune is available
        if mistune is None:
            logger.error("mistune library not found. Please run ./install.sh")
            raise ValidationError("Missing dependency: mistune. Please install it first.")

        # 1. Pre-process: Convert Obsidian WikiLink ![[img.png]] to standard MD ![img](<img.png>)
        processed_md = re.sub(r'!\[\[(.*?)\]\]', r'![\1](<\1>)', md_content)

        # Validate style
        if style_name not in self.STYLES:
            logger.warning(f"Unknown style '{style_name}', using 'swiss'")
            style_name = "swiss"
        
        style = self.STYLES[style_name]
        
        # Initialize mistune with custom renderer
        renderer = WeChatRenderer(style, style_name)
        markdown = mistune.create_markdown(
            renderer=renderer,
            plugins=['strikethrough', 'table']
        )
        
        # Convert content
        main_html = markdown(processed_md)
        
        # 2. Post-process: Upload local images and replace URLs
        img_tags = re.findall(r'<img src="(.*?)"', main_html)
        
        # Determine base directory for searching (where the MD is)
        md_path = sys.argv[-1] if len(sys.argv) > 1 else ""
        # Get absolute path of the MD file relative to the CURRENT working directory
        if md_path and not os.path.isabs(md_path):
            md_path = os.path.join(os.getcwd(), md_path)
            
        md_dir = os.path.dirname(os.path.abspath(md_path)) if md_path else os.getcwd()
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        for local_path in img_tags:
            if local_path.startswith(('http://', 'https://')):
                continue
            
            # Decode URL (e.g., %20 -> space) and unescape HTML entities
            local_path_decoded = urllib.parse.unquote(local_path)
            filename = os.path.basename(local_path_decoded)
                
            # Recursive search for the file
            found_path = None
            
            # Search order:
            # 1. MD directory and its subdirectories
            # 2. Project root and its subdirectories
            search_bases = [md_dir, project_root]
            
            logger.info(f"Searching for image '{filename}'...")
            
            for base in search_bases:
                if found_path: break
                logger.debug(f"  Searching in: {base}")
                for root, dirs, files in os.walk(base):
                    if filename in files:
                        found_path = os.path.join(root, filename)
                        break
            
            if found_path:
                try:
                    wechat_url = self.upload_image(found_path)
                    main_html = main_html.replace(f'src="{local_path}"', f'src="{wechat_url}"')
                except Exception as e:
                    logger.warning(f"Failed to upload image {found_path}: {e}")
            else:
                logger.warning(f"Image '{filename}' not found in any search path.")
        
        # Wrap with global container
        header = f'<section style="background-color: {style["bg"]}; padding: 25px 15px; font-family: {style["font"]}; color: {style["text"]};">'
        footer = (f'<section style="margin-top: 60px; text-align: center; border-top: 5px solid {style["text"]}; '
                 f'padding-top: 25px; font-size: 14px; font-weight: 900; letter-spacing: 2px; '
                 f'text-transform: uppercase;">PUBLISHED VIA AGENT SKILL | STYLE: {style_name.upper()}</section></section>')
        
        return header + main_html + footer

    def create_draft(self, title: str, html_content: str, thumb_id: str) -> dict:
        """Create a draft in WeChat Official Account."""
        logger.info(f"Creating draft: {title}")
        
        # Validate inputs
        if not title or not title.strip():
            raise DraftError("Title cannot be empty")
        
        if not html_content:
            raise DraftError("HTML content cannot be empty")
        
        if not thumb_id:
            raise DraftError("Thumbnail media_id is required")
        
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
        
        try:
            json_data = json.dumps(data, ensure_ascii=False).encode('utf-8')
            req = urllib.request.Request(url, data=json_data, method="POST")
            req.add_header("Content-Type", "application/json")
            req.add_header("User-Agent", "WeChatPublisher/1.0")
            
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode())
                
                if "media_id" in result:
                    logger.info(f"✓ Draft created successfully! media_id: {result['media_id']}")
                    return result
                
                errcode = result.get("errcode")
                errmsg = result.get("errmsg", "Unknown error")
                raise DraftError(f"Failed to create draft. Error {errcode}: {errmsg}")
                
        except urllib.error.HTTPError as e:
            logger.error(f"HTTP error during draft creation: {e.code}")
            raise DraftError(f"HTTP error: {e.code} {e.reason}")


# ============================================================
# Main Entry Point
# ============================================================

def main():
    """Main entry point with error handling."""
    global logger
    
    parser = argparse.ArgumentParser(
        description="Publish MD to WeChat Drafts with Frontend Slides Styles",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Credentials - supports command line args or environment variables
    # Priority: command line args > environment variables
    parser.add_argument("--id", 
                       default=os.environ.get("WECHAT_APP_ID"),
                       help="WeChat AppID (or set WECHAT_APP_ID env var)")
    parser.add_argument("--secret", 
                       default=os.environ.get("WECHAT_APP_SECRET"),
                       help="WeChat AppSecret (or set WECHAT_APP_SECRET env var)")
    parser.add_argument("--md", required=True, help="Path to MD file")
    
    # Optional arguments
    parser.add_argument("--thumb", help="Path to thumb image (optional, will auto-generate if missing)")
    parser.add_argument("--style", default="swiss", 
                       choices=["swiss", "terminal", "bold", "botanical", "notebook", "cyber", "voltage", "geometry", "editorial", "ink"],
                       help="Style preset (default: swiss)")
    parser.add_argument("--title", help="Article Title (optional, auto-detect from MD)")
    parser.add_argument("--verify-ssl", action="store_true", default=False, 
                       help="Enable SSL verification (disabled by default)")
    parser.add_argument("-v", "--verbose", action="store_true", 
                       help="Enable verbose debug logging")
    
    args = parser.parse_args()
    
    # Validate credentials (from args or environment variables)
    app_id = args.id or os.environ.get("WECHAT_APP_ID")
    app_secret = args.secret or os.environ.get("WECHAT_APP_SECRET")
    
    if not app_id or not app_secret:
        parser.error("Credentials required. Use --id/--secret or set WECHAT_APP_ID/WECHAT_APP_SECRET environment variables.")
    
    # Setup logging
    logger = setup_logging(args.verbose)
    
    logger.info("=" * 50)
    logger.info("WeChat Markdown Publisher v1.0 (with Error Handling)")
    logger.info("=" * 50)
    
    try:
        # Validate MD file
        logger.info(f"Reading Markdown file: {args.md}")
        if not os.path.exists(args.md):
            raise ValidationError(f"Markdown file not found: {args.md}")
        
        with open(args.md, "r", encoding="utf-8") as f:
            md_content = f.read()
        
        if not md_content.strip():
            raise ValidationError("Markdown file is empty")
        
        # Extract title from MD or use provided
        title_match = re.search(r'^# (.*)$', md_content, re.M)
        title = args.title or (title_match.group(1) if title_match else "Untitled Article")
        logger.info(f"Article title: {title}")
        
        # Handle thumbnail
        thumb_path = args.thumb
        if not thumb_path:
            logger.info(f"No thumb provided. Auto-generating cover for style: {args.style}...")
            script_dir = os.path.dirname(os.path.abspath(__file__))
            gen_script = os.path.join(script_dir, "generate_cover.py")
            auto_thumb = os.path.join(os.path.dirname(script_dir), "assets", "auto_cover.png")
            
            # Clean up old auto_thumb if exists
            if os.path.exists(auto_thumb):
                os.remove(auto_thumb)
                logger.debug(f"Removed old thumbnail: {auto_thumb}")
            
            # Generate cover
            cmd = f'python3 "{gen_script}" --title "{title}" --style "{args.style}" --output "{auto_thumb}"'
            logger.debug(f"Running: {cmd}")
            result = os.system(cmd)
            
            if result == 0 and os.path.exists(auto_thumb):
                thumb_path = auto_thumb
                logger.info(f"✓ Auto-generated cover: {auto_thumb}")
            else:
                # If generation failed, check if we have a default thumb
                default_thumb = os.path.join(os.path.dirname(script_dir), "assets", "default_thumb.png")
                if os.path.exists(default_thumb):
                    thumb_path = default_thumb
                    logger.warning(f"Generation failed, using default thumbnail")
                else:
                    raise ValidationError("No thumbnail provided and auto-generation failed")
        
        # Initialize publisher
        logger.info("Initializing WeChat publisher...")
        publisher = WeChatPublisher(app_id, app_secret, args.verify_ssl)
        
        # Upload thumbnail
        thumb_id = publisher.upload_thumb(thumb_path)
        
        # Convert MD to HTML
        html = publisher.convert_md_to_html(md_content, args.style)
        logger.info(f"✓ Converted Markdown to HTML ({len(html)} bytes)")
        
        # Create draft
        result = publisher.create_draft(title, html, thumb_id)
        
        # Success
        logger.info("=" * 50)
        logger.info("🎉 Successfully published to WeChat Drafts!")
        logger.info(f"   media_id: {result.get('media_id')}")
        logger.info("=" * 50)
        
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
        
    except ValidationError as e:
        logger.error(f"Validation Error: {e}")
        logger.info("Run with --help for usage information")
        return 1
        
    except AuthError as e:
        logger.error(f"Authentication Error: {e}")
        logger.info("Please check your AppID and AppSecret, and ensure your IP is whitelisted")
        return 1
        
    except UploadError as e:
        logger.error(f"Upload Error: {e}")
        return 1
        
    except DraftError as e:
        logger.error(f"Draft Error: {e}")
        return 1
        
    except WeChatPublisherError as e:
        logger.error(f"Publisher Error: {e}")
        return 1
        
    except KeyboardInterrupt:
        logger.info("\n⚠ Cancelled by user")
        return 130
        
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        logger.info("Please run with -v flag for more details")
        return 1


if __name__ == "__main__":
    sys.exit(main())