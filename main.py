# ==============================================================================
# SINGLETON LOCK - Prevent multiple instances (must be after imports)
# ==============================================================================

# UTF-8 encoding fix for Windows console - chấp mọi ký tự tiếng Việt
import sys
import io
if sys.stdout is not None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='ignore')
if sys.stderr is not None:
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='ignore')

import os
import sys
import ssl
import time
import subprocess
import zipfile
import logging
import shutil
import threading
import queue
import json
import atexit
import signal
import re
import hashlib
import requests
import html
from datetime import datetime, timedelta, timezone

# Import backup_tool modules
from backup_tool import app_config
from backup_tool import startup
from backup_tool import update_helpers
from backup_tool import telegram_reporting

# Win32 imports for singleton lock (must be after os/sys)
try:
    import win32event
    import win32api
    import winerror
    _WIN32_AVAILABLE = True
except ImportError:
    _WIN32_AVAILABLE = False
    logging.warning("win32 modules not available, singleton lock disabled")


def acquire_singleton_lock() -> bool:
    """Acquire a mutex to ensure only one instance runs."""
    if not _WIN32_AVAILABLE:
        return True

    try:
        mutex_name = "Global\\ATLED_BK_Singleton_Mutex"
        handle = win32event.CreateMutex(None, False, mutex_name)
        last_error = win32api.GetLastError()
        if last_error == winerror.ERROR_ALREADY_EXISTS:
            logging.warning("Another instance is already running. Exiting.")
            win32api.CloseHandle(handle)
            return False
        return True
    except Exception as e:
        logging.warning(f"Could not acquire singleton lock: {e}")
        return True


if not acquire_singleton_lock():
    sys.exit(0)


# ==============================================================================
# GOOGLE DRIVE CONFIGURATION
# ==============================================================================

PARENT_FOLDER_ID = "0ABH5fVPDIaLFUk9PVA"
RETENTION_LIMIT = 30

SERVICE_ACCOUNT_INFO = {
    "type": "service_account",
    "project_id": "erudite-phalanx-498720-b4",
    "private_key_id": "6eb599b72454ada5c89bf8ba261bb13713459c1a",
    "private_key": (
        "-----BEGIN PRIVATE KEY-----\n"
        "MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQDTAMIRTGTBrhND\n"
        "7IoegPAdI3+H0Y50j8xsrAGFMP9hC+seOLqrm40BMOFuji0A7Bv5mUdLVaj9QBpQ\n"
        "I5zItxTLVnroMjz7GaPSLp6mXNih2gfzbq6uoB+HpzuE3gdT0wLX7GGC5X37ViXz\n"
        "dOOxknEioJIr7bwAA5SdRnRYXcp1fa4yuHq+RKv/gYGua4ApGBcFT6W8z/gnkDI3\n"
        "ndE+1iU5nxaI+CUd8PKLGS8NWyzIMgsZqN5iY0zZnK1fo7XoK9hiPyiKOWqJJ/Vk\n"
        "5Av99PvM28yGm3LycCkWi5TGfknvXuoD2eyM0rETJs9bViQFGwrOXP7/BthCgHC5\n"
        "UjMpWZzfAgMBAAECggEAPxR8cCB3BMHuR4GpHwpr/kIVB70ZyfYNZrWbdL6bsl8W\n"
        "SMAr6k7D/kWnN15wzNRJXrq4qihvL1rhIvEql4TIRivR7aXLPkRBif3e9xxNtUFR\n"
        "3DBML692DZ9st0GLTj+Im5Wy5yeFnMR57wkUYwtFIFWBrXlSmWx4mvYrpRlRBANm\n"
        "OelJz4qmWvXy/OXzStCvjDPGFn3pPnnPkTNMYaMw8M67UnlVe6FZdvEZ6FO4njxr\n"
        "rVfOkAGitrGr0BFlCaWtoBm6jvfLht9u5R1j2USPz6FUHyCpWjrEiNEaaetJXNAM\n"
        "EmNahA0sz/gZZebVcPOQPDFENSAOTA8h7xeDX9TXuQKBgQDsytP07DOaKajqBy9o\n"
        "2GNFbPaWQz4trN3b5m5FQHijuQL/C5e/Xu6jRuFQy7edgn/q7EGa7cLRM/RFnWSH\n"
        "gSkk1XT2c5bCDsxwVWW/eVyFzmlW5/zvPJanU48z7NHL/kWsMlqM9GJkTrgZx6xJ\n"
        "eJZdDr6cchSjdhwA8/OXMj5FaQKBgQDkHmUcb+npWs9+EKdhw1zb09I2lcyQ9pcA\n"
        "h9tIHYv+ldpoz628q251IOtBoD/v27wYqtiK2GeOnxmfwerdEIkTz81G9zaJAXnR\n"
        "HKJeYkqVzsRB27uWTGkA1GANDmm59c9mM0rtRhYXqg83bc6/jOP+j0y98ZXUPM1O\n"
        "Y+93544fBwKBgQCe7vSdK/zmuJebnP8BTFw1ORG5gaC2X5T6CAxzhvZyTbfpIArW\n"
        "dA2Qof6RkGrJ2dGqCLFwH63nZQvLvfy/xr2q72r2EFdcITqvG2KTxg2H8idaIZPv\n"
        "r6ce4EL6AzY9yYlSLuoAOffgg8Wl6BOHrNyf0Um3EAsyPBBHw3X4QczyIQKBgQCR\n"
        "OlSOzSTy3lB45qtZTyIABZOwEqBAreymdteAyubEdqysy4LFObLBuOptRlNOJetT\n"
        "HPltM6aCIwISNkeK46sRRNtgUaSThrACFCO+yP7I7vD9KKH9Zrn2wD5CManXrQmT\n"
        "/BW4h0UrXaYAWNUmF9FSz/JAftwvWWIvhOoAwRc24wKBgFpAkYt8rfgqdz+yZszz\n"
        "lw/0l22eKKZER/kwmA3knLHnfBcSFEHu2L+jwVlCYcVpFo42eBXaiatwuoWipDtm\n"
        "/w15UUBEhcCan+6FslQovpavW+RBjqAHeEb5SNyu5QhF1PNkR1qwVqT/NyS3CDKV\n"
        "ICxkTP+66Iby89+X16sMt99d\n"
        "-----END PRIVATE KEY-----\n"
    ),
    "client_email": "backup-aio@erudite-phalanx-498720-b4.iam.gserviceaccount.com",
    "client_id": "110799607165422267310",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": (
        "https://www.googleapis.com/robot/v1/metadata/x509/"
        "backup-aio%40erudite-phalanx-498720-b4.iam.gserviceaccount.com"
    ),
    "universe_domain": "googleapis.com",
}

# ==============================================================================
# CONFIGURATION FROM config.json
# ==============================================================================

_get_resource_base = app_config.get_resource_base
_get_app_base = app_config.get_app_base
_resolve_asset = app_config.resolve_asset
_resolve_exe_path = app_config.resolve_exe_path
_load_config = app_config.load_config
_save_config = app_config.save_config
_get_startup_folder = startup.get_startup_folder
_get_startup_shortcut_path = startup.get_startup_shortcut_path
_get_legacy_startup_shortcut_path = startup.get_legacy_startup_shortcut_path
_remove_startup_shortcut = startup.remove_startup_shortcut
_escape_ps_single_quotes = startup.escape_ps_single_quotes
_configure_auto_start = startup.configure_auto_start
_get_confirm_token = update_helpers.get_confirm_token
_download_from_drive = update_helpers._download_file_from_drive
_validate_zip_file = update_helpers.validate_zip_file
_download_update_zip = update_helpers.download_update_zip
_sha256_file = update_helpers.sha256_file
_is_newer_version = update_helpers.is_newer_version
_check_for_update = update_helpers.check_for_update
_run_update_script = update_helpers.run_update_script
_send_post_update_notification = update_helpers.send_post_update_notification
_handle_exit_signal = update_helpers.handle_exit_signal

def _send_update_telegram_message(message: str):
    """Send update notification to Box 1 (synchronous, immediate)."""
    from backup_tool import telegram_reporting
    if TELEGRAM_UPDATE_TOKEN and TELEGRAM_UPDATE_CHAT_ID:
        success = telegram_reporting.send_telegram_message_sync(
            TELEGRAM_UPDATE_CHAT_ID,
            f"🚀 [ATLED SYSTEM UPDATE SUCCESS]\n{message}",
            TELEGRAM_UPDATE_TOKEN,
            "post_update"
        )
        logging.info(f"[BOX1] Post-update notification sent: {success}")
    else:
        logging.warning("[BOX1] Update token/chat_id not configured - notification skipped")

