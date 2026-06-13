# Build script cho ATLED_BK
# Chi build exe, khong tao zip/json vi khong co chuc nang update

import sys
import os
import subprocess
import re

VERSION = sys.argv[1] if len(sys.argv) > 1 else None

if not VERSION:
    # Doc version hien tai tu app_config.py
    with open("backup_tool/app_config.py", "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("APP_VERSION"):
                VERSION = line.split('"')[1]
                break

print(f"Building version {VERSION}...")

# 0.5. Verify required assets exist
print("0.5. Verifying required assets...")
required_files = [
    "assets/drive_v3_discovery.json",
    "assets/background.jpg",
    "assets/app_icon.ico",
    "assets/logo-transperant.png",
    "assets/app.png",
]
for f in required_files:
    if not os.path.exists(f):
        raise FileNotFoundError(f"Missing required file: {f}")
    print(f"   OK: {f}")

# 1. Build exe
print("1. Building exe with PyInstaller...")
result = subprocess.run(["pyinstaller", "--clean", "--noconfirm", "ATLED_BK.spec"],
                       capture_output=True, text=True)
if result.returncode != 0:
    print("LOI build exe!")
    print(result.stderr)
    sys.exit(1)

print(f"\nBuild hoan tat! Version {VERSION}")
print(f"  - dist/ATLED_BK.exe")
