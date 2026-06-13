"""
OFFLINE WATCHER - Chạy trên máy DESKTOP-JVHR1D2 (Box 3 Server)

Nhiệm vụ:
- Mỗi 60 giây, query Drive để lấy danh sách merchant folders
- Đọc check-in status từ Drive (file checkin.json trong folder mỗi merchant)
- So sánh: không check-in trong 15 phút → OFFLINE → gửi Box 4

Logic:
| Check-in (15 phút) | Backup hôm nay | Status  |
|---------------------|---------------|---------|
| ✅ Có              | ✅ Có         | ON      |
| ✅ Có              | ❌ Không      | ON      |
| ❌ Không           | ✅ Có         | OFF     |
| ❌ Không           | ❌ Không      | OFF     |

OFFLINE = không check-in trong 15 phút (bất kể có backup hay không)
"""

import json
import logging
import os
import socket
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# UTF-8 encoding fix for Windows console
if sys.stdout is not None:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='ignore')
if sys.stderr is not None:
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='ignore')

import requests

# ============================================================================
# CONFIGURATION
# ============================================================================

CHECKIN_TIMEOUT_MINUTES = 15  # OFFLINE nếu không check-in trong 15 phút
CHECK_INTERVAL_SECONDS = 60   # Kiểm tra mỗi 60 giây

# Box 4: System channel cho OFFLINE notifications
SYSTEM_TOKEN = "8759922361:AAHSTyqiH-_vzjK-jBBD_Zn-E5pPKF9zqxw"
SYSTEM_CHAT_ID = "-5164973240"

# Google Drive config
PARENT_FOLDER_ID = "0ABH5fVPDIaLFUk9PVA"

SERVICE_ACCOUNT_INFO = {
    "type": "service_account",
    "project_id": "erudite-phalanx-498720-b4",
    "private_key_id": "6eb599b72454ada5c89bf8ba261bb13713459c1a",
    "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQDTAMIRTGTBrhND\n7IoegPAdI3+H0Y50j8xsrAGFMP9hC+seOLqrm40BMOFuji0A7Bv5mUdLVaj9QBpQ\nI5zItxTLVnroMjz7GaPSLp6mXNih2gfzbq6uoB+HpzuE3gdT0wLX7GGC5X37ViXz\ndOOxknEioJIr7bwAA5SdRnRYXcp1fa4yuHq+RKv/gYGua4ApGBcFT6W8z/gnkDI3\nndE+1iU5nxaI+CUd8PKLGS8NWyzIMgsZqN5iY0zZnK1fo7XoK9hiPyiKOWqJJ/Vk\n5Av99PvM28yGm3LycCkWi5TGfknvXuoD2eyM0rETJs9bViQFGwrOXP7/BthCgHC5\nUjMpWZzfAgMBAAECggEAPxR8cCB3BMHuR4GpHwpr/kIVB70ZyfYNZrWbdL6bsl8W\nSMAr6k7D/kWnN15wzNRJXrq4qihvL1rhIvEql4TIRivR7aXLPkRBif3e9xxNtUFR\n3DBML692DZ9st0GLTj+Im5Wy5yeFnMR57wkUYwtFIFWBrXlSmWx4mvYrpRlRBANm\nOelJz4qmWvXy/OXzStCvjDPGFn3pPnnPkTNMYaMw8M67UnlVe6FZdvEZ6FO4njxr\nrVfOkAGitrGr0BFlCaWtoBm6jvfLht9u5R1j2USPz6FUHyCpWjrEiNEaaetJXNAM\nEmNahA0sz/gZZebVcPOQPDFENSAOTA8h7xeDX9TXuQKBgQDsytP07DOaKajqBy9o\n2GNFbPaWQz4trN3b5m5FQHijuQL/C5e/Xu6jRuFQy7edgn/q7EGa7cLRM/RFnWSH\ngSkk1XT2c5bCDsxwVWW/eVyFzmlW5/zvPJanU48z7NHL/kWsMlqM9GJkTrgZx6xJ\neJZdDr6cchSjdhwA8/OXMj5FaQKBgQDkHmUcb+npWs9+EKdhw1zb09I2lcyQ9pcA\nh9tIHYv+ldpoz628q251IOtBoD/v27wYqtiK2GeOnxmfwerdEIkTz81G9zaJAXnR\nHKJeYkqVzsRB27uWTGkA1GANDmm59c9mM0rtRhYXqg83bc6/jOP+j0y98ZXUPM1O\nY+93544fBwKBgQCe7vSdK/zmuJebnP8BTFw1ORG5gaC2X5T6CAxzhvZyTbfpIArW\ndA2Qof6RkGrJ2dGqCLFwH63nZQvLvfy/xr2q72r2EFdcITqvG2KTxg2H8idaIZPv\nr6ce4EL6AzY9yYlSLuoAOffgg8Wl6BOHrNyf0Um3EAsyPBBHw3X4QczyIQKBgQCR\nOlSOzSTy3lB45qtZTyIABZOwEqBAreymdteAyubEdqysy4LFObLBuOptRlNOJetT\nHPltM6aCIwISNkeK46sRRNtgUaSThrACFCO+yP7I7vD9KKH9Zrn2wD5CManXrQmT\n/BW4h0UrXaYAWNUmF9FSz/JAftwvWWIvhOoAwRc24wKBgFpAkYt8rfgqdz+yZszz\nlw/0l22eKKZER/kwmA3knLHnfBcSFEHu2L+jwVlCYcVpFo42eBXaiatwuoWipDtm\n/w15UUBEhcCan+6FslQovpavW+RBjqAHeEb5SNyu5QhF1PNkR1qwVqT/NyS3CDKV\nICxkTP+66Iby89+X16sMt99d\n-----END PRIVATE KEY-----\n",
    "client_email": "backup-aio@erudite-phalanx-498720-b4.iam.gserviceaccount.com",
    "client_id": "110799607165422267310",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/backup-aio%40erudite-phalanx-498720-b4.iam.gserviceaccount.com",
    "universe_domain": "googleapis.com",
}

