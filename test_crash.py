import sys
import os

os.chdir(r'c:\Users\AIO - MKT PC\Desktop\Backup_tool')

print('Step 1: Basic imports')
from backup_tool import app_config
from backup_tool import startup
from backup_tool import update_helpers
print('Step 1 OK')

print('Step 2: PyQt6')
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
app = QApplication(sys.argv)
print('Step 2 OK - QApplication created')

print('Step 3: APP_DIR check')
print(f'  APP_DIR = {app_config.APP_DIR}')
print(f'  CONFIG_PATH = {app_config.CONFIG_PATH}')
print(f'  LOG_DIR = {app_config.LOG_DIR}')
print(f'  CONFIG exists: {os.path.exists(app_config.CONFIG_PATH)}')

print('Step 4: Load config tuple')
cfg_tuple = app_config.load_config()
print(f'  Config loaded: STORE_NAME={cfg_tuple[0]!r}, WATCH_DIR={cfg_tuple[1]!r}')

print('Step 5: google imports')
import google_auth_httplib2
import httplib2
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account
print('Step 5 OK')

print('Step 6: watchdog imports')
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
print('Step 6 OK')

print('Step 7: Logging setup')
os.makedirs(app_config.LOG_DIR, exist_ok=True)
import logging
logging.basicConfig(
    filename=os.path.join(app_config.LOG_DIR, "backup.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8",
)
print('Step 7 OK')

print('Step 8: Telegram imports')
from backup_tool import telegram_reporting
print('Step 8 OK')

print('All imports OK, app would run now')
sys.exit(0)
