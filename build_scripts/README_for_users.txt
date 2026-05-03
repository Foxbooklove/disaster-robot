===========================================
 Disaster Rescue Robot - Operator System
===========================================

[실행 방법]

1. 이 폴더 전체를 컴퓨터에 복사 (USB에서 직접 실행하면 매우 느립니다)

2. DisasterRobot-Operator 폴더 안의
   DisasterRobot-Operator.exe 를 더블클릭

   → 검은 콘솔 창과 함께 GUI 창이 뜹니다
   → 처음 실행 시 10~30초 정도 걸릴 수 있습니다
   → "라즈베리파이 연결 대기..." 메시지가 보일 때까지 기다리세요

3. DisasterRobot-RobotSim 폴더 안의
   DisasterRobot-RobotSim.exe 를 더블클릭

   → 또 다른 콘솔 창이 뜹니다
   → 자동으로 Operator에 연결됩니다

4. Operator 창의 영상 영역을 한 번 클릭하여 키보드 포커스를 줍니다

5. 키보드로 조종:
   W/S    : 전진/후진
   A/D    : 좌/우 조향
   Space  : 정지
   R/F    : 앞바퀴 사이즈 +/-
   T/G    : 뒷바퀴 사이즈 +/-
   M      : 조향 모드 전환 (Ackermann/SkidSteer/Crab/DoubleAckermann)
   H      : 도움말 토글
   Q      : 종료

[주의사항]

- 노트북에 웹캠이 연결되어 있으면 자동으로 인식됩니다
- 웹캠이 없으면 합성 영상으로 자동 전환됩니다
- 종료할 때는 Operator 창의 X 버튼 또는 Q 키
- RobotSim은 Operator 종료 후 자동으로 종료됩니다 (또는 콘솔 창 닫기)

[문제 해결]

Q. Windows Defender가 실행을 막아요
A. "추가 정보" → "실행" 클릭. PyInstaller로 만든 .exe는 일부 보안 프로그램이
   의심하는 경우가 있습니다. 안전한 파일입니다.

Q. "라즈베리파이 연결 시간 초과" 메시지
A. RobotSim이 먼저 종료되었거나 시작되지 않은 경우입니다.
   Operator를 종료하고, 1번부터 다시 실행하세요.

Q. 영상이 까맣게 나옵니다
A. 다른 프로그램(Zoom, Teams, OBS 등)이 웹캠을 사용 중일 수 있습니다.
   해당 프로그램을 종료하고 다시 실행하세요.

Q. 키보드가 안 먹어요
A. GUI의 영상 영역을 한 번 클릭하여 포커스를 잡아주세요.

[기술 스택]

- 영상 탐지: YOLOv8 (Ultralytics)
- GUI: PySide6
- 통신: TCP (제어/텔레메트리) + UDP (영상)
- 조향: Ackermann + Skid Steer + Crab + Double Ackermann
- 동역학: Pacejka Tire Model + Bicycle Model
- 제어: PID + Pure Pursuit + Stanley
- 추정: Differential Odometry + Extended Kalman Filter
