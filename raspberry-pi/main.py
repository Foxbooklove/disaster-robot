"""
Raspberry Pi Main

전체 흐름:
    [카메라] ──jpeg──▶ [VideoSender] ──UDP──▶ 노트북
    
    노트북 ──TCP──▶ [Command Receiver] ──▶ [Kinematics] ──▶ [Motor HAL]
    
    [Sensors] + [Odometry] ──▶ [Telemetry Sender] ──TCP──▶ 노트북

[스레드 구성]
- main: 명령 수신 + 모터 제어 + 메인 루프
- video_thread: 카메라 → 영상 송신 (별도 스레드, 메인 영향 X)
- telemetry_thread: 센서 + 텔레메트리 송신 (별도 스레드)

[안전]
- 명령 timeout: 일정 시간 명령 없으면 정지
- 영상 송신 실패: 로그 후 무시 (메인 멈추지 않음)
- 통신 끊김 감지 시 return_to_base
"""

import sys
import os
import time
import socket
import threading
import argparse
import math
from pathlib import Path
from collections import deque

# 경로 설정
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "raspberry-pi"))

import cv2
import numpy as np

from shared.config import load_config, Config
from shared.tcp_framing import send_framed, recv_framed
from shared.udp_video import VideoSender
from shared.messages import (
    DriveCommand, WheelSizeCommand, SteeringModeCommand, StopCommand,
    TelemetryMessage, LogMessage, MessageType,
    parse_command, encode_message,
)

from camera import create_camera
from motor import create_motor_hal, create_encoders
from sensor import create_ultrasonic_hal
from kinematics import KinematicsManager
from estimation import (
    DifferentialOdometry, WheelEncoderData,
    EstimationManager, OpticalFlowEstimator,
)


# ════════════════════════════════════════════════════════════════
# 영상 송신 스레드
# ════════════════════════════════════════════════════════════════

def video_loop(camera, video_sender: VideoSender, jpeg_quality: int,
               send_size: tuple, stop_event: threading.Event,
               optical_flow=None, estimation=None):
    """카메라 프레임을 JPEG으로 압축해서 UDP 청크로 송신.
    
    부수적으로 광학 흐름도 계산해서 EstimationManager에 전달.
    """
    print("[Video] 영상 송신 스레드 시작")
    sw, sh = send_size
    frame_count = 0
    last_log_time = time.monotonic()
    fps_count = 0
    optical_skip_count = 0
    
    while not stop_event.is_set():
        frame = camera.read()
        if frame is None:
            time.sleep(0.05)
            continue
        
        # 광학 흐름 (원본 프레임에서, 다운스케일 전)
        # 매 프레임 돌리면 부담이라 2프레임마다 한 번
        if optical_flow is not None and estimation is not None and optical_flow.is_available:
            optical_skip_count += 1
            if optical_skip_count >= 2:
                optical_skip_count = 0
                try:
                    v_flow, valid = optical_flow.update(frame)
                    estimation.on_optical_flow(v_flow, valid)
                except Exception as e:
                    print(f"[OpticalFlow] 에러: {e}")
        
        # 송신용 다운스케일
        if frame.shape[1] != sw or frame.shape[0] != sh:
            frame = cv2.resize(frame, (sw, sh))
        
        # JPEG 인코딩
        ok, encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
        if not ok:
            continue
        
        try:
            video_sender.send(encoded.tobytes())
            fps_count += 1
        except OSError as e:
            print(f"[Video] 송신 실패: {e}")
        
        frame_count += 1
        
        # 1초마다 FPS 로그
        now = time.monotonic()
        if now - last_log_time >= 5.0:
            fps = fps_count / (now - last_log_time)
            print(f"[Video] {fps:.1f} fps, {frame_count} frames sent")
            fps_count = 0
            last_log_time = now
    
    print("[Video] 영상 송신 스레드 종료")


# ════════════════════════════════════════════════════════════════
# 텔레메트리 송신 스레드
# ════════════════════════════════════════════════════════════════