# ============================================================================
# LOGGING
# ============================================================================

LOG_DIR = r"C:\ATLED\logs"
os.makedirs(LOG_DIR, exist_ok=True)

def setup_logging():
    log_file = os.path.join(LOG_DIR, "offline_watcher.log")
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        encoding="utf-8",
    )
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logging.getLogger().addHandler(console)

setup_logging()

# ============================================================================
# GOOGLE DRIVE HELPERS
# ============================================================================

_drive_service = None

def _build_drive_service():
    """Build Google Drive service v3 using service account."""
    try:
        import certifi
        certifi_path = certifi.where()
        if certifi_path and os.path.exists(certifi_path):
            os.environ["SSL_CERT_FILE"] = certifi_path
            os.environ["SSL_CERT_DIR"] = os.path.dirname(certifi_path)
    except Exception:
        pass

    import google_auth_httplib2
    import httplib2
    from google.oauth2 import service_account
    from backup_tool.drive_discovery_embed import DRIVE_V3_DISCOVERY_JSON
    from googleapiclient.discovery import build_from_document

    creds = service_account.Credentials.from_service_account_info(
        SERVICE_ACCOUNT_INFO,
        scopes=["https://www.googleapis.com/auth/drive.file"],
    )
    http = google_auth_httplib2.AuthorizedHttp(
        creds,
        http=httplib2.Http(timeout=30),
    )
    
    return build_from_document(
        DRIVE_V3_DISCOVERY_JSON,
        http=http,
    )

def get_drive_service():
    global _drive_service
    if _drive_service is None:
        _drive_service = _build_drive_service()
        logging.info("[DRIVE] Google Drive service initialized")
    return _drive_service

def get_today_utc_bounds():
    """Get UTC start/end bounds for today."""
    local_now = datetime.now().astimezone()
    local_tz = local_now.tzinfo
    today = local_now.date()
    local_start = datetime(today.year, today.month, today.day, tzinfo=local_tz)
    local_end = local_start + timedelta(days=1)
    utc_start = local_start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    utc_end = local_end.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return utc_start, utc_end

