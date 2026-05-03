# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for the Robot Simulator (raspberry-pi) executable.

빌드 방법:
    cd <project root>
    pyinstaller build_scripts/rpi.spec --clean

결과:
    dist/DisasterRobot-RobotSim.exe
"""

from pathlib import Path
import sys

ROOT = Path(SPECPATH).parent.resolve()

block_cipher = None


# ─────────────────────────────────────────────
# Hidden imports (라파 측은 PyTorch/Ultralytics 안 씀 - 가벼움)
# ─────────────────────────────────────────────
hiddenimports = [
    'shared.config',
    'shared.messages',
    'shared.tcp_framing',
    'shared.udp_video',
    'camera.capture',
    'motor.hal',
    'motor.sim_motor',
    'sensor.ultrasonic',
    'kinematics.base',
    'kinematics.ackermann',
    'kinematics.skid_steer',
    'kinematics.crab',
    'kinematics.double_ackermann',
    'kinematics.manager',
    'estimation.odometry',
]


# ─────────────────────────────────────────────
# Data files
# ─────────────────────────────────────────────
datas = [
    (str(ROOT / 'config' / 'sim.yaml'), 'config'),
    (str(ROOT / 'config' / 'real.yaml'), 'config'),
]


# ─────────────────────────────────────────────
# Analysis
# ─────────────────────────────────────────────
a = Analysis(
    [str(ROOT / 'raspberry-pi' / 'main.py')],
    pathex=[
        str(ROOT),
        str(ROOT / 'raspberry-pi'),
    ],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 라파 측은 GUI/ML 안 씀
        'PySide6',
        'PyQt5',
        'PyQt6',
        'torch',
        'torchvision',
        'ultralytics',
        'matplotlib',
        'tkinter',
        'wx',
    ],
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
    name='DisasterRobot-RobotSim',
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
    upx=True,
    upx_exclude=[],
    name='DisasterRobot-RobotSim',
)
