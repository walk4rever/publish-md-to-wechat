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
from datetime import datetime

# ============================================================
# Logging Configuration
# ============================================================

def setup_logging(verbose: bool = False) -> logging.Logger:
    """Setup logging with console handler."""
    logger = logging.getLogger("DraftCleaner")
    level = logging.DEBUG if verbose else logging.INFO
    logger.setLevel(level)
    
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    formatter = logging.Formatter('%(asctime)s | %(levelname)-8s | %(message)s', datefmt='%H:%M:%S')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger

logger = None

class DraftCleaner:
    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self.access_token = self._get_access_token()
        
    def _get_access_token(self) -> str:
        """Get WeChat API access token."""
        url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={self.app_id}&secret={self.app_secret}"
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                data = json.loads(response.read().decode())
                if "access_token" in data:
                    return data["access_token"]
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
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode())
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
            with urllib.request.urlopen(req, timeout=30) as response:
                res = json.loads(response.read().decode())
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
    logger = setup_logging()
    
    # Try to get credentials from environment
    app_id = os.environ.get("WECHAT_APP_ID")
    app_secret = os.environ.get("WECHAT_APP_SECRET")
    
    if not app_id or not app_secret:
        logger.error("WECHAT_APP_ID or WECHAT_APP_SECRET environment variables not found.")
        sys.exit(1)
        
    try:
        cleaner = DraftCleaner(app_id, app_secret)
        cleaner.clear_all()
    except Exception as e:
        logger.error(f"Failed to clear drafts: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Disable SSL verification for development environments if needed
    ssl._create_default_https_context = ssl._create_unverified_context
    main()
