"""
TCP Framed Messaging

TCP는 스트림이라 메시지 경계가 없음 → 직접 framing 해야 함.
방식: 4바이트 big-endian 길이 prefix + 페이로드.

예: "Hello" (5바이트) → b'\\x00\\x00\\x00\\x05Hello'

[왜 필요한가]
원본 코드의 cmd_socket.recv(16) 같은 방식은 위험:
- 명령이 16바이트보다 짧으면 다음 메시지와 합쳐짐
- 명령이 길면 잘림
→ 메시지 경계를 명시적으로 표시해야 안정적

[양방향]
보내기: send_framed
받기:   recv_framed
같은 socket으로 양쪽 다 가능 (TCP는 양방향).
"""

import socket
import struct
from typing import Optional


# 길이 prefix: 4바이트 unsigned int, big-endian
LENGTH_PREFIX_FORMAT = '>I'
LENGTH_PREFIX_SIZE = 4


def send_framed(sock: socket.socket, payload: bytes) -> None:
    """
    길이 prefix를 붙여서 전송.
    
    Raises:
        OSError: 소켓 에러
    """
    if len(payload) > 2**32 - 1:
        raise ValueError(f"페이로드가 너무 큼: {len(payload)} bytes")
    
    header = struct.pack(LENGTH_PREFIX_FORMAT, len(payload))
    # sendall: 부분 전송 자동 재시도
    sock.sendall(header + payload)


def recv_framed(sock: socket.socket, timeout: Optional[float] = None) -> Optional[bytes]:
    """
    한 메시지 전체를 받아서 반환.
    
    Args:
        sock: TCP 소켓
        timeout: None이면 소켓 기본값 사용
    
    Returns:
        페이로드 bytes, 또는 연결 끊김 시 None
    
    Raises:
        socket.timeout: timeout 만료
    """
    if timeout is not None:
        sock.settimeout(timeout)
    
    # 1. 길이 prefix 읽기
    header = _recv_exact(sock, LENGTH_PREFIX_SIZE)
    if header is None:
        return None
    length, = struct.unpack(LENGTH_PREFIX_FORMAT, header)
    
    # 2. 페이로드 읽기
    return _recv_exact(sock, length)


def _recv_exact(sock: socket.socket, n: int) -> Optional[bytes]:
    """
    정확히 n 바이트 받을 때까지 반복 호출.
    
    Returns:
        n 바이트, 또는 연결 끊김 시 None
    """
    data = bytearray()
    while len(data) < n:
        try:
            chunk = sock.recv(n - len(data))
        except BlockingIOError:
            # non-blocking 모드인데 아직 데이터 없음
            # 호출자가 처리해야 함
            raise
        if not chunk:
            # 연결 끊김
            return None
        data.extend(chunk)
    return bytes(data)
