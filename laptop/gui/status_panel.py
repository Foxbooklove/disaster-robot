"""
Status Panel

오른쪽 상단에 위치. 로봇 현재 상태 표시.
- 조향 모드
- Throttle / Steer
- Pose (x, y, yaw)
- Velocity
- Wheel size
- 통신 상태 (FPS, latency)
"""

from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout

from .theme import COLORS


class StatusPanel(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("STATUS", parent)
        
        layout = QGridLayout()
        layout.setColumnStretch(0, 0)
        layout.setColumnStretch(1, 1)
        layout.setVerticalSpacing(6)
        
        self._values = {}
        rows = [
            ("Mode",       "mode",        "Ackermann"),
            ("Throttle",   "throttle",    "+0.00"),
            ("Steer",      "steer",       "+0.00"),
            ("Position",   "pose",        "(0.00, 0.00)"),
            ("Heading",    "heading",     "+0.0°"),
            ("Velocity",   "velocity",    "+0.00 m/s"),
            ("Wheel F/R",  "wheel_size",  "0.50 / 0.50"),
            ("Video",      "video_fps",   "-- FPS"),
            ("Telemetry",  "tele_status", "--"),
            ("Cmd age",    "cmd_age",     "0.0 s"),
        ]
        for i, (label_text, key, default) in enumerate(rows):
            label = QLabel(label_text)
            label.setStyleSheet(f"color: {COLORS['text_dim']};")
            value = QLabel(default)
            value.setObjectName("status_value")
            value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            layout.addWidget(label, i, 0)
            layout.addWidget(value, i, 1)
            self._values[key] = value
        
        self.setLayout(layout)
    
    def update_control(self, throttle: float, steer: float,
                       mode: str, wheel_front: float, wheel_rear: float):
        self._values['mode'].setText(mode)
        self._values['throttle'].setText(f"{throttle:+.2f}")
        self._values['steer'].setText(f"{steer:+.2f}")
        self._values['wheel_size'].setText(f"{wheel_front:.2f} / {wheel_rear:.2f}")
    
    def update_telemetry(self, telemetry):
        if telemetry is None:
            return
        import math
        pose = telemetry.pose
        vel = telemetry.velocity
        
        self._values['pose'].setText(f"({pose['x']:+.2f}, {pose['y']:+.2f})")
        self._values['heading'].setText(f"{math.degrees(pose['psi']):+.1f}°")
        self._values['velocity'].setText(f"{vel['v_x']:+.2f} m/s")
        self._values['cmd_age'].setText(f"{telemetry.last_command_age:.1f} s")
        
        # Cmd age 색상 (오래되면 경고)
        cmd_age_lbl = self._values['cmd_age']
        if telemetry.last_command_age > 2.0:
            cmd_age_lbl.setObjectName("status_value_danger")
        elif telemetry.last_command_age > 1.0:
            cmd_age_lbl.setObjectName("status_value_warning")
        else:
            cmd_age_lbl.setObjectName("status_value")
        # objectName 변경 후엔 스타일 재적용 필요
        cmd_age_lbl.setStyleSheet(cmd_age_lbl.styleSheet())
    
    def update_video_fps(self, fps: float):
        self._values['video_fps'].setText(f"{fps:.1f} FPS")
    
    def update_telemetry_status(self, status: str, ok: bool = True):
        self._values['tele_status'].setText(status)
        if ok:
            self._values['tele_status'].setStyleSheet(f"color: {COLORS['success']};")
        else:
            self._values['tele_status'].setStyleSheet(f"color: {COLORS['danger']};")
