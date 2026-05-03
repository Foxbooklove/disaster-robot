# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for the Operator (laptop) executable.

빌드 방법:
    cd <project root>
    pyinstaller build_scripts/laptop.spec --clean

결과:
    dist/DisasterRobot-Operator.exe
"""

from pathlib import Path
import sys

# 프로젝트 루트 경로 (spec 파일은 build_scripts/ 안)
ROOT = Path(SPECPATH).parent.resolve()

block_cipher = None


# ─────────────────────────────────────────────
# Hidden imports
# PyInstaller가 자동으로 못 찾는 동적 import들
# ─────────────────────────────────────────────
hiddenimports = [
    # PySide6
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    
    # Ultralytics는 동적 import 많음
    'ultralytics',
    'ultralytics.nn.tasks',
    'ultralytics.utils',
    'ultralytics.engine.predictor',
    'ultralytics.engine.results',
    
    # PyTorch backend
    'torch',
    'torchvision',
    
    # 우리 모듈들
    'shared.config',
    'shared.messages',
    'shared.tcp_framing',
    'shared.udp_video',
    'communication.manager',
    'detection.yolo',
    'gui.main_window',
    'gui.video_widget',
    'gui.status_panel',
    'gui.radar_widget',
    'gui.help_widget',
    'gui.theme',
]


# ─────────────────────────────────────────────
# Data files (런타임에 필요한 비-Python 파일)
# ─────────────────────────────────────────────
datas = [
    # config 파일
    (str(ROOT / 'config' / 'sim.yaml'), 'config'),
    (str(ROOT / 'config' / 'real.yaml'), 'config'),
    
    # YOLO 모델 (없으면 빌드는 되지만 런타임에 다운로드 시도)
    # yolov8n.pt가 프로젝트 루트에 있어야 함
]

# YOLO 모델이 있으면 같이 묶기
yolo_pt = ROOT / 'yolov8n.pt'
if yolo_pt.exists():
    datas.append((str(yolo_pt), '.'))


# ─────────────────────────────────────────────
# Analysis
# ─────────────────────────────────────────────
a = Analysis(
    [str(ROOT / 'laptop' / 'main.py')],
    pathex=[
        str(ROOT),
        str(ROOT / 'laptop'),
    ],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 안 쓰는 거 빼서 용량 절약
        'matplotlib',  # GUI에선 안 씀 (visualize.py들에서만)
        'tkinter',
        'PyQt5',
        'PyQt6',
        'wx',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)


# ─────────────────────────────────────────────
# Executable
# --onefile 대신 --onedir 사용 (시작 빠름, 디버깅 쉬움)
# ─────────────────────────────────────────────
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='DisasterRobot-Operator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # 콘솔 창도 같이 (디버그 메시지 보기 위해)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='build_scripts/icon.ico',  # 아이콘 있으면 추가
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='DisasterRobot-Operator',
)
