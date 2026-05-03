"""
Video Widget

영상 표시 + 키보드 이벤트 처리.

[키 입력 처리 방식]
PySide6의 keyPressEvent / keyReleaseEvent 사용.
"누르고 있는 동안 동작" 위해 Set으로 관리.

타이머가 16ms마다 깨워서 현재 눌린 키 set으로 명령 갱신.
이게 자동차 게임처럼 자연스러운 조종감.
"""

from typing import Set, Optional
import numpy as np
import cv2
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QImage, QPixmap, QKeyEvent
from PySide6.QtWidgets import QLabel, QSizePolicy

from .theme import COLORS


class VideoWidget(QLabel):
    """영상 표시 + 키 입력 캡처"""
    
    # 시그널: 키 상태 변화 시 외부에 알림
    keys_changed = Signal(set)         # 현재 눌린 키 집합
    key_pressed = Signal(int)          # 단발 동작용 (M, H, Q 등)
    
    # 단발 동작 키 (한 번 누름)
    DISCRETE_KEYS = {Qt.Key_M, Qt.Key_H, Qt.Key_Q, Qt.Key_Space,
                     Qt.Key_R, Qt.Key_F, Qt.Key_T, Qt.Key_G}
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("video_label")
        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(640, 480)
        self.setText("Waiting for video stream...")
        self.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 14pt;")
        
        # 키보드 입력 받으려면 focus 필요
        self.setFocusPolicy(Qt.StrongFocus)
        
        self._pressed_keys: Set[int] = set()
    
    def show_frame(self, bgr_frame: np.ndarray) -> None:
        """OpenCV BGR → QImage → 표시"""
        if bgr_frame is None:
            return
        
        h, w = bgr_frame.shape[:2]
        # BGR → RGB
        rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        # numpy → QImage
        bytes_per_line = 3 * w
        qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        # 위젯 크기에 맞게 스케일
        pixmap = QPixmap.fromImage(qimg)
        scaled = pixmap.scaled(self.size(), Qt.KeepAspectRatio,
                               Qt.SmoothTransformation)
        self.setPixmap(scaled)
    
    # ─── 키보드 이벤트 ───
    
    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.isAutoRepeat():
            # 누르고 있는 동안 OS가 반복 발생시키는 이벤트는 무시
            # 우리는 set으로 직접 관리
            return
        
        key = event.key()
        self._pressed_keys.add(key)
        
        # 단발 동작 키는 즉시 시그널
        if key in self.DISCRETE_KEYS:
            self.key_pressed.emit(key)
        
        # 연속 입력 (W/A/S/D)은 set 변화 알림
        self.keys_changed.emit(self._pressed_keys.copy())
        
        super().keyPressEvent(event)
    
    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if event.isAutoRepeat():
            return
        
        key = event.key()
        self._pressed_keys.discard(key)
        self.keys_changed.emit(self._pressed_keys.copy())
        
        super().keyReleaseEvent(event)
    
    def get_pressed_keys(self) -> Set[int]:
        return self._pressed_keys.copy()
