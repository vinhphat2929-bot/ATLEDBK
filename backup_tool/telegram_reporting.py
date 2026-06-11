import html
import json
import logging
import os
import queue
import re
import threading
import time
from datetime import datetime, timedelta, timezone

import requests

from . import app_config

# ============================================================================
# TELEGRAM TOKEN VALIDATION & DEBUGGING
# ============================================================================

def _debug_print_tokens(token1, chat_id1, token2, chat_id2, token3, chat_id3, token4, chat_id4):
    """Debug function to print all telegram tokens status."""
    try:
        print("\n" + "="*60)
        print("[TELEGRAM_DEBUG] Checking Telegram Token Status v1.0.28")
        print("="*60)

        tokens = [
            ("Box 2 (Backup: thanh cong/loi realtime)", token1, chat_id1),
            ("Box 4 (System: Online/Offline realtime)", token2, chat_id2),
            ("Box 3 (Report: daily + bot commands)", token3, chat_id3),
            ("Box 1 (Update: thanh cong/loi/phien ban)", token4, chat_id4),
        ]

        for name, token, chat_id in tokens:
            token_ok = bool(token and len(token) > 10)
            chat_ok = bool(chat_id and len(chat_id) > 0)
            print(f"  {name}:")
            print(f"    - Token: {'OK (' + token[:8] + '...' + ')' if token_ok else 'EMPTY/NULL'}")
            print(f"    - ChatID: {'OK (' + str(chat_id) + ')' if chat_ok else 'EMPTY/NULL'}")
            print(f"    - Status: {'READY' if token_ok and chat_ok else 'NOT CONFIGURED'}")
            print()

        print("="*60 + "\n")
    except Exception:
        pass
    return tokens

def _validate_token_for_sending(token: str, chat_id: str, label: str) -> bool:
    """Validate token and chat_id before sending. Returns True if valid."""
    if not token:
        print(f"[TELEGRAM_ERROR] {label}: Token is EMPTY/NULL!")
        logging.error(f"[TELEGRAM_ERROR] {label}: Token is EMPTY/NULL - cannot send message")
        return False
    if len(token) < 10:
        print(f"[TELEGRAM_ERROR] {label}: Token too short ('{token}')")
        logging.error(f"[TELEGRAM_ERROR] {label}: Token appears invalid (too short)")
        return False
    if not chat_id:
        print(f"[TELEGRAM_ERROR] {label}: Chat ID is EMPTY/NULL!")
        logging.error(f"[TELEGRAM_ERROR] {label}: Chat ID is EMPTY/NULL - cannot send message")
        return False
    return True


# Background sender thread — all Telegram API calls run off the main thread.
_sender_queue: queue.Queue[tuple[str, str, str, str] | None] = queue.Queue()
_sender_running = False
_sender_thread: threading.Thread | None = None
_daily_report_thread: threading.Thread | None = None
_daily_report_running = False


