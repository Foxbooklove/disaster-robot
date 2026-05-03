"""
Help Panel & Time-Series Graph

Help: 단축키 도움말
Graph: 초음파 거리 시계열 (최근 10초)
"""

from collections import deque
from typing import Dict, List, Deque
import time

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainter, QPen, QColor, QFont
from PySide6.QtWidgets import QGroupBox, QGridLayout, QVBoxLayout, QLabel, QWidget

from .theme import COLORS


# ════════════════════════════════════════════════════════════════
# Help Panel
# ════════════════════════════════════════════════════════════════

HELP_ITEMS = [
    ("W / S",   "Forward / Backward"),
    ("A / D",   "Steer Left / Right"),
    ("Space",   "Stop"),
    ("R / F",   "Front Wheel Size +/-"),
    ("T / G",   "Rear Wheel Size +/-"),
    ("M",       "Cycle Steering Mode"),
    ("H",       "Toggle Help"),
    ("Q",       "Quit"),
]


class HelpPanel(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("KEYBOARD CONTROLS", parent)
        
        layout = QGridLayout()
        layout.setColumnStretch(0, 0)
        layout.setColumnStretch(1, 1)
        layout.setHorizontalSpacing(20)
        layout.setVerticalSpacing(5)
        
        for i, (key, desc) in enumerate(HELP_ITEMS):
            key_label = QLabel(key)
            key_label.setObjectName("help_key")
            key_label.setStyleSheet(f"color: {COLORS['accent']}; font-weight: bold;")
            
            desc_label = QLabel(desc)
            desc_label.setObjectName("help_desc")
            desc_label.setStyleSheet(f"color: {COLORS['text_dim']};")
            
            row = i // 2
            col = (i % 2) * 2
            layout.addWidget(key_label, row, col)
            layout.addWidget(desc_label, row, col + 1)
        
        self.setLayout(layout)


# ════════════════════════════════════════════════════════════════
# Time-Series Graph
# ════════════════════════════════════════════════════════════════

class TimeSeriesCanvas(QWidget):
    """초음파 거리의 시계열 그래프 (최근 N초)"""
    
    def __init__(self, sensor_configs, max_range: float,
                 history_seconds: float = 10.0, parent=None):
        super().__init__(parent)
        self.sensor_configs = sensor_configs
        self.max_range = max_range
        self.history_seconds = history_seconds
        
        # 센서별 (timestamp, distance) deque
        self._series: Dict[str, Deque] = {
            s.name: deque(maxlen=300) for s in sensor_configs
        }
        
        # 색상 (다양하게)
        self._colors = [
            QColor("#58a6ff"),  # 파랑
            QColor("#7ee787"),  # 초록
            QColor("#f0883e"),  # 주황
            QColor("#bc8cff"),  # 보라
            QColor("#ffa657"),  # 살구
            QColor("#a5d6ff"),  # 연파랑
        ]
        
        self.setMinimumHeight(140)
        self.setStyleSheet(f"background-color: {COLORS['bg_panel']};")
    
    def add_readings(self, readings) -> None:
        now = time.monotonic()
        for r in readings:
            if r['name'] in self._series:
                self._series[r['name']].append((now, r['distance']))
        
        # 오래된 데이터 정리
        cutoff = now - self.history_seconds
        for name, dq in self._series.items():
            while dq and dq[0][0] < cutoff:
                dq.popleft()
        
        self.update()
    
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        
        rect = self.rect()
        margin_l, margin_r, margin_t, margin_b = 40, 90, 10, 25
        plot_w = rect.width() - margin_l - margin_r
        plot_h = rect.height() - margin_t - margin_b
        
        if plot_w <= 0 or plot_h <= 0:
            return
        
        # 배경 grid
        pen = QPen(QColor(COLORS['border']))
        pen.setStyle(Qt.DashLine)
        p.setPen(pen)
        # 거리 가로선 (1m 간격)
        for y_meters in range(0, int(self.max_range) + 1):
            y_px = margin_t + plot_h - (y_meters / self.max_range) * plot_h
            p.drawLine(margin_l, int(y_px), margin_l + plot_w, int(y_px))
        
        # 축 라벨
        p.setPen(QPen(QColor(COLORS['text_dim'])))
        font = QFont(); font.setPointSize(8)
        p.setFont(font)
        for y_meters in range(0, int(self.max_range) + 1):
            y_px = margin_t + plot_h - (y_meters / self.max_range) * plot_h
            p.drawText(5, int(y_px) + 4, f"{y_meters}m")
        # x축 (시간)
        p.drawText(margin_l, rect.height() - 8, f"-{int(self.history_seconds)}s")
        p.drawText(margin_l + plot_w - 20, rect.height() - 8, "now")
        
        # 시간 윈도우
        now = time.monotonic()
        t_start = now - self.history_seconds
        
        # 각 센서 그리기
        for i, sensor in enumerate(self.sensor_configs):
            color = self._colors[i % len(self._colors)]
            data = self._series[sensor.name]
            
            if len(data) < 2:
                continue
            
            pen = QPen(color, 2)
            p.setPen(pen)
            
            points = []
            for t, dist in data:
                if dist <= 0:
                    continue
                x_frac = (t - t_start) / self.history_seconds
                if x_frac < 0:
                    continue
                x_px = margin_l + x_frac * plot_w
                y_frac = min(dist / self.max_range, 1.0)
                y_px = margin_t + plot_h - y_frac * plot_h
                points.append(QPointF(x_px, y_px))
            
            if len(points) >= 2:
                for j in range(len(points) - 1):
                    p.drawLine(points[j], points[j + 1])
            
            # 범례 (우측)
            legend_y = margin_t + 14 * (i + 1)
            p.fillRect(margin_l + plot_w + 10, legend_y - 6, 12, 3, color)
            p.setPen(QPen(color))
            p.drawText(margin_l + plot_w + 25, legend_y, sensor.name)


class TimeSeriesPanel(QGroupBox):
    def __init__(self, sensor_configs, max_range: float, parent=None):
        super().__init__("DISTANCE HISTORY", parent)
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 16, 10, 10)
        self.canvas = TimeSeriesCanvas(sensor_configs, max_range)
        layout.addWidget(self.canvas)
        self.setLayout(layout)
    
    def add_readings(self, readings) -> None:
        self.canvas.add_readings(readings)
