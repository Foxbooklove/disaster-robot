"""
GPIO Motor HAL (실제 라파)

회로도 기준 실제 모터 제어:
- PCA9685 16채널 PWM 보드 (I2C)
  - 채널 0~5: 변형 서보 6개 (바퀴 사이즈)
  - 채널 6~11: 조향 서보 6개 (steer)
- BTS7960 듀얼 DC 모터 드라이버
  - 좌 그룹 (3개 모터 병렬): GPIO 18 (PWM), 23 (DIR)
  - 우 그룹 (3개 모터 병렬): GPIO 19 (PWM), 24 (DIR)

[속도 변환 흐름]
1. Kinematics → 6개 wheel_velocities [m/s]
2. 좌3 평균, 우3 평균 (회로상 좌/우 그룹이라)
3. 정규화 ([-1, 1])
4. 캘리브레이션 변환 → (duty, direction)
5. BTS7960 출력

[조향 변환 흐름]
1. Kinematics → 6개 steer_angles [rad]
2. 캘리브레이션 변환 → 펄스폭 [us]
3. PCA9685 채널 6~11 출력

[사이즈 변환 흐름]
1. 6개 wheel_sizes [0,1]
2. 캘리브레이션 변환 → 펄스폭 [us]
3. PCA9685 채널 0~5 출력

[안전]
- 라이브러리 import 실패 → SimMotorHAL fallback (factory에서 처리)
- 초기 상태: 모든 모터 정지 + 서보 중립
- emergency_stop: 모든 출력 0
"""

import time
import math
from typing import List, Optional
from pathlib import Path

from .hal import MotorHAL, MotorState
from .calibration import MotorCalibration


# 회로도 기준 핀/채널 매핑
DEFAULT_TRANSFORM_CHANNELS = [0, 1, 2, 3, 4, 5]   # FL, FR, ML, MR, RL, RR
DEFAULT_STEER_CHANNELS = [6, 7, 8, 9, 10, 11]
DEFAULT_DC_LEFT_PWM = 18
DEFAULT_DC_LEFT_DIR = 23
DEFAULT_DC_RIGHT_PWM = 19
DEFAULT_DC_RIGHT_DIR = 24

# 바퀴 인덱스 (Kinematics base와 일치)
FL, FR, ML, MR, RL, RR = 0, 1, 2, 3, 4, 5


