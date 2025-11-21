# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['yzuCourseBot_GUI.py'],
    pathex=[],
    binaries=[],
    datas=[('model.h5', '.')],  # 包含 model.h5 檔案
    hiddenimports=[
        'tensorflow',
        'keras',
        'cv2',
        'numpy',
        'requests',
        'bs4',
        'lxml',
        'PIL',
        'h5py',
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='元智選課機器人',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 不顯示命令列視窗
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 可以在這裡指定 .ico 圖示檔案
)

