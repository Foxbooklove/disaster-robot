"""
BTS7960 Driver Wrapper (lgpio version)

BTS7960 H-Bridge DC 모터 드라이버 (43A 듀얼 채널).
회로도 기준: 좌측 3개 모터 병렬, 우측 3개 모터 병렬.

[하드웨어]
PWM + DIR 방식:
  - PWM: 속도 (0~100%)
  - DIR: 방향 (HIGH/LOW)

회로도 핀:
- 좌: GPIO 18 (PWM), GPIO 23 (DIR)
- 우: GPIO 19 (PWM), GPIO 24 (DIR)

[라이브러리]
lgpio 사용 (Raspberry Pi OS Trixie/Bookworm 표준).

Trixie에선 pigpio가 deprecated 되고 lgpio가 표준이 됨.
- 라파 재단 공식
- daemon 불필요 (단순)
- 직접 chip 핸들 열고 닫음

설치 (이미 깔려있어야 함):
    sudo apt install python3-lgpio

[사용]
    bts = BTS7960Driver(pwm_pin=18, dir_pin=23)
    bts.set(duty=0.5, direction=1)   # 50% 정회전
    bts.set(duty=0.0, direction=1)   # 정지
    bts.shutdown()
"""

from typing import Optional


# BTS7960 권장 PWM 주파수
DEFAULT_PWM_FREQ_HZ = 1000


class BTS7960Driver:
    """BTS7960 단일 채널 (좌 또는 우 그룹)"""
    
    # 클래스 레벨에서 chip 핸들 공유 (한 번만 열기)
    _chip_handle = None
    _refcount = 0
    
    def __init__(self,
                 pwm_pin: int,
                 dir_pin: int,
                 frequency_hz: int = DEFAULT_PWM_FREQ_HZ,
                 chip: int = 0):
        """
        Args:
            pwm_pin: PWM 출력 GPIO 번호 (BCM)
            dir_pin: 방향 출력 GPIO 번호 (BCM)
            frequency_hz: PWM 주파수
            chip: GPIO chip 번호 (라파4는 0)
        """
        self._pwm_pin = pwm_pin
        self._dir_pin = dir_pin
        self._freq = frequency_hz
        self._available = False
        self._chip = chip
        
        try:
            import lgpio
            self._lgpio = lgpio
            
            # chip 한 번만 열기 (여러 BTS7960 인스턴스가 공유)
            if BTS7960Driver._chip_handle is None:
                BTS7960Driver._chip_handle = lgpio.gpiochip_open(chip)
            BTS7960Driver._refcount += 1
            
            h = BTS7960Driver._chip_handle
            
            # GPIO 설정
            lgpio.gpio_claim_output(h, pwm_pin, 0)
            lgpio.gpio_claim_output(h, dir_pin, 0)
            
            # 초기 상태: 정지
            lgpio.gpio_write(h, dir_pin, 0)
            lgpio.tx_pwm(h, pwm_pin, frequency_hz, 0.0)  # duty 0%
            
            self._available = True
            print(f"[BTS7960] 초기화 완료 (PWM={pwm_pin}, DIR={dir_pin}, {frequency_hz}Hz)")
        except ImportError as e:
            print(f"[BTS7960] lgpio 라이브러리 없음: {e}")
            print("[BTS7960] 설치: sudo apt install python3-lgpio")
        except Exception as e:
            print(f"[BTS7960] 초기화 실패: {e}")
    
    @property
    def is_available(self) -> bool:
        return self._available
    
    def set(self, duty: float, direction: int) -> None:
        """
        Args:
            duty: PWM 듀티 [0, 1]
            direction: 1 (정회전) 또는 -1 (역회전)
        """
        if not self._available:
            return
        
        duty = max(0.0, min(1.0, duty))
        dir_value = 1 if direction >= 0 else 0
        
        h = BTS7960Driver._chip_handle
        try:
            self._lgpio.gpio_write(h, self._dir_pin, dir_value)
            # lgpio.tx_pwm 은 듀티를 % (0~100) 로 받음
            self._lgpio.tx_pwm(h, self._pwm_pin, self._freq, duty * 100.0)
        except Exception as e:
            print(f"[BTS7960] set 에러: {e}")
    
    def stop(self) -> None:
        """정지 (PWM=0)"""
        if not self._available:
            return
        try:
            self._lgpio.tx_pwm(BTS7960Driver._chip_handle, self._pwm_pin, self._freq, 0.0)
        except Exception as e:
            print(f"[BTS7960] stop 에러: {e}")
    
    def shutdown(self) -> None:
        """리소스 정리"""
        if not self._available:
            return
        try:
            self.stop()
            h = BTS7960Driver._chip_handle
            # 핀 free
            self._lgpio.gpio_free(h, self._pwm_pin)
            self._lgpio.gpio_free(h, self._dir_pin)
            
            # 마지막 인스턴스면 chip 닫기
            BTS7960Driver._refcount -= 1
            if BTS7960Driver._refcount <= 0 and BTS7960Driver._chip_handle is not None:
                self._lgpio.gpiochip_close(BTS7960Driver._chip_handle)
                BTS7960Driver._chip_handle = None
                BTS7960Driver._refcount = 0
        except Exception as e:
            print(f"[BTS7960] 종료 중 에러: {e}")
        finally:
            self._available = False
