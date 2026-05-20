@echo off
REM ====================================================================
REM Disaster Robot - 원클릭 시연 시작 스크립트
REM
REM 작동:
REM   1. 라파에 SSH 접속해서 main.py 실행 (백그라운드 윈도우)
REM   2. 잠깐 기다리고 노트북에서 laptop/main.py 실행
REM
REM 사용 전 1회 셋업 필요:
REM   - 라파에 SSH 키 등록 (비밀번호 없이 접속)
REM     → 노트북 PowerShell:
REM        ssh-keygen -t ed25519     (있으면 스킵)
REM        ssh-copy-id pi@100.67.88.118
REM
REM 종료:
REM   Ctrl+C 또는 두 창 다 닫기. 라파 측 프로세스는 SSH 끊기면 함께 정지.
REM ====================================================================

setlocal

REM ───── 설정 (필요 시 수정) ─────
set RPI_USER=pi
set RPI_HOST=100.67.88.118
set RPI_PROJECT_DIR=~/disaster-robot
set RPI_VENV=~/dr-env/bin/activate
set CONFIG=config/sim.yaml

REM ───── 경로 (자동) ─────
set SCRIPT_DIR=%~dp0
cd /d %SCRIPT_DIR%

echo ====================================================================
echo  Disaster Robot 시작
echo  RPi: %RPI_USER%@%RPI_HOST%
echo  Config: %CONFIG%
echo ====================================================================
echo.

REM ───── 라파 main.py 실행 (별도 창) ─────
echo [1/2] 라파 main 실행 중...
start "RPi Main" cmd /k "ssh -t %RPI_USER%@%RPI_HOST% ""cd %RPI_PROJECT_DIR% && source %RPI_VENV% && python raspberry-pi/main.py --config %CONFIG%"""

REM ───── 라파가 준비될 시간 (3초) ─────
echo 라파 부팅 대기 (3초)...
timeout /t 3 /nobreak >nul

REM ───── 노트북 GUI 실행 ─────
echo [2/2] 노트북 GUI 실행 중...
echo.

REM 가상환경 활성화 시도 (conda 또는 venv)
if exist "%SCRIPT_DIR%venv\Scripts\activate.bat" (
    call "%SCRIPT_DIR%venv\Scripts\activate.bat"
) else if defined CONDA_DEFAULT_ENV (
    echo (conda 환경 %CONDA_DEFAULT_ENV% 활성화됨)
) else (
    echo (가상환경 자동 감지 실패 - 시스템 Python으로 진행)
)

python laptop/main.py --config %CONFIG%

REM ───── 종료 처리 ─────
echo.
echo ====================================================================
echo 노트북 GUI 종료됨. 라파 창은 수동으로 닫아주세요.
echo ====================================================================
pause