class GpioMotorHAL(MotorHAL):
    """라즈베리파이 실제 모터 제어"""
    
    def __init__(self,
                 calibration: Optional[MotorCalibration] = None,
                 calibration_path: Optional[str] = None,
                 max_velocity: float = 1.0,
                 transform_channels: List[int] = None,
                 steer_channels: List[int] = None,
                 dc_left_pwm_pin: int = DEFAULT_DC_LEFT_PWM,
                 dc_left_dir_pin: int = DEFAULT_DC_LEFT_DIR,
                 dc_right_pwm_pin: int = DEFAULT_DC_RIGHT_PWM,
                 dc_right_dir_pin: int = DEFAULT_DC_RIGHT_DIR,
                 verbose: bool = True):
        """
        Args:
            calibration: 캘리브레이션 객체. None이면 calibration_path에서 로드.
            calibration_path: 캘리브레이션 yaml 경로. None이면 기본값.
            max_velocity: 최대 선속도 [m/s]. 정규화 기준.
            transform_channels: 변형 서보 채널 (기본 [0~5])
            steer_channels: 조향 서보 채널 (기본 [6~11])
            dc_left_pwm_pin/dir_pin: 좌측 DC PWM/DIR 핀
            dc_right_pwm_pin/dir_pin: 우측 DC PWM/DIR 핀
            verbose: 로그 출력
        """
        # 캘리브레이션 로드
        if calibration is not None:
            self._cal = calibration
        elif calibration_path is not None:
            self._cal = MotorCalibration.load(calibration_path)
        else:
            self._cal = MotorCalibration.default()
            if verbose:
                print("[GpioMotorHAL] 캘리브레이션 기본값 사용 (튜닝 안 됨)")
        
        self._max_velocity = max_velocity
        self._verbose = verbose
        
        self._transform_channels = transform_channels or DEFAULT_TRANSFORM_CHANNELS
        self._steer_channels = steer_channels or DEFAULT_STEER_CHANNELS
        
        self._state = MotorState()
        
        # 드라이버 초기화 (지연 import - 라파에서만 동작)
        self._pca = None
        self._dc_left = None
        self._dc_right = None
        self._initialized = False
        
        try:
            from .pca9685_driver import PCA9685Driver
            from .bts7960_driver import BTS7960Driver
            
            # PCA9685 (서보 12개)
            self._pca = PCA9685Driver(frequency_hz=50)
            
            # BTS7960 좌/우 (lgpio 기반, chip handle 자동 공유)
            self._dc_left = BTS7960Driver(
                pwm_pin=dc_left_pwm_pin, dir_pin=dc_left_dir_pin)
            self._dc_right = BTS7960Driver(
                pwm_pin=dc_right_pwm_pin, dir_pin=dc_right_dir_pin)
            
            # 모두 정상 동작 확인
            if (self._pca.is_available and
                self._dc_left.is_available and
                self._dc_right.is_available):
                self._initialized = True
                # 초기 상태: 서보는 중간, DC는 정지
                self._set_all_servos_center()
                if verbose:
                    print("[GpioMotorHAL] 초기화 완료")
            else:
                print("[GpioMotorHAL] 일부 드라이버 사용 불가:")
                print(f"  PCA9685: {self._pca.is_available}")
                print(f"  DC Left: {self._dc_left.is_available}")
                print(f"  DC Right: {self._dc_right.is_available}")
                raise RuntimeError("드라이버 초기화 실패")
                
        except Exception as e:
            print(f"[GpioMotorHAL] 초기화 실패: {e}")
            print("[GpioMotorHAL] SimMotorHAL로 fallback 추천")
            raise
    
    def _set_all_servos_center(self) -> None:
        """모든 서보를 중간(또는 안전 기본 위치)으로"""
        if not self._initialized:
            return
        # 변형 서보: 사이즈 0.5 (중간)
        for ch in self._transform_channels:
            cal = self._find_transform_cal(ch)
            if cal:
                pulse = cal.value_to_pulse(0.5)
                self._pca.set_pulse_us(ch, pulse)
        # 조향 서보: 각도 0 (직진)
        for ch in self._steer_channels:
            cal = self._find_steer_cal(ch)
            if cal:
                pulse = cal.value_to_pulse(0.0)
                self._pca.set_pulse_us(ch, pulse)
    
    def _find_transform_cal(self, channel: int):
        for s in self._cal.transform_servos:
            if s.channel == channel:
                return s
        return None
    
    def _find_steer_cal(self, channel: int):
        for s in self._cal.steer_servos:
            if s.channel == channel:
                return s
        return None
    
    # ════════════════════════════════════════════════════════════════
    # MotorHAL 인터페이스 구현
    # ════════════════════════════════════════════════════════════════
    
    def set_wheel_velocities(self, velocities: List[float]) -> None:
        """6개 [m/s] → 좌3/우3 평균 → BTS7960 출력"""
        if len(velocities) != 6:
            raise ValueError(f"6개 속도 필요, 받음: {len(velocities)}")
        
        self._state.wheel_velocities = list(velocities)
        self._state.last_update_time = time.monotonic()
        
        if not self._initialized:
            return
        
        # 좌/우 그룹 평균 (회로상 병렬이라 같은 명령)
        v_left_avg = (velocities[FL] + velocities[ML] + velocities[RL]) / 3
        v_right_avg = (velocities[FR] + velocities[MR] + velocities[RR]) / 3
        
        # 정규화 ([-1, 1])
        v_left_norm = max(-1.0, min(1.0, v_left_avg / self._max_velocity))
        v_right_norm = max(-1.0, min(1.0, v_right_avg / self._max_velocity))
        
        # 캘리브레이션 변환
        duty_l, dir_l = self._cal.dc_left.velocity_to_duty(v_left_norm)
        duty_r, dir_r = self._cal.dc_right.velocity_to_duty(v_right_norm)
        
        # 출력
        self._dc_left.set(duty_l, dir_l)
        self._dc_right.set(duty_r, dir_r)
    
    def set_steer_angles(self, angles: List[float]) -> None:
        """6개 조향각 [rad] → PCA9685 채널 6~11"""
        if len(angles) != 6:
            raise ValueError(f"6개 조향각 필요, 받음: {len(angles)}")
        
        self._state.steer_angles = list(angles)
        self._state.last_update_time = time.monotonic()
        
        if not self._initialized:
            return
        
        for i, angle in enumerate(angles):
            ch = self._steer_channels[i]
            cal = self._find_steer_cal(ch)
            if cal is None:
                continue
            pulse = cal.value_to_pulse(angle)
            self._pca.set_pulse_us(ch, pulse)
    
    def set_wheel_sizes(self, sizes: List[float]) -> None:
        """6개 사이즈 [0,1] → PCA9685 채널 0~5"""
        if len(sizes) != 6:
            raise ValueError(f"6개 사이즈 필요, 받음: {len(sizes)}")
        
        self._state.wheel_sizes = [max(0.0, min(1.0, s)) for s in sizes]
        self._state.last_update_time = time.monotonic()
        
        if not self._initialized:
            return
        
        for i, size in enumerate(sizes):
            ch = self._transform_channels[i]
            cal = self._find_transform_cal(ch)
            if cal is None:
                continue
            pulse = cal.value_to_pulse(size)
            self._pca.set_pulse_us(ch, pulse)
    
    def emergency_stop(self) -> None:
        """모든 모터 즉시 정지. 서보는 현재 위치 유지."""
        self._state.wheel_velocities = [0.0] * 6
        if self._initialized:
            try:
                self._dc_left.stop()
                self._dc_right.stop()
            except Exception as e:
                print(f"[GpioMotorHAL] emergency_stop 에러: {e}")
        if self._verbose:
            print("[GpioMotorHAL] EMERGENCY STOP")
    
    def shutdown(self) -> None:
        """리소스 정리. 모든 PWM 끔."""
        if self._verbose:
            print("[GpioMotorHAL] 종료 중...")
        
        try:
            # DC 정지
            if self._dc_left is not None:
                self._dc_left.stop()
                self._dc_left.shutdown()
            if self._dc_right is not None:
                self._dc_right.stop()
                self._dc_right.shutdown()
            
            # PCA9685 끔 (서보 힘 빠짐)
            if self._pca is not None:
                self._pca.disable_all()
                self._pca.shutdown()
        except Exception as e:
            print(f"[GpioMotorHAL] 종료 중 에러: {e}")
        finally:
            self._initialized = False
    
    def get_state(self) -> MotorState:
        return self._state