APP_DIR = app_config.APP_DIR
APP_VERSION = app_config.APP_VERSION
CONFIG_PATH = app_config.CONFIG_PATH
CREDENTIALS_PATH = app_config.CREDENTIALS_PATH
LOG_DIR = app_config.LOG_DIR
URL_DOWNLOAD_ZIP = app_config.URL_DOWNLOAD_ZIP
URL_VERSION_CHECK = app_config.URL_VERSION_CHECK
URL_DOWNLOAD_EXE = app_config.URL_DOWNLOAD_EXE
UPDATE_TEMP_NAME = app_config.UPDATE_TEMP_NAME
AUTO_UPDATE_INITIAL_DELAY_SECONDS = app_config.AUTO_UPDATE_INITIAL_DELAY_SECONDS
DEFAULT_CONFIG = app_config.DEFAULT_CONFIG
AUTO_START_ARG = app_config.AUTO_START_ARG
AUTO_UPDATED_ARG = app_config.AUTO_UPDATED_ARG
AUTO_MINIMIZED_ARG = app_config.AUTO_MINIMIZED_ARG
APP_STARTUP_NAME = app_config.APP_STARTUP_NAME
LEGACY_STARTUP_SHORTCUTS = app_config.LEGACY_STARTUP_SHORTCUTS
MAX_NETWORK_RETRIES = app_config.MAX_NETWORK_RETRIES
NETWORK_RETRY_DELAY_SECONDS = app_config.NETWORK_RETRY_DELAY_SECONDS
FILE_SETTLE_DELAY_SECONDS = app_config.FILE_SETTLE_DELAY_SECONDS
DAILY_REPORT_HOUR = app_config.DAILY_REPORT_HOUR
DAILY_REPORT_MINUTE = app_config.DAILY_REPORT_MINUTE
STALE_BACKUP_DAYS = app_config.STALE_BACKUP_DAYS
COMMAND_LOCK_FOLDER_NAME = app_config.COMMAND_LOCK_FOLDER_NAME
COMMAND_LOCK_RETENTION_DAYS = app_config.COMMAND_LOCK_RETENTION_DAYS
COMMAND_CLAIM_SETTLE_SECONDS = app_config.COMMAND_CLAIM_SETTLE_SECONDS

(
    STORE_NAME,
    WATCH_DIRECTORY,
    TELEGRAM_TOKEN,
    TELEGRAM_CHAT_ID,
    TELEGRAM_SYSTEM_TOKEN,
    TELEGRAM_SYSTEM_CHAT_ID,
    TELEGRAM_REPORT_TOKEN,
    TELEGRAM_REPORT_CHAT_ID,
    TELEGRAM_UPDATE_TOKEN,
    TELEGRAM_UPDATE_CHAT_ID,
    AUTO_START_ENABLED,
    AUTO_UPDATE_ENABLED,
    LAST_UPDATE_CHECK_DATE,
) = _load_config()


def _has_background_runtime_configuration() -> bool:
    return bool(STORE_NAME and WATCH_DIRECTORY)


def _is_started_from_registry() -> bool:
    """Check if app was started from Windows Registry Run key."""
    if AUTO_START_ARG not in sys.argv:
        return False

    exe_path = _resolve_exe_path()
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
        try:
            value, _ = winreg.QueryValueEx(key, "ATLED_BK")
            winreg.CloseKey(key)
            return exe_path.lower() in value.lower()
        except FileNotFoundError:
            winreg.CloseKey(key)
            return False
    except Exception:
        return False


def _ensure_auto_start_shortcut():
    startup.ensure_auto_start_shortcut(STORE_NAME, WATCH_DIRECTORY)


# ==============================================================================
# LOGGING
# ==============================================================================

os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(LOG_DIR, "backup.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8",
)

# ==============================================================================
# BACKUP HANDLERS (BACKGROUND WATCHDOG MODE)
# ==============================================================================

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import google_auth_httplib2
import httplib2
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account

# --- Google Drive helpers ----------------------------------------------------

_drive_service = None
_drive_service_lock = threading.Lock()
_drive_request_lock = threading.Lock()


def _is_retryable_http_error(error: HttpError) -> bool:
    status = getattr(getattr(error, "resp", None), "status", None)
    return status is None or status in {408, 429, 500, 502, 503, 504}


def _run_with_network_retries(action_name: str, operation):
    last_error = None
    for attempt in range(1, MAX_NETWORK_RETRIES + 1):
        try:
            return operation()
        except HttpError as e:
            last_error = e
            if not _is_retryable_http_error(e):
                logging.error(f"{action_name} failed with non-retryable HTTP error: {e}")
                raise
            logging.warning(
                f"{action_name} failed on attempt {attempt}/{MAX_NETWORK_RETRIES}: {e}"
            )
        except requests.RequestException as e:
            last_error = e
            logging.warning(
                f"{action_name} failed on attempt {attempt}/{MAX_NETWORK_RETRIES}: {e}"
            )

        if attempt < MAX_NETWORK_RETRIES:
            time.sleep(NETWORK_RETRY_DELAY_SECONDS)

    logging.error(f"{action_name} failed after {MAX_NETWORK_RETRIES} attempt(s): {last_error}")
    raise last_error


def _execute_drive_request(action_name: str, request_factory):
    with _drive_request_lock:
        return _run_with_network_retries(
            action_name,
            lambda: request_factory().execute(num_retries=0),
        )


def _initialize_drive_service():
    global _drive_service
    with _drive_service_lock:
        if _drive_service is not None:
            return _drive_service

        _drive_service = _build_drive_service()
        logging.info("Google Drive service initialized.")
        return _drive_service


def _get_drive_service():
    if _drive_service is None:
        raise RuntimeError("Google Drive service has not been initialized.")
    return _drive_service


def _build_drive_service():
    # Patch certifi path before building HTTP client to avoid
    # "invalid path: C:\Users\...\\_MEI....\certifi\cacert.pem" in frozen builds
    try:
        import certifi
        certifi_path = certifi.where()
        if certifi_path and os.path.exists(certifi_path):
            import urllib.request
            urllib.request.install_opener(
                urllib.request.build_opener(
                    urllib.request.HTTPSHandler(
                        context=ssl.create_default_context(
                            cafile=certifi_path,
                            capath=None,
                            cadata=None,
                        )
                    )
                )
            )
    except Exception:
        pass

    if os.path.exists(CREDENTIALS_PATH):
        creds = service_account.Credentials.from_service_account_file(
            CREDENTIALS_PATH,
            scopes=["https://www.googleapis.com/auth/drive.file"],
        )
    else:
        creds = service_account.Credentials.from_service_account_info(
            SERVICE_ACCOUNT_INFO,
            scopes=["https://www.googleapis.com/auth/drive.file"],
        )
    http = google_auth_httplib2.AuthorizedHttp(
        creds,
        http=httplib2.Http(timeout=15),
    )
    return build("drive", "v3", http=http, cache_discovery=False, num_retries=0)


def _find_or_create_store_folder(drive_service, store_name: str) -> str:
    results = _execute_drive_request(
        "Find Google Drive merchant folder",
        lambda: drive_service.files().list(
            q=(
                f"'{PARENT_FOLDER_ID}' in parents "
                f"and name='{store_name}' "
                f"and mimeType='application/vnd.google-apps.folder' "
                f"and trashed=false"
            ),
            fields="files(id, name)",
            pageSize=10,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ),
    )
    folders = results.get("files", [])
    if folders:
        logging.info(f"Google Drive folder found: {store_name}")
        return folders[0]["id"]
    file_metadata = {
        "name": store_name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [PARENT_FOLDER_ID],
    }
    new_folder = _execute_drive_request(
        "Create Google Drive merchant folder",
        lambda: drive_service.files().create(
            body=file_metadata, fields="id, name", supportsAllDrives=True
        ),
    )
    logging.info(f"Created new Google Drive folder: {store_name}")
    return new_folder["id"]


def _find_or_create_child_folder(drive_service, parent_folder_id: str, folder_name: str) -> str:
    results = _execute_drive_request(
        f"Find Google Drive folder ({folder_name})",
        lambda: drive_service.files().list(
            q=(
                f"'{parent_folder_id}' in parents "
                f"and name='{folder_name}' "
                "and mimeType='application/vnd.google-apps.folder' "
                "and trashed=false"
            ),
            fields="files(id, name, createdTime)",
            pageSize=10,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ),
    )
    folders = results.get("files", [])
    if folders:
        folders.sort(key=lambda item: (item.get("createdTime", ""), item.get("id", "")))
        return folders[0]["id"]

    metadata = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_folder_id],
    }
    new_folder = _execute_drive_request(
        f"Create Google Drive folder ({folder_name})",
        lambda: drive_service.files().create(
            body=metadata,
            fields="id, name, createdTime",
            supportsAllDrives=True,
        ),
    )
    time.sleep(COMMAND_CLAIM_SETTLE_SECONDS)
    results = _execute_drive_request(
        f"Refresh Google Drive folder contenders ({folder_name})",
        lambda: drive_service.files().list(
            q=(
                f"'{parent_folder_id}' in parents "
                f"and name='{folder_name}' "
                "and mimeType='application/vnd.google-apps.folder' "
                "and trashed=false"
            ),
            fields="files(id, name, createdTime)",
            pageSize=10,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ),
    )
    folders = results.get("files", []) or [new_folder]
    folders.sort(key=lambda item: (item.get("createdTime", ""), item.get("id", "")))
    return folders[0]["id"]


def _list_configured_merchant_folders(drive_service) -> list[str]:
    records = _list_configured_merchant_folder_records(drive_service)
    return sorted(
        {
            item["name"]
            for item in records
            if item["name"] != COMMAND_LOCK_FOLDER_NAME
        },
        key=lambda name: name.casefold(),
    )


