@echo off
REM ════════════════════════════════════════════════════════════════
REM  Build script for Disaster Robot executables
REM  
REM  사용법:
REM    1. conda 환경 활성화: conda activate <환경 이름>
REM    2. pip install pyinstaller
REM    3. 프로젝트 루트에서 실행: build_scripts\build_all.bat
REM  
REM  결과:
REM    dist\DisasterRobot-Operator\DisasterRobot-Operator.exe
REM    dist\DisasterRobot-RobotSim\DisasterRobot-RobotSim.exe
REM ════════════════════════════════════════════════════════════════

echo.
echo ============================================
echo  Disaster Robot - Build Script
echo ============================================
echo.

REM PyInstaller 설치 확인
where pyinstaller >nul 2>nul
if errorlevel 1 (
    echo [ERROR] pyinstaller가 설치되지 않았습니다.
    echo   pip install pyinstaller
    echo 를 실행한 후 다시 시도하세요.
    pause
    exit /b 1
)

REM 이전 빌드 결과 정리
echo [1/4] 이전 빌드 정리...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
echo.

REM 노트북 측 빌드
echo [2/4] Operator (laptop) 빌드 중... (수 분 소요)
pyinstaller build_scripts\laptop.spec --clean --noconfirm
if errorlevel 1 (
    echo [ERROR] Laptop 빌드 실패
    pause
    exit /b 1
)
echo.

REM 라파 측 빌드
echo [3/4] RobotSim (raspberry-pi) 빌드 중...
pyinstaller build_scripts\rpi.spec --clean --noconfirm
if errorlevel 1 (
    echo [ERROR] RobotSim 빌드 실패
    pause
    exit /b 1
)
echo.

REM 배포 폴더 정리
echo [4/4] 배포 폴더 구성...
if not exist dist\release mkdir dist\release

REM 두 폴더를 release로 복사
xcopy /E /I /Y dist\DisasterRobot-Operator dist\release\DisasterRobot-Operator >nul
xcopy /E /I /Y dist\DisasterRobot-RobotSim dist\release\DisasterRobot-RobotSim >nul

REM README 복사
copy build_scripts\README_for_users.txt dist\release\README.txt >nul 2>nul

echo.
echo ============================================
echo  빌드 완료!
echo ============================================
echo.
echo  배포 폴더: dist\release\
echo.
echo  USB로 옮길 것:
echo    1. dist\release\ 폴더 통째로
echo  
echo  학교 컴퓨터에서:
echo    1. USB에서 release 폴더 복사 (USB 직접 실행은 느림)
echo    2. DisasterRobot-Operator\DisasterRobot-Operator.exe 더블클릭
echo    3. 잠시 후 (10초~30초) GUI 뜸, 라파 연결 대기 메시지
echo    4. DisasterRobot-RobotSim\DisasterRobot-RobotSim.exe 더블클릭
echo    5. 자동 연결 후 시연 시작
echo.
pause
