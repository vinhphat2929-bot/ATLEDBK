import logging
import os
import subprocess
import sys

from . import app_config


def get_startup_folder() -> str:
    """Get Windows Startup folder path."""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RuntimeError("APPDATA was not found, so Windows startup could not be configured.")
    return os.path.join(
        appdata,
        "Microsoft",
        "Windows",
        "Start Menu",
        "Programs",
        "Startup",
    )


def get_startup_shortcut_path() -> str:
    """Get the shortcut path for this app."""
    return os.path.join(get_startup_folder(), app_config.APP_STARTUP_NAME)


def get_legacy_startup_shortcut_path(name: str) -> str:
    """Get legacy shortcut path by name."""
    return os.path.join(get_startup_folder(), name)


def remove_startup_shortcut(path: str):
    """Remove a startup shortcut if it exists."""
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def escape_ps_single_quotes(value: str) -> str:
    """Escape single quotes for PowerShell strings."""
    return value.replace("'", "''")


def _run_powershell_hidden(command: str) -> bool:
    """Run PowerShell command with hidden window."""
    try:
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-WindowStyle",
                "Hidden",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                command,
            ],
            capture_output=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return True
    except Exception as e:
        logging.warning(f"PowerShell command failed: {e}")
        return False


def is_registry_startup_enabled() -> bool:
    """Check if app is registered in Windows Registry Run key."""
    exe_path = app_config.resolve_exe_path()
    ps_script = f"""
        $regPath = 'HKCU:\\{app_config.REGISTRY_RUN_PATH}'
        $keyName = '{app_config.REGISTRY_STARTUP_KEY_NAME}'
        try {{
            $value = (Get-ItemProperty -Path $regPath -Name $keyName -ErrorAction SilentlyContinue).$keyName
            if ($value -and $value.ToString().StartsWith('{escape_ps_single_quotes(exe_path)}')) {{
                Write-Output 'YES'
            }} else {{
                Write-Output 'NO'
            }}
        }} catch {{
            Write-Output 'NO'
        }}
    """
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-WindowStyle",
                "Hidden",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                ps_script,
            ],
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return "YES" in result.stdout.strip()
    except Exception:
        return False


def register_registry_startup() -> bool:
    """Register app to Windows Registry for auto-start with --background flag.

    Nếu exe không nằm ở C:\\ATLED\\ATLED_BK.exe thì tự động copy chính nó
    về đó trước, rồi mới ghi Registry. Tránh trường hợp exe chạy từ
    Downloads/Desktop bị Windows chặn ở startup.
    """
    import shutil
    import winreg

    current_exe = app_config.resolve_exe_path()
    if not current_exe.lower().endswith(".exe"):
        logging.info("Skipping registry startup because not running from .exe")
        return False

    # Xác định đường dẫn đích cố định
    target_dir = r"C:\ATLED"
    target_exe = os.path.join(target_dir, "ATLED_BK.exe")

    # Nếu exe hiện tại không phải ở C:\ATLED thì copy lại
    exe_to_register = current_exe
    if not current_exe.lower().replace("\\", "/").startswith(target_dir.lower().replace("\\", "/") + "/"):
        logging.info(f"EXE not in {target_dir}, copying: {current_exe} -> {target_exe}")
        try:
            os.makedirs(target_dir, exist_ok=True)
            shutil.copy2(current_exe, target_exe)
            exe_to_register = target_exe
            logging.info(f"Copied EXE to {target_exe}")
        except Exception as e:
            logging.error(f"Failed to copy EXE to {target_exe}: {e}")
            # Vẫn thử đăng ký với path hiện tại
            exe_to_register = current_exe

    # Escape cho PowerShell
    escaped_exe = exe_to_register.replace("'", "''")
    ps_script = f"""
        $regPath = 'HKCU:\\{app_config.REGISTRY_RUN_PATH}'
        $keyName = '{app_config.REGISTRY_STARTUP_KEY_NAME}'
        $exePath = '{escaped_exe}'
        $argValue = '"' + $exePath + '" {app_config.AUTO_START_ARG}'
        try {{
            Set-ItemProperty -Path $regPath -Name $keyName -Value $argValue -Force
            Write-Output 'OK'
        }} catch {{
            Write-Output 'FAIL'
        }}
    """

    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-WindowStyle",
                "Hidden",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                ps_script,
            ],
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        success = "OK" in result.stdout.strip()
        if success:
            logging.info(f"Registry startup registered: {exe_to_register}")
        else:
            logging.warning(f"Failed to register registry startup: {result.stderr}")
        return success
    except Exception as e:
        logging.warning(f"Exception registering registry startup: {e}")
        return False


