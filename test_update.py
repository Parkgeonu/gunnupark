# -*- coding: utf-8 -*-
"""
업데이트 기능 테스트 스크립트
GitHub API 연결 여부 및 버전 비교 로직을 검증합니다.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from updater import (
    _parse_version,
    _is_newer,
    fetch_latest_release,
    find_asset,
)


def test_version_parse():
    assert _parse_version("1.0.0")  == [1, 0, 0]
    assert _parse_version("v2.3.1") == [2, 3, 1]
    assert _parse_version("10.0")   == [10, 0]
    print("[OK] _parse_version")


def test_version_compare():
    assert _is_newer("1.0.1", "1.0.0") is True
    assert _is_newer("2.0.0", "1.9.9") is True
    assert _is_newer("1.0.0", "1.0.0") is False
    assert _is_newer("0.9.9", "1.0.0") is False
    print("[OK] _is_newer")


def test_github_api():
    print("\n[GitHub API 연결 테스트]")
    try:
        release = fetch_latest_release()
        tag  = release.get("tag_name", "(없음)")
        name = release.get("name", "(없음)")
        assets = release.get("assets", [])
        print(f"  최신 태그 : {tag}")
        print(f"  릴리즈명  : {name}")
        print(f"  assets    : {[a['name'] for a in assets]}")
        print("[OK] GitHub API 연결 성공")
        return release
    except Exception as e:
        print(f"[WARN] GitHub API 연결 실패 (릴리즈 없음 또는 네트워크 오류): {e}")
        return None


def test_find_asset(release):
    if release is None:
        print("[SKIP] find_asset (릴리즈 없음)")
        return

    for exe in ["LineageHP", "LineageBot"]:
        asset = find_asset(release, exe)
        if asset:
            print(f"[OK] {exe}.exe 발견: {asset['browser_download_url']}")
        else:
            print(f"[INFO] {exe}.exe 없음 (아직 업로드 전)")


def test_update_check_ui():
    print("\n[UI 팝업 테스트] (tkinter 창이 열립니다)")
    import tkinter as tk
    from updater import check_and_update

    APP_VERSION  = "0.0.1"
    APP_EXE_NAME = "LineageHP"

    root = tk.Tk()
    root.withdraw()

    print(f"  현재 버전: {APP_VERSION}  →  GitHub 최신 버전 비교 중...")
    check_and_update(APP_VERSION, APP_EXE_NAME, parent=root, silent=False)

    root.mainloop()


if __name__ == "__main__":
    print("=" * 50)
    print(" updater.py 테스트")
    print("=" * 50)

    test_version_parse()
    test_version_compare()

    release = test_github_api()
    test_find_asset(release)

    print()
    ans = input("UI 팝업 테스트도 실행할까요? (y/N): ").strip().lower()
    if ans == "y":
        test_update_check_ui()

    print("\n모든 테스트 완료.")
