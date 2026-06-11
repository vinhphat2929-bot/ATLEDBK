"""
update_helpers.py - ZIP-based Update System (v1.1.7)

Update Workflow (Mẹ bồng con - trực tiếp bằng Python, KHÔNG .BAT):
1. Download update.zip from Google Drive
2. Validate ZIP integrity using zipfile.is_zipfile()
3. Rename running ATLED_BK.exe -> ATLED_BK_OLD.exe
4. Extract new ATLED_BK.exe directly to C:\ATLED\
5. Launch new app with CREATE_NO_WINDOW (no CMD, no .bat)
6. Exit current app with os._exit(0)
"""

import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import zipfile

import requests

from . import app_config


def get_confirm_token(response):
    """Extract download confirmation token from Google Drive response."""
    for key, value in response.cookies.items():
        if key.startswith("download_warning"):
            return value
    match = re.search(r"confirm=([0-9A-Za-z_]+)&", response.text)
    if match:
        return match.group(1)
    match = re.search(r"confirm=([0-9A-Za-z_]+)\"", response.text)
    if match:
        return match.group(1)
    return None


def parse_version(version_str: str) -> tuple:
    """Parse version string into comparable tuple."""
    version_str = str(version_str).strip().lstrip('vV')
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


def _download_file_from_drive(file_id: str, destination_path: str) -> bool:
    """
    Download any file from Google Drive to destination path.
    Returns True on success, False on failure.

    Google Drive trả về trang cảnh báo virus trước khi cho tải file.
    Cần bóc tách mã confirm token từ cả cookies lẫn HTML response,
    sau đó gửi lại request với token đó để nhận file thật.
    """
    session = requests.Session()
    url = f"https://drive.google.com/uc?export=download&id={file_id}"

    # Bước 1: Request lần đầu — lấy trang cảnh báo
    response = session.get(url, stream=True, timeout=30)
    if response.status_code != 200:
        logging.warning(f"Initial request failed: HTTP {response.status_code}")
        return False

    # Bước 2: Bóc tách confirm token từ cookies trước
    confirm_token = None
    for key, value in response.cookies.items():
        if key.startswith("download_warning"):
            confirm_token = value
            break

    # Bước 3: Nếu không có trong cookies, thử quét HTML
    if not confirm_token:
        match = re.search(r"confirm=([0-9A-Za-z_]+)&", response.text)
        if match:
            confirm_token = match.group(1)
        else:
            match = re.search(r"confirm=([0-9A-Za-z_]+)[\"']", response.text)
            if match:
                confirm_token = match.group(1)

    if not confirm_token:
        # Thử đọc thêm một số bytes từ response để tìm token
        extra = b"".join(response.iter_content(chunk_size=8192))
        combined = response.content + extra
        text = combined.decode("utf-8", errors="ignore")
        match = re.search(r"confirm=([0-9A-Za-z_]+)", text)
        if match:
            confirm_token = match.group(1)

    if not confirm_token:
        logging.warning("Could not extract confirm token from Drive response")
        return False

    # Bước 4: Gửi request thật với confirm token
    url = url.replace("export=download", "uc?export=download")
    if "confirm=" in url:
        url = re.sub(r"confirm=[A-Za-z0-9_]+", f"confirm={confirm_token}", url)
    else:
        url += f"&confirm={confirm_token}"

    response = session.get(url, stream=True, timeout=60)
    if response.status_code != 200:
        logging.warning(f"Download request failed: HTTP {response.status_code}")
        return False

    # Bước 5: Kiểm tra xem response có phải là file thật không (không phải HTML cảnh báo)
    content_type = response.headers.get("Content-Type", "")
    content_length = response.headers.get("Content-Length", "")

    if "text/html" in content_type.lower():
        # Thử đọc thêm để xác nhận
        sample = b"".join(response.iter_content(chunk_size=4096))
        if b"<html" in sample.lower() or b"warning" in sample.lower():
            logging.warning("Drive still returned HTML warning page")
            return False

    # Bước 6: Lưu file
    dest_dir = os.path.dirname(destination_path)
    if dest_dir:
        os.makedirs(dest_dir, exist_ok=True)

    try:
        downloaded = 0
        with open(destination_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)

        if downloaded == 0:
            logging.warning("Downloaded file is empty")
            if os.path.exists(destination_path):
                try:
                    os.remove(destination_path)
                except Exception:
                    pass
            return False

        logging.info(f"Downloaded {downloaded} bytes to {destination_path}")
        return True
    except Exception as e:
        logging.error(f"Failed to save file: {e}")
        if os.path.exists(destination_path):
            try:
                os.remove(destination_path)
            except Exception:
                pass
        return False


