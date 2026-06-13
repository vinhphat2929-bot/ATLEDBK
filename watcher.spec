# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['backup_tool/offline_watcher.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('backup_tool', 'backup_tool'),
    ],
    hiddenimports=[
        'requests', 'urllib3', 'certifi', 'charset_normalizer', 'idna',
        'backup_tool.drive_discovery_embed'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ATLED_BK_Watcher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_creator=[],
    name='ATLED_BK_Watcher',
    include_files=[
        ('C:\\Users\\AIO Tech\\AppData\\Local\\Programs\\Python\\Python314\\python314.dll', 'python314.dll'),
        ('C:\\Users\\AIO Tech\\AppData\\Local\\Programs\\Python\\Python314\\python3.dll', 'python3.dll'),
    ],
)