def _list_configured_merchant_folder_records(drive_service) -> list[dict[str, str]]:
    folders: list[dict[str, str]] = []
    page_token = None

    while True:
        results = _execute_drive_request(
            "List configured merchant folders",
            lambda page_token=page_token: drive_service.files().list(
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
            ),
        )
        for item in results.get("files", []):
            folder_id = str(item.get("id", "")).strip()
            folder_name = str(item.get("name", "")).strip()
            if folder_id and folder_name and folder_name != COMMAND_LOCK_FOLDER_NAME:
                folders.append({"id": folder_id, "name": folder_name})
        page_token = results.get("nextPageToken")
        if not page_token:
            break

    return sorted(folders, key=lambda item: item["name"].casefold())


def _get_today_drive_query_bounds() -> tuple[str, str, str]:
    local_now = datetime.now().astimezone()
    local_tz = local_now.tzinfo
    today = local_now.date()
    local_start = datetime(today.year, today.month, today.day, tzinfo=local_tz)
    local_end = local_start + timedelta(days=1)
    utc_start = local_start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    utc_end = local_end.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return today.strftime("%Y-%m-%d"), utc_start, utc_end


def _get_recent_drive_query_bounds(days: int) -> tuple[str, str, str]:
    local_now = datetime.now().astimezone()
    local_tz = local_now.tzinfo
    today = local_now.date()
    local_start = datetime(today.year, today.month, today.day, tzinfo=local_tz) - timedelta(days=days - 1)
    local_end = datetime(today.year, today.month, today.day, tzinfo=local_tz) + timedelta(days=1)
    utc_start = local_start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    utc_end = local_end.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return today.strftime("%Y-%m-%d"), utc_start, utc_end


def _list_merchant_folder_ids_with_zip_today(
    drive_service,
    merchant_folder_ids: set[str],
    utc_start: str,
    utc_end: str,
) -> set[str]:
    backed_up_folder_ids: set[str] = set()
    page_token = None

    while True:
        results = _execute_drive_request(
            "List Google Drive backups uploaded today",
            lambda page_token=page_token: drive_service.files().list(
                q=(
                    "trashed=false "
                    "and name contains '.zip' "
                    f"and createdTime >= '{utc_start}' "
                    f"and createdTime < '{utc_end}'"
                ),
                fields="nextPageToken, files(id, name, parents, createdTime)",
                pageSize=1000,
                pageToken=page_token,
                corpora="allDrives",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            ),
        )
        for item in results.get("files", []):
            if not str(item.get("name", "")).lower().endswith(".zip"):
                continue
            for parent_id in item.get("parents", []):
                if parent_id in merchant_folder_ids:
                    backed_up_folder_ids.add(parent_id)

            if len(backed_up_folder_ids) == len(merchant_folder_ids):
                return backed_up_folder_ids

        page_token = results.get("nextPageToken")
        if not page_token:
            break

    return backed_up_folder_ids


def _list_merchant_folder_ids_with_zip_in_window(
    drive_service,
    merchant_folder_ids: set[str],
    utc_start: str,
    utc_end: str,
) -> set[str]:
    backed_up_folder_ids: set[str] = set()
    page_token = None

    while True:
        results = _execute_drive_request(
            "List Google Drive backups uploaded in date window",
            lambda page_token=page_token: drive_service.files().list(
                q=(
                    "trashed=false "
                    "and name contains '.zip' "
                    f"and createdTime >= '{utc_start}' "
                    f"and createdTime < '{utc_end}'"
                ),
                fields="nextPageToken, files(id, name, parents, createdTime)",
                pageSize=1000,
                pageToken=page_token,
                corpora="allDrives",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            ),
        )
        for item in results.get("files", []):
            if not str(item.get("name", "")).lower().endswith(".zip"):
                continue
            for parent_id in item.get("parents", []):
                if parent_id in merchant_folder_ids:
                    backed_up_folder_ids.add(parent_id)

            if len(backed_up_folder_ids) == len(merchant_folder_ids):
                return backed_up_folder_ids

        page_token = results.get("nextPageToken")
        if not page_token:
            break

    return backed_up_folder_ids


def _upload_zip_to_drive(drive_service, zip_path: str, store_folder_id: str) -> str:
    file_name = os.path.basename(zip_path)
    file_metadata = {"name": file_name, "parents": [store_folder_id]}

    def _create_upload_request():
        media = MediaFileUpload(zip_path, mimetype="application/zip", resumable=True)
        return drive_service.files().create(
            body=file_metadata,
            media_body=media,
            supportsAllDrives=True,
            fields="id, name",
        )

    uploaded = _execute_drive_request(
        f"Upload backup archive to Google Drive ({file_name})",
        _create_upload_request,
    )
    logging.info(f"Upload successful: {file_name}")
    return uploaded.get("id")


def _cleanup_old_backups(drive_service, store_folder_id: str):
    try:
        results = _execute_drive_request(
            "List Google Drive backups for retention cleanup",
            lambda: drive_service.files().list(
                q=(
                    f"'{store_folder_id}' in parents "
                    f"and trashed=false"
                ),
                fields="files(id, name, createdTime)",
                pageSize=1000,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            ),
        )
        files = [f for f in results.get("files", []) if f.get("name", "").lower().endswith(".zip")]
        if len(files) <= RETENTION_LIMIT:
            logging.info(f"Drive currently has {len(files)} zip backup(s), within the retention limit of {RETENTION_LIMIT}.")
            return
        files_sorted = sorted(files, key=lambda f: f.get("createdTime", ""))
        to_delete = files_sorted[: len(files_sorted) - RETENTION_LIMIT]
        logging.info(f"Drive currently has {len(files)} file(s) - keeping the newest {RETENTION_LIMIT} and deleting {len(to_delete)} older file(s).")
        for f in to_delete:
            try:
                _execute_drive_request(
                    f"Delete old Google Drive backup ({f['name']})",
                    lambda file_id=f["id"]: drive_service.files().delete(
                        fileId=file_id,
                        supportsAllDrives=True,
                    ),
                )
                logging.info(f"  Deleted old backup: {f['name']}")
            except Exception as ex:
                logging.warning(f"  Could not delete {f['name']}: {ex}")
    except Exception as e:
        logging.warning(f"Drive cleanup error: {e}")


def _delete_local_files(*paths: str):
    for path in paths:
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass


# --- Watchdog handler --------------------------------------------------------

class BakFileHandler(FileSystemEventHandler):
    def __init__(self, file_queue: queue.Queue):
        self._file_queue = file_queue
        self._processed: set[str] = set()
        self._lock = threading.Lock()

    def on_created(self, event):
        if event.is_directory or not event.src_path.lower().endswith(".bak"):
            return
        bak_path = event.src_path
        with self._lock:
            if bak_path in self._processed:
                return
            self._processed.add(bak_path)
        logging.info(f"New .bak file detected: {bak_path}")
        self._file_queue.put(bak_path)

    def release(self, bak_path: str):
        with self._lock:
            self._processed.discard(bak_path)


def _process_bak_file(
    bak_path: str,
    backup_dir: str,
    drive_service,
    store_name: str,
    critical_error_callback=None,
) -> bool:
    file_name = os.path.basename(bak_path)
    
    for attempt in range(20):
        try:
            time.sleep(2)
            s1 = os.path.getsize(bak_path)
            time.sleep(2)
            s2 = os.path.getsize(bak_path)
        except FileNotFoundError:
            return True
        except Exception as e:
            logging.warning(f"File stability check error (attempt {attempt+1}): {e}")
            continue
        if s1 == 0:
            return True
        if s1 != s2:
            continue
        try:
            with open(bak_path, "rb") as f:
                f.read(1)
        except (IOError, OSError, PermissionError):
            continue
        break
    else:
        logging.error(f"File remained unstable after 40 seconds: {bak_path}")
        _send_backup_failure_notification(store_name, file_name, "File remained unstable after 40 seconds")
        return False

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    zip_name = f"{store_name}_{timestamp}.zip"
    zip_path = os.path.join(backup_dir, zip_name)

    try:
        with open(bak_path, "rb") as f_in, zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(os.path.basename(bak_path), f_in.read())
        time.sleep(2)
        if os.path.getsize(zip_path) < 1024:
            os.remove(zip_path)
            _send_backup_failure_notification(store_name, file_name, "ZIP file too small after compression")
            return False
        logging.info(f"Compressed file created: {zip_path}")
    except Exception as e:
        logging.error(f"Compression error: {e}")
        if os.path.exists(zip_path):
            try:
                os.remove(zip_path)
            except Exception:
                pass
        _send_backup_failure_notification(store_name, file_name, f"Compression failed: {str(e)[:100]}")
        if critical_error_callback:
            critical_error_callback("Backup Error", f"Archive compression failed.\n\nDetails: {e}")
        return False

    try:
        folder_id = _find_or_create_store_folder(drive_service, store_name)
        _upload_zip_to_drive(drive_service, zip_path, folder_id)
        _cleanup_old_backups(drive_service, folder_id)
    except Exception as e:
        logging.error(f"Google Drive upload error: {e}")
        _send_backup_failure_notification(store_name, file_name, f"Google Drive upload failed: {str(e)[:100]}")
        if critical_error_callback:
            critical_error_callback("Backup Error", f"Google Drive upload failed after retry attempts.\n\nDetails: {e}")
        return False

    _delete_local_files(bak_path, zip_path)
    logging.info(f"Backup completed for: {store_name}")
    _send_backup_success_notification(store_name, file_name, zip_path)
    return True


# --- Background mode entry point --------------------------------------------

_watchdog_active = False