def download_version_config() -> dict | None:
    """Download and parse version.json from Dropbox."""
    try:
        session = requests.Session()
        response = session.get(app_config.URL_VERSION_CHECK, timeout=30)
        if response.status_code != 200:
            logging.warning(f"Version config download failed: HTTP {response.status_code}")
            return None

        content_type = response.headers.get("Content-Type", "")
        if "text/html" in content_type.lower():
            sample = response.text[:500].lower()
            if "<html" in sample or "error" in sample:
                logging.warning("Dropbox returned HTML error page for version.json")
                return None

        try:
            config = json.loads(response.text)
            if isinstance(config, dict) and "version" in config:
                return config
        except json.JSONDecodeError:
            pass

        version_patterns = [
            r'"version"["\s:]+["\']?([vV]?\d+\.\d+\.\d+)',
            r'\b(v?\d+\.\d+\.\d+)\b',
        ]
        for pattern in version_patterns:
            match = re.search(pattern, response.text)
            if match:
                return {"version": match.group(1).lstrip("vV")}

        logging.warning("Could not extract version from version.json content")
        return None

    except Exception as e:
        logging.warning(f"Failed to download version config: {e}")
        return None


def sha256_file(path: str) -> str:
    """Calculate SHA256 hash of a file."""
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_zip_file(zip_path: str) -> tuple[bool, str]:
    """
    Validate that a file is a valid ZIP archive.
    This protects against:
    - HTML warning pages from Google Drive
    - Incomplete downloads
    - Corrupted files
    Returns (is_valid, message)
    """
    if not os.path.exists(zip_path):
        msg = "ZIP file does not exist."
        logging.warning(f"ZIP validation failed: {msg}")
        return False, msg

    try:
        file_size = os.path.getsize(zip_path)
        if file_size == 0:
            msg = "ZIP file is empty."
            logging.warning(f"ZIP validation failed: {msg}")
            return False, msg

        if file_size < 100:
            msg = "ZIP file is too small to be valid."
            logging.warning(f"ZIP validation failed: {msg}")
            return False, msg

        if not zipfile.is_zipfile(zip_path):
            msg = "File is not a valid ZIP archive (may be HTML warning page from Google Drive or corrupted download)."
            logging.warning(f"ZIP validation failed: {msg}")
            try:
                with open(zip_path, "rb") as f:
                    header = f.read(256)
                    if b"<!DOCTYPE" in header or b"<html" in header or b"Virus" in header:
                        msg = "Downloaded file is HTML warning page, not a ZIP file."
                        logging.error(f"Downloaded file is HTML (Google Drive warning page), not a ZIP")
            except Exception:
                pass
            return False, msg

        with zipfile.ZipFile(zip_path, 'r') as zf:
            bad_file = zf.testzip()
            if bad_file is not None:
                msg = f"ZIP file is corrupted: {bad_file}"
                logging.warning(f"ZIP validation failed: {msg}")
                return False, msg

            namelist = zf.namelist()
            if not namelist:
                msg = "ZIP file is empty."
                logging.warning(f"ZIP validation failed: {msg}")
                return False, msg

            expected_exe = app_config.UPDATE_EXE_EXTRACTED_NAME
            has_exe = any(os.path.basename(name).lower() == expected_exe.lower() for name in namelist)
            if not has_exe:
                exe_names = [n for n in namelist if n.lower().endswith('.exe')]
                if not exe_names:
                    msg = f"ZIP does not contain {expected_exe}."
                    logging.warning(f"ZIP validation: {msg}")
                    return False, msg
                msg = f"ZIP does not contain {expected_exe}, found: {exe_names}"
                logging.warning(f"ZIP validation: {msg}")
                return False, msg

        msg = f"ZIP file is valid ({len(namelist)} files)."
        logging.info(f"ZIP validation passed: {zip_path}")
        return True, msg

    except zipfile.BadZipFile as e:
        msg = f"Invalid ZIP structure: {e}"
        logging.error(f"ZIP validation error: {msg}")
        return False, msg
    except Exception as e:
        msg = f"ZIP validation error: {str(e)}"
        logging.error(f"ZIP validation error: {e}")
        return False, msg