def telemetry_loop(telemetry_conn, ultrasonic_hal, robot_state,
                   ultrasonic_rate: float, stop_event: threading.Event,
                   estimation=None):
    """센서 + 자세 추정 → 텔레메트리 메시지 주기 송신.
    
    Args:
        estimation: EstimationManager (None이면 estimation 필드 비움)
    """
    print("[Telemetry] 텔레메트리 송신 스레드 시작")
    interval = 1.0 / ultrasonic_rate
    
    while not stop_event.is_set():
        loop_start = time.monotonic()
        
        # 센서 읽기
        try:
            us_readings = ultrasonic_hal.read_all()
        except Exception as e:
            print(f"[Telemetry] 센서 읽기 실패: {e}")
            us_readings = []
        
        # Estimation 상세 정보
        if estimation is not None:
            est = estimation.state
            estimation_dict = {
                "odom": {"x": est.odom_x, "y": est.odom_y, "psi": est.odom_psi},
                "ekf": {"x": est.ekf_x, "y": est.ekf_y, "psi": est.ekf_psi,
                        "v": est.ekf_v, "omega": est.ekf_omega},
                "measurements": {
                    "v_left": est.v_left, "v_right": est.v_right,
                    "v_encoder": est.v_encoder, "omega_encoder": est.omega_encoder,
                    "v_optical": est.v_optical, "optical_valid": est.optical_valid,
                },
            }
        else:
            estimation_dict = None
        
        # 텔레메트리 메시지 구성
        msg = TelemetryMessage(
            timestamp=time.monotonic(),
            pose={
                "x": robot_state['pose'][0],
                "y": robot_state['pose'][1],
                "psi": robot_state['pose'][2],
            },
            velocity={
                "v_x": robot_state['velocity'][0],
                "v_y": robot_state['velocity'][1],
                "yaw_rate": robot_state['velocity'][2],
            },
            estimation=estimation_dict if estimation_dict else TelemetryMessage().estimation,
            steering_mode=robot_state['steering_mode'],
            wheel_size={
                "front": robot_state['wheel_size_front'],
                "middle": robot_state.get('wheel_size_middle', 0.5),
                "rear": robot_state['wheel_size_rear'],
            },
            ultrasonic=[
                {"name": r.name, "distance": r.distance}
                for r in us_readings
            ],
            last_command_age=time.monotonic() - robot_state['last_command_time'],
        )
        
        # 송신
        try:
            send_framed(telemetry_conn, encode_message(msg))
        except (OSError, BrokenPipeError) as e:
            print(f"[Telemetry] 송신 실패 (연결 끊김?): {e}")
            stop_event.set()
            break
        
        # 다음 주기까지 대기
        elapsed = time.monotonic() - loop_start
        sleep_time = max(0, interval - elapsed)
        time.sleep(sleep_time)
    
    print("[Telemetry] 텔레메트리 송신 스레드 종료")