def _emit_or_log_critical(callback, title: str, message: str):
    logging.error(f"{title}: {message}")
    if callback:
        callback(title, message)


def _run_watchdog_loop(
    backup_dir: str,
    store_name: str,
    drive_service,
    should_stop_callback,
    status_callback=None,
    critical_error_callback=None,
):
    logging.info(f"Watchdog started - monitoring: {backup_dir}")
    print(f"[WATCHDOG] Monitoring: {backup_dir}")
    if not os.path.isdir(backup_dir):
        _emit_or_log_critical(
            critical_error_callback,
            "Backup Directory Error",
            f"Directory does not exist:\n{backup_dir}",
        )
        return

    file_queue: queue.Queue[str] = queue.Queue()
    handler = BakFileHandler(file_queue)
    observer = Observer()
    observer.schedule(handler, backup_dir, recursive=False)
    observer.start()
    logging.info("Watchdog observer is running.")

    if status_callback:
        status_callback(f"Backup monitor active - watching: {backup_dir}")

    try:
        while not should_stop_callback():
            try:
                bak_path = file_queue.get(timeout=1)
            except queue.Empty:
                continue

            try:
                logging.info(f"Queued .bak file for processing: {bak_path}")
                if status_callback:
                    status_callback(f"Processing backup file: {os.path.basename(bak_path)}")
                time.sleep(FILE_SETTLE_DELAY_SECONDS)
                _process_bak_file(
                    bak_path,
                    backup_dir,
                    drive_service,
                    store_name,
                    critical_error_callback=critical_error_callback,
                )
            except Exception as e:
                logging.error(f"Backup worker error for {bak_path}: {e}")
                _emit_or_log_critical(
                    critical_error_callback,
                    "Backup Error",
                    f"Background backup worker failed.\n\nDetails: {e}",
                )
            finally:
                handler.release(bak_path)
                file_queue.task_done()

    finally:
        observer.stop()
        observer.join()
        logging.info("Watchdog observer stopped.")
        if status_callback:
            status_callback("Backup monitor stopped.")


def run_watchdog(backup_dir: str):
    global _watchdog_active
    _watchdog_active = True
    store_name = STORE_NAME or os.path.basename(os.path.normpath(backup_dir))
    drive_service = _initialize_drive_service()
    _run_watchdog_loop(
        backup_dir,
        store_name,
        drive_service,
        should_stop_callback=lambda: not _watchdog_active,
    )


def stop_watchdog():
    global _watchdog_active
    _watchdog_active = False


# ==============================================================================
# UPDATE MECHANISM - ZIP WORKFLOW
# ==============================================================================

_update_in_progress = False


def _send_backup_success_notification(store_name: str, file_name: str, zip_path: str):
    """Send backup success notification to Box 2."""
    try:
        message = (
            f"✅ [ATLED BACKUP SUCCESS]\n"
            f"🏪 Merchant: {store_name}\n"
            f"📁 File: {file_name}\n"
            f"🕐 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"💾 Status: Backup uploaded to Google Drive successfully!"
        )
        if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
            telegram_reporting.send_telegram_message_async(
                TELEGRAM_CHAT_ID,
                message,
                TELEGRAM_TOKEN,
                "backup_success"
            )
            logging.info(f"[BOX2] Backup success notification sent for {store_name}")
            print(f"[BOX2_SUCCESS] Backup notification sent: {store_name}")
        else:
            logging.warning("[BOX2] Backup success notification skipped - token or chat_id empty")
    except Exception as e:
        logging.error(f"[BOX2] Failed to send backup success notification: {e}")
        print(f"[BOX2_ERROR] Failed to send backup success notification: {e}")


def _send_backup_failure_notification(store_name: str, file_name: str, error_message: str):
    """Send backup failure notification to Box 2."""
    try:
        message = (
            f"❌ [ATLED BACKUP FAILED]\n"
            f"🏪 Merchant: {store_name}\n"
            f"📁 File: {file_name}\n"
            f"🕐 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"⚠️ Error: {error_message[:200]}"
        )
        if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
            telegram_reporting.send_telegram_message_async(
                TELEGRAM_CHAT_ID,
                message,
                TELEGRAM_TOKEN,
                "backup_failure"
            )
            logging.info(f"[BOX2] Backup failure notification sent for {store_name}")
            print(f"[BOX2_FAILURE] Backup failure notification sent: {store_name} - {error_message[:50]}")
        else:
            logging.warning("[BOX2] Backup failure notification skipped - token or chat_id empty")
    except Exception as e:
        logging.error(f"[BOX2] Failed to send backup failure notification: {e}")
        print(f"[BOX2_ERROR] Failed to send backup failure notification: {e}")


def _send_system_online_notification(store_name: str = None, watch_directory: str = None):
    """Send app online notification to Box 4 with full merchant info."""
    resolved_store = store_name if store_name is not None else STORE_NAME
    resolved_watch = watch_directory if watch_directory is not None else WATCH_DIRECTORY
    try:
        message = (
            f"🟢 [ATLED APP ONLINE]\n"
            f"🖥️ Host: {os.environ.get('COMPUTERNAME', 'Unknown')}\n"
            f"👤 User: {os.environ.get('USERNAME', 'Unknown')}\n"
            f"🏪 Merchant: {resolved_store or '[Not configured]'}\n"
            f"📂 Watch: {resolved_watch or '[Not configured]'}\n"
            f"🕐 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"📦 Version: v{APP_VERSION}"
        )
        if TELEGRAM_SYSTEM_TOKEN and TELEGRAM_SYSTEM_CHAT_ID:
            telegram_reporting.send_telegram_message_async(
                TELEGRAM_SYSTEM_CHAT_ID,
                message,
                TELEGRAM_SYSTEM_TOKEN,
                "system_online"
            )
            logging.info("[BOX4] System online notification sent")
            print("[BOX4_ONLINE] App online notification sent")
        else:
            logging.warning("[BOX4] System online notification skipped - token or chat_id empty")
    except Exception as e:
        logging.error(f"[BOX4] Failed to send system online notification: {e}")
        print(f"[BOX4_ERROR] Failed to send system online notification: {e}")


def _send_system_offline_notification():
    """Send app offline notification to Box 4."""
    try:
        message = (
            f"🔴 [ATLED APP OFFLINE]\n"
            f"🖥️ Host: {os.environ.get('COMPUTERNAME', 'Unknown')}\n"
            f"👤 User: {os.environ.get('USERNAME', 'Unknown')}\n"
            f"🏪 Merchant: {STORE_NAME or '[Not configured]'}\n"
            f"🕐 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"📦 Version: v{APP_VERSION}"
        )
        if TELEGRAM_SYSTEM_TOKEN and TELEGRAM_SYSTEM_CHAT_ID:
            telegram_reporting.send_telegram_message_async(
                TELEGRAM_SYSTEM_CHAT_ID,
                message,
                TELEGRAM_SYSTEM_TOKEN,
                "system_offline"
            )
            logging.info("[BOX4] System offline notification sent")
            print("[BOX4_OFFLINE] App offline notification sent")
        else:
            logging.warning("[BOX4] System offline notification skipped - token or chat_id empty")
    except Exception as e:
        logging.error(f"[BOX4] Failed to send system offline notification: {e}")
        print(f"[BOX4_ERROR] Failed to send system offline notification: {e}")


def _send_update_started_notification(trigger: str):
    store_name = STORE_NAME or "[Unknown store]"
    message = (
        "🔄 [UPDATE] Update Starting\n"
        f"Version: v{APP_VERSION}\n"
        f"Trigger: {trigger}\n"
        f"Merchant: {store_name}\n"
        f"Status: App is closing to install the new build."
    )
    logging.info(message)


def _send_update_failure_notification(stage: str, details: str):
    logging.error(f"Update failed at stage '{stage}': {details}")


atexit.register(lambda: logging.info("App exited"))
for sig in (signal.SIGINT, signal.SIGTERM):
    try:
        signal.signal(sig, _handle_exit_signal)
    except Exception:
        pass


# ==============================================================================
# GLOBAL EMERGENCY SHUTDOWN HANDLER - ATEXIT FOR PC SHUTDOWN/CRASH
# ==============================================================================

