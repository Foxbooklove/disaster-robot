"""Motor package - HAL pattern으로 시뮬/실제 추상화"""

from .hal import MotorHAL, MotorState
from .sim_motor import SimMotorHAL
from .calibration import MotorCalibration, ServoCalibration, DcMotorCalibration


def create_motor_hal(config) -> MotorHAL:
    """
    Config에 따라 적절한 모터 HAL 생성.
    
    - simulation 모드: SimMotorHAL
    - real 모드: GpioMotorHAL 시도 → 실패 시 SimMotorHAL fallback
    """
    if config.is_simulation:
        verbose = False  # 메인 루프에서 너무 자주 호출되니 기본 false
        return SimMotorHAL(
            response_delay=config.simulation.motor_response_delay if config.simulation else 0.02,
            verbose=verbose,
        )
    
    # real 모드
    try:
        from .gpio_motor import GpioMotorHAL
        
        # config에서 캘리브레이션 경로 + 핀 매핑 가져오기
        cal_path = getattr(config, "motor_calibration_path", None) or "config/calibration.yaml"
        max_v = config.robot.motion.max_velocity
        
        # config.motor_pins 같은 게 있으면 활용 (없으면 기본값)
        pins = getattr(config, "motor_pins", None)
        kwargs = {}
        if pins is not None:
            kwargs.update({
                "transform_channels": pins.get("transform_channels"),
                "steer_channels": pins.get("steer_channels"),
                "dc_left_pwm_pin": pins.get("dc_left_pwm_pin", 18),
                "dc_left_dir_pin": pins.get("dc_left_dir_pin", 23),
                "dc_right_pwm_pin": pins.get("dc_right_pwm_pin", 19),
                "dc_right_dir_pin": pins.get("dc_right_dir_pin", 24),
            })
        # None 값 제거
        kwargs = {k: v for k, v in kwargs.items() if v is not None}
        
        return GpioMotorHAL(
            calibration_path=cal_path,
            max_velocity=max_v,
            verbose=True,
            **kwargs,
        )
    except (ImportError, RuntimeError, NotImplementedError) as e:
        print(f"[Motor] GpioMotorHAL 사용 불가 ({e}), SimMotorHAL로 fallback")
        return SimMotorHAL(verbose=True)


__all__ = [
    'MotorHAL', 'MotorState', 'SimMotorHAL', 'create_motor_hal',
    'MotorCalibration', 'ServoCalibration', 'DcMotorCalibration',
]