def get_all_merchant_folders():
    """Lấy tất cả merchant folder từ Drive."""
    service = get_drive_service()
    folders = []
    page_token = None
    
    while True:
        results = service.files().list(
            q=(
                f"'{PARENT_FOLDER_ID}' in parents "
                "and mimeType='application/vnd.google-apps.folder' "
                "and trashed=false"
            ),
            fields="nextPageToken, files(id, name)",
            pageSize=1000,
            pageToken=page_token,
            corpora="allDrives",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute(num_retries=3)
        
        for item in results.get("files", []):
            folders.append({
                "id": item.get("id"),
                "name": item.get("name"),
            })
        
        page_token = results.get("nextPageToken")
        if not page_token:
            break
    
    return folders

def get_folders_with_backup_today():
    """Lấy folder IDs có backup .zip hôm nay."""
    service = get_drive_service()
    utc_start, utc_end = get_today_utc_bounds()
    
    backed_up_ids = set()
    page_token = None
    
    while True:
        results = service.files().list(
            q=(
                "trashed=false "
                "and name contains '.zip' "
                f"and createdTime >= '{utc_start}' "
                f"and createdTime < '{utc_end}'"
            ),
            fields="nextPageToken, files(id, name, parents)",
            pageSize=1000,
            pageToken=page_token,
            corpora="allDrives",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute(num_retries=3)
        
        for item in results.get("files", []):
            if not str(item.get("name", "")).lower().endswith(".zip"):
                continue
            for parent_id in item.get("parents", []):
                backed_up_ids.add(parent_id)
        
        page_token = results.get("nextPageToken")
        if not page_token:
            break
    
    return backed_up_ids

def read_checkin_from_folder(service, folder_id: str, store_name: str) -> Optional[dict]:
    """
    Đọc check-in file (checkin.json) từ Drive folder của merchant.
    """
    try:
        # Tìm file checkin.json trong folder
        results = service.files().list(
            q=(
                f"'{folder_id}' in parents "
                "and name='checkin.json' "
                "and trashed=false"
            ),
            fields="files(id, name, createdTime, modifiedTime)",
            pageSize=10,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute(num_retries=2)
        
        files = results.get("files", [])
        if not files:
            logging.debug(f"[CHECKIN] No checkin.json for {store_name}")
            return None
        
        # Đọc nội dung file
        file_id = files[0]["id"]
        content = service.files().get_media(fileId=file_id).execute(num_retries=2)
        data = json.loads(content.decode("utf-8"))
        
        logging.debug(f"[CHECKIN] Read OK: {store_name}")
        return data
        
    except Exception as e:
        logging.debug(f"[CHECKIN] Error reading {store_name}: {e}")
        return None

# ============================================================================
# OFFLINE DETECTION & REPORTING
# ============================================================================

_last_offline_reports: dict[str, float] = {}  # store_name -> last report timestamp
OFFLINE_REPORT_COOLDOWN_MINUTES = 30  # Chỉ báo lại OFFLINE sau 30 phút

def send_offline_notification(store_name: str, checkin_data: dict, has_backup: bool):
    """
    Gửi OFFLINE notification vào Box 4.
    """
    global _last_offline_reports
    
    if not store_name:
        return
    
    # Cooldown check - không báo lại quá thường xuyên
    now = time.time()
    last_report = _last_offline_reports.get(store_name, 0)
    if now - last_report < OFFLINE_REPORT_COOLDOWN_MINUTES * 60:
        logging.debug(f"[OFFLINE] Cooldown active for {store_name} - skipping report")
        return
    
    try:
        hostname = checkin_data.get("hostname", "Unknown")
        user = checkin_data.get("user", "Unknown")
        ip = checkin_data.get("ip", "Unknown")
        app_version = checkin_data.get("app_version", "Unknown")
        watch_dir = checkin_data.get("watch_directory", "Unknown")
        
        last_seen = "Unknown"
        if checkin_data.get("timestamp"):
            last_seen = datetime.fromtimestamp(checkin_data["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
        
        message = (
            f"⚠️ <b>[ATLED MACHINE OFFLINE]</b>\n"
            f"\n"
            f"🖥️ <b>Host:</b> {hostname}\n"
            f"🌐 <b>IP:</b> {ip}\n"
            f"👤 <b>User:</b> {user}\n"
            f"🏪 <b>Merchant:</b> {store_name}\n"
            f"📂 <b>Watch:</b> {watch_dir}\n"
            f"📅 <b>Last Seen:</b> {last_seen}\n"
            f"💾 <b>Has Backup Today:</b> {'✅ Có' if has_backup else '❌ Không'}\n"
            f"📦 <b>App Version:</b> {app_version}\n"
            f"\n"
            f"⏰ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"📝 <b>Reason:</b> Không check-in trong {CHECKIN_TIMEOUT_MINUTES} phút"
        )
        
        url = f"https://api.telegram.org/bot{SYSTEM_TOKEN}/sendMessage"
        response = requests.post(
            url,
            data={
                "chat_id": SYSTEM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=15,
            verify=False,
        )
        
        if response.status_code == 200:
            logging.info(f"[OFFLINE] Notification sent for {store_name} ({hostname})")
            _last_offline_reports[store_name] = now
        else:
            logging.warning(f"[OFFLINE] Failed to send notification: HTTP {response.status_code}")
            
    except Exception as e:
        logging.error(f"[OFFLINE] Error sending notification for {store_name}: {e}")

# ============================================================================
# MAIN WATCHER LOOP
# ============================================================================

def check_all_machines():
    """
    Kiểm tra tất cả máy backup.
    Logic:
    - Query Drive để lấy merchant folders
    - Đọc checkin.json từ Drive folder của mỗi merchant
    - So sánh: không check-in trong 15 phút → OFFLINE
    """
    logging.info("[WATCHER] Starting machine status check...")
    
    service = get_drive_service()
    
    # 1. Lấy danh sách merchant folders từ Drive
    all_folders = get_all_merchant_folders()
    all_folder_ids = {f["id"]: f["name"] for f in all_folders}
    
    logging.info(f"[WATCHER] Total folders on Drive: {len(all_folders)}")
    
    # 2. Lấy folders có backup hôm nay
    backed_up_ids = get_folders_with_backup_today()
    logging.info(f"[WATCHER] Folders with backup today: {len(backed_up_ids)}")
    
    # 3. Phân tích từng merchant
    offline_machines = []
    online_machines = []
    
    for folder_id, store_name in all_folder_ids.items():
        has_backup_today = folder_id in backed_up_ids
        
        # Đọc check-in từ Drive
        checkin_data = read_checkin_from_folder(service, folder_id, store_name)
        
        # Kiểm tra online status
        is_online = False
        if checkin_data:
            timestamp = checkin_data.get("timestamp", 0)
            if timestamp:
                last_checkin = datetime.fromtimestamp(timestamp)
                elapsed = (datetime.now() - last_checkin).total_seconds() / 60
                is_online = elapsed <= CHECKIN_TIMEOUT_MINUTES
        
        if is_online:
            hostname = checkin_data.get("hostname", "Unknown")
            online_machines.append({
                "hostname": hostname,
                "store_name": store_name,
                "has_backup": has_backup_today,
            })
            logging.info(f"[WATCHER] ✅ ON: {store_name} ({hostname}) - Backup: {'Yes' if has_backup_today else 'No'}")
        else:
            hostname = checkin_data.get("hostname", "Unknown") if checkin_data else "Unknown"
            status = "OFFLINE (no check-in)" if not checkin_data else "OFFLINE (check-in expired)"
            offline_machines.append({
                "hostname": hostname,
                "store_name": store_name,
                "has_backup": has_backup_today,
                "checkin_data": checkin_data,
            })
            logging.warning(f"[WATCHER] ❌ {status}: {store_name} ({hostname}) - Backup: {'Yes' if has_backup_today else 'No'}")
            
            # Gửi OFFLINE notification
            if checkin_data:
                send_offline_notification(store_name, checkin_data, has_backup_today)
    
    # Log summary
    logging.info(f"[WATCHER] ═══ SUMMARY ═══")
    logging.info(f"[WATCHER] Online: {len(online_machines)} machines")
    logging.info(f"[WATCHER] Offline: {len(offline_machines)} machines")
    
    return {
        "online": online_machines,
        "offline": offline_machines,
        "total_folders": len(all_folders),
        "backed_up_today": len(backed_up_ids),
    }

def watcher_loop():
    """Main watcher loop - chạy mãi mãi."""
    logging.info("=" * 60)
    logging.info("ATLED OFFLINE WATCHER - STARTED")
    logging.info(f"Hostname: {socket.gethostname()}")
    logging.info(f"Check interval: {CHECK_INTERVAL_SECONDS}s")
    logging.info(f"Timeout: {CHECKIN_TIMEOUT_MINUTES} minutes")
    logging.info("Reading check-in from Google Drive (no network share needed)")
    logging.info("=" * 60)
    
    # Initial check
    try:
        check_all_machines()
    except Exception as e:
        logging.error(f"[WATCHER] Initial check failed: {e}")
    
    # Main loop
    while True:
        try:
            time.sleep(CHECK_INTERVAL_SECONDS)
            check_all_machines()
        except KeyboardInterrupt:
            logging.info("[WATCHER] Stopped by user")
            break
        except Exception as e:
            logging.error(f"[WATCHER] Error in watcher loop: {e}")
            import traceback
            logging.error(traceback.format_exc())
            time.sleep(CHECK_INTERVAL_SECONDS)

# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    watcher_loop()