def _emergency_offline_notification():
    """
    CRITICAL: Send OFFLINE notification to Bot 4 when app is terminated unexpectedly.
    This handles:
    - PC shutdown/hibernate
    - Force kill (Ctrl+C, taskkill)
    - Uncaught exceptions
    - System crash
    """
    try:
        # Read config directly to get fresh values
        from backup_tool import app_config
        cfg = app_config._read_json_config(app_config.CONFIG_PATH)
        
        system_token = cfg.get("TELEGRAM_SYSTEM_TOKEN", "") or ""
        system_chat_id = cfg.get("TELEGRAM_SYSTEM_CHAT_ID", "") or ""
        
        if not system_token or not system_chat_id:
            logging.warning("[EMERGENCY_SHUTDOWN] No Bot 4 config - skipping offline notification")
            return
        
        logging.info("[EMERGENCY_SHUTDOWN] Sending OFFLINE notification (SYNC) to Bot 4...")
        
        message = (
            f"⚠️ [ATLED APP OFFLINE]\n"
            f"🖥️ Host: {os.environ.get('COMPUTERNAME', 'Unknown')}\n"
            f"👤 User: {os.environ.get('USERNAME', 'Unknown')}\n"
            f"🏪 Merchant: {cfg.get('STORE_NAME', '[Not configured]')}\n"
            f"🕐 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"📦 Version: v{app_config.APP_VERSION}\n"
            f"⚠️ Reason: App terminated unexpectedly (PC shutdown/crash/kill)."
        )
        
        # Use requests directly for synchronous send (no queue, no threading)
        import requests
        url = f"https://api.telegram.org/bot{system_token}/sendMessage"
        response = requests.post(
            url,
            data={
                "chat_id": system_chat_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=10,
            verify=False,
        )
        if response.status_code == 200:
            logging.info("[EMERGENCY_SHUTDOWN] OFFLINE notification sent successfully!")
        else:
            logging.warning(f"[EMERGENCY_SHUTDOWN] Failed to send OFFLINE: HTTP {response.status_code}")
    except Exception as e:
        logging.error(f"[EMERGENCY_SHUTDOWN] Error sending OFFLINE notification: {e}")


def _cleanup_on_exit():
    """
    Global cleanup function registered with atexit.
    Called when Python interpreter is shutting down.
    """
    try:
        logging.info("[ATEXIT] App shutdown initiated via atexit")
        
        # Send OFFLINE notification to Bot 4
        _emergency_offline_notification()
        
        # Stop all telegram workers to prevent 409
        try:
            from backup_tool import telegram_reporting
            telegram_reporting.stop_sender()
            telegram_reporting.stop_daily_report_sender()
            logging.info("[ATEXIT] Telegram workers stopped")
        except Exception as e:
            logging.error(f"[ATEXIT] Error stopping Telegram workers: {e}")
        
        logging.info("[ATEXIT] Cleanup complete - forcing exit")
        
        # Force immediate exit - no cleanup, no flush
        import os
        os._exit(0)
    except Exception:
        pass


# Register the emergency exit handler
atexit.register(_cleanup_on_exit)


# ==============================================================================
# GUI - PYQT6
# ==============================================================================

from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QFileDialog,
    QSystemTrayIcon,
    QMenu,
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap, QIcon, QPainter, QAction, QColor


class BackupWatchdogThread(QThread):
    ready = pyqtSignal(str)
    status_changed = pyqtSignal(str)
    critical_error = pyqtSignal(str, str)
    stopped = pyqtSignal()

    def __init__(self, store_name: str, backup_dir: str):
        super().__init__()
        self._store_name = store_name
        self._backup_dir = backup_dir

    def run(self):
        try:
            self.status_changed.emit("Initializing Google Drive service...")
            drive_service = _initialize_drive_service()
            self.ready.emit(self._backup_dir)
            logging.info(f"System activated - Store: {self._store_name}, Directory: {self._backup_dir}")
            _run_watchdog_loop(
                self._backup_dir,
                self._store_name,
                drive_service,
                should_stop_callback=self.isInterruptionRequested,
                status_callback=self.status_changed.emit,
                critical_error_callback=self.critical_error.emit,
            )
        except Exception as e:
            logging.error(f"Watchdog thread failed: {e}")
            self.critical_error.emit(
                "Backup Monitor Error",
                f"The backup monitor could not be started or has stopped unexpectedly.\n\nDetails: {e}",
            )
        finally:
            self.stopped.emit()


class AutoUpdateCheckThread(QThread):
    """
    Auto-update thread that handles BOTH:
    1. Auto-check (startup) - with 20s delay and date check
    2. Manual check (tray menu) - no delay, no date check
    """
    update_ready = pyqtSignal(str)  # zip_path
    check_finished = pyqtSignal(str, bool)  # status, is_latest
    check_failed = pyqtSignal(str)
    stopped = pyqtSignal()

    def __init__(self, initial_delay_seconds: int = AUTO_UPDATE_INITIAL_DELAY_SECONDS, manual_check: bool = False):
        super().__init__()
        self._initial_delay_seconds = initial_delay_seconds
        self._manual_check = manual_check

    def _wait_initial_delay(self):
        if self._manual_check:
            return
        deadline = time.time() + self._initial_delay_seconds
        while not self.isInterruptionRequested() and time.time() < deadline:
            time.sleep(1)

    def run(self):
        global LAST_UPDATE_CHECK_DATE
        try:
            logging.info(f"Update check started. manual_check={self._manual_check}")

            if not AUTO_UPDATE_ENABLED and not self._manual_check:
                logging.info("Auto-update check skipped: feature is disabled.")
                self.check_finished.emit("Auto-update feature is disabled.", False)
                return

            exe_path = _resolve_exe_path()
            if not exe_path.lower().endswith(".exe"):
                logging.info("Update check skipped: not running from .exe file.")
                self.check_finished.emit("Not running from .exe file.", False)
                return

            if not self._manual_check:
                logging.info(f"Waiting {self._initial_delay_seconds}s before checking for update...")
                self._wait_initial_delay()
                if self.isInterruptionRequested():
                    logging.info("Update check interrupted.")
                    return

                today = datetime.now().astimezone().strftime("%Y-%m-%d")
                logging.info(f"Today: {today}, Last check date: {LAST_UPDATE_CHECK_DATE}")
                if LAST_UPDATE_CHECK_DATE == today:
                    logging.info(f"Auto-update check already completed for {today}.")
                    self.check_finished.emit("Already checked today.", True)
                    return

            has_update, status = _check_for_update()

            if not self._manual_check:
                _save_config(
                    STORE_NAME,
                    WATCH_DIRECTORY,
                    last_update_check_date=datetime.now().astimezone().strftime("%Y-%m-%d"),
                )
                LAST_UPDATE_CHECK_DATE = datetime.now().astimezone().strftime("%Y-%m-%d")

            logging.info(f"Update check result: has_update={has_update}, status={status}")

            if has_update:
                import tempfile
                zip_path = os.path.join(tempfile.gettempdir(), UPDATE_TEMP_NAME)
                success, msg = _download_update_zip(URL_DOWNLOAD_ZIP, zip_path)
                if success:
                    logging.info(f"Update ZIP ready: {zip_path}")
                    self.update_ready.emit(zip_path)
                else:
                    logging.warning(f"Failed to download update ZIP: {msg}")
                    self.check_finished.emit(f"Download failed: {msg}", False)
            else:
                self.check_finished.emit(status, True)

        except Exception as e:
            logging.error(f"Update check failed with exception: {e}")
            self.check_failed.emit(str(e))
        finally:
            self.stopped.emit()


class ManualUpdateCheckThread(QThread):
    """
    Manual update check triggered from System Tray menu.
    No delay, no date check, immediate version check on Drive.
    """
    update_available = pyqtSignal(str, str)  # version, zip_path
    no_update = pyqtSignal(str)
    check_failed = pyqtSignal(str)
    stopped = pyqtSignal()

    def run(self):
        try:
            logging.info("Manual update check started")
            has_update, status = _check_for_update()

            if has_update:
                import tempfile
                zip_path = os.path.join(tempfile.gettempdir(), UPDATE_TEMP_NAME)
                success, msg = _download_update_zip(URL_DOWNLOAD_ZIP, zip_path)
                if success:
                    version_config = update_helpers.download_version_config()
                    version = version_config.get('version', 'unknown') if version_config else 'unknown'
                    self.update_available.emit(version, zip_path)
                else:
                    self.check_failed.emit(f"Download failed: {msg}")
            else:
                self.no_update.emit(status)

        except Exception as e:
            logging.error(f"Manual update check failed: {e}")
            self.check_failed.emit(str(e))
        finally:
            self.stopped.emit()


class TelegramCommandListenerThread(QThread):
    command_ready = pyqtSignal(str, int, str)

    def run(self):
        update_offset = None

        while not self.isInterruptionRequested():
            try:
                updates = telegram_reporting.get_telegram_updates(
                    update_offset,
                    TELEGRAM_REPORT_TOKEN
                )

                for update in updates:
                    update_id = update.get("update_id")
                    message = update.get("message", {})
                    chat = message.get("chat", {})
                    chat_id = str(chat.get("id", ""))
                    text = message.get("text", "").strip()

                    if text.startswith("/"):
                        allowed = telegram_reporting.get_allowed_command_chat_ids(TELEGRAM_REPORT_CHAT_ID)
                        if chat_id in allowed:
                            self.command_ready.emit(text, update_id, chat_id)
                            logging.info(f"Telegram command received: {text} from {chat_id}")

                    update_offset = update_id + 1

            except Exception as e:
                logging.warning(f"Telegram command listener error: {e}")

            time.sleep(3)


class BackupConfigWindow(QWidget):
    WINDOW_TITLE = f"ATLED BK - SETUP v{APP_VERSION}"
    FIXED_WIDTH = 600
    FIXED_HEIGHT = 520

    def __init__(self, start_hidden: bool = False, auto_updated: bool = False):
        super().__init__()
        self._exe_path = _resolve_exe_path()
        self._bg_path = _resolve_asset("background.jpg")
        self._window_icon = self._load_window_icon()
        self._watchdog_thread: BackupWatchdogThread | None = None
        self._auto_update_thread: AutoUpdateCheckThread | None = None
        self._manual_update_thread: ManualUpdateCheckThread | None = None
        self._telegram_command_thread: TelegramCommandListenerThread | None = None
        self._running = False
        self._tray_icon: QSystemTrayIcon | None = None
        self._tray_message_shown = False
        self._is_quitting = False
        self._start_hidden = start_hidden
        self._auto_updated = auto_updated

        self._init_ui()
        self._setup_system_tray()
        self._load_from_config()

        if auto_updated:
            logging.info("App was just updated. Sending post-update notification.")
            _send_post_update_notification(
                APP_VERSION,
                STORE_NAME,
                WATCH_DIRECTORY,
                lambda msg: _send_update_telegram_message(msg),
            )

        if start_hidden and _has_background_runtime_configuration():
            logging.info("Starting in background mode (hidden)")
            QTimer.singleShot(100, self._start_background_mode)
        elif start_hidden:
            logging.info("Started hidden but no runtime config - will show setup window")
        else:
            self.show()

    def _start_background_mode(self):
        """Start monitoring in background mode without showing window."""
        if _has_background_runtime_configuration():
            self._start_monitoring(STORE_NAME, WATCH_DIRECTORY, show_ready_dialog=False)
            self._start_telegram_command_listener()
            telegram_reporting.start_daily_report_sender()
            # Send ONLINE notification with full merchant info
            _send_system_online_notification(STORE_NAME, WATCH_DIRECTORY)
            if self._auto_updated:
                logging.info("Skipping auto-update check after restart (auto_updated mode)")
                return
            self._start_auto_update_checker()

    def paintEvent(self, event):
        painter = QPainter(self)
        if os.path.exists(self._bg_path):
            pixmap = QPixmap(self._bg_path)
            painter.drawPixmap(self.rect(), pixmap)
        else:
            painter.fillRect(self.rect(), Qt.GlobalColor.white)

    def _load_window_icon(self) -> QIcon:
        for icon_path in (_resolve_asset("app_icon.ico"), _resolve_asset("app_icon.png"), _resolve_asset("app.png")):
            if not os.path.exists(icon_path):
                continue
            icon = QIcon(icon_path)
            if not icon.isNull():
                return icon
        return self._create_fallback_icon()

    def _create_fallback_icon(self) -> QIcon:
        icon_size = 256
        pixmap = QPixmap(icon_size, icon_size)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#0f172a"))
        painter.drawEllipse(8, 8, icon_size - 16, icon_size - 16)
        painter.setBrush(QColor("#22c55e"))
        painter.drawEllipse(28, 28, icon_size - 56, icon_size - 56)
        painter.setBrush(QColor("#ffffff"))
        painter.drawRoundedRect(86, 62, 84, 132, 18, 18)
        painter.drawRoundedRect(66, 92, 124, 18, 9, 9)
        painter.drawRoundedRect(66, 126, 124, 18, 9, 9)
        painter.drawRoundedRect(66, 160, 92, 18, 9, 9)
        painter.end()

        return QIcon(pixmap)

    def _setup_system_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            logging.warning("System tray is not available on this machine.")
            return

        self._tray_icon = QSystemTrayIcon(self)
        tray_icon = self._window_icon
        if tray_icon.isNull():
            tray_icon = self._create_fallback_icon()
        self._tray_icon.setIcon(tray_icon)
        self._window_icon = tray_icon
        self._tray_icon.setToolTip("ATLED BK")

        tray_menu = QMenu(self)
        open_action = QAction("Open", self)
        open_action.triggered.connect(self._restore_from_tray)
        tray_menu.addAction(open_action)

        update_action = QAction("Update", self)
        update_action.triggered.connect(self._on_update)
        tray_menu.addAction(update_action)

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self._exit_application)
        tray_menu.addAction(exit_action)

        self._tray_icon.setContextMenu(tray_menu)
        self._tray_icon.activated.connect(self._on_tray_activated)
        self._tray_icon.show()

    def _on_tray_activated(self, reason):
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._restore_from_tray()

    def _restore_from_tray(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _start_monitoring(self, store_name: str, backup_dir: str, show_ready_dialog: bool = True):
        if self._watchdog_thread and self._watchdog_thread.isRunning():
            return

        self._show_ready_dialog = show_ready_dialog
        self._running = True
        self._activate_btn.setEnabled(False)
        self._activate_btn.setText("Starting...")
        self._browse_btn.setEnabled(False)
        self._store_input.setEnabled(False)
        self._status_label.setText(f"Starting backup monitor for: {backup_dir}")
        self._status_label.setStyleSheet(
            "QLabel#statusLabel { background-color: rgba(0,0,0,50); padding: 6px 10px; border-radius: 4px; color: #f59e0b; font-weight: bold; }"
        )
        self.repaint()

        self._watchdog_thread = BackupWatchdogThread(store_name, backup_dir)
        self._watchdog_thread.ready.connect(self._on_watchdog_ready)
        self._watchdog_thread.status_changed.connect(self._on_watchdog_status_changed)
        self._watchdog_thread.critical_error.connect(self._on_watchdog_critical_error)
        self._watchdog_thread.stopped.connect(self._on_watchdog_stopped)
        self._watchdog_thread.start()

    def _stop_monitoring_thread(self):
        self._stop_telegram_command_listener()
        if self._watchdog_thread and self._watchdog_thread.isRunning():
            self._watchdog_thread.requestInterruption()
            self._watchdog_thread.wait(30000)

    def _start_auto_update_checker(self):
        if self._auto_update_thread and self._auto_update_thread.isRunning():
            return
        self._auto_update_thread = AutoUpdateCheckThread(manual_check=False)
        self._auto_update_thread.update_ready.connect(self._on_auto_update_ready)
        self._auto_update_thread.check_finished.connect(self._on_auto_update_finished)
        self._auto_update_thread.check_failed.connect(self._on_auto_update_failed)
        self._auto_update_thread.stopped.connect(self._on_auto_update_stopped)
        self._auto_update_thread.start()

    def _stop_auto_update_checker(self):
        if self._auto_update_thread and self._auto_update_thread.isRunning():
            self._auto_update_thread.requestInterruption()
            self._auto_update_thread.wait(30000)

    def _start_telegram_command_listener(self):
        if self._telegram_command_thread and self._telegram_command_thread.isRunning():
            return
        self._telegram_command_thread = TelegramCommandListenerThread()
        self._telegram_command_thread.command_ready.connect(self._on_telegram_command)
        self._telegram_command_thread.start()

    def _stop_telegram_command_listener(self):
        if self._telegram_command_thread and self._telegram_command_thread.isRunning():
            self._telegram_command_thread.requestInterruption()
            self._telegram_command_thread.wait(30000)

    def _on_telegram_command(self, command: str, update_id: int, chat_id: str):
        def send_msg(msg_chat_id: str, text: str):
            telegram_reporting.send_telegram_message(
                msg_chat_id,
                text,
                TELEGRAM_REPORT_TOKEN,
                _run_with_network_retries,
            )

        command_lower = command.lower()
        logging.info(f"Processing command: {command} from chat {chat_id}")

        if command_lower in ("/help", "/start"):
            send_msg(chat_id, (
                "📖 ATLED BK - Available Commands\n\n"
                "• /link  - Download link for ATLED BK app\n"
                "• /list  - List all configured merchants\n"
                "• /check - Check backup status for all merchants\n"
                "• /help  - Show this help message\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "🚀 ATLED BK v" + APP_VERSION + "\n"
                "Automated Backup System"
            ))

        elif command_lower == "/link":
            send_msg(chat_id, (
                "🔗 ATLED BK - Download Link\n\n"
                "📥 Direct EXE Download:\n"
                f"→ {URL_DOWNLOAD_EXE}\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "Contact support for access."
            ))

        elif command_lower == "/list":
            telegram_reporting.send_configured_merchants_list(
                chat_id,
                _initialize_drive_service,
                _list_configured_merchant_folders,
                send_msg,
            )

        elif command_lower == "/check":
            telegram_reporting.send_stale_backup_check(
                chat_id,
                _initialize_drive_service,
                _get_recent_drive_query_bounds,
                _list_configured_merchant_folder_records,
                _list_merchant_folder_ids_with_zip_in_window,
                send_msg,
            )

        else:
            send_msg(chat_id, (
                "⚠️ Unknown command.\n"
                "Send /help for available commands."
            ))

    def _reset_monitoring_ui(self):
        self._running = False
        self._browse_btn.setEnabled(True)
        self._store_input.setEnabled(True)
        self._activate_btn.setEnabled(True)
        self._activate_btn.setText("ENABLE SYNC")
        self._status_label.setText("Monitoring Not Active")
        self._status_label.setStyleSheet(
            "QLabel#statusLabel { background-color: rgba(0,0,0,50); padding: 6px 10px; border-radius: 4px; color: #e0e0e0; font-weight: 600; }"
        )

    def _on_watchdog_ready(self, backup_dir: str):
        self._status_label.setText(f"Backup monitor active - watching: {backup_dir}")
        self._status_label.setStyleSheet(
            "QLabel#statusLabel { background-color: rgba(0,0,0,50); padding: 6px 10px; border-radius: 4px; color: #22c55e; font-weight: bold; }"
        )
        self._activate_btn.setText("MONITORING")
        self._activate_btn.setEnabled(False)
        if getattr(self, "_show_ready_dialog", True) and self._tray_icon:
            self._tray_icon.showMessage(
                "ATLED BK",
                "The application is now running in the background and monitoring backup files. "
                "Use the system tray icon to reopen it.",
                QSystemTrayIcon.MessageIcon.Information,
                4000,
            )
        if getattr(self, "_show_ready_dialog", True) and self.isVisible():
            QMessageBox.information(
                self,
                "Success",
                "Real-time monitoring has been activated successfully.\n\n"
                f"Merchant: {STORE_NAME}\n"
                f"Directory: {backup_dir}\n\n"
                "Whenever a new .bak file appears, the tool will compress it and upload it to Google Drive.\n\n"
                "The app will keep running until you click Done or close the window, at which point it will hide to the system tray.",
            )

    def _on_watchdog_status_changed(self, text: str):
        self._status_label.setText(text)

    def _on_watchdog_critical_error(self, title: str, message: str):
        self._status_label.setText("Backup monitor error")
        self._status_label.setStyleSheet(
            "QLabel#statusLabel { background-color: rgba(0,0,0,50); padding: 6px 10px; border-radius: 4px; color: #ef4444; font-weight: bold; }"
        )
        QMessageBox.critical(self, title, message)

    def _on_watchdog_stopped(self):
        self._watchdog_thread = None
        if not self._is_quitting:
            self._reset_monitoring_ui()

    def _on_auto_update_ready(self, zip_path: str):
        """Handle auto-update ready signal - apply update and restart."""
        global _update_in_progress
        logging.info(f"[SIGNAL] _on_auto_update_ready received with path: {zip_path}")
        restart_background = _has_background_runtime_configuration()

        if _run_update_script(zip_path, restart_background=restart_background):
            _update_in_progress = True
            _send_update_started_notification("Automatic")
            logging.info("Update script launched successfully, app will exit now")

            # CRITICAL: Stop all Telegram workers to prevent 409 conflict
            self._stop_telegram_command_listener()
            telegram_reporting.stop_sender()
            telegram_reporting.stop_daily_report_sender()

            if self._running:
                self._stop_monitoring_thread()

            if self._tray_icon:
                self._tray_icon.hide()

            self._is_quitting = True
            self.close()
            QTimer.singleShot(300, lambda: QApplication.instance().quit())
        else:
            logging.error("Failed to launch update script")
            _send_update_failure_notification(
                "Launch installer",
                "The update package was downloaded but the installer script could not be started.",
            )

    def _on_auto_update_finished(self, status: str, is_latest: bool):
        logging.info(f"[SIGNAL] _on_auto_update_finished: status={status}, is_latest={is_latest}")

    def _on_auto_update_failed(self, error_message: str):
        logging.warning(f"[SIGNAL] _on_auto_update_failed: {error_message}")
        _send_update_failure_notification("Check update", error_message)

    def _on_auto_update_stopped(self):
        logging.info("[SIGNAL] _on_auto_update_stopped")
        self._auto_update_thread = None

    def _on_update(self):
        """Manual update from tray menu - check version and show appropriate message."""
        if not _resolve_exe_path().lower().endswith(".exe"):
            if self._tray_icon:
                self._tray_icon.showMessage(
                    "ATLED BK",
                    "The update feature is only available when the application is running from the packaged .exe file.",
                    QSystemTrayIcon.MessageIcon.Information,
                    5000,
                )
            return

        if self._manual_update_thread and self._manual_update_thread.isRunning():
            return

        self._manual_update_thread = ManualUpdateCheckThread()
        self._manual_update_thread.update_available.connect(self._on_manual_update_available)
        self._manual_update_thread.no_update.connect(self._on_manual_no_update)
        self._manual_update_thread.check_failed.connect(self._on_manual_update_failed)
        self._manual_update_thread.stopped.connect(self._on_manual_update_stopped)
        self._manual_update_thread.start()

    def _on_manual_update_available(self, version: str, zip_path: str):
        """Manual update found - ask user and apply."""
        answer = QMessageBox.question(
            self,
            "Update Available",
            f"A new version ({version}) is available.\n\n"
            "Download and install now? The application will restart automatically.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        if _run_update_script(zip_path, restart_background=_has_background_runtime_configuration()):
            global _update_in_progress
            _update_in_progress = True
            _send_update_started_notification("Manual tray update")
            logging.info("Manual update: script launched, app will exit")

            # CRITICAL: Stop all Telegram workers to prevent 409 conflict
            self._stop_telegram_command_listener()
            telegram_reporting.stop_sender()
            telegram_reporting.stop_daily_report_sender()

            if self._running:
                self._stop_monitoring_thread()

            if self._tray_icon:
                self._tray_icon.hide()

            self._is_quitting = True
            self.close()
            QTimer.singleShot(300, lambda: QApplication.instance().quit())

    def _on_manual_no_update(self, status: str):
        """User is on latest version - show balloon tip."""
        logging.info(f"Manual check: {status}")
        if self._tray_icon:
            self._tray_icon.showMessage(
                "ATLED BK",
                "You are running the latest version!",
                QSystemTrayIcon.MessageIcon.Information,
                5000,
            )

    def _on_manual_update_failed(self, error: str):
        """Manual update check failed."""
        logging.error(f"Manual update check failed: {error}")
        if self._tray_icon:
            self._tray_icon.showMessage(
                "ATLED BK",
                "Update check failed:\n{error}",
                QSystemTrayIcon.MessageIcon.Warning,
                5000,
            )

    def _on_manual_update_stopped(self):
        self._manual_update_thread = None

    def _hide_to_tray(self):
        if self._tray_icon and self._tray_icon.icon().isNull():
            self._tray_icon.setIcon(self._create_fallback_icon())
        self.hide()
        if self._tray_icon and not self._tray_message_shown:
            self._tray_icon.showMessage(
                "ATLED BK",
                "The application is still running in the background. Click the system tray icon to reopen it.",
                QSystemTrayIcon.MessageIcon.Information,
                4000,
            )
            self._tray_message_shown = True

    def _exit_application(self):
        self._is_quitting = True
        self._stop_auto_update_checker()
        self._stop_monitoring_thread()
        
        # CRITICAL: Stop all Telegram workers FIRST to prevent 409 conflict
        self._stop_telegram_command_listener()
        telegram_reporting.stop_sender()
        telegram_reporting.stop_daily_report_sender()
        
        logging.info("App exiting via user request")
        
        # CRITICAL: Send OFFLINE notification SYNC to Bot 4 BEFORE closing window
        if TELEGRAM_SYSTEM_TOKEN and TELEGRAM_SYSTEM_CHAT_ID:
            logging.info("[BOX4] Sending OFFLINE notification (SYNC) via _exit_application...")
            try:
                message = (
                    f"⚠️ [ATLED APP OFFLINE]\n"
                    f"🖥️ Host: {os.environ.get('COMPUTERNAME', 'Unknown')}\n"
                    f"👤 User: {os.environ.get('USERNAME', 'Unknown')}\n"
                    f"🏪 Merchant: {STORE_NAME or '[Not configured]'}\n"
                    f"🕐 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"📦 Version: v{APP_VERSION}\n"
                    f"⚠️ Reason: App closed by user."
                )
                # Use synchronous send - MUST complete before process dies
                telegram_reporting.send_telegram_message_sync(
                    TELEGRAM_SYSTEM_CHAT_ID,
                    message,
                    TELEGRAM_SYSTEM_TOKEN,
                    "system_offline_sync"
                )
                logging.info("[BOX4] OFFLINE notification sent (SYNC) - safe to exit")
            except Exception as e:
                logging.error(f"[BOX4] Failed to send OFFLINE notification: {e}")
        
        if self._tray_icon:
            self._tray_icon.hide()
        self.close()

    def _init_ui(self):
        self.setWindowTitle(self.WINDOW_TITLE)
        self.setFixedSize(self.FIXED_WIDTH, self.FIXED_HEIGHT)
        self.setStyleSheet(self._get_stylesheet())
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        if not self._window_icon.isNull():
            self.setWindowIcon(self._window_icon)

        main_layout = QVBoxLayout()
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(20, 16, 20, 20)

        logo_path = _resolve_asset("app.png")
        if os.path.exists(logo_path):
            logo_layout = QHBoxLayout()
            logo_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            logo_label = QLabel()
            logo_label.setObjectName("logoLabel")
            logo_pixmap = QPixmap(logo_path)
            logo_label.setPixmap(logo_pixmap.scaled(
                260, 130,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
            logo_layout.addWidget(logo_label)
            main_layout.addLayout(logo_layout)

        step1_label = QLabel("Step 1: Merchant Name")
        step1_label.setObjectName("stepLabel")
        main_layout.addWidget(step1_label)

        self._store_input = QLineEdit()
        self._store_input.setPlaceholderText("Enter the merchant name exactly as shown in Asana")
        self._store_input.textChanged.connect(self._on_fields_changed)
        main_layout.addWidget(self._store_input)

        step2_label = QLabel("Step 2: Select Backup Directory")
        step2_label.setObjectName("stepLabel")
        main_layout.addWidget(step2_label)

        path_layout = QHBoxLayout()
        path_layout.setSpacing(8)

        self._path_input = QLineEdit()
        self._path_input.setPlaceholderText("C:\\ATLED\\BK")
        self._path_input.setReadOnly(True)
        self._path_input.textChanged.connect(self._on_fields_changed)

        self._browse_btn = QPushButton("Browse...")
        self._browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._browse_btn.clicked.connect(self._on_browse)

        path_layout.addWidget(self._path_input, stretch=1)
        path_layout.addWidget(self._browse_btn)
        main_layout.addLayout(path_layout)

        step3_label = QLabel("Step 3: Activate Monitoring")
        step3_label.setObjectName("stepLabel")
        main_layout.addWidget(step3_label)

        self._activate_btn = QPushButton("ENABLE SYNC")
        self._activate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._activate_btn.setObjectName("step2Btn")
        self._activate_btn.clicked.connect(self._on_activate)
        self._activate_btn.setEnabled(False)
        main_layout.addWidget(self._activate_btn)

        main_layout.addStretch()

        self._status_label = QLabel("Monitoring Not Active")
        self._status_label.setObjectName("statusLabel")
        main_layout.addWidget(self._status_label)

        version_layout = QHBoxLayout()
        version_layout.addStretch()
        version_label = QLabel(f"App Version: v{APP_VERSION}")
        version_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        version_label.setStyleSheet("color: #000000; font-size: 11px; font-weight: 600;")
        version_layout.addWidget(version_label)
        main_layout.addLayout(version_layout)

        self._done_btn = QPushButton("Done")
        self._done_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._done_btn.setObjectName("doneBtn")
        self._done_btn.clicked.connect(self._on_done_clicked)
        main_layout.addWidget(self._done_btn)

        self.setLayout(main_layout)

    def _load_from_config(self):
        if STORE_NAME:
            self._store_input.setText(STORE_NAME)
        if WATCH_DIRECTORY:
            self._path_input.setText(WATCH_DIRECTORY)
        self._on_fields_changed()

    def _on_fields_changed(self):
        store_ok = bool(self._store_input.text().strip())
        path_ok = bool(self._path_input.text().strip())
        self._activate_btn.setEnabled(store_ok and path_ok)

    def _on_browse(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select the folder that contains BAK files",
            self._path_input.text() or os.expanduser("~"),
            QFileDialog.Option.ShowDirsOnly,
        )
        if folder:
            self._path_input.setText(folder)

    def _on_activate(self):
        store_name = self._store_input.text().strip()
        backup_dir = self._path_input.text().strip()

        if not store_name:
            QMessageBox.warning(self, "Missing Information", "Please enter the merchant name.")
            return
        if not backup_dir:
            QMessageBox.warning(self, "Missing Information", "Please select a backup folder.")
            return
        if not os.path.isdir(backup_dir):
            QMessageBox.critical(self, "Error", f"Directory does not exist:\n{backup_dir}")
            return

        _save_config(store_name, backup_dir, auto_start_enabled=True)

        global STORE_NAME, WATCH_DIRECTORY, AUTO_START_ENABLED
        STORE_NAME = store_name
        WATCH_DIRECTORY = backup_dir
        AUTO_START_ENABLED = True

        try:
            _configure_auto_start(True)
        except Exception as e:
            logging.warning(f"Auto-start could not be enabled: {e}")
            QMessageBox.warning(
                self,
                "Warning",
                "Your settings were saved, but Windows auto-start could not be enabled.\n"
                f"Details: {e}",
            )

        try:
            _initialize_drive_service()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Backup Error",
                f"Google Drive service could not be initialized.\n\nDetails: {e}",
            )
            return

        self._start_monitoring(store_name, backup_dir)
        self._start_auto_update_checker()
        self._start_telegram_command_listener()
        # Send ONLINE notification with full merchant info
        _send_system_online_notification(store_name, backup_dir)

    def _on_done_clicked(self):
        if self._running:
            self._hide_to_tray()
            return
        self.close()

    def closeEvent(self, event):
        logging.info(f"closeEvent called, is_quitting={self._is_quitting}, running={self._running}")
        
        # CRITICAL: Before anything else, stop all Telegram workers to prevent 409 conflict
        self._stop_telegram_command_listener()
        self._stop_auto_update_checker()
        self._stop_monitoring_thread()
        telegram_reporting.stop_daily_report_sender()
        
        # CRITICAL: Send OFFLINE notification SYNC to Bot 4 BEFORE any shutdown
        if TELEGRAM_SYSTEM_TOKEN and TELEGRAM_SYSTEM_CHAT_ID:
            logging.info("[BOX4] Sending OFFLINE notification (SYNC) before exit...")
            try:
                message = (
                    f"⚠️ [ATLED APP OFFLINE]\n"
                    f"🖥️ Host: {os.environ.get('COMPUTERNAME', 'Unknown')}\n"
                    f"👤 User: {os.environ.get('USERNAME', 'Unknown')}\n"
                    f"🏪 Merchant: {STORE_NAME or '[Not configured]'}\n"
                    f"🕐 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"📦 Version: v{APP_VERSION}\n"
                    f"⚠️ Reason: App closed or PC shutdown/hibernate."
                )
                # Use synchronous send - MUST complete before process dies
                telegram_reporting.send_telegram_message_sync(
                    TELEGRAM_SYSTEM_CHAT_ID,
                    message,
                    TELEGRAM_SYSTEM_TOKEN,
                    "system_offline_sync"
                )
                logging.info("[BOX4] OFFLINE notification sent (SYNC) - safe to exit")
            except Exception as e:
                logging.error(f"[BOX4] Failed to send OFFLINE notification: {e}")
        
        if self._is_quitting:
            logging.info("App is quitting, accepting close event")
            event.accept()
            return
        if self._running:
            self._hide_to_tray()
            event.ignore()
            return
        event.accept()

    @staticmethod
    def _get_stylesheet() -> str:
        return """
        QWidget {
            background-color: transparent;
            font-family: 'Segoe UI', sans-serif;
            font-size: 13px;
            color: #ffffff;
        }
        QLabel#logoLabel {
            border: none;
            background-color: transparent;
        }
        QLabel#stepLabel {
            font-weight: 700;
            color: #ffffff;
            font-size: 14px;
            background-color: rgba(0, 0, 0, 90);
            padding: 4px 10px;
            border-radius: 4px;
        }
        QLabel#statusLabel {
            font-weight: 600;
            font-size: 12px;
            background-color: rgba(0, 0, 0, 50);
            padding: 6px 10px;
            border-radius: 4px;
            color: #e0e0e0;
        }
        QLineEdit {
            background-color: rgba(255, 255, 255, 180);
            color: #1e1e2e;
            border: 1px solid rgba(255, 255, 255, 100);
            border-radius: 6px;
            padding: 6px 10px;
            selection-background-color: #cba6f7;
        }
        QLineEdit:focus {
            border: 1px solid #cba6f7;
        }
        QPushButton {
            background-color: rgba(69, 71, 90, 200);
            color: #ffffff;
            border: none;
            border-radius: 6px;
            padding: 7px 14px;
            font-weight: 600;
        }
        QPushButton:hover {
            background-color: rgba(88, 91, 112, 220);
        }
        QPushButton:pressed {
            background-color: rgba(49, 50, 68, 220);
        }
        QPushButton:disabled {
            background-color: rgba(49, 50, 68, 150);
            color: rgba(255, 255, 255, 80);
        }
        QPushButton#step2Btn {
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #a855f7, stop:1 #6366f1);
            color: #ffffff;
            font-size: 15px;
            padding: 12px;
            border-radius: 8px;
            font-weight: 700;
        }
        QPushButton#step2Btn:hover {
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #b87af8, stop:1 #7477f2);
        }
        QPushButton#step2Btn:pressed {
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #9333ea, stop:1 #4f46e5);
        }
        QPushButton#doneBtn {
            background-color: rgba(17, 24, 39, 220);
            color: #ffffff;
            border: 1px solid rgba(255, 255, 255, 140);
        }
        QPushButton#doneBtn:hover {
            background-color: rgba(31, 41, 55, 235);
            color: #ffffff;
        }
        """


def launch_gui(start_hidden: bool = False, auto_updated: bool = False):
    telegram_reporting.start_sender()
    telegram_reporting.start_daily_report_sender()
    app = QApplication(sys.argv)
    app.setApplicationName("ATLED BK")
    _ensure_auto_start_shortcut()

    window = BackupConfigWindow(start_hidden=start_hidden, auto_updated=auto_updated)
    
    sys.exit(app.exec())


# ==============================================================================
# PROGRAM ENTRY POINT - HIDDEN BACKGROUND STARTUP
# ==============================================================================

if __name__ == "__main__":
    telegram_reporting.start_sender()
    telegram_reporting.start_daily_report_sender()
    auto_start_mode = AUTO_START_ARG in sys.argv
    auto_updated_mode = AUTO_UPDATED_ARG in sys.argv
    auto_minimized_mode = AUTO_MINIMIZED_ARG in sys.argv

    logging.info(f"App starting: auto_start={auto_start_mode}, auto_updated={auto_updated_mode}, auto_minimized={auto_minimized_mode}")

    if auto_start_mode:
        if not STORE_NAME or not WATCH_DIRECTORY:
            logging.error("Missing configuration for Windows background startup.")
            launch_gui(start_hidden=False, auto_updated=auto_updated_mode)
        else:
            logging.info(f"Starting in background mode - Store: {STORE_NAME}, Directory: {WATCH_DIRECTORY}")
            launch_gui(start_hidden=True, auto_updated=auto_updated_mode)
    elif auto_minimized_mode:
        logging.info("Starting in minimized mode (after update)")
        launch_gui(start_hidden=True, auto_updated=auto_updated_mode)
    else:
        launch_gui(start_hidden=False, auto_updated=auto_updated_mode)
