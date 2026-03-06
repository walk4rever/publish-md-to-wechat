#!/usr/bin/env python3
"""
Clear all drafts from WeChat Official Account Draft Box.
Uses the WeChat API to fetch and delete drafts in batches.
"""

import urllib.request
import urllib.error
import json
import os
import sys
import ssl
import logging
import argparse
import re
import time
from datetime import datetime
from typing import Optional, Any, Dict

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ============================================================
# Logging Configuration
# ============================================================

def setup_logging(verbose: bool = False) -> logging.Logger:
    """Setup logging with console handler."""
    logger = logging.getLogger("DraftCleaner")
    level = logging.DEBUG if verbose else logging.INFO
    logger.setLevel(level)
    logger.handlers.clear()
    
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    formatter = logging.Formatter('%(asctime)s | %(levelname)-8s | %(message)s', datefmt='%H:%M:%S')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger

logger = None


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


def _write_json_file_atomic(path: str, data: Dict[str, Any]) -> None:
    tmp_path = f"{path}.tmp.{os.getpid()}"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


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


def _raise_if_wechat_error(data: Dict[str, Any], context: str) -> None:
    if not isinstance(data, dict):
        raise Exception(f"{context}: Invalid response from WeChat API")
    if "errcode" in data and data.get("errcode") not in [0, None]:
        raise Exception(f"{context}: {_format_wechat_error(data.get('errcode'), data.get('errmsg'))}")

class DraftCleaner:
    def __init__(self, app_id: str, app_secret: str, verify_ssl: bool = True):
        self.app_id = app_id
        self.app_secret = app_secret
        self.verify_ssl = verify_ssl
        self.ssl_context = ssl.create_default_context() if verify_ssl else ssl._create_unverified_context()
        self.access_token = self._get_access_token()
        
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
        
    def _get_access_token(self) -> str:
        """Get WeChat API access token."""
        url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={self.app_id}&secret={self.app_secret}"
        cached = self._load_cached_access_token()
        if cached:
            logger.debug("Using cached access token")
            return cached
        try:
            with urllib.request.urlopen(url, timeout=30, context=self.ssl_context) as response:
                data = json.loads(response.read().decode())
                if "access_token" in data:
                    try:
                        self._save_access_token(data["access_token"], int(data.get("expires_in", 7200)))
                    except Exception:
                        logger.debug("Failed to write token cache")
                    return data["access_token"]
                _raise_if_wechat_error(data, "Get access token")
                raise Exception(f"Failed to get access token: {data}")
        except Exception as e:
            raise Exception(f"Network error while getting access token: {e}")

    def get_draft_list(self, offset=0, count=20):
        """Fetch a batch of drafts."""
        url = f"https://api.weixin.qq.com/cgi-bin/draft/batchget?access_token={self.access_token}"
        data = json.dumps({
            "offset": offset,
            "count": count,
            "no_content": 1
        }).encode('utf-8')
        
        req = urllib.request.Request(url, data=data, method='POST')
        req.add_header('Content-Type', 'application/json')
        
        try:
            with urllib.request.urlopen(req, timeout=30, context=self.ssl_context) as response:
                payload = json.loads(response.read().decode())
                _raise_if_wechat_error(payload, "Get draft list")
                return payload
        except Exception as e:
            logger.error(f"Error fetching drafts: {e}")
            return None

    def delete_draft(self, media_id):
        """Delete a single draft."""
        url = f"https://api.weixin.qq.com/cgi-bin/draft/delete?access_token={self.access_token}"
        data = json.dumps({"media_id": media_id}).encode('utf-8')
        
        req = urllib.request.Request(url, data=data, method='POST')
        req.add_header('Content-Type', 'application/json')
        
        try:
            with urllib.request.urlopen(req, timeout=30, context=self.ssl_context) as response:
                res = json.loads(response.read().decode())
                _raise_if_wechat_error(res, "Delete draft")
                return res.get("errcode") == 0
        except Exception as e:
            logger.error(f"Error deleting draft {media_id}: {e}")
            return False

    def clear_all(self):
        """Iteratively delete all drafts."""
        logger.info("Starting to clear draft box...")
        
        total_deleted = 0
        while True:
            # We always use offset 0 because deleting items shifts the list
            response = self.get_draft_list(offset=0, count=20)
            
            if not response or "item" not in response or not response["item"]:
                break
                
            items = response["item"]
            total_count = response.get("total_count", 0)
            logger.info(f"Found {len(items)} drafts (Total remaining: {total_count})")
            
            for item in items:
                media_id = item["media_id"]
                title = item["content"]["news_item"][0]["title"]
                
                logger.info(f"Deleting: {title} ({media_id[:10]}...)")
                if self.delete_draft(media_id):
                    total_deleted += 1
                else:
                    logger.error(f"Failed to delete: {title}")
            
            # Small delay to avoid hitting rate limits too hard if there are many
            import time
            time.sleep(0.5)
            
        logger.info(f"✓ Finished. Total drafts deleted: {total_deleted}")

def main():
    global logger
    parser = argparse.ArgumentParser(description="Clear all WeChat drafts")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--verify-ssl", dest="verify_ssl", action="store_true", help="Enable SSL verification (default: enabled)")
    parser.add_argument("--no-verify-ssl", dest="verify_ssl", action="store_false", help="Disable SSL verification (use only for development)")
    parser.set_defaults(verify_ssl=True)
    args = parser.parse_args()
    
    logger = setup_logging(args.verbose)
    
    # Try to get credentials from environment
    app_id = os.environ.get("WECHAT_APP_ID")
    app_secret = os.environ.get("WECHAT_APP_SECRET")
    
    if not app_id or not app_secret:
        logger.error("WECHAT_APP_ID or WECHAT_APP_SECRET environment variables not found.")
        sys.exit(1)
        
    try:
        cleaner = DraftCleaner(app_id, app_secret, verify_ssl=args.verify_ssl)
        cleaner.clear_all()
    except Exception as e:
        logger.error(f"Failed to clear drafts: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
