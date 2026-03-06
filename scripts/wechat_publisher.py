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
import hashlib
import time
from datetime import datetime
from typing import Optional, Any, Dict

try:
    from dotenv import load_dotenv
    # 1. Load from current working directory (User Project) - Priority: High
    load_dotenv()
    
    # 2. Load from global config (User Home) - Priority: Low
    global_config_dir = os.path.expanduser("~/.config/publish-md-to-wechat")
    global_env = os.path.join(global_config_dir, ".env")
    
    # Common typo fallback: .evn
    global_evn_typo = os.path.join(global_config_dir, ".evn")
    
    if os.path.exists(global_env):
        load_dotenv(global_env)
    elif os.path.exists(global_evn_typo):
        # Fallback for typo, but warn user
        print(f"Warning: Found configuration at '{global_evn_typo}'. Please rename it to '.env' for standard compliance.", file=sys.stderr)
        load_dotenv(global_evn_typo)
         
except ImportError:
    # Warn user if dotenv is missing (but continue, as env vars might be set in shell)
    print("Warning: python-dotenv not installed. .env files will not be loaded.", file=sys.stderr)
    pass

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
        # Simplified Swiss style for long articles
        if self.style_name == "swiss":
            if level == 1:
                return (f'<section style="margin: 30px 0 20px; text-align: left; border-bottom: {s["border_width"]} solid {s["accent"]}; padding-bottom: 10px;">'
                        f'<h1 style="font-size: 28px; font-weight: bold; color: {s["text"]}; margin: 0;">{text}</h1></section>\n')
            elif level == 2:
                return (f'<section style="margin: 35px 0 15px; border-top: 2px solid {s["text"]}; padding-top: 10px;">'
                        f'<h2 style="font-size: 22px; font-weight: bold; color: {s["text"]}; margin: 0;">{text}</h2></section>\n')
            elif level == 3:
                return (f'<section style="margin: 25px 0 10px; border-left: 4px solid {s["accent"]}; padding-left: 12px;">'
                        f'<h3 style="font-size: 19px; font-weight: bold; color: {s["text"]}; margin: 0;">{text}</h3></section>\n')
        
        # Original slide-like styles for other presets
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
        line_height = "1.75" if self.style_name == "swiss" else "1.8"
        font_size = "15px" if self.style_name == "swiss" else "16px"
        margin = "16px 0" if self.style_name == "swiss" else "15px 0"
        return f'<p style="font-size: {font_size}; line-height: {line_height}; margin: {margin}; color: {self.style["text"]};">{text}</p>\n'

    def block_quote(self, text):
        s = self.style
        if self.style_name == "swiss":
            return (f'<section style="margin: 25px 0; padding: 20px; background-color: #f9f9f9; '
                    f'border-left: 5px solid {s["accent"]}; color: {s["secondary"]}; font-size: 15px; line-height: 1.6;">'
                    f'{text}</section>\n')
        
        bg = "#f9f9f9" if s["bg"] == "#ffffff" else "rgba(255,255,255,0.05)"
        border_color = s["accent"]
        return (f'<section style="margin: 30px 0; padding: 25px; border: 1px solid #eeeeee; '
                f'background-color: {bg}; border-left: 6px solid {border_color}; border-radius: 4px;">'
                f'<section style="color: {s["text"]}; font-size: 15px; line-height: 1.8; '
                f'font-style: italic; opacity: 0.9;">{text}</section></section>\n')

    def block_code(self, code, info=None):
        s = self.style
        # Simplified code block for swiss
        if self.style_name == "swiss":
            escaped_code = code.replace('<', '&lt;').replace('>', '&gt;')
            return (f'<section style="margin: 20px 0; padding: 15px; background-color: #f6f6f6; '
                    f'border-radius: 4px; overflow-x: auto; border: 1px solid #eeeeee;">'
                    f'<pre style="margin: 0; font-family: {s["font"]}; font-size: 13px; line-height: 1.5; '
                    f'color: #333333; white-space: pre;">{escaped_code}</pre></section>\n')
        
        bg = "rgba(255,255,255,0.05)" if s["bg"] != "#ffffff" else "#f6f6f6"
        border_color = s["accent"] if self.style_name in ["terminal", "cyber"] else s["secondary"]
        escaped_code = code.replace('<', '&lt;').replace('>', '&gt;')
        return (f'<section style="margin: 20px 0; padding: 15px; background-color: {bg}; '
                f'border: 1px solid {border_color}; border-radius: 4px; overflow-x: auto;">'
                f'<pre style="margin: 0; font-family: {s["font"]}; font-size: 14px; line-height: 1.5; '
                f'color: {s["text"]}; white-space: pre;">{escaped_code}</pre></section>\n')

    def list(self, text, ordered, **kwargs):
        margin = "16px 0" if self.style_name == "swiss" else "15px 0"
        return f'<section style="margin: {margin};">{text}</section>\n'

    def list_item(self, text, **kwargs):
        s = self.style
        bullet = "•" if self.style_name == "swiss" else "■"
        bullet_size = "18px"
        margin_right = "8px"
        
        return (f'<section style="margin: 8px 0; display: flex; align-items: flex-start;">'
                f'<span style="color: {s["accent"]}; font-weight: bold; margin-right: {margin_right}; '
                f'font-size: {bullet_size}; line-height: 1.2;">{bullet}</span>'
                f'<section style="font-size: 15px; line-height: 1.6; color: {s["text"]};">{text}</section></section>\n')

    def strong(self, text):
        s = self.style
        color = s["accent"] if self.style_name in ["terminal", "cyber"] else "inherit"
        return f'<strong style="font-weight: bold; color: {color};">{text}</strong>'

    def codespan(self, text):
        s = self.style
        if self.style_name == "swiss":
            return f'<code style="background: #f3f3f3; padding: 2px 4px; font-size: 13px; border-radius: 3px; color: {s["accent"]}; font-family: {s["font"]};">{text}</code>'
        bg = "rgba(255,255,255,0.1)" if s["bg"] != "#ffffff" else "#f0f0f0"
        return f'<code style="background: {bg}; padding: 2px 4px; font-size: 13px; border-radius: 3px;">{text}</code>'

    def table(self, text):
        s = self.style
        border_color = "#dddddd" if self.style_name == "swiss" else s["text"]
        return (f'<section style="margin: 25px 0; overflow-x: auto; -webkit-overflow-scrolling: touch;">'
                f'<table style="border-collapse: collapse; width: 100%; border: 1px solid {border_color}; '
                f'background-color: {s["bg"]}; font-size: 14px;">{text}</table></section>\n')

    def table_head(self, text):
        s = self.style
        bg = "#f2f2f2" if self.style_name == "swiss" else s["text"]
        color = s["text"] if self.style_name == "swiss" else s["bg"]
        return f'<thead style="background-color: {bg}; color: {color}; font-weight: bold;">{text}</thead>\n'

    def table_body(self, text):
        # We can't easily do nth-child in inline CSS for WeChat, 
        # but mistune 3.x table_row doesn't give us the index.
        # We will keep it simple with white background for all rows or 
        # handle it in a post-processing step if really needed.
        return f'<tbody>{text}</tbody>\n'

    def table_row(self, text):
        return f'<tr style="border-bottom: 1px solid #eeeeee;">{text}</tr>\n'

    def table_cell(self, text, align=None, head=False):
        s = self.style
        tag = 'th' if head else 'td'
        border = "#dddddd" if self.style_name == "swiss" else s["secondary"]
        padding = "12px 10px" if head else "10px"
        return f'<{tag} style="border: 1px solid {border}; padding: {padding}; text-align: {align or "left"};">{text}</{tag}>'

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
        ssl._create_default_https_context = ssl.create_default_context
    else:
        logger.warning("SSL verification disabled - use only for development")
        ssl._create_default_https_context = ssl._create_unverified_context