# ════════════════════════════════════════════════════════════════
# 메인
# ════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='config/sim.yaml',
                        help='config YAML 경로')
    parser.add_argument('--mode', choices=['dev-wired', 'dev-wireless'],
                        default=None,
                        help='네트워크 모드 (기본: 시연용)')
    args = parser.parse_args()
    
    config = load_config(ROOT / args.config)
    
    # --mode 옵션으로 laptop_ip 오버라이드
    if args.mode:
        mode_cfg = config.network.modes.get(args.mode, {})
        if 'laptop_ip' in mode_cfg:
            config.network.laptop_ip = mode_cfg['laptop_ip']
            print(f"[Main] 네트워크 모드: {args.mode} (laptop_ip → {config.network.laptop_ip})")
    
    print(f"[Main] Config 로드 완료 (mode={config.mode})")
    
    # ─── 모듈 초기화 ───
    camera = create_camera(config)
    motor = create_motor_hal(config)
    ultrasonic = create_ultrasonic_hal(config)
    kinematics_mgr = KinematicsManager(config.robot)
    odometry = DifferentialOdometry(track_width=config.robot.track)
    
    # 엔코더 + 추정 매니저 (실기 모드일 때만 실제 엔코더, 그 외엔 None)
    encoder_left, encoder_right = create_encoders(config)
    estimation = EstimationManager(
        encoder_left=encoder_left,
        encoder_right=encoder_right,
        track_width=config.robot.track,
        dt=0.02,
    )
    has_real_encoders = estimation.has_real_encoders
    print(f"[Main] 엔코더: {'실기' if has_real_encoders else '시뮬 (명령 속도 기반)'}")
    
    # 광학흐름 추정기 (영상 송신 스레드에서 호출)
    optical_flow = OpticalFlowEstimator(
        scale=getattr(config, "optical_flow_scale", 0.001),  # 캘 전 placeholder
    )
    
    # 통신 - 노트북에 연결 시도
    laptop_ip = config.network.laptop_ip
    
    print(f"[Main] 노트북 ({laptop_ip}) 연결 시도...")
    
    # Retry 로직: 노트북이 먼저 listen해야 하는데 timing 이슈 방지
    def connect_with_retry(port: int, name: str, retries: int = 30, delay: float = 1.0):
        for attempt in range(retries):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect((laptop_ip, port))
                return s
            except (ConnectionRefusedError, OSError) as e:
                if attempt == retries - 1:
                    raise
                if attempt % 5 == 0:
                    print(f"[Main] {name} 연결 재시도 {attempt+1}/{retries}...")
                time.sleep(delay)
        return None
    
    # TCP: 명령 수신 (노트북이 서버, 라파가 클라이언트)
    cmd_sock = connect_with_retry(config.network.command_port, "명령")
    print(f"[Main] 명령 채널 연결 완료 (port {config.network.command_port})")
    
    # TCP: 텔레메트리 송신
    tele_sock = connect_with_retry(config.network.telemetry_port, "텔레메트리")
    print(f"[Main] 텔레메트리 채널 연결 완료 (port {config.network.telemetry_port})")
    
    # UDP: 영상 송신
    video_sender = VideoSender(
        target_host=laptop_ip,
        target_port=config.network.video_port,
        chunk_payload_size=config.network.video_chunk_size,
    )
    
    # ─── 공유 상태 (스레드 간) ───
    robot_state = {
        'pose': [0.0, 0.0, 0.0],          # x, y, psi
        'velocity': [0.0, 0.0, 0.0],      # v_x, v_y, yaw_rate
        'steering_mode': kinematics_mgr.current_name,
        'wheel_size_front': config.robot.wheel.radius_default / config.robot.wheel.radius_max,
        'wheel_size_middle': config.robot.wheel.radius_default / config.robot.wheel.radius_max,
        'wheel_size_rear': config.robot.wheel.radius_default / config.robot.wheel.radius_max,
        'last_command_time': time.monotonic(),
    }
    
    # 명령 히스토리 (return_to_base용)
    command_history = deque(maxlen=500)
    
    stop_event = threading.Event()
    
    # ─── 스레드 시작 ───
    video_thread = threading.Thread(
        target=video_loop,
        args=(camera, video_sender, config.camera.jpeg_quality,
              (config.camera.send_width, config.camera.send_height), stop_event,
              optical_flow, estimation),
        daemon=True,
    )
    video_thread.start()
    
    telemetry_thread = threading.Thread(
        target=telemetry_loop,
        args=(tele_sock, ultrasonic, robot_state,
              config.sensors.ultrasonic.update_rate, stop_event,
              estimation),
        daemon=True,
    )
    telemetry_thread.start()
    
    # ─── 메인 루프 (명령 수신 + 모터 제어) ───
    cmd_sock.setblocking(True)
    cmd_sock.settimeout(0.1)  # 100ms 타임아웃 (non-blocking 흉내)
    
    print("[Main] 메인 루프 시작")
    last_command_time = time.monotonic()
    last_drive = DriveCommand()
    
    try:
        while not stop_event.is_set():
            loop_start = time.monotonic()
            
            # ─── 명령 수신 (non-blocking) ───
            try:
                payload = recv_framed(cmd_sock, timeout=0.05)
                if payload is None:
                    print("[Main] 명령 채널 끊김")
                    break
                
                cmd = parse_command(payload)
                last_command_time = time.monotonic()
                robot_state['last_command_time'] = last_command_time
                
                # 명령 처리
                if isinstance(cmd, DriveCommand):
                    last_drive = cmd
                    command_history.append({
                        'time': last_command_time,
                        'cmd': cmd,
                    })
                elif isinstance(cmd, WheelSizeCommand):
                    # 6개 사이즈로 확장: 앞 2개=front, 중간 2개=middle, 뒤 2개=rear
                    sizes = [cmd.front, cmd.front, cmd.middle, cmd.middle, cmd.rear, cmd.rear]
                    motor.set_wheel_sizes(sizes)
                    robot_state['wheel_size_front'] = cmd.front
                    robot_state['wheel_size_middle'] = cmd.middle
                    robot_state['wheel_size_rear'] = cmd.rear
                elif isinstance(cmd, SteeringModeCommand):
                    if kinematics_mgr.set_mode(cmd.mode):
                        robot_state['steering_mode'] = cmd.mode
                        print(f"[Main] 조향 모드: {cmd.mode}")
                elif isinstance(cmd, StopCommand):
                    motor.emergency_stop()
                    last_drive = DriveCommand()
            except socket.timeout:
                pass
            except Exception as e:
                print(f"[Main] 명령 처리 에러: {e}")
            
            # ─── 명령 timeout 체크 ───
            now = time.monotonic()
            if now - last_command_time > config.safety.command_timeout:
                print(f"[Main] 명령 timeout ({config.safety.command_timeout}s) → 정지")
                motor.emergency_stop()
                last_drive = DriveCommand()
                # timeout 후엔 이 메시지 한 번만 (다시 명령 오면 풀림)
                last_command_time = now  # 스팸 방지
            
            # ─── Kinematics → 모터 명령 ───
            kin_cmd = kinematics_mgr.compute(last_drive.throttle, last_drive.steer)
            
            velocities = [w.velocity for w in kin_cmd.wheels]
            # 조향각 6개 (모든 바퀴) - 회로도 기준
            steer_angles = [w.steer_angle for w in kin_cmd.wheels]
            
            motor.set_wheel_velocities(velocities)
            motor.set_steer_angles(steer_angles)
            
            # ─── Estimation 업데이트 (엔코더 + EKF) ───
            from kinematics import FL, FR, ML, MR, RL, RR
            # 시뮬 모드 fallback용 명령 속도 (실기엔 안 쓰임)
            v_left_avg = (velocities[FL] + velocities[ML] + velocities[RL]) / 3
            v_right_avg = (velocities[FR] + velocities[MR] + velocities[RR]) / 3
            
            dt = 0.02  # 메인 루프 주기 가정
            est_state = estimation.step(
                dt=dt,
                v_left_sim=v_left_avg,
                v_right_sim=v_right_avg,
            )
            
            # GUI에 보낼 pose/velocity (EKF 결과 사용)
            robot_state['pose'][0] = est_state.ekf_x
            robot_state['pose'][1] = est_state.ekf_y
            robot_state['pose'][2] = est_state.ekf_psi
            robot_state['velocity'][0] = est_state.ekf_v
            robot_state['velocity'][2] = est_state.ekf_omega
            
            # 루프 주기 유지
            elapsed = time.monotonic() - loop_start
            sleep_time = max(0, dt - elapsed)
            time.sleep(sleep_time)
    
    except KeyboardInterrupt:
        print("\n[Main] Ctrl+C 종료")
    finally:
        print("[Main] 종료 처리...")
        stop_event.set()
        motor.emergency_stop()
        motor.shutdown()
        # 엔코더 정리
        if encoder_left is not None and encoder_left.is_available:
            encoder_left.shutdown()
        if encoder_right is not None and encoder_right.is_available:
            encoder_right.shutdown()
        camera.release()
        video_sender.close()
        cmd_sock.close()
        tele_sock.close()
        ultrasonic.shutdown()
        video_thread.join(timeout=2)
        telemetry_thread.join(timeout=2)
        print("[Main] 종료 완료")


if __name__ == "__main__":
    main()
