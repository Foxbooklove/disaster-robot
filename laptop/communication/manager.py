"""
Laptop Communication Manager

노트북이 서버 역할:
- TCP 9998: 라파의 명령 수신 연결 받음 (실제론 노트북이 명령 송신)
- TCP 9997: 라파의 텔레메트리 수신 연결 받음
- UDP 9999: 라파의 영상 수신

[연결 흐름]
1. 노트북: 두 TCP 포트에서 listen()
2. 라파: 두 TCP 포트로 connect()
3. 노트북: accept() → 두 connection 확보
4. 이후 통신 시작

[스레드 구성]
- main: GUI/메인 로직
- video_thread: UDP 영상 수신 → 큐
- telemetry_thread: TCP 텔레메트리 수신 → 큐
- 명령 송신은 메인 스레드에서 직접 (요청 시점에)
"""

import socket
import threading
import queue
import time
from typing import Optional, Callable

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from shared.config import Config
from shared.tcp_framing import send_framed, recv_framed
from shared.udp_video import VideoReceiver
from shared.messages import (
    encode_message, parse_telemetry,
    DriveCommand, WheelSizeCommand, SteeringModeCommand, StopCommand,
    TelemetryMessage,
)


class CommunicationManager:
    """노트북 측 통신 총괄"""
    
    def __init__(self, config: Config):
        self.config = config
        self.network = config.network
        
        # 연결 상태
        self.cmd_conn: Optional[socket.socket] = None
        self.tele_conn: Optional[socket.socket] = None
        self.video_receiver: Optional[VideoReceiver] = None
        
        # 큐 (프로듀서: 수신 스레드, 컨슈머: GUI/메인)
        self.frame_queue: queue.Queue = queue.Queue(maxsize=2)  # 영상 큐 (작게 - 최신 우선)
        self.telemetry_queue: queue.Queue = queue.Queue(maxsize=20)  # 텔레메트리 큐
        
        # 스레드
        self._stop_event = threading.Event()
        self._video_thread: Optional[threading.Thread] = None
        self._telemetry_thread: Optional[threading.Thread] = None
        
        # 통계
        self.stats = {
            'frames_received': 0,
            'frames_dropped': 0,
            'telemetries_received': 0,
            'last_frame_time': 0.0,
            'last_telemetry_time': 0.0,
        }
    
    def start_servers(self) -> None:
        """TCP 서버 소켓 listen 시작 (라파 연결 대기 전)"""
        # 명령 채널
        self._cmd_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._cmd_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._cmd_server.bind(('0.0.0.0', self.network.command_port))
        self._cmd_server.listen(1)
        print(f"[Comm] 명령 채널 listen ({self.network.command_port})")
        
        # 텔레메트리 채널
        self._tele_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._tele_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._tele_server.bind(('0.0.0.0', self.network.telemetry_port))
        self._tele_server.listen(1)
        print(f"[Comm] 텔레메트리 채널 listen ({self.network.telemetry_port})")
        
        # UDP 영상 수신기
        self.video_receiver = VideoReceiver(
            host='0.0.0.0',
            port=self.network.video_port,
            frame_timeout=0.5,
            socket_timeout=1.0,
        )
        print(f"[Comm] 영상 채널 bind ({self.network.video_port})")
    
    def accept_robot(self, timeout: float = 30.0) -> bool:
        """라파의 연결 수락. timeout 안에 두 채널 모두 연결되면 True."""
        print(f"[Comm] 라즈베리파이 연결 대기 (timeout={timeout}s)...")
        self._cmd_server.settimeout(timeout)
        self._tele_server.settimeout(timeout)
        
        try:
            self.cmd_conn, addr1 = self._cmd_server.accept()
            print(f"[Comm] 명령 채널 연결됨: {addr1}")
            
            self.tele_conn, addr2 = self._tele_server.accept()
            print(f"[Comm] 텔레메트리 채널 연결됨: {addr2}")
            
            return True
        except socket.timeout:
            print("[Comm] 라파 연결 timeout")
            return False
    
    def start_receivers(self) -> None:
        """수신 스레드 시작"""
        self._video_thread = threading.Thread(
            target=self._video_loop, daemon=True
        )
        self._video_thread.start()
        
        self._telemetry_thread = threading.Thread(
            target=self._telemetry_loop, daemon=True
        )
        self._telemetry_thread.start()
        
        print("[Comm] 수신 스레드 시작")
    
    def _video_loop(self) -> None:
        """UDP 영상 수신 → frame_queue"""
        while not self._stop_event.is_set():
            try:
                jpeg_bytes = self.video_receiver.recv_frame()
                if jpeg_bytes is None:
                    continue
                
                # 큐가 꽉 차면 가장 오래된 것 버리고 새것 넣기 (최신 우선)
                if self.frame_queue.full():
                    try:
                        self.frame_queue.get_nowait()
                        self.stats['frames_dropped'] += 1
                    except queue.Empty:
                        pass
                
                self.frame_queue.put(jpeg_bytes)
                self.stats['frames_received'] += 1
                self.stats['last_frame_time'] = time.monotonic()
            except OSError:
                break
        print("[Comm] 영상 수신 스레드 종료")
    
    def _telemetry_loop(self) -> None:
        """TCP 텔레메트리 수신 → telemetry_queue"""
        while not self._stop_event.is_set():
            try:
                payload = recv_framed(self.tele_conn, timeout=2.0)
                if payload is None:
                    print("[Comm] 텔레메트리 채널 끊김")
                    break
                
                msg = parse_telemetry(payload)
                
                # 큐 꽉 차면 오래된 것 버림
                if self.telemetry_queue.full():
                    try:
                        self.telemetry_queue.get_nowait()
                    except queue.Empty:
                        pass
                self.telemetry_queue.put(msg)
                
                self.stats['telemetries_received'] += 1
                self.stats['last_telemetry_time'] = time.monotonic()
            except socket.timeout:
                continue
            except Exception as e:
                print(f"[Comm] 텔레메트리 에러: {e}")
                break
        print("[Comm] 텔레메트리 스레드 종료")
    
    # ─── 명령 송신 (메인 스레드에서 호출) ───
    
    def send_command(self, command) -> bool:
        """제어 명령 송신. 성공 시 True."""
        if self.cmd_conn is None:
            return False
        try:
            send_framed(self.cmd_conn, encode_message(command))
            return True
        except (OSError, BrokenPipeError) as e:
            print(f"[Comm] 명령 송신 실패: {e}")
            return False
    
    def send_drive(self, throttle: float, steer: float) -> bool:
        return self.send_command(DriveCommand(throttle=throttle, steer=steer))
    
    def send_wheel_size(self, front: float, rear: float, middle: float = None) -> bool:
        if middle is None:
            middle = (front + rear) / 2  # 기본: 앞/뒤 평균
        return self.send_command(WheelSizeCommand(front=front, rear=rear, middle=middle))
    
    def send_wheel_sizes(self, sizes: list) -> bool:
        """6개 바퀴 각각 독립 사이즈 명령. sizes = [FL, FR, ML, MR, RL, RR]"""
        if len(sizes) != 6:
            raise ValueError(f"sizes는 6개 필요, 받음: {len(sizes)}")
        # front/middle/rear 평균도 같이 채워서 호환성 유지
        front = (sizes[0] + sizes[1]) / 2
        middle = (sizes[2] + sizes[3]) / 2
        rear = (sizes[4] + sizes[5]) / 2
        return self.send_command(WheelSizeCommand(
            front=front, middle=middle, rear=rear, sizes=list(sizes)
        ))
    
    def send_steering_mode(self, mode: str) -> bool:
        return self.send_command(SteeringModeCommand(mode=mode))
    
    def send_stop(self) -> bool:
        return self.send_command(StopCommand())
    
    # ─── 데이터 받기 (논블로킹) ───
    
    def get_latest_frame(self) -> Optional[bytes]:
        """가장 최신 프레임. 없으면 None."""
        try:
            return self.frame_queue.get_nowait()
        except queue.Empty:
            return None
    
    def get_latest_telemetry(self) -> Optional[TelemetryMessage]:
        """가장 최신 텔레메트리. 없으면 None.
        큐에 여러 개 쌓여있으면 마지막 것만."""
        latest = None
        while True:
            try:
                latest = self.telemetry_queue.get_nowait()
            except queue.Empty:
                break
        return latest
    
    # ─── 종료 ───
    
    def shutdown(self) -> None:
        print("[Comm] 종료 중...")
        self._stop_event.set()
        
        if self.cmd_conn:
            try: self.cmd_conn.close()
            except: pass
        if self.tele_conn:
            try: self.tele_conn.close()
            except: pass
        if self.video_receiver:
            self.video_receiver.close()
        
        try: self._cmd_server.close()
        except: pass
        try: self._tele_server.close()
        except: pass
        
        if self._video_thread:
            self._video_thread.join(timeout=2)
        if self._telemetry_thread:
            self._telemetry_thread.join(timeout=2)
        print("[Comm] 종료 완료")
