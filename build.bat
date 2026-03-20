@echo off
chcp 65001 > nul
echo ================================================
echo   리니지1 파티어시 매크로 - EXE 빌드 스크립트
echo ================================================
echo.

echo [1/3] 필요 패키지 설치 중...
pip install keyboard pyautogui pyinstaller --quiet
if %errorlevel% neq 0 (
    echo.
    echo [오류] pip 설치 실패. Python 3.8 이상이 설치되어 있는지 확인하세요.
    pause
    exit /b 1
)
echo 패키지 설치 완료.
echo.

echo [2/3] EXE 파일 빌드 중...
pyinstaller --onefile ^
            --noconsole ^
            --uac-admin ^
            --name "LineagePartyAssist" ^
            lineage_assist.py

echo.
if exist "dist\LineagePartyAssist.exe" (
    echo [3/3] 빌드 성공!
    echo.
    echo  -^> dist\LineagePartyAssist.exe 파일이 생성되었습니다.
    echo  -^> 반드시 관리자 권한으로 실행하세요.
    echo.
    echo 사용법:
    echo   F12  매크로 켜기 / 끄기
    echo   F6   파티어시 -^> F9클릭 -^> F10클릭 -^> F11클릭 자동 실행
) else (
    echo [오류] 빌드 실패. 위 오류 메시지를 확인하세요.
)

echo.
pause
