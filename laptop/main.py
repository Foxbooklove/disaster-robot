"""
Laptop Main (PySide6 GUI)

전체 흐름:
1. CommunicationManager 시작 → 라파 연결 대기
2. PySide6 GUI 초기화
3. QTimer 기반 메인 루프 (영상/텔레메트리/명령)
"""

import sys
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "laptop"))

from PySide6.QtWidgets import QApplication

from shared.config import load_config
from communication import CommunicationManager
from gui import MainWindow


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='config/sim.yaml')
    parser.add_argument('--no-yolo', action='store_true', help='YOLO 비활성화')
    parser.add_argument('--connect-timeout', type=float, default=60.0)
    args = parser.parse_args()
    
    config = load_config(ROOT / args.config)
    print(f"[Main] Config 로드 (mode={config.mode})")
    
    # ─── 통신 ───
    comm = CommunicationManager(config)
    comm.start_servers()
    
    print(f"[Main] 라즈베리파이 연결 대기 ({args.connect_timeout}s)...")
    if not comm.accept_robot(timeout=args.connect_timeout):
        print("[Main] 연결 실패")
        comm.shutdown()
        return 1
    comm.start_receivers()
    
    # ─── YOLO ───
    detector = None
    if not args.no_yolo:
        try:
            from detection import PersonDetector
            detector = PersonDetector(config.yolo)
            print("[Main] YOLO 준비 완료")
        except Exception as e:
            print(f"[Main] YOLO 로드 실패 (계속 진행): {e}")
    
    # ─── GUI ───
    app = QApplication(sys.argv)
    window = MainWindow(comm, detector, config)
    window.show()
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