def check_for_update() -> tuple[bool, str]:
    """
    Check if update is available using semantic version comparison.
    Returns (has_update, status_message)
    """
    if not app_config.UPDATE_VERSION_FILE_ID:
        return False, "Update source is not configured."

    try:
        version_config = download_version_config()
        if not version_config:
            return False, "Could not download version information."

        drive_version = version_config.get('version', '')
        if not drive_version:
            return False, "Version information is invalid."

        current_version = app_config.APP_VERSION

        drive_v = parse_version(drive_version)
        current_v = parse_version(current_version)

        logging.info(f"Version check: current={current_version} ({current_v}), drive={drive_version} ({drive_v})")

        if is_newer_version(drive_version, current_version):
            return True, f"New version available: {drive_version} > {current_version}"
        else:
            return False, f"Already on latest version ({current_version})."

    except Exception as e:
        logging.error(f"Update check failed: {e}")
        return False, f"Update check failed: {str(e)}"


def download_update_zip(url: str, zip_destination: str) -> tuple[bool, str]:
    """
    Thay the hoan toan logic cu bang luong boc tach token dynamic qua requests.Session
    """
    import requests
    import re
    import os
    import logging
    import zipfile

    logger = logging.getLogger(__name__)
    logger.info(f"Bat dau luong tai file ZIP tu URL: {url}")

    # Dam bao thu muc dich ton tai
    dest_dir = os.path.dirname(zip_destination)
    if dest_dir:
        os.makedirs(dest_dir, exist_ok=True)

    # Xoa file cu neu ton tai
    if os.path.exists(zip_destination):
        try:
            os.remove(zip_destination)
        except Exception:
            pass

    try:
        session = requests.Session()
        # Buoc 1: Goi len de lay cookie va trang canh bao virus
        response = session.get(url, stream=True, timeout=30)

        confirm_token = None
        # Quet token tu cookie
        for key, value in response.cookies.items():
            if key.startswith('download_warning'):
                confirm_token = value
                break

        # Neu cookie ko co, quet trong text HTML
        if not confirm_token:
            match = re.search(r'confirm=([A-Za-z0-9_]+)', response.text)
            if match:
                confirm_token = match.group(1)

        logger.info(f"Ket qua tim kiem confirm_token: {confirm_token}")

        # Buoc 2: Append token vao URL de xac nhan tai file lon
        if confirm_token:
            if 'confirm=' in url:
                url = re.sub(r'confirm=[A-Za-z0-9_]+', f'confirm={confirm_token}', url)
            else:
                url += f"&confirm={confirm_token}"

        # Buoc 3: Gui request thuc su de tai file ZIP bieu kien
        final_response = session.get(url, stream=True, timeout=60)

        # Kiem tra content-type, neu la HTML thi chan luon
        content_type = final_response.headers.get('Content-Type', '')
        if 'text/html' in content_type or 'text/plain' in response.text[:200] and '<html' in response.text.lower():
            return False, "Google Drive van tra ve trang HTML canh bao virus. Token ko hop le."

        # Tien hanh ghi file ra o cung
        with open(zip_destination, 'wb') as f:
            for chunk in final_response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        # Buoc 4: Validate file ZIP xem co hop le ko sau khi tai xong
        if not zipfile.is_zipfile(zip_destination):
            return False, "File tai ve khong phai la file ZIP hop le (Giam dinh that bai)."

        logger.info(f"Da tai va validate file ZIP thanh cong ve: {zip_destination}")
        return True, "Update ZIP ready."

    except Exception as e:
        logger.error(f"Loi thuc te trong qua trinh tai file: {str(e)}")
        return False, f"Download failed due to exception: {str(e)}"