def _telegram_sender_worker():
    """Worker thread that pulls send requests from the queue and calls the API serially."""
    print("[TELEGRAM_WORKER] Sender worker thread started")
    logging.info("[TELEGRAM_WORKER] Sender worker thread started")
    
    while True:
        try:
            item = _sender_queue.get()
            if item is None:
                print("[TELEGRAM_WORKER] Received stop signal, shutting down")
                logging.info("[TELEGRAM_WORKER] Sender worker received stop signal")
                break
            
            chat_id, message, token, label = item
            
            print(f"[TELEGRAM_WORKER] Processing message for {label} to chat_id={chat_id}")
            logging.info(f"[TELEGRAM_WORKER] Processing message for {label} to chat_id={chat_id}")
            
            # Validate before sending
            if not _validate_token_for_sending(token, chat_id, label):
                print(f"[TELEGRAM_ERROR] Skipping send for {label} - validation failed")
                logging.error(f"[TELEGRAM_ERROR] Skipping send for {label} - token/chat_id validation failed")
                continue
            
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            print(f"[TELEGRAM_DEBUG] Sending to URL: https://api.telegram.org/bot{token[:8]}.../sendMessage")

            def _post():
                try:
                    response = requests.post(
                        url,
                        data={
                            "chat_id": chat_id,
                            "text": message,
                            "parse_mode": "HTML",
                            "disable_web_page_preview": True,
                        },
                        timeout=app_config.TELEGRAM_HTTP_TIMEOUT_SECONDS,
                        verify=False,
                    )
                    if response.status_code == 200:
                        logging.info(f"Telegram notification sent to {chat_id} ({label}).")
                        print(f"[TELEGRAM_SUCCESS] Message sent successfully to {chat_id} ({label})")
                        return True
                    if response.status_code in (429,) or response.status_code >= 500:
                        raise requests.RequestException(
                            f"Telegram retryable HTTP {response.status_code}: {response.text[:200]}"
                        )
                    logging.warning(f"Telegram error {response.status_code}: {response.text[:200]}")
                    print(f"[TELEGRAM_WARNING] HTTP {response.status_code}: {response.text[:200]}")
                    return False
                except requests.exceptions.ConnectionError as e:
                    print(f"[TELEGRAM_ERROR] Connection error for {label}: {e}")
                    raise requests.RequestException(f"Connection error: {e}")
                except requests.exceptions.Timeout as e:
                    print(f"[TELEGRAM_ERROR] Timeout error for {label}: {e}")
                    raise requests.RequestException(f"Timeout error: {e}")

            try:
                _run_with_network_retries_sync(label, _post)
            except Exception as e:
                logging.warning(f"Telegram send failed after retries ({label}): {e}")
                print(f"[TELEGRAM_ERROR] Send failed after retries for {label}: {e}")
                
        except Exception as e:
            logging.error(f"[TELEGRAM_ERROR] Unexpected error in sender worker: {e}")
            print(f"[TELEGRAM_ERROR] Unexpected error in sender worker: {e}")


def _run_with_network_retries_sync(label: str, fn):
    for attempt in range(app_config.MAX_NETWORK_RETRIES):
        try:
            if fn():
                return True
        except requests.RequestException as e:
            if attempt == app_config.MAX_NETWORK_RETRIES - 1:
                raise
            logging.warning(f"{label} attempt {attempt + 1} failed: {e}. Retrying...")
            print(f"[TELEGRAM_RETRY] {label} attempt {attempt + 1} failed: {e}. Retrying...")
            time.sleep(app_config.NETWORK_RETRY_DELAY_SECONDS)
        except Exception as e:
            if attempt == app_config.MAX_NETWORK_RETRIES - 1:
                raise
            logging.warning(f"{label} attempt {attempt + 1} failed: {e}. Retrying...")
            print(f"[TELEGRAM_RETRY] {label} attempt {attempt + 1} failed: {e}. Retrying...")
            time.sleep(app_config.NETWORK_RETRY_DELAY_SECONDS)
    return False


