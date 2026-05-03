# 빌드 가이드 (개발자용)

이 문서는 너 (개발자) 가 .exe 만들 때 보는 거.

---

## 1. 사전 준비

### conda 환경 활성화
```powershell
conda activate <기존 환경 이름>
```

### PyInstaller 설치
```powershell
pip install pyinstaller
```

### YOLO 모델 미리 다운로드
.exe에 묶기 위해 프로젝트 루트에 yolov8n.pt가 있어야 함:

```powershell
# yolov8n.pt 가 없으면 한 번 실행해서 다운받기
python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"
```

다운로드 완료 후 yolov8n.pt 가 프로젝트 루트(또는 laptop/) 에 생김.
그걸 프로젝트 루트로 옮겨놔.

---

## 2. 빌드 실행

### 방법 1: 자동 (권장)
```powershell
.\build_scripts\build_all.bat
```

### 방법 2: 수동 (디버깅 시)
```powershell
# 노트북 측만
pyinstaller build_scripts\laptop.spec --clean --noconfirm

# 라파 측만
pyinstaller build_scripts\rpi.spec --clean --noconfirm
```

---

## 3. 결과 확인

```
dist/
├── DisasterRobot-Operator/
│   ├── DisasterRobot-Operator.exe        ← 더블클릭으로 실행
│   ├── _internal/                        ← 의존성 라이브러리들
│   ├── config/
│   └── yolov8n.pt
└── DisasterRobot-RobotSim/
    ├── DisasterRobot-RobotSim.exe
    ├── _internal/
    └── config/
```

각 폴더 통째로 이동해야 동작함 (.exe만 빼면 안 됨).

---

## 4. 동작 테스트 (USB 옮기기 전)

너 컴퓨터에서 먼저 테스트:

1. `dist/DisasterRobot-Operator/DisasterRobot-Operator.exe` 더블클릭
   - 콘솔 + GUI 뜸
   - "라즈베리파이 연결 대기" 메시지

2. `dist/DisasterRobot-RobotSim/DisasterRobot-RobotSim.exe` 더블클릭
   - 자동 연결
   - 영상/레이더 동작

잘 되면 USB로.

---

## 5. USB 옮기기

```
USB:/disaster-robot/
├── DisasterRobot-Operator/
│   └── (Operator 폴더 통째로)
├── DisasterRobot-RobotSim/
│   └── (RobotSim 폴더 통째로)
└── README.txt
```

또는 `dist/release/` 폴더 통째로.

---

## 6. 흔한 빌드 에러와 해결

### `ModuleNotFoundError: No module named 'XXX'`
spec 파일의 `hiddenimports` 에 'XXX' 추가:

```python
hiddenimports = [
    ...
    'XXX',
]
```

재빌드.

### `FileNotFoundError: yolov8n.pt`
프로젝트 루트에 yolov8n.pt 가 있어야 함. 위 1번 단계 다시.

### .exe 실행 시 즉시 닫힘 (콘솔 안 보임)
spec 파일에서 `console=True` 인지 확인. False면 에러 못 봄.
콘솔 창에 뜬 에러를 캡처해서 알려줘.

### `ImportError: DLL load failed`
보통 PySide6 또는 OpenCV 관련. 해결책:
1. spec의 binaries 섹션에 dll 직접 추가
2. 또는 `--collect-all PySide6` 옵션 추가

### 빌드 매우 느림 / 메모리 부족
PyTorch/Ultralytics가 워낙 무거워서 그래.
- 노트북이라 RAM 적으면 8GB 이상 권장
- 첫 빌드는 15분도 가능

### 결과 파일 너무 큼 (>2GB)
PyTorch CPU 버전만 쓰면 GPU 라이브러리 빠져서 작아짐:
```powershell
# CPU 전용 PyTorch로 재설치 (GPU 안 쓸 거면)
pip uninstall torch torchvision
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

다시 빌드.

### Windows Defender 차단
빌드 중 Defender가 .exe를 격리할 수 있어. 빌드 폴더를 Defender 예외에 추가하거나, 빌드 후 격리 해제.

---

## 7. 디버그 모드 빌드

문제 생겼을 때 더 자세한 로그 보려면 spec 파일에서:
```python
debug=True,           # 부트로더 디버그
console=True,         # 콘솔 강제
strip=False,          # 심볼 유지
upx=False,            # 압축 안 함 (디버깅 쉬움)
```
