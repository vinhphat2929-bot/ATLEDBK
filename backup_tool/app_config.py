import json
import os
import re
import sys
import urllib3


def parse_version(version_str: str) -> tuple:
    """Parse version string like 'v1.0.7' or '1.0.7' into comparable tuple."""
    version_str = version_str.strip().lstrip('vV')
    parts = re.split(r'[\.\-_]', version_str)
    result = []
    for part in parts:
        match = re.match(r'^(\d+)', part)
        if match:
            result.append(int(match.group(1)))
        else:
            result.append(0)
    while len(result) < 3:
        result.append(0)
    return tuple(result[:3])


def is_newer_version(drive_version: str, current_version: str) -> bool:
    """Check if drive_version > current_version using semantic version comparison."""
    drive_v = parse_version(drive_version)
    current_v = parse_version(current_version)
    return drive_v > current_v


def get_resource_base() -> str:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_app_base() -> str:
    # Fixed location in C:\ATLED\ - never changes
    return r"C:\ATLED"


def resolve_asset(filename: str) -> str:
    """Resolve asset path - uses fixed C:\ATLED\assets\ if available, otherwise falls back to bundled."""
    fixed_path = os.path.join(ATLED_DIR, "assets", filename)
    if os.path.exists(fixed_path):
        return fixed_path
    bundled_path = os.path.join(get_resource_base(), "assets", filename)
    if os.path.exists(bundled_path):
        return bundled_path
    return fixed_path


def resolve_exe_path() -> str:
    if getattr(sys, "frozen", False):
        return os.path.abspath(sys.executable)
    return os.path.abspath(sys.argv[0])


# Fixed installation directory
ATLED_DIR = r"C:\ATLED"
ATLED_EXE_NAME = "ATLED_BK.exe"
ATLED_EXE_PATH = os.path.join(ATLED_DIR, ATLED_EXE_NAME)

# Alias for backward compatibility with existing code
APP_DIR = ATLED_DIR
APP_VERSION = "1.0.9"
CONFIG_PATH = os.path.join(APP_DIR, "config.json")
CREDENTIALS_PATH = os.path.join(APP_DIR, "credentials.json")
LOG_DIR = os.path.join(APP_DIR, "logs")

UPDATE_VERSION_FILE_ID = "YOUR_VERSION_FILE_ID"
UPDATE_ZIP_FILE_ID = "YOUR_ZIP_FILE_ID"
EXE_DIRECT_DOWNLOAD_ID = "YOUR_EXE_FILE_ID"

# Direct download URLs (Dropbox)
URL_DOWNLOAD_ZIP = "https://www.dropbox.com/scl/fi/yato6wqngpgqqahtlygse/update.zip?rlkey=dg4xie639qemoun0xorq40a4u&st=mjopafhf&dl=1"
URL_VERSION_CHECK = "https://www.dropbox.com/scl/fi/tpp2kdrxg0it6uiv8m3wv/version.json?rlkey=t8z7vusamwpfowc40vrfnvnz8&st=s79h33vs&dl=1"
URL_DOWNLOAD_EXE = "https://www.dropbox.com/scl/fi/bt4fmb66t1sfgmdihgqqs/ATLED_BK.exe?rlkey=5udjbeaqsxr1wpp70d8ew36ln&st=6c3mdvtz&dl=1"
UPDATE_TEMP_NAME = "update.zip"  # Ten file ZIP tam thoi
UPDATE_EXE_EXTRACTED_NAME = "ATLED_BK.exe"  # Ten file exe ben trong ZIP
UPDATE_EXE_TEMP_NAME = "ATLED_BK_NEW.exe"  # Ten file exe tam (tranh Permission Denied khi extract)
AUTO_UPDATE_INITIAL_DELAY_SECONDS = 20

DEFAULT_CONFIG = {
    "STORE_NAME": "",
    "WATCH_DIRECTORY": "C:/ATLED/BK",
    # Box 2: Daily backup success notifications
    "TELEGRAM_TOKEN": "8617754004:AAE0wNcUtJPg4HI0wH1peotyLkgXkYiklFg",
    "TELEGRAM_CHAT_ID": "-5256646090",
    # Box 4: New install / offline detection
    "TELEGRAM_SYSTEM_TOKEN": "8759922361:AAHSTyqiH-_vzjK-jBBD_Zn-E5pPKF9zqxw",
    "TELEGRAM_SYSTEM_CHAT_ID": "-5164973240",
    # Box 3: Daily report + bot commands (/list, /check, /link, /help)
    "TELEGRAM_REPORT_TOKEN": "8736119995:AAHF-YDtwpS59N8j-o9SjL7SP7oPGpiJAkE",
    "TELEGRAM_REPORT_CHAT_ID": "-3955550032",
    # Box 1: Auto-update success notification
    "TELEGRAM_UPDATE_TOKEN": "8655662127:AAE3eXBlKJeG25PoWJWtRz50ZD6JCoQgDnU",
    "TELEGRAM_UPDATE_CHAT_ID": "-5270541132",
    "AUTO_START_ENABLED": False,
    "AUTO_UPDATE_ENABLED": False,  # Disabled - manual update only
    "LAST_UPDATE_CHECK_DATE": "",
}

AUTO_START_ARG = "--background"
AUTO_UPDATED_ARG = "--auto-updated"
AUTO_MINIMIZED_ARG = "--minimized"
APP_STARTUP_NAME = "ATLED_BK.lnk"
LEGACY_STARTUP_SHORTCUTS = (
    "ATLED BK.lnk",
    "ATLED POS Backup.lnk",
    "ATLED BACKUP.lnk",
    "ATLED_BACKUP.lnk",
)

