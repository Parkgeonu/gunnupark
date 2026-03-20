@echo off
chcp 65001 >nul
echo ===================================================
echo   리니지1 자동 사냥 도우미 ^- EXE 빌드 스크립트
echo ===================================================
echo.

echo [1/2] 필요 패키지 설치 중...
pip install pyinstaller pyautogui keyboard Pillow numpy opencv-python pywin32
if errorlevel 1 (
    echo [오류] 패키지 설치 실패. pip 및 Python 환경을 확인하세요.
    pause
    exit /b 1
)

echo.
echo [2/2] EXE 빌드 중... (시간이 걸릴 수 있습니다)
echo.

pyinstaller ^
  --onefile ^
  --windowed ^
  --name "LineageBot" ^
  --hidden-import=win32api ^
  --hidden-import=win32con ^
  --hidden-import=win32gui ^
  --hidden-import=win32process ^
  --hidden-import=pywintypes ^
  --hidden-import=cv2 ^
  --hidden-import=PIL ^
  --hidden-import=PIL.ImageGrab ^
  --hidden-import=numpy ^
  --hidden-import=pyautogui ^
  --hidden-import=keyboard ^
  --collect-all cv2 ^
  lineage_bot.py

echo.
if exist dist\LineageBot.exe (
    echo ===================================================
    echo   [완료] dist\LineageBot.exe 생성되었습니다!
    echo ===================================================
    explorer dist
) else (
    echo [오류] 빌드 실패. 위 오류 메시지를 확인하세요.
)
echo.
pause