def _daily_report_worker():
    """Worker thread that sends daily report at scheduled time."""
    import schedule
    import atexit as _atexit
    
    print("[DAILY_REPORT] Daily report worker thread started")
    logging.info("[DAILY_REPORT] Daily report worker thread started")
    
    # Import config at runtime
    from . import app_config
    cfg = app_config._read_json_config(app_config.CONFIG_PATH)
    
    report_token = cfg.get("TELEGRAM_REPORT_TOKEN", "") or ""
    report_chat_id = cfg.get("TELEGRAM_REPORT_CHAT_ID", "") or ""
    
    print(f"[DAILY_REPORT] Config: token={'OK' if report_token else 'EMPTY'}, chat_id={report_chat_id}")
    
    while _daily_report_running:
        try:
            # Run daily report check every minute
            now = datetime.now()
            
            # Check if it's time for daily report (default: 02:00)
            if now.hour == app_config.DAILY_REPORT_HOUR and now.minute == app_config.DAILY_REPORT_MINUTE:
                print("[DAILY_REPORT] Time for daily report!")
                logging.info("[DAILY_REPORT] Triggering daily report")
                
                if not report_token or not report_chat_id:
                    print("[DAILY_REPORT_ERROR] Cannot send daily report - token or chat_id is empty!")
                    logging.error("[DAILY_REPORT_ERROR] Cannot send daily report - token or chat_id is empty!")
                else:
                    try:
                        # Call generate_daily_report
                        result = generate_daily_report(
                            initialize_drive_service=_get_initialize_drive_service(),
                            get_today_drive_query_bounds=_get_today_drive_query_bounds(),
                            list_configured_merchant_folder_records=_get_list_configured_merchant_folder_records(),
                            list_merchant_folder_ids_with_zip_today=_get_list_merchant_folder_ids_with_zip_today(),
                            report_chat_id=report_chat_id,
                            send_message=lambda cid, msg: send_telegram_message_async(cid, msg, report_token, "daily_report"),
                        )
                        print(f"[DAILY_REPORT] Report sent: {result}")
                        logging.info(f"[DAILY_REPORT] Daily report completed: {result}")
                    except Exception as e:
                        print(f"[DAILY_REPORT_ERROR] Failed to generate/send daily report: {e}")
                        logging.error(f"[DAILY_REPORT_ERROR] Failed to generate/send daily report: {e}")
            
            time.sleep(60)  # Check every minute
            
        except Exception as e:
            print(f"[DAILY_REPORT_ERROR] Unexpected error in daily report worker: {e}")
            logging.error(f"[DAILY_REPORT_ERROR] Unexpected error in daily report worker: {e}")
            time.sleep(60)


# Placeholder functions - will be set by main.py
_initialize_drive_service_func = None
_get_today_drive_query_bounds_func = None
_get_list_configured_merchant_folder_records_func = None
_get_list_merchant_folder_ids_with_zip_today_func = None


def _get_initialize_drive_service():
    global _initialize_drive_service_func
    if _initialize_drive_service_func:
        return _initialize_drive_service_func
    from . import app_config
    import main as _main_module
    if hasattr(_main_module, '_initialize_drive_service'):
        _initialize_drive_service_func = _main_module._initialize_drive_service
        return _initialize_drive_service_func
    raise RuntimeError("Drive service initializer not configured")


def _get_today_drive_query_bounds():
    global _get_today_drive_query_bounds_func
    if _get_today_drive_query_bounds_func:
        return _get_today_drive_query_bounds_func
    from . import app_config
    import main as _main_module
    if hasattr(_main_module, '_get_today_drive_query_bounds'):
        _get_today_drive_query_bounds_func = _main_module._get_today_drive_query_bounds
        return _get_today_drive_query_bounds_func
    raise RuntimeError("_get_today_drive_query_bounds not configured")


def _get_list_configured_merchant_folder_records():
    global _get_list_configured_merchant_folder_records_func
    if _get_list_configured_merchant_folder_records_func:
        return _get_list_configured_merchant_folder_records_func
    from . import app_config
    import main as _main_module
    if hasattr(_main_module, '_list_configured_merchant_folder_records'):
        _get_list_configured_merchant_folder_records_func = _main_module._list_configured_merchant_folder_records
        return _get_list_configured_merchant_folder_records_func
    raise RuntimeError("_list_configured_merchant_folder_records not configured")


def _get_list_merchant_folder_ids_with_zip_today():
    global _get_list_merchant_folder_ids_with_zip_today_func
    if _get_list_merchant_folder_ids_with_zip_today_func:
        return _get_list_merchant_folder_ids_with_zip_today_func
    from . import app_config
    import main as _main_module
    if hasattr(_main_module, '_list_merchant_folder_ids_with_zip_today'):
        _get_list_merchant_folder_ids_with_zip_today_func = _main_module._list_merchant_folder_ids_with_zip_today
        return _get_list_merchant_folder_ids_with_zip_today_func
    raise RuntimeError("_list_merchant_folder_ids_with_zip_today not configured")