def unregister_registry_startup() -> bool:
    """Remove app from Windows Registry Run key."""
    ps_script = f"""
        $regPath = 'HKCU:\\{app_config.REGISTRY_RUN_PATH}'
        $keyName = '{app_config.REGISTRY_STARTUP_KEY_NAME}'
        try {{
            Remove-ItemProperty -Path $regPath -Name $keyName -ErrorAction SilentlyContinue
            Write-Output 'OK'
        }} catch {{
            Write-Output 'OK'
        }}
    """

    try:
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-WindowStyle",
                "Hidden",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                ps_script,
            ],
            capture_output=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        logging.info("Registry startup unregistered")
        return True
    except Exception as e:
        logging.warning(f"Exception unregistering registry startup: {e}")
        return False


def configure_auto_start(enabled: bool):
    """
    Configure both Registry and Shortcut for maximum compatibility.
    Registry is the primary method for silent startup.
    """
    shortcut_path = get_startup_shortcut_path()

    if not enabled:
        unregister_registry_startup()
        remove_startup_shortcut(shortcut_path)
        for legacy_name in app_config.LEGACY_STARTUP_SHORTCUTS:
            remove_startup_shortcut(get_legacy_startup_shortcut_path(legacy_name))
        return

    exe_path = app_config.resolve_exe_path()
    if not exe_path.lower().endswith(".exe"):
        logging.info("Skipping auto-start because the app is running from a .py file.")
        return

    for legacy_name in app_config.LEGACY_STARTUP_SHORTCUTS:
        remove_startup_shortcut(get_legacy_startup_shortcut_path(legacy_name))

    register_registry_startup()

    startup_dir = get_startup_folder()
    os.makedirs(startup_dir, exist_ok=True)

    icon_path = app_config.resolve_asset("app_icon.ico")
    if not os.path.exists(icon_path):
        icon_path = exe_path

    ps_command = (
        "$WScriptShell = New-Object -ComObject WScript.Shell; "
        f"$Shortcut = $WScriptShell.CreateShortcut('{escape_ps_single_quotes(shortcut_path)}'); "
        f"$Shortcut.TargetPath = '{escape_ps_single_quotes(exe_path)}'; "
        f"$Shortcut.Arguments = '{app_config.AUTO_START_ARG}'; "
        f"$Shortcut.WorkingDirectory = '{escape_ps_single_quotes(os.path.dirname(exe_path))}'; "
        f"$Shortcut.IconLocation = '{escape_ps_single_quotes(icon_path)}'; "
        "$Shortcut.Save();"
    )
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            ps_command,
        ],
        check=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    logging.info(f"Auto-start configured: Registry + Shortcut")


def ensure_auto_start_shortcut(store_name: str, watch_directory: str):
    """Ensure auto-start is configured when app has runtime configuration."""
    if store_name and watch_directory and app_config.resolve_exe_path().lower().endswith(".exe"):
        try:
            configure_auto_start(True)
        except Exception as e:
            logging.warning(f"Auto-start shortcut refresh failed: {e}")


def cleanup_old_exe_after_update():
    """
    App mới sẽ xóa ATLED_BK_OLD.exe sau 60 giây.
    Retry nhiều lần vì app cũ có thể vẫn đang cleanup.
    """
    import time
    import threading

    old_exe = os.path.join(r"C:\ATLED", "ATLED_BK_OLD.exe")

    def _cleanup():
        # Đợi 60s cho app cũ exit hoàn toàn
        logging.info("[CLEANUP] Cho 60s truoc khi xoa _OLD...")
        time.sleep(60)

        # Retry nhiều lần với backoff
        for attempt in range(5):
            if not os.path.exists(old_exe):
                logging.info("[CLEANUP] _OLD da bi xoa boi qua trinh khac")
                return

            try:
                os.remove(old_exe)
                logging.info(f"[CLEANUP] Da xoa ATLED_BK_OLD.exe (attempt {attempt + 1})")
                return
            except Exception as e:
                logging.warning(f"[CLEANUP] Attempt {attempt + 1} failed: {e}")
                if attempt < 4:
                    time.sleep(5)  # Retry sau 5s

        logging.warning(f"[CLEANUP] Khong the xoa _OLD sau 5 attempts: {old_exe}")

    t = threading.Thread(target=_cleanup, daemon=True)
    t.start()
