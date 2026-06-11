import sys
import os

os.chdir(r'c:\Users\AIO - MKT PC\Desktop\Backup_tool')

import logging
import traceback
import threading
import time

print('Setting up error handler...')

def exception_handler(exc_type, exc_value, exc_traceback):
    print(f'EXCEPTION: {exc_type.__name__}: {exc_value}')
    traceback.print_exception(exc_type, exc_value, exc_traceback)

sys.excepthook = exception_handler

print('Importing main module...')
import main
print('Main imported successfully')

print('Creating QApplication...')
from PyQt6.QtWidgets import QApplication
app = QApplication(sys.argv)
print('QApplication created')

print('Creating BackupConfigWindow...')
try:
    window = main.BackupConfigWindow(start_hidden=True)
    print(f'Window created: {window}')
    print(f'Window visible: {window.isVisible()}')
    print('SUCCESS')
except Exception as e:
    print(f'CRASH creating window: {type(e).__name__}: {e}')
    traceback.print_exc()

print('Calling app.exec()...')
sys.exit(app.exec())