def start_daily_report_sender():
    """Start the daily report sender thread."""
    global _daily_report_running, _daily_report_thread
    
    if _daily_report_running:
        print("[DAILY_REPORT] Daily report sender already running")
        return
    
    print("[DAILY_REPORT] Starting daily report sender thread...")
    logging.info("[DAILY_REPORT] Starting daily report sender thread")
    
    _daily_report_running = True
    _daily_report_thread = threading.Thread(target=_daily_report_worker, daemon=True)
    _daily_report_thread.start()
    print("[DAILY_REPORT] Daily report sender thread started successfully")
    logging.info("[DAILY_REPORT] Daily report sender thread started successfully")


def stop_daily_report_sender():
    """Stop the daily report sender thread."""
    global _daily_report_running, _daily_report_thread
    
    if not _daily_report_running:
        return
    
    _daily_report_running = False
    if _daily_report_thread:
        _daily_report_thread.join(timeout=10)
        _daily_report_thread = None
    
    print("[DAILY_REPORT] Daily report sender stopped")
    logging.info("[DAILY_REPORT] Daily report sender stopped")


def _start_sender():
    global _sender_running, _sender_thread
    if _sender_running:
        return
    _sender_running = True
    
    # Import config values at runtime to ensure we have the latest
    from . import app_config
    cfg = app_config._read_json_config(app_config.CONFIG_PATH)
    
    token1 = cfg.get("TELEGRAM_TOKEN", "") or ""
    chat_id1 = cfg.get("TELEGRAM_CHAT_ID", "") or ""
    token2 = cfg.get("TELEGRAM_SYSTEM_TOKEN", "") or ""
    chat_id2 = cfg.get("TELEGRAM_SYSTEM_CHAT_ID", "") or ""
    token3 = cfg.get("TELEGRAM_REPORT_TOKEN", "") or ""
    chat_id3 = cfg.get("TELEGRAM_REPORT_CHAT_ID", "") or ""
    token4 = cfg.get("TELEGRAM_UPDATE_TOKEN", "") or ""
    chat_id4 = cfg.get("TELEGRAM_UPDATE_CHAT_ID", "") or ""
    
    # Debug print all tokens
    _debug_print_tokens(token1, chat_id1, token2, chat_id2, token3, chat_id3, token4, chat_id4)
    
    print("[TELEGRAM_SENDER] Starting Telegram sender thread...")
    logging.info("[TELEGRAM_SENDER] Starting Telegram sender thread")
    _sender_thread = threading.Thread(target=_telegram_sender_worker, daemon=True)
    _sender_thread.start()
    print("[TELEGRAM_SENDER] Telegram sender thread started successfully")
    logging.info("[TELEGRAM_SENDER] Telegram sender thread started successfully")


def _stop_sender():
    global _sender_running, _sender_thread
    if not _sender_running:
        return
    _sender_running = False
    _sender_queue.put(None)
    if _sender_thread:
        _sender_thread.join(timeout=10)
        _sender_thread = None


# Public entry points for external callers (e.g. main.py)
def start_sender():
    _start_sender()


def stop_sender():
    _stop_sender()


def send_telegram_message_async(
    chat_id: str,
    message: str,
    token: str,
    label: str = "notification",
):
    """
    Non-blocking Telegram send — enqueues the request so the caller's thread is never blocked.
    Falls back to synchronous send if the sender thread is not running.
    """
    print(f"[TELEGRAM_ASYNC] Queuing message for {label} to chat_id={chat_id}")
    logging.info(f"[TELEGRAM_ASYNC] Queuing message for {label} to chat_id={chat_id}")
    
    # Validate before queueing
    if not _validate_token_for_sending(token, chat_id, label):
        print(f"[TELEGRAM_ERROR] Cannot queue message for {label} - validation failed")
        logging.error(f"[TELEGRAM_ERROR] Cannot queue message for {label} - token/chat_id validation failed")
        return
    
    _start_sender()
    try:
        _sender_queue.put_nowait((chat_id, message, token, label))
        print(f"[TELEGRAM_ASYNC] Message queued successfully for {label}")
        logging.info(f"[TELEGRAM_ASYNC] Message queued successfully for {label}")
    except queue.Full:
        logging.warning("Telegram send queue full; using synchronous send.")
        print("[TELEGRAM_WARNING] Queue full, falling back to synchronous send")
        send_telegram_message_sync(chat_id, message, token, label)


