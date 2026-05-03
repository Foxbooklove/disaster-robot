"""
UDP Video Chunking

JPEG 프레임이 UDP 패킷 한 개에 안 들어갈 때 (>1500바이트) 청크 분할.

[패킷 헤더 형식]
    [frame_id: 4B][total_chunks: 2B][chunk_index: 2B][payload]
    
    frame_id: 매 프레임마다 증가 (재조립 그룹 식별)
    total_chunks: 이 프레임의 총 청크 수
    chunk_index: 0부터 시작
    payload: 실제 JPEG 데이터 일부

[수신 측 재조립]
- frame_id별로 청크 모음
- 모든 chunk가 도착하면 합쳐서 반환
- 일부 손실되면 그 프레임 버림 (UDP는 어차피 손실 가능)
- 새 frame_id 도착 시 이전 미완성 프레임은 폐기

[중요한 제약]
UDP MTU 안전 크기: ~1400 bytes (이더넷 1500 - 헤더 여유)
이 파일에선 청크 헤더 8B + 페이로드 ≤ 1400.
"""

import socket
import struct
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional, Dict, Tuple


# 헤더 형식: frame_id(4B), total_chunks(2B), chunk_index(2B)
CHUNK_HEADER_FORMAT = '>IHH'
CHUNK_HEADER_SIZE = struct.calcsize(CHUNK_HEADER_FORMAT)  # 8 bytes


class VideoSender:
    """프레임을 청크로 나눠 UDP 전송"""
    
    def __init__(self, target_host: str, target_port: int, chunk_payload_size: int = 1400):
        """
        Args:
            chunk_payload_size: 헤더 제외 페이로드 크기. 기본 1400.
        """
        self.target = (target_host, target_port)
        self.chunk_size = chunk_payload_size
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._frame_id = 0
    
    def send(self, jpeg_bytes: bytes) -> None:
        """한 프레임을 청크로 분할 전송"""
        total = (len(jpeg_bytes) + self.chunk_size - 1) // self.chunk_size
        if total > 65535:
            raise ValueError(f"프레임이 너무 큼: {len(jpeg_bytes)} bytes")
        
        for i in range(total):
            start = i * self.chunk_size
            end = min(start + self.chunk_size, len(jpeg_bytes))
            payload = jpeg_bytes[start:end]
            
            header = struct.pack(CHUNK_HEADER_FORMAT, self._frame_id, total, i)
            self.sock.sendto(header + payload, self.target)
        
        # 다음 프레임 ID
        self._frame_id = (self._frame_id + 1) & 0xFFFFFFFF
    
    def close(self) -> None:
        self.sock.close()


@dataclass
class _PartialFrame:
    """재조립 중인 프레임"""
    total: int
    chunks: Dict[int, bytes]
    received_at: float           # 첫 청크 받은 시각 (timeout용)
    
    def is_complete(self) -> bool:
        return len(self.chunks) == self.total
    
    def assemble(self) -> bytes:
        return b''.join(self.chunks[i] for i in range(self.total))


class VideoReceiver:
    """UDP 청크 수신 + 재조립"""
    
    def __init__(self, host: str, port: int,
                 buffer_size: int = 65535,
                 frame_timeout: float = 0.5,
                 socket_timeout: float = 1.0):
        """
        Args:
            frame_timeout: 미완성 프레임을 폐기하는 시간 [s]
            socket_timeout: socket recv 타임아웃 [s]
        """
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((host, port))
        self.sock.settimeout(socket_timeout)
        self.buffer_size = buffer_size
        self.frame_timeout = frame_timeout
        
        self._partials: Dict[int, _PartialFrame] = {}
    
    def recv_frame(self) -> Optional[bytes]:
        """
        한 프레임 받기. 청크가 다 모일 때까지 반복 수신.
        
        Returns:
            완성된 프레임 bytes, 또는 socket timeout 시 None
        """
        try:
            while True:
                data, _ = self.sock.recvfrom(self.buffer_size)
                if len(data) < CHUNK_HEADER_SIZE:
                    continue
                
                # 헤더 파싱
                frame_id, total, chunk_idx = struct.unpack(
                    CHUNK_HEADER_FORMAT, data[:CHUNK_HEADER_SIZE]
                )
                payload = data[CHUNK_HEADER_SIZE:]
                
                # 부분 프레임에 저장
                if frame_id not in self._partials:
                    self._partials[frame_id] = _PartialFrame(
                        total=total, chunks={}, received_at=time.monotonic()
                    )
                self._partials[frame_id].chunks[chunk_idx] = payload
                
                # 완성됐으면 반환
                if self._partials[frame_id].is_complete():
                    frame_bytes = self._partials[frame_id].assemble()
                    
                    # 이 frame 이전의 모든 미완성 프레임 폐기 (오래된 것)
                    self._cleanup_older_than(frame_id)
                    del self._partials[frame_id]
                    
                    return frame_bytes
                
                # 너무 오래된 부분 프레임 정리
                self._cleanup_stale()
        except socket.timeout:
            return None
    
    def _cleanup_older_than(self, current_frame_id: int) -> None:
        """현재 frame_id보다 오래된 미완성 프레임 폐기.
        Wraparound 고려해 단순히 받은 시간으로 판단."""
        now = time.monotonic()
        to_delete = [
            fid for fid, p in self._partials.items()
            if now - p.received_at > self.frame_timeout
        ]
        for fid in to_delete:
            del self._partials[fid]
    
    def _cleanup_stale(self) -> None:
        """frame_timeout 지난 부분 프레임 폐기"""
        now = time.monotonic()
        to_delete = [
            fid for fid, p in self._partials.items()
            if now - p.received_at > self.frame_timeout
        ]
        for fid in to_delete:
            del self._partials[fid]
    
    def close(self) -> None:
        self.sock.close()