def run_update_script(
    zip_path: str,
    restart_background: bool = False,
) -> bool:
    """
    Update workflow (v1.1.7 - "Mẹ bồng con" trực tiếp bằng Python, KHÔNG DÙNG .BAT):

    1. Dọn file _OLD cũ nếu có
    2. Đổi tên ATLED_BK.exe đang chạy -> ATLED_BK_OLD.exe (Windows cho phép đổi tên file đang chạy)
    3. Giải nén trực tiếp file mới vào ATLED_BK.exe (chỗ này giờ đã trống)
    4. Bật app mới lên ngay với CREATE_NO_WINDOW (không CMD, không .bat)
    5. App cũ tự sát văn minh bằng os._exit(0)
    """
    target_dir = r"C:\ATLED"
    main_exe = os.path.join(target_dir, "ATLED_BK.exe")
    old_exe = os.path.join(target_dir, "ATLED_BK_OLD.exe")

    try:
        # Bước 1: Dọn SẠCH TẤT CẢ file _OLD trước khi làm gì khác
        # (Tránh tích tụ nhiều file old qua các lần update)
        if os.path.exists(old_exe):
            try:
                os.remove(old_exe)
                logging.info("[UPDATE] Da xoa ATLED_BK_OLD.exe cu")
            except Exception:
                pass

        # Bước 2: Đổi tên chính mình thành _OLD (Windows cho phép đổi tên file đang chạy)
        if os.path.exists(main_exe):
            os.rename(main_exe, old_exe)
            logging.info("[UPDATE] Da doi ten ATLED_BK.exe -> ATLED_BK_OLD.exe")

        # Bước 3: Giải nén TRỰC TIẾP file mới vào ATLED_BK.exe
        # (Vì chỗ này giờ đã trống sau khi rename ở bước 2)
        if not os.path.exists(zip_path):
            logging.error(f"[UPDATE] ZIP file not found: {zip_path}")
            return False

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for member in zip_ref.namelist():
                filename = os.path.basename(member)
                if not filename:
                    continue
                if filename.lower() == "atled_bk.exe":
                    with open(main_exe, "wb") as f:
                        f.write(zip_ref.read(member))
                    logging.info(f"[UPDATE] Da giai nen ATLED_BK.exe moi vao {main_exe}")

        # Bước 4: Verify file moi
        if not os.path.exists(main_exe):
            logging.error("[UPDATE] File moi khong ton tai sau khi giai nen!")
            return False

        exe_size = os.path.getsize(main_exe)
        if exe_size < 1024:
            logging.error(f"[UPDATE] File moi qua nho ({exe_size} bytes), co the bi loi!")
            return False

        logging.info(f"[UPDATE] File moi verified: {exe_size} bytes")

        # Bước 5: Bật app MỚI ngay lập tức với MÔI TRƯỜNG SẠCH + chạy ẩn ngay
        # Quan trọng: Xóa sạch biến _MEIPASS để Windows tạo _MEI mới hoàn toàn cho app mới,
        # tránh crash "FileNotFoundError: base_library.zip" khi app cũ bị kill/súc mà Windows xóa temp của nó
        # Quan trọng: Đợi 5 giây để Windows hoàn tất dọn temp của app cũ trước khi app mới khởi động
        import time
        logging.info("[UPDATE] Cho 5 giay de Windows don temp cu (tranh _MEI conflict)...")
        time.sleep(5)

        logging.info("[UPDATE] Khoi dong app moi voi moi truong sach, che do an (--auto-updated --minimized)...")
        clean_env = os.environ.copy()
        # Only remove PyInstaller's own _MEIPASS variable (which points to old _MEI temp dir)
        # Keep all other env vars including SSL_CERT_FILE so the new app's certifi still works
        if '_MEIPASS' in clean_env:
            clean_env.pop('_MEIPASS')

        # Ensure SSL certs are available in new process by setting certifi path explicitly
        try:
            import certifi
            certifi_path = certifi.where()
            if certifi_path:
                clean_env['SSL_CERT_FILE'] = certifi_path
                clean_env['REQUESTS_CA_BUNDLE'] = certifi_path
        except Exception:
            pass

        subprocess.Popen(
            [main_exe, "--auto-updated", "--minimized"],
            env=clean_env,
            creationflags=subprocess.CREATE_NO_WINDOW,
            close_fds=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logging.info("[UPDATE] App moi da khoi dong an - app cu tu tat ngay bay gio")

        # Bước 6: Xóa file _OLD để không tích tụ (chờ 2 giây để app mới khởi động xong)
        # QUAN TRỌNG: daemon=True để thread này sống sót sau os._exit(0)
        def _cleanup_old():
            import time
            time.sleep(2)
            if os.path.exists(old_exe):
                try:
                    os.remove(old_exe)
                    logging.info("[UPDATE] Da xoa ATLED_BK_OLD.exe sau khi update thanh cong")
                except Exception:
                    pass

        import threading
        cleanup_thread = threading.Thread(target=_cleanup_old, daemon=True)
        cleanup_thread.start()

        # Bước 7: Đợi 2 giây để app mới khởi động xong trước khi app cũ tự sát
        # Tránh tình trạng app mới bị ảnh hưởng khi app cũ gọi os._exit(0) quá nhanh
        import time
        logging.info("[UPDATE] Cho 2 giay de app moi khoi dong xong truoc khi app cu tat...")
        time.sleep(2)

        # Bước 8: App cũ tự sát văn minh
        os._exit(0)

    except Exception as e:
        logging.error(f"[UPDATE] Loi luong Mẹ bồng con: {e}")
        return False


def download_update_if_changed(destination_path: str, delete_local_files) -> tuple[bool, str]:
    """
    Download update ZIP only if version on Drive is newer.
    Validates ZIP before returning success.
    Returns (success, status_message)
    """
    if not app_config.UPDATE_VERSION_FILE_ID:
        return False, "Update source is not configured."

    has_update, status = check_for_update()

    if not has_update:
        logging.info(f"Update check result: {status}")
        return False, status

    # Download and validate ZIP
    return download_update_zip(
        f"https://drive.google.com/uc?export=download&id={app_config.UPDATE_ZIP_FILE_ID}",
        destination_path
    )


def send_post_update_notification(
    app_version: str,
    store_name: str,
    watch_directory: str,
    send_update_notification,
):
    """Send notification after successful update to Box 1."""
    resolved_store_name = store_name or "[Unknown store]"
    resolved_watch_directory = watch_directory or "[Not configured]"
    message = (
        "🚀 [ATLED SYSTEM UPDATE SUCCESS]\n"
        f"🖥️ Host: {os.environ.get('COMPUTERNAME')} | User: {os.environ.get('USERNAME')}\n"
        f"🏪 Merchant: {resolved_store_name}\n"
        f"📂 Watch Directory: {resolved_watch_directory}\n"
        f"✅ Status: Successfully updated to the latest version!\n"
        f"🆕 Current Version: {app_version}"
    )
    send_update_notification(message)


def handle_exit_signal(signum, frame, send_system_shutdown_notification):
    send_system_shutdown_notification()
    sys.exit(0)
