# ATLED_BK_Watcher - Theo doi check-in tu Box 1
# Neu 15 phut khong nhan check-in -> Gui OFFLINE vao Box 4

import os
import sys
import time
import json
import logging
from datetime import datetime, timedelta
import requests

# Config
CONFIG_PATH = "config.json"
CHECK_INTERVAL = 60  # 1 phut kiem tra 1 lan
OFFLINE_THRESHOLD = 15 * 60  # 15 phut khong check-in = offline

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('watcher.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def load_config():
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)

def get_last_checkin_time(chat_id: str, token: str) -> datetime | None:
    """Lay thoi diem check-in cuoi cung tu Box 1 bang cach doc message."""
    try:
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        params = {"chat_id": chat_id, "limit": 100}
        resp = requests.get(url, params=params, timeout=30)
        data = resp.json()
        
        if not data.get("ok"):
            logger.error(f"getUpdates failed: {data}")
            return None
        
        messages = data.get("result", [])
        for msg in reversed(messages):
            text = msg.get("message", {}).get("text", "")
            if "CHECK IN" in text:
                date_str = msg.get("message", {}).get("date")
                if date_str:
                    return datetime.fromtimestamp(date_str)
        
        return None
    except Exception as e:
        logger.error(f"Error getting last checkin: {e}")
        return None

def send_offline_to_box4(system_token: str, system_chat_id: str, merchant: str, watch_dir: str):
    """Gui thong bao OFFLINE vao Box 4."""
    try:
        hostname = os.environ.get('COMPUTERNAME', 'Unknown')
        username = os.environ.get('USERNAME', 'Unknown')
        
        message = (
            f"🔴 <b>[ATLED APP OFFLINE]</b>\n"
            f"🖥️ Host: {hostname}\n"
            f"👤 User: {username}\n"
            f"🏪 Merchant: {merchant}\n"
            f"📂 Watch: {watch_dir}\n"
            f"🕐 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        )
        
        url = f"https://api.telegram.org/bot{system_token}/sendMessage"
        resp = requests.post(url, data={
            "chat_id": system_chat_id,
            "text": message,
            "parse_mode": "HTML"
        }, timeout=30)
        
        if resp.status_code == 200:
            logger.info(f"Sent OFFLINE to Box4")
            return True
        else:
            logger.error(f"Failed to send OFFLINE: {resp.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending OFFLINE: {e}")
        return False

def main():
    logger.info("ATLED_BK_Watcher started")
    
    if not os.path.exists(CONFIG_PATH):
        logger.error(f"Config file not found: {CONFIG_PATH}")
        sys.exit(1)
    
    config = load_config()
    
    update_token = config.get("TELEGRAM_UPDATE_TOKEN", "")
    update_chat_id = config.get("TELEGRAM_UPDATE_CHAT_ID", "")
    system_token = config.get("TELEGRAM_SYSTEM_TOKEN", "")
    system_chat_id = config.get("TELEGRAM_SYSTEM_CHAT_ID", "")
    merchant = config.get("STORE_NAME", "[Not configured]")
    watch_dir = config.get("WATCH_DIRECTORY", "[Not configured]")
    
    if not update_token or not update_chat_id:
        logger.error("Box 1 (update) token/chat_id not configured")
        sys.exit(1)
    
    if not system_token or not system_chat_id:
        logger.error("Box 4 (system) token/chat_id not configured")
        sys.exit(1)
    
    last_offline_sent = None
    offline_sent_for_this_event = False
    
    logger.info(f"Monitoring Box 1: {update_chat_id}")
    logger.info(f"Will alert Box 4: {system_chat_id} if no check-in for {OFFLINE_THRESHOLD//60} minutes")
    
    while True:
        try:
            last_checkin = get_last_checkin_time(update_chat_id, update_token)
            
            if last_checkin:
                elapsed = (datetime.now() - last_checkin).total_seconds()
                logger.info(f"Last check-in: {last_checkin.strftime('%H:%M:%S')} ({elapsed:.0f}s ago)")
                
                if elapsed >= OFFLINE_THRESHOLD:
                    if not offline_sent_for_this_event:
                        logger.warning("No check-in for 15 minutes! Sending OFFLINE to Box 4")
                        send_offline_to_box4(system_token, system_chat_id, merchant, watch_dir)
                        offline_sent_for_this_event = True
                        last_offline_sent = datetime.now()
                else:
                    # Check-in lai -> reset flag
                    if offline_sent_for_this_event:
                        logger.info("Check-in resumed, resetting OFFLINE flag")
                        offline_sent_for_this_event = False
            else:
                logger.warning("No check-in found in recent messages")
                if not offline_sent_for_this_event:
                    # Thu 15 phut khong co check-in nao
                    logger.warning("No check-in ever detected, waiting...")
            
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            logger.info("Watcher stopped by user")
            break
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
