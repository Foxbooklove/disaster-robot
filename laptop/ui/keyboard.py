"""
Keyboard Input Handler (cv2.waitKey 버전)

cv2.imshow 창 위에서 동작하는 단순 키보드 입력.
PySide6 GUI 만들면 이건 참고용으로 남기고 GUI 측 keyPressEvent 사용.

[키 매핑]
W/S: 전진/후진 (throttle)
A/D: 좌/우 조향 (steer)
Space: 정지
R/F: 앞바퀴 사이즈 +/-
T/G: 뒷바퀴 사이즈 +/-
M: 조향 모드 순환
H: 도움말 토글
Q: 종료

[연속 입력 처리]
cv2.waitKey는 한 번 누름만 감지. 누르고 있는 동안 연속 입력은
GUI(PySide6) 들어가야 가능. 이 단순 버전에선 한 번 누름으로 동작.
"""

import cv2
from dataclasses import dataclass
from typing import Optional


@dataclass
class ControlState:
    """현재 조종 상태 (메인 루프가 들고 있음)"""
    throttle: float = 0.0
    steer: float = 0.0
    wheel_size_front: float = 0.5
    wheel_size_rear: float = 0.5
    steering_mode: str = "Ackermann"
    show_help: bool = True
    quit_requested: bool = False


# 모드 순환 순서
STEERING_MODES = ["Ackermann", "SkidSteer", "Crab", "DoubleAckermann"]


class CV2KeyboardHandler:
    """cv2.waitKey 기반 단순 키보드 핸들러"""
    
    THROTTLE_STEP = 0.2
    STEER_STEP = 0.3
    SIZE_STEP = 0.1
    
    def __init__(self):
        self.state = ControlState()
        self._mode_idx = 0
    
    def process(self, key: int) -> Optional[str]:
        """
        cv2.waitKey 반환값 처리.
        
        Returns:
            액션 종류 문자열 ('drive', 'wheel_size', 'mode', 'stop', 'quit') 또는 None
        """
        if key == -1:
            return None
        
        key_lower = key & 0xFF
        action = None
        
        if key_lower == ord('w'):
            self.state.throttle = min(1.0, self.state.throttle + self.THROTTLE_STEP)
            action = 'drive'
        elif key_lower == ord('s'):
            self.state.throttle = max(-1.0, self.state.throttle - self.THROTTLE_STEP)
            action = 'drive'
        elif key_lower == ord('a'):
            self.state.steer = min(1.0, self.state.steer + self.STEER_STEP)
            action = 'drive'
        elif key_lower == ord('d'):
            self.state.steer = max(-1.0, self.state.steer - self.STEER_STEP)
            action = 'drive'
        elif key_lower == ord(' '):
            self.state.throttle = 0.0
            self.state.steer = 0.0
            action = 'stop'
        elif key_lower == ord('r'):
            self.state.wheel_size_front = min(1.0, self.state.wheel_size_front + self.SIZE_STEP)
            action = 'wheel_size'
        elif key_lower == ord('f'):
            self.state.wheel_size_front = max(0.0, self.state.wheel_size_front - self.SIZE_STEP)
            action = 'wheel_size'
        elif key_lower == ord('t'):
            self.state.wheel_size_rear = min(1.0, self.state.wheel_size_rear + self.SIZE_STEP)
            action = 'wheel_size'
        elif key_lower == ord('g'):
            self.state.wheel_size_rear = max(0.0, self.state.wheel_size_rear - self.SIZE_STEP)
            action = 'wheel_size'
        elif key_lower == ord('m'):
            self._mode_idx = (self._mode_idx + 1) % len(STEERING_MODES)
            self.state.steering_mode = STEERING_MODES[self._mode_idx]
            action = 'mode'
        elif key_lower == ord('h'):
            self.state.show_help = not self.state.show_help
        elif key_lower == ord('q'):
            self.state.quit_requested = True
            action = 'quit'
        
        return action


HELP_TEXT = """
=== 조작법 ===
W/S    : 전진/후진
A/D    : 좌/우 조향
Space  : 정지
R/F    : 앞바퀴 사이즈 +/-
T/G    : 뒷바퀴 사이즈 +/-
M      : 조향 모드 전환
H      : 도움말 토글
Q      : 종료
"""