def _get_cache_dir() -> str:
    if sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Caches")
    else:
        base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    path = os.path.join(base, "publish-md-to-wechat")
    os.makedirs(path, exist_ok=True)
    return path


def _read_json_file(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception:
        return None


def _write_json_file_atomic(path: str, data: dict) -> None:
    tmp_path = f"{path}.tmp.{os.getpid()}"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _ensure_supported_image(path: str) -> None:
    if not os.path.exists(path):
        raise UploadError(f"Image not found: {path}")
    file_size = os.path.getsize(path)
    if file_size > 2 * 1024 * 1024:
        raise UploadError(f"Image too large ({file_size / 1024 / 1024:.1f}MB). Must be under 2MB: {path}")
    ext = os.path.splitext(path)[1].lower()
    if ext not in [".png", ".jpg", ".jpeg", ".gif"]:
        raise UploadError(f"Unsupported image format: {ext}. Use PNG, JPG, or GIF: {path}")


def _mime_type_for_image(path: str) -> str:
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    if ext == "png":
        return "image/png"
    if ext in ["jpg", "jpeg"]:
        return "image/jpeg"
    if ext == "gif":
        return "image/gif"
    return "application/octet-stream"


def _format_wechat_error(errcode: Optional[int], errmsg: Optional[str]) -> str:
    code = errcode if errcode is not None else "unknown"
    msg = (errmsg or "Unknown error").strip()
    hint = None
    if errcode in [40013]:
        hint = "Invalid AppID. Verify AppID in WeChat admin console."
    elif errcode in [40125, 40001]:
        hint = "Invalid AppSecret or access token. Check credentials and try again."
    elif errcode in [40164]:
        hint = "IP not whitelisted. Add your current IP to WeChat console whitelist."
    elif errcode in [42001]:
        hint = "Access token expired. Retry; token will refresh automatically."
    elif errcode in [45009]:
        hint = "API rate limit reached. Wait and retry."
    return f"WeChat API Error {code}: {msg}" + (f" | Hint: {hint}" if hint else "")


def _raise_if_wechat_error(data: dict, exc_cls: type[WeChatPublisherError], context: str) -> None:
    if not isinstance(data, dict):
        raise exc_cls(f"{context}: Invalid response from WeChat API")
    if "errcode" in data and data.get("errcode") not in [0, None]:
        raise exc_cls(f"{context}: {_format_wechat_error(data.get('errcode'), data.get('errmsg'))}")


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
            "font": "Helvetica, Arial, sans-serif", "border_width": "3px"
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

    def __init__(self, app_id: Optional[str], app_secret: Optional[str], verify_ssl: bool = True, enable_network: bool = True):
        """Initialize publisher with app credentials."""
        global logger
        
        self.app_id = app_id or ""
        self.app_secret = app_secret or ""
        self.verify_ssl = verify_ssl
        self.enable_network = enable_network
        
        # Configure SSL
        configure_ssl(verify_ssl)
        self.ssl_context = ssl.create_default_context() if verify_ssl else ssl._create_unverified_context()
        
        if not enable_network:
            logger.info("Network disabled (dry-run/validate mode)")
            self.access_token = None
            return
        
        if not self.app_id or not self.app_secret:
            raise ValidationError("AppID and AppSecret are required for publish mode")
        
        logger.info(f"Initializing WeChat Publisher for AppID: {self.app_id[:8]}...")
        
        # Get access token
        self.access_token = self._get_access_token()
        logger.info("✓ Successfully obtained access token")

    def _token_cache_path(self) -> str:
        safe = re.sub(r"[^a-zA-Z0-9_.-]", "_", self.app_id) if self.app_id else "unknown"
        return os.path.join(_get_cache_dir(), f"token.{safe}.json")

    def _load_cached_access_token(self) -> Optional[str]:
        data = _read_json_file(self._token_cache_path())
        if not data:
            return None
        token = data.get("access_token")
        expires_at = data.get("expires_at")
        if not token or not expires_at:
            return None
        try:
            if float(expires_at) <= time.time():
                return None
        except Exception:
            return None
        return token

    def _save_access_token(self, token: str, expires_in: int) -> None:
        skew = 300
        expires_at = time.time() + max(int(expires_in) - skew, 60)
        _write_json_file_atomic(self._token_cache_path(), {
            "access_token": token,
            "expires_in": int(expires_in),
            "expires_at": expires_at,
            "updated_at": time.time(),
            "app_id": self.app_id,
        })

    def _image_cache_path(self) -> str:
        safe = re.sub(r"[^a-zA-Z0-9_.-]", "_", self.app_id) if self.app_id else "unknown"
        return os.path.join(_get_cache_dir(), f"image_cache.{safe}.json")

    def _load_image_cache(self) -> Dict[str, Any]:
        return _read_json_file(self._image_cache_path()) or {"version": 1, "items": {}}

    def _save_image_cache(self, cache: Dict[str, Any]) -> None:
        _write_json_file_atomic(self._image_cache_path(), cache)

    def _get_cached_image_result(self, kind: str, sha256: str) -> Optional[str]:
        cache = self._load_image_cache()
        item = (cache.get("items") or {}).get(f"{kind}:{sha256}")
        if isinstance(item, dict):
            value = item.get("value")
            if isinstance(value, str) and value:
                return value
        return None

    def _set_cached_image_result(self, kind: str, sha256: str, value: str) -> None:
        cache = self._load_image_cache()
        items = cache.setdefault("items", {})
        items[f"{kind}:{sha256}"] = {"value": value, "updated_at": time.time()}
        self._save_image_cache(cache)

    def _get_access_token(self) -> str:
        """Get WeChat API access token."""
        url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={self.app_id}&secret={self.app_secret}"
        
        logger.debug(f"Requesting access token from: {url.split('?')[0]}")
        
        cached = self._load_cached_access_token()
        if cached:
            logger.debug("Using cached access token")
            return cached
        
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'WeChatPublisher/1.0'})
            with urllib.request.urlopen(req, timeout=30, context=self.ssl_context) as response:
                data = json.loads(response.read().decode())
                
                if "access_token" in data:
                    expires_in = data.get("expires_in", 7200)
                    logger.debug(f"Access token expires in {expires_in}s")
                    try:
                        self._save_access_token(data["access_token"], int(expires_in))
                    except Exception:
                        logger.debug("Failed to write token cache")
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
        
        if not self.enable_network or not self.access_token:
            raise UploadError("Network disabled; cannot upload thumbnail in dry-run/validate mode")
        
        _ensure_supported_image(img_path)
        sha = _sha256_file(img_path)
        cached = self._get_cached_image_result("thumb", sha)
        if cached:
            logger.info("✓ Thumbnail cache hit")
            return cached
        
        url = f"https://api.weixin.qq.com/cgi-bin/material/add_material?access_token={self.access_token}&type=thumb"
        
        boundary = "----WeChatPublisherBoundary"
        
        try:
            with open(img_path, "rb") as f:
                img_data = f.read()
            
            filename = os.path.basename(img_path)
            mime_type = _mime_type_for_image(img_path)
            
            parts = [
                f"--{boundary}".encode(),
                f'Content-Disposition: form-data; name="media"; filename="{filename}"'.encode(),
                f"Content-Type: {mime_type}".encode(),
                b"",
                img_data,
                f"--{boundary}--".encode(),
                b""
            ]
            
            body = b"\r\n".join(parts)
            req = urllib.request.Request(url, data=body)
            req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
            req.add_header("User-Agent", "WeChatPublisher/1.0")
            
            with urllib.request.urlopen(req, timeout=60, context=self.ssl_context) as response:
                data = json.loads(response.read().decode())
                
                if "media_id" in data:
                    logger.info(f"✓ Thumbnail uploaded successfully, media_id: {data['media_id'][:16]}...")
                    try:
                        self._set_cached_image_result("thumb", sha, data["media_id"])
                    except Exception:
                        logger.debug("Failed to write thumbnail cache")
                    return data["media_id"]
                
                _raise_if_wechat_error(data, UploadError, "Upload thumbnail")
                raise UploadError("Failed to upload thumbnail: Unknown error")
                
        except urllib.error.HTTPError as e:
            logger.error(f"HTTP error during upload: {e.code} {e.reason}")
            raise UploadError(f"HTTP error: {e.code} {e.reason}")
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            raise UploadError(f"Failed to upload thumbnail: {e}")

    def upload_image(self, img_path: str) -> str:
        """Upload image to WeChat and return permanent URL for use in articles."""
        logger.info(f"Uploading image to WeChat: {img_path}")
        
        if not self.enable_network or not self.access_token:
            raise UploadError("Network disabled; cannot upload image in dry-run/validate mode")
        
        _ensure_supported_image(img_path)
        sha = _sha256_file(img_path)
        cached = self._get_cached_image_result("article_image", sha)
        if cached:
            logger.info("✓ Image cache hit")
            return cached
        
        url = f"https://api.weixin.qq.com/cgi-bin/media/uploadimg?access_token={self.access_token}"
        
        boundary = "----WeChatPublisherBoundary"
        with open(img_path, "rb") as f:
            img_data = f.read()
        
        filename = os.path.basename(img_path)
        mime_type = _mime_type_for_image(img_path)
        
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
            with urllib.request.urlopen(req, timeout=60, context=self.ssl_context) as response:
                res_data = json.loads(response.read().decode())
                if "url" in res_data:
                    logger.info(f"✓ Image uploaded: {res_data['url']}")
                    try:
                        self._set_cached_image_result("article_image", sha, res_data["url"])
                    except Exception:
                        logger.debug("Failed to write image cache")
                    return res_data["url"]
                else:
                    _raise_if_wechat_error(res_data, UploadError, "Upload image")
                    raise UploadError(f"Failed to get URL: {res_data}")
        except Exception as e:
            logger.error(f"Image upload failed: {e}")
            raise UploadError(f"Failed to upload image: {e}")

    def render_md_table_to_html(self, table_str, style):
        """Manually convert a markdown table string to robust HTML with inline styles."""
        lines = [line.strip() for line in table_str.strip().split('\n')]
        if len(lines) < 2: return table_str
        
        # Parse headers
        headers = [c.strip() for c in lines[0].strip('|').split('|')]
        # Skip separator line (lines[1])
        rows = []
        for line in lines[2:]:
            if '|' in line:
                rows.append([c.strip() for c in line.strip('|').split('|')])
        
        # Build HTML
        html = [f'<div style="margin: 20px 0; overflow-x: auto; -webkit-overflow-scrolling: touch;">']
        table_border = "#dddddd" if style["bg"] == "#ffffff" else "#444"
        html.append(f'<table style="border-collapse: collapse; width: 100%; border: 1px solid {table_border}; font-size: 14px; line-height: 1.5; background-color: {style["bg"]};">')
        
        # Header
        head_bg = "#f2f2f2" if style["bg"] == "#ffffff" else style["text"]
        head_color = style["text"] if style["bg"] == "#ffffff" else style["bg"]
        html.append(f'<thead style="background-color: {head_bg}; color: {head_color};">')
        html.append(f'<tr>')
        for h in headers:
            html.append(f'<th style="border: 1px solid {table_border}; padding: 12px 10px; font-weight: bold; text-align: left;">{h}</th>')
        html.append(f'</tr></thead>')
        
        # Body
        html.append(f'<tbody>')
        for i, row in enumerate(rows):
            bg = "#fafafa" if i % 2 == 0 and style["bg"] == "#ffffff" else style["bg"]
            html.append(f'<tr style="background-color: {bg}; border-bottom: 1px solid #eeeeee;">')
            for cell in row:
                html.append(f'<td style="border: 1px solid {table_border}; padding: 10px; color: {style["text"]};">{cell}</td>')
            html.append(f'</tr>')
        html.append(f'</tbody></table></div>')
        
        return "".join(html)

    def convert_md_to_html(self, md_content: str, style_name: str = "swiss", md_path: Optional[str] = None, upload_images: bool = True, validate_images: bool = False) -> str:
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

        # ULTIMATE PROTECTION v2: Use Placeholders to bypass Markdown parser
        table_cache = {}
        def table_placeholder_replacer(match):
            quote_content = match.group(0)
            # Find the table part within the quote
            table_match = re.search(r'((?:^> *\|.*\|\s*)+(?:^> *\|[- :|]+\|\s*)(?:^> *\|.*\|\s*)*)', quote_content, re.MULTILINE)
            if table_match:
                raw_table = table_match.group(1)
                clean_table = re.sub(r'^> *', '', raw_table, flags=re.MULTILINE)
                html_table = self.render_md_table_to_html(clean_table, style)
                
                # Store HTML in cache and return a safe placeholder
                placeholder_id = f"[[WECHAT_TABLE_{len(table_cache)}]]"
                table_cache[placeholder_id] = html_table
                return quote_content.replace(raw_table, "\n" + placeholder_id + "\n")
            return quote_content

        # Apply placeholder logic
        processed_md = re.sub(r'(?:^>.*\n?)+', table_placeholder_replacer, processed_md, flags=re.MULTILINE)

        # Initialize mistune with custom renderer
        renderer = WeChatRenderer(style, style_name)
        markdown = mistune.create_markdown(
            renderer=renderer,
            plugins=['strikethrough', 'table']
        )
        
        # Convert content
        main_html = markdown(processed_md)
        
        # Post-process: Replace placeholders with real HTML
        for p_id, p_html in table_cache.items():
            # Mistune might wrap the placeholder in <p> tags, so we replace carefully
            main_html = main_html.replace(p_id, p_html)
            # Also handle if it was escaped (though unlikely inside placeholders)
            main_html = main_html.replace(p_id.replace('[', '&#91;').replace(']', '&#93;'), p_html)
        
        # 2. Post-process: Upload local images and replace URLs
        img_tags = re.findall(r'<img src="(.*?)"', main_html)
        
        md_abs = md_path or ""
        if md_abs and not os.path.isabs(md_abs):
            md_abs = os.path.join(os.getcwd(), md_abs)
        md_dir = os.path.dirname(os.path.abspath(md_abs)) if md_abs else os.getcwd()
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
                    if validate_images:
                        _ensure_supported_image(found_path)
                        logger.info(f"✓ Image OK: {found_path}")
                    if upload_images:
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
        
        if not self.enable_network or not self.access_token:
            raise DraftError("Network disabled; cannot create draft in dry-run/validate mode")
        
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
            
            with urllib.request.urlopen(req, timeout=30, context=self.ssl_context) as response:
                result = json.loads(response.read().decode())
                
                if "media_id" in result:
                    logger.info(f"✓ Draft created successfully! media_id: {result['media_id']}")
                    return result
                
                _raise_if_wechat_error(result, DraftError, "Create draft")
                raise DraftError("Failed to create draft: Unknown error")
                
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
    parser.add_argument("--verify-ssl", dest="verify_ssl", action="store_true",
                       help="Enable SSL verification (default: enabled)")
    parser.add_argument("--no-verify-ssl", dest="verify_ssl", action="store_false",
                       help="Disable SSL verification (use only for development)")
    parser.set_defaults(verify_ssl=True)
    parser.add_argument("--dry-run", action="store_true",
                       help="Render and validate locally; skip all WeChat API calls")
    parser.add_argument("--validate", action="store_true",
                       help="Only validate inputs and local images; no rendering output required")
    parser.add_argument("--out-html", help="Write rendered HTML to a file (dry-run only)")
    parser.add_argument("-v", "--verbose", action="store_true", 
                       help="Enable verbose debug logging")
    
    args = parser.parse_args()
    
    # Setup logging early
    logger = setup_logging(args.verbose)
    logger.info("=" * 50)
    logger.info("WeChat Markdown Publisher v1.2 (Hardened for Agent Runs)")
    logger.info("=" * 50)
    
    enable_network = not (args.dry_run or args.validate)
    app_id = (args.id or os.environ.get("WECHAT_APP_ID") or "") if enable_network else (args.id or os.environ.get("WECHAT_APP_ID") or "")
    app_secret = (args.secret or os.environ.get("WECHAT_APP_SECRET") or "") if enable_network else (args.secret or os.environ.get("WECHAT_APP_SECRET") or "")
    
    if enable_network and (not app_id or not app_secret):
        logger.error("Missing WeChat credentials!")
        logger.error(f"Searched in: Command line args, Shell env, Project .env, and Global config (~/.config/publish-md-to-wechat/.env)")
        parser.error("Credentials required for publish mode. Please set WECHAT_APP_ID/WECHAT_APP_SECRET.")
    
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
        
        thumb_path = args.thumb
        if enable_network:
            if not thumb_path:
                logger.info(f"No thumb provided. Auto-generating cover for style: {args.style}...")
                script_dir = os.path.dirname(os.path.abspath(__file__))
                gen_script = os.path.join(script_dir, "generate_cover.py")
                auto_thumb = os.path.join(os.path.dirname(script_dir), "assets", "auto_cover.png")
                
                if os.path.exists(auto_thumb):
                    os.remove(auto_thumb)
                    logger.debug(f"Removed old thumbnail: {auto_thumb}")
                
                cmd = f'python3 "{gen_script}" --title "{title}" --style "{args.style}" --output "{auto_thumb}"'
                logger.debug(f"Running: {cmd}")
                result = os.system(cmd)
                
                if result == 0 and os.path.exists(auto_thumb):
                    thumb_path = auto_thumb
                    logger.info(f"✓ Auto-generated cover: {auto_thumb}")
                else:
                    default_thumb = os.path.join(os.path.dirname(script_dir), "assets", "default_thumb.png")
                    if os.path.exists(default_thumb):
                        thumb_path = default_thumb
                        logger.warning("Generation failed, using default thumbnail")
                    else:
                        raise ValidationError("No thumbnail provided and auto-generation failed")
        else:
            if thumb_path:
                _ensure_supported_image(thumb_path)
        
        logger.info("Initializing WeChat publisher...")
        publisher = WeChatPublisher(app_id, app_secret, verify_ssl=args.verify_ssl, enable_network=enable_network)
        
        html = publisher.convert_md_to_html(
            md_content,
            args.style,
            md_path=args.md,
            upload_images=enable_network,
            validate_images=(args.validate or args.dry_run),
        )
        logger.info(f"✓ Converted Markdown to HTML ({len(html)} bytes)")
        
        if args.out_html:
            if not args.dry_run:
                raise ValidationError("--out-html is only supported with --dry-run")
            out_dir = os.path.dirname(os.path.abspath(args.out_html))
            if out_dir and not os.path.exists(out_dir):
                os.makedirs(out_dir, exist_ok=True)
            with open(args.out_html, "w", encoding="utf-8") as f:
                f.write(html)
            logger.info(f"✓ Wrote HTML: {args.out_html}")
        
        if args.validate:
            logger.info("✓ Validation OK")
            return 0
        
        if args.dry_run:
            logger.info("✓ Dry-run complete (no WeChat API calls made)")
            return 0
        
        thumb_id = publisher.upload_thumb(thumb_path)
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
