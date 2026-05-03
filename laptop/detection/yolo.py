"""
YOLO Person Detector

YOLOv8 기반 사람 탐지. ultralytics 패키지 사용.

[프레임 스킵 최적화]
매 프레임 detect() 호출하면 비용 큼. 3프레임에 1번만 새로 detect.
중간 프레임은 직전 박스 그대로 표시 (정지 영상 효과).
나중에 트래커(KCF/CSRT)로 보간 가능.
"""

import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import cv2

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from shared.config import YoloConfig


@dataclass
class Detection:
    """단일 탐지 결과"""
    class_name: str
    confidence: float
    bbox: tuple  # (x1, y1, x2, y2) in pixels
    
    def width(self) -> int:
        return self.bbox[2] - self.bbox[0]
    
    def height(self) -> int:
        return self.bbox[3] - self.bbox[1]
    
    def center(self) -> tuple:
        return ((self.bbox[0] + self.bbox[2]) // 2,
                (self.bbox[1] + self.bbox[3]) // 2)


class PersonDetector:
    """
    YOLOv8 사람 탐지.
    
    detect_every_n_frames마다 새로 추론, 중간엔 이전 결과 재사용.
    """
    
    def __init__(self, config: YoloConfig):
        self.config = config
        self._frame_count = 0
        self._last_detections: List[Detection] = []
        
        # YOLO 모델 로드 (실제 사용 시점에 lazy)
        self._model = None
        self._model_path = config.model_path
    
    def _ensure_loaded(self) -> None:
        if self._model is None:
            from ultralytics import YOLO
            self._model = YOLO(self._model_path)
            print(f"[YOLO] 모델 로드: {self._model_path}")
    
    def detect(self, frame: np.ndarray) -> List[Detection]:
        """
        프레임 분석. 스킵 카운터에 따라 새로 추론하거나 이전 결과 반환.
        """
        self._frame_count += 1
        
        if self._frame_count % self.config.detect_every_n_frames != 0 \
                and self._last_detections is not None:
            return self._last_detections
        
        self._ensure_loaded()
        
        results = self._model(frame, verbose=False, conf=self.config.confidence_threshold)
        detections = []
        
        if len(results) > 0:
            r = results[0]
            for box in r.boxes:
                cls_id = int(box.cls)
                if cls_id not in self.config.target_classes:
                    continue
                
                xyxy = box.xyxy[0].tolist()
                detections.append(Detection(
                    class_name=r.names[cls_id],
                    confidence=float(box.conf),
                    bbox=tuple(int(v) for v in xyxy),
                ))
        
        self._last_detections = detections
        return detections
    
    @staticmethod
    def draw_detections(frame: np.ndarray, detections: List[Detection]) -> np.ndarray:
        """프레임 위에 박스 그려서 반환 (in-place 수정 후 반환)"""
        out = frame.copy()
        for det in detections:
            x1, y1, x2, y2 = det.bbox
            label = f"{det.class_name} {det.confidence:.2f}"
            
            # 박스 (재난 구조 색감 - 빨강/노랑)
            color = (0, 200, 255)  # BGR: 주황빛
            cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
            
            # 라벨 배경
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(out, (x1, y1 - th - 8), (x1 + tw + 4, y1), color, -1)
            cv2.putText(out, label, (x1 + 2, y1 - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        return out