# Windows Registry for auto-start (HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run)
REGISTRY_STARTUP_KEY_NAME = "ATLED_BK"
REGISTRY_RUN_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"

MAX_NETWORK_RETRIES = 3
NETWORK_RETRY_DELAY_SECONDS = 15
FILE_SETTLE_DELAY_SECONDS = 3
TELEGRAM_POLL_API_TIMEOUT_SECONDS = 5  # Keep short for fast interrupt during update
TELEGRAM_HTTP_TIMEOUT_SECONDS = 15
TELEGRAM_MESSAGE_LIMIT = 4096
TELEGRAM_SAFE_MESSAGE_LIMIT = 3800
DAILY_REPORT_HOUR = 23
DAILY_REPORT_MINUTE = 55
# Chỉ máy nào có hostname này mới gửi daily report (tránh trùng lặp khi cài nhiều máy)
DAILY_REPORT_HOSTNAME = "DESKTOP-JVHR1D2"
STALE_BACKUP_DAYS = 3
COMMAND_LOCK_FOLDER_NAME = "_ATLED_TELEGRAM_COMMAND_LOCKS"
COMMAND_LOCK_RETENTION_DAYS = 7
COMMAND_CLAIM_SETTLE_SECONDS = 2

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _read_json_config(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _merge_config_values(base: dict, incoming: dict) -> dict:
    merged = dict(base)
    for key in DEFAULT_CONFIG:
        if key not in incoming:
            continue
        value = incoming[key]
        if isinstance(value, str):
            value = value.strip()
            if value:
                merged[key] = value
        elif value is not None:
            merged[key] = value
    return merged


def _config_has_runtime_values(cfg: dict) -> bool:
    return bool(str(cfg.get("STORE_NAME", "")).strip()) and bool(str(cfg.get("WATCH_DIRECTORY", "")).strip())


def load_config():
    os.makedirs(APP_DIR, exist_ok=True)
    cfg = dict(DEFAULT_CONFIG)

    config_candidates = []
    resource_config = os.path.join(get_resource_base(), "config.json")
    legacy_root_config = os.path.join(os.path.dirname(APP_DIR), "config.json")

    for candidate in (resource_config, legacy_root_config, CONFIG_PATH):
        if candidate not in config_candidates and os.path.exists(candidate):
            config_candidates.append(candidate)

    for candidate in config_candidates:
        cfg = _merge_config_values(cfg, _read_json_config(candidate))

    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)
    except Exception:
        pass

    return (
        cfg.get("STORE_NAME", "").strip(),
        cfg.get("WATCH_DIRECTORY", "").strip(),
        cfg.get("TELEGRAM_TOKEN", "").strip(),
        cfg.get("TELEGRAM_CHAT_ID", "").strip(),
        cfg.get("TELEGRAM_SYSTEM_TOKEN", "").strip(),
        cfg.get("TELEGRAM_SYSTEM_CHAT_ID", "").strip(),
        cfg.get("TELEGRAM_REPORT_TOKEN", "").strip(),
        cfg.get("TELEGRAM_REPORT_CHAT_ID", "").strip(),
        cfg.get("TELEGRAM_UPDATE_TOKEN", "").strip(),
        cfg.get("TELEGRAM_UPDATE_CHAT_ID", "").strip(),
        bool(cfg.get("AUTO_START_ENABLED", False)),
        bool(cfg.get("AUTO_UPDATE_ENABLED", True)),
        cfg.get("LAST_UPDATE_CHECK_DATE", "").strip(),
    )


def save_config(
    store_name: str,
    watch_directory: str,
    telegram_token: str | None = None,
    telegram_chat_id: str | None = None,
    telegram_system_token: str | None = None,
    telegram_system_chat_id: str | None = None,
    telegram_report_token: str | None = None,
    telegram_report_chat_id: str | None = None,
    telegram_update_token: str | None = None,
    telegram_update_chat_id: str | None = None,
    auto_start_enabled: bool | None = None,
    auto_update_enabled: bool | None = None,
    last_update_check_date: str | None = None,
):
    os.makedirs(APP_DIR, exist_ok=True)
    try:
        cfg = _read_json_config(CONFIG_PATH)
    except Exception:
        cfg = dict(DEFAULT_CONFIG)
    if not cfg:
        cfg = dict(DEFAULT_CONFIG)
    cfg["STORE_NAME"] = store_name
    cfg["WATCH_DIRECTORY"] = watch_directory
    if telegram_token is not None:
        cfg["TELEGRAM_TOKEN"] = telegram_token
    if telegram_chat_id is not None:
        cfg["TELEGRAM_CHAT_ID"] = telegram_chat_id
    if telegram_system_token is not None:
        cfg["TELEGRAM_SYSTEM_TOKEN"] = telegram_system_token
    if telegram_system_chat_id is not None:
        cfg["TELEGRAM_SYSTEM_CHAT_ID"] = telegram_system_chat_id
    if telegram_report_token is not None:
        cfg["TELEGRAM_REPORT_TOKEN"] = telegram_report_token
    if telegram_report_chat_id is not None:
        cfg["TELEGRAM_REPORT_CHAT_ID"] = telegram_report_chat_id
    if telegram_update_token is not None:
        cfg["TELEGRAM_UPDATE_TOKEN"] = telegram_update_token
    if telegram_update_chat_id is not None:
        cfg["TELEGRAM_UPDATE_CHAT_ID"] = telegram_update_chat_id
    if auto_start_enabled is not None:
        cfg["AUTO_START_ENABLED"] = auto_start_enabled
    if auto_update_enabled is not None:
        cfg["AUTO_UPDATE_ENABLED"] = auto_update_enabled
    if last_update_check_date is not None:
        cfg["LAST_UPDATE_CHECK_DATE"] = last_update_check_date
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4, ensure_ascii=False)