def send_telegram_message_sync(
    chat_id: str,
    message: str,
    token: str,
    label: str = "notification",
) -> bool:
    """Synchronous Telegram send (used by bot command handlers so they can wait for the reply)."""
    print(f"[TELEGRAM_SYNC] Sending message for {label} to chat_id={chat_id}")
    logging.info(f"[TELEGRAM_SYNC] Sending message for {label} to chat_id={chat_id}")
    
    if not token or not chat_id:
        logging.warning("Telegram token or chat_id is missing; notification skipped.")
        print(f"[TELEGRAM_ERROR] {label}: Token or ChatID is missing! token={token}, chat_id={chat_id}")
        return False
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    print(f"[TELEGRAM_DEBUG] Sending to URL: https://api.telegram.org/bot{token[:8]}.../sendMessage")

    def _post():
        try:
            response = requests.post(
                url,
                data={
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                timeout=app_config.TELEGRAM_HTTP_TIMEOUT_SECONDS,
                verify=False,
            )
            if response.status_code == 200:
                logging.info(f"Telegram notification sent to {chat_id} ({label}).")
                print(f"[TELEGRAM_SUCCESS] Message sent successfully to {chat_id} ({label})")
                return True
            if response.status_code in (429,) or response.status_code >= 500:
                raise requests.RequestException(
                    f"Telegram retryable HTTP {response.status_code}: {response.text[:200]}"
                )
            logging.warning(f"Telegram error {response.status_code}: {response.text[:200]}")
            print(f"[TELEGRAM_WARNING] HTTP {response.status_code}: {response.text[:200]}")
            return False
        except requests.exceptions.ConnectionError as e:
            print(f"[TELEGRAM_ERROR] Connection error for {label}: {e}")
            raise requests.RequestException(f"Connection error: {e}")
        except requests.exceptions.Timeout as e:
            print(f"[TELEGRAM_ERROR] Timeout error for {label}: {e}")
            raise requests.RequestException(f"Timeout error: {e}")

    try:
        result = bool(_run_with_network_retries_sync(label, _post))
        print(f"[TELEGRAM_SYNC] Send result for {label}: {result}")
        return result
    except Exception as e:
        logging.warning(f"Telegram error after retry attempts ({label}): {e}")
        print(f"[TELEGRAM_ERROR] Send failed after retries for {label}: {e}")
        return False


def send_telegram_message(
    chat_id: str,
    message: str,
    telegram_token: str,
    run_with_network_retries,
    bot_token: str | None = None,
) -> bool:
    """Legacy shim — forwards to synchronous version."""
    token = bot_token or telegram_token
    return send_telegram_message_sync(chat_id, message, token, "legacy")


def get_allowed_command_chat_ids(report_chat_id: str) -> set[str]:
    return {str(chat_id).strip() for chat_id in (report_chat_id,) if str(chat_id).strip()}


def telegram_api_get(
    method: str,
    params: dict,
    telegram_token: str,
    request_timeout: int = app_config.TELEGRAM_HTTP_TIMEOUT_SECONDS,
    bot_token: str | None = None,
) -> dict | None:
    token = bot_token or telegram_token
    if not token:
        logging.warning("Telegram token is missing; command polling skipped.")
        return None
    try:
        response = requests.get(
            f"https://api.telegram.org/bot{token}/{method}",
            params=params,
            timeout=request_timeout,
            verify=False,
        )
        if response.status_code == 409:
            # Conflict: có instance khác đang polling cùng token
            # Sleep 2s rồi skip cycle này, không để nghẽn luồng chính
            logging.info("Telegram 409 Conflict: another instance is polling. Skipping after 2s sleep.")
            time.sleep(2)
            return None
        if response.status_code != 200:
            logging.warning(f"Telegram {method} failed: HTTP {response.status_code}: {response.text[:200]}")
            return None
        payload = response.json()
        if not payload.get("ok"):
            logging.warning(f"Telegram {method} returned ok=false: {response.text[:200]}")
            return None
        return payload
    except requests.Timeout:
        if method != "getUpdates":
            logging.warning(f"Telegram {method} request timed out.")
    except requests.RequestException as e:
        logging.warning(f"Telegram {method} network error: {e}")
    except Exception as e:
        logging.warning(f"Telegram {method} error: {e}")
    return None


def get_telegram_updates(offset: int | None, report_token: str) -> list[dict]:
    params = {
        "timeout": app_config.TELEGRAM_POLL_API_TIMEOUT_SECONDS,
        "allowed_updates": json.dumps(["message"]),
    }
    if offset is not None:
        params["offset"] = offset
    payload = telegram_api_get(
        "getUpdates",
        params,
        telegram_token=report_token,
        request_timeout=app_config.TELEGRAM_HTTP_TIMEOUT_SECONDS,
        bot_token=report_token,
    )
    if not payload:
        return []
    return payload.get("result", [])


def format_merchants_list_messages(merchant_names: list[str]) -> list[str]:
    total = len(merchant_names)
    separator = "━" * 18
    header = (
        "📋 [ATLED] CONFIGURED MERCHANTS LIST\n"
        f"⚙️ Total Installed: {total} stores\n"
        f"{separator}\n"
    )
    footer = f"{separator}\nStatus: Live data retrieved from ATLED Cloud."

    if not merchant_names:
        return [header + "No configured merchants were found.\n" + footer]

    messages: list[str] = []
    current = header
    for index, merchant_name in enumerate(merchant_names, start=1):
        line = f"{index}. {html.escape(merchant_name)}\n"
        projected_length = len(current) + len(line) + len(footer)
        if current != header and projected_length > app_config.TELEGRAM_SAFE_MESSAGE_LIMIT:
            messages.append(current + footer)
            current = header
        current += line

    messages.append(current + footer)
    return messages


def send_configured_merchants_list(chat_id: str, initialize_drive_service, list_configured_merchant_folders, send_message):
    try:
        drive_service = initialize_drive_service()
        merchant_names = list_configured_merchant_folders(drive_service)
        for message in format_merchants_list_messages(merchant_names):
            send_message(chat_id, message)
            time.sleep(0.5)
    except Exception as e:
        logging.error(f"Failed to process Telegram /list command: {e}")
        send_message(
            chat_id,
            "📋 [ATLED] CONFIGURED MERCHANTS LIST\n"
            "❌ Status: Unable to retrieve live merchant data right now.\n"
            f"🧾 Error: {html.escape(str(e))[:500]}",
        )


def safe_drive_name(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z_.-]+", "_", value).strip("_")[:120] or "unknown"


def cleanup_old_command_locks(drive_service, lock_folder_id: str, execute_drive_request):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=app_config.COMMAND_LOCK_RETENTION_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        results = execute_drive_request(
            "List old Telegram command locks",
            lambda: drive_service.files().list(
                q=(
                    f"'{lock_folder_id}' in parents "
                    "and trashed=false "
                    f"and createdTime < '{cutoff}'"
                ),
                fields="files(id, name, createdTime)",
                pageSize=1000,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            ),
        )
        for item in results.get("files", []):
            try:
                execute_drive_request(
                    f"Delete old Telegram command lock ({item.get('name', '')})",
                    lambda file_id=item["id"]: drive_service.files().delete(
                        fileId=file_id,
                        supportsAllDrives=True,
                    ),
                )
            except Exception as e:
                logging.warning(f"Could not delete old Telegram command lock: {e}")
    except Exception as e:
        logging.warning(f"Telegram command lock cleanup failed: {e}")


def claim_telegram_command_update(
    drive_service,
    update_id: int,
    chat_id: str,
    command: str,
    parent_folder_id: str,
    find_or_create_child_folder,
    execute_drive_request,
) -> bool:
    try:
        lock_folder_id = find_or_create_child_folder(
            drive_service,
            parent_folder_id,
            app_config.COMMAND_LOCK_FOLDER_NAME,
        )
        cleanup_old_command_locks(drive_service, lock_folder_id, execute_drive_request)

        host = safe_drive_name(f"{os.environ.get('COMPUTERNAME')}_{os.environ.get('USERNAME')}")
        command_name = safe_drive_name(command)
        lock_name = f"telegram_update_{update_id}_{safe_drive_name(chat_id)}_{command_name}_{host}.lock"
        metadata = {
            "name": lock_name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [lock_folder_id],
        }
        created = execute_drive_request(
            "Create Telegram command lock",
            lambda: drive_service.files().create(
                body=metadata,
                fields="id, name, createdTime",
                supportsAllDrives=True,
            ),
        )
        time.sleep(app_config.COMMAND_CLAIM_SETTLE_SECONDS)

        prefix = f"telegram_update_{update_id}_{safe_drive_name(chat_id)}_{command_name}_"
        results = execute_drive_request(
            "List Telegram command lock contenders",
            lambda: drive_service.files().list(
                q=(
                    f"'{lock_folder_id}' in parents "
                    "and trashed=false "
                    f"and name contains '{prefix}'"
                ),
                fields="files(id, name, createdTime)",
                pageSize=100,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            ),
        )
        contenders = [
            item
            for item in results.get("files", [])
            if str(item.get("name", "")).startswith(prefix)
        ]
        contenders.sort(key=lambda item: (item.get("createdTime", ""), item.get("id", "")))
        winner_id = contenders[0].get("id") if contenders else created.get("id")
        is_winner = winner_id == created.get("id")
        logging.info(
            f"Telegram command lock for update {update_id}: "
            f"{'won' if is_winner else 'skipped'} by {lock_name}"
        )
        return is_winner
    except Exception as e:
        logging.warning(f"Telegram command claim failed; skipping duplicate-sensitive response: {e}")
        return False


def normalize_telegram_command(text: str) -> str:
    normalized_text = str(text or "").strip()
    if not normalized_text:
        return ""
    command = normalized_text.split(maxsplit=1)[0].lower()
    if "@" in command:
        command = command.split("@", 1)[0]
    return command


def format_stale_backup_check_messages(
    report_date: str,
    days: int,
    total_folders: int,
    stale_store_names: list[str],
) -> list[str]:
    separator = "━" * 18
    stale_count = len(stale_store_names)
    healthy_count = total_folders - stale_count
    header = (
        "🔎 [ATLED] BACKUP GAP CHECK\n"
        f"📅 Date: {report_date}\n"
        f"{separator}\n"
        f"⚙️ Total Merchants Configured: {total_folders} stores\n"
        f"✅ Backed Up Within Last {days} Days: {healthy_count}/{total_folders} stores\n"
        f"❌ No Backup For {days}+ Days: {stale_count} stores\n\n"
        f"⚠️ Stores with no backup activity for {days}+ days:\n"
    )
    footer = f"{separator}\nStatus: Live data retrieved from ATLED Cloud."

    if not stale_store_names:
        return [header + "✅ All stores have recent backup activity.\n" + footer]

    messages: list[str] = []
    current = header
    for store_name in stale_store_names:
        line = f"- {html.escape(store_name)}\n"
        if current != header and len(current) + len(line) + len(footer) > app_config.TELEGRAM_SAFE_MESSAGE_LIMIT:
            messages.append(current + footer)
            current = header
        current += line

    messages.append(current + footer)
    return messages


def send_stale_backup_check(
    chat_id: str,
    initialize_drive_service,
    get_recent_drive_query_bounds,
    list_configured_merchant_folder_records,
    list_merchant_folder_ids_with_zip_in_window,
    send_message,
    days: int = app_config.STALE_BACKUP_DAYS,
):
    try:
        drive_service = initialize_drive_service()
        report_date, utc_start, utc_end = get_recent_drive_query_bounds(days)
        merchant_folders = list_configured_merchant_folder_records(drive_service)
        merchant_folder_ids = {item["id"] for item in merchant_folders}

        backed_up_folder_ids: set[str] = set()
        if merchant_folder_ids:
            backed_up_folder_ids = list_merchant_folder_ids_with_zip_in_window(
                drive_service,
                merchant_folder_ids,
                utc_start,
                utc_end,
            )

        stale_store_names = sorted(
            [item["name"] for item in merchant_folders if item["id"] not in backed_up_folder_ids],
            key=lambda name: name.casefold(),
        )
        for message in format_stale_backup_check_messages(
            report_date,
            days,
            len(merchant_folders),
            stale_store_names,
        ):
            send_message(chat_id, message)
            time.sleep(0.5)
    except Exception as e:
        logging.error(f"Failed to process Telegram /check command: {e}")
        send_message(
            chat_id,
            "🔎 [ATLED] BACKUP GAP CHECK\n"
            "❌ Status: Unable to retrieve live merchant data right now.\n"
            f"🧾 Error: {html.escape(str(e))[:500]}",
        )


def format_daily_report_messages(
    report_date: str,
    total_folders: int,
    success_count: int,
    failed_store_names: list[str],
) -> list[str]:
    separator = "━" * 18
    error_count = len(failed_store_names)
    header = (
        "📊 [ATLED] DAILY SYSTEM BACKUP REPORT\n"
        f"📅 Date: {report_date}\n"
        f"{separator}\n"
        f"⚙️ Total Merchants Configured: {total_folders} stores\n"
        f"✅ Backup Successful: {success_count}/{total_folders} stores\n"
        f"❌ Merchant Errors / No Backup: {error_count} stores\n\n"
        "⚠️ Details of stores with NO backup today (Action Required):\n"
    )
    footer = f"{separator}\nStatus: Automated report from ATLED Cloud System."

    if not failed_store_names:
        return [header + "- All stores backed up successfully!\n" + footer]

    messages: list[str] = []
    current = header
    for store_name in failed_store_names:
        line = f"- {html.escape(store_name)}\n"
        if current != header and len(current) + len(line) + len(footer) > app_config.TELEGRAM_SAFE_MESSAGE_LIMIT:
            messages.append(current + footer)
            current = header
        current += line

    messages.append(current + footer)
    return messages


def generate_daily_report(
    initialize_drive_service,
    get_today_drive_query_bounds,
    list_configured_merchant_folder_records,
    list_merchant_folder_ids_with_zip_today,
    report_chat_id: str,
    send_message,
) -> dict:
    report_date, utc_start, utc_end = get_today_drive_query_bounds()
    drive_service = initialize_drive_service()
    merchant_folders = list_configured_merchant_folder_records(drive_service)
    total_folders = len(merchant_folders)
    merchant_folder_ids = {item["id"] for item in merchant_folders}

    backed_up_folder_ids: set[str] = set()
    if merchant_folder_ids:
        backed_up_folder_ids = list_merchant_folder_ids_with_zip_today(
            drive_service,
            merchant_folder_ids,
            utc_start,
            utc_end,
        )

    failed_store_names = [item["name"] for item in merchant_folders if item["id"] not in backed_up_folder_ids]
    failed_store_names = sorted(failed_store_names, key=lambda name: name.casefold())
    success_count = total_folders - len(failed_store_names)

    messages = format_daily_report_messages(
        report_date,
        total_folders,
        success_count,
        failed_store_names,
    )

    for message in messages:
        send_message(report_chat_id, message)
        time.sleep(0.5)

    return {
        "date": report_date,
        "total_folders": total_folders,
        "success_count": success_count,
        "error_count": len(failed_store_names),
        "message_count": len(messages),
    }
