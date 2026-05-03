"""
Radar Widget

탑뷰 레이더. 로봇을 중앙에 두고 각 초음파 센서의 측정 거리를
부채꼴(원호)로 시각화. 군용/항공 레이더 스타일.

[그리기 요소]
1. 동심원 (거리 눈금) - 1m, 2m, 3m, 4m
2. 각도 grid (8방향 또는 4방향)
3. 로봇 (중앙, 차체 외곽 사각형)
4. 각 센서:
   - 위치점
   - 측정 거리만큼 떨어진 부채꼴 (sweep)
   - 거리에 따른 색상 (위험/경고/안전)
5. 거리값 텍스트
"""

import math
from typing import List, Dict, Optional
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QPainterPath
from PySide6.QtWidgets import QWidget, QGroupBox, QVBoxLayout

from .theme import COLORS


class RadarCanvas(QWidget):
    """실제 그리기를 담당하는 위젯"""
    
    def __init__(self, sensor_configs, max_range: float,
                 danger: float, warning: float, parent=None):
        super().__init__(parent)
        self.sensor_configs = sensor_configs   # config의 List[UltrasonicSensor]
        self.max_range = max_range
        self.danger_threshold = danger
        self.warning_threshold = warning
        
        self._distances: Dict[str, float] = {s.name: -1.0 for s in sensor_configs}
        
        self.setMinimumSize(280, 280)
        # 다크 배경
        self.setStyleSheet(f"background-color: {COLORS['bg_panel']};")
    
    def update_distances(self, ultrasonic_readings: List[Dict]) -> None:
        """텔레메트리에서 받은 초음파 데이터 갱신"""
        for r in ultrasonic_readings:
            self._distances[r['name']] = r['distance']
        self.update()  # repaint
    
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        
        rect = self.rect()
        cx = rect.center().x()
        cy = rect.center().y()
        # 반지름 (위젯 크기 - 여백)
        size = min(rect.width(), rect.height())
        radius = (size - 30) / 2
        # 거리 → 픽셀 스케일
        scale = radius / self.max_range
        
        # ─── 1. 거리 동심원 ───
        pen = QPen(QColor(COLORS['border']))
        pen.setStyle(Qt.DashLine)
        pen.setWidth(1)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        for r_meters in [1.0, 2.0, 3.0, 4.0]:
            if r_meters > self.max_range:
                break
            r_px = r_meters * scale
            p.drawEllipse(QPointF(cx, cy), r_px, r_px)
            # 거리 라벨
            p.setPen(QPen(QColor(COLORS['text_dim'])))
            p.drawText(int(cx + r_px - 8), int(cy - 4), f"{r_meters:.0f}m")
            p.setPen(pen)
        
        # ─── 2. 각도 grid (45도 단위) ───
        pen.setStyle(Qt.DotLine)
        p.setPen(pen)
        for angle_deg in range(0, 360, 45):
            a_rad = math.radians(angle_deg)
            ex = cx + radius * math.cos(a_rad)
            ey = cy - radius * math.sin(a_rad)  # y축 반전 (화면 좌표계)
            p.drawLine(QPointF(cx, cy), QPointF(ex, ey))
        
        # ─── 3. 로봇 (중앙) ───
        # 사각형 (실제 로봇 비율로)
        # 크기는 작게 (시각적으로 점 수준)
        robot_w = 30
        robot_h = 40
        p.setPen(QPen(QColor(COLORS['accent']), 2))
        p.setBrush(QColor(COLORS['accent']))
        p.drawRoundedRect(QRectF(cx - robot_w/2, cy - robot_h/2, robot_w, robot_h),
                          4, 4)
        # 전방 표시 (삼각형)
        path = QPainterPath()
        path.moveTo(cx, cy - robot_h/2 - 8)
        path.lineTo(cx - 6, cy - robot_h/2 + 2)
        path.lineTo(cx + 6, cy - robot_h/2 + 2)
        path.closeSubpath()
        p.fillPath(path, QColor(COLORS['accent']))
        
        # ─── 4. 각 센서 ───
        # 좌표 매핑:
        # 로봇 좌표계: x 전방(+), y 좌측(+)
        # 화면 좌표계: 화면 위쪽이 -y, 화면 우측이 +x
        # → 로봇 전방(x+) = 화면 위(-y)
        # → 로봇 좌측(y+) = 화면 좌(-x)
        # 따라서 화면 좌표 = (cx - robot_y * scale, cy - robot_x * scale)
        
        for sensor in self.sensor_configs:
            sx_px = cx - sensor.y * scale * 4   # 위치는 작게 보이게 4배 축소
            sy_px = cy - sensor.x * scale * 4
            
            distance = self._distances.get(sensor.name, -1.0)
            
            # 센서 위치점
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(COLORS['text_dim']))
            p.drawEllipse(QPointF(sx_px, sy_px), 3, 3)
            
            if distance > 0:
                # 색상 (거리에 따라)
                if distance < self.danger_threshold:
                    color = QColor(COLORS['sensor_danger'])
                elif distance < self.warning_threshold:
                    color = QColor(COLORS['sensor_warn'])
                else:
                    color = QColor(COLORS['sensor_safe'])
                
                # 부채꼴 그리기
                # 센서 yaw 방향으로 ±15도 부채꼴, 반지름 = distance * scale
                fan_radius = distance * scale
                fan_angle = 30  # 부채꼴 각도 [deg]
                
                # 센서 yaw (로봇 좌표계) → 화면 좌표계 각도
                # 로봇 yaw=0 (전방) → 화면 위쪽 = 90도
                # Qt의 drawArc는 16분의 1도 단위, 시계 반대 방향 +
                # Qt 0도 = 3시 방향
                screen_angle_deg = 90 + math.degrees(sensor.yaw)
                start_angle = (screen_angle_deg - fan_angle/2) * 16
                span_angle = fan_angle * 16
                
                # 부채꼴 채움 (alpha 살짝 줘서 겹쳐도 OK)
                fan_color = QColor(color)
                fan_color.setAlpha(80)
                p.setBrush(fan_color)
                p.setPen(QPen(color, 1))
                
                # 센서 위치 기준 부채꼴
                fan_rect = QRectF(sx_px - fan_radius, sy_px - fan_radius,
                                  fan_radius * 2, fan_radius * 2)
                p.drawPie(fan_rect, int(start_angle), int(span_angle))
                
                # 거리 라벨 (부채꼴 끝점)
                label_angle_rad = math.radians(screen_angle_deg)
                lx = sx_px + (fan_radius + 12) * math.cos(label_angle_rad)
                ly = sy_px - (fan_radius + 12) * math.sin(label_angle_rad)
                
                p.setPen(QPen(color))
                font = QFont()
                font.setPointSize(8)
                font.setBold(True)
                p.setFont(font)
                p.drawText(int(lx - 16), int(ly), f"{distance:.2f}m")


class RadarPanel(QGroupBox):
    """레이더를 감싸는 GroupBox"""
    
    def __init__(self, sensor_configs, max_range: float,
                 danger: float, warning: float, parent=None):
        super().__init__("PROXIMITY RADAR", parent)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 16, 10, 10)
        
        self.canvas = RadarCanvas(sensor_configs, max_range, danger, warning)
        layout.addWidget(self.canvas)
        
        self.setLayout(layout)
    
    def update_distances(self, ultrasonic_readings) -> None:
        self.canvas.update_distances(ultrasonic_readings)
