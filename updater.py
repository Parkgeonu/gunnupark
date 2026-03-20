# -*- coding: utf-8 -*-
"""
GitHub Release API 자동 업데이트 모듈
GitHub: https://github.com/Parkgeonu/gunnupark

사용 예:
    from updater import check_update_on_startup
    check_update_on_startup(root, "1.0.0", "LineageHP")
"""

import os
import sys
import json
import threading
import tempfile
import subprocess
import urllib.request
import urllib.error
import tkinter as tk
from tkinter import ttk, messagebox

GITHUB_OWNER = "Parkgeonu"
GITHUB_REPO  = "gunnupark"
API_URL      = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"


# ── 버전 비교 ────────────────────────────────────────────────────────────────

def _parse_version(ver: str) -> list:
    ver = ver.lstrip("v").strip()
    result = []
    for part in ver.split("."):
        try:
            result.append(int(part))
        except ValueError:
            result.append(0)
    return result


def _is_newer(latest: str, current: str) -> bool:
    return _parse_version(latest) > _parse_version(current)


# ── GitHub API ───────────────────────────────────────────────────────────────

def fetch_latest_release() -> dict:
    """GitHub API에서 최신 릴리즈 정보를 가져옵니다."""
    req = urllib.request.Request(
        API_URL,
        headers={
            "User-Agent": "LineageAutoUpdater/1.0",
            "Accept":     "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def find_asset(release: dict, exe_name: str) -> dict | None:
    """릴리즈 assets에서 exe_name.exe 파일을 찾습니다."""
    target = f"{exe_name.lower()}.exe"
    for asset in release.get("assets", []):
        if asset["name"].lower() == target:
            return asset
    return None


# ── exe 교체 (배치 스크립트) ──────────────────────────────────────────────────

def _apply_update_bat(new_exe: str, current_exe: str) -> None:
    """현재 프로세스 종료 후 배치 스크립트로 exe를 교체하고 재시작합니다."""
    bat = (
        "@echo off\n"
        "ping -n 3 127.0.0.1 > nul\n"
        f'move /Y "{new_exe}" "{current_exe}"\n'
        f'if errorlevel 1 copy /Y "{new_exe}" "{current_exe}"\n'
        f'start "" "{current_exe}"\n'
        'del "%~f0"\n'
    )
    bat_path = os.path.join(tempfile.gettempdir(), "_lineage_updater.bat")
    with open(bat_path, "w", encoding="cp949") as f:
        f.write(bat)
    subprocess.Popen(
        ["cmd.exe", "/c", bat_path],
        creationflags=subprocess.CREATE_NO_WINDOW,
        close_fds=True,
    )


# ── 다운로드 진행 창 ──────────────────────────────────────────────────────────

class _ProgressWindow(tk.Toplevel):
    def __init__(self, parent: tk.Misc):
        super().__init__(parent)
        self.title("업데이트 다운로드")
        self.resizable(False, False)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", lambda: None)

        w, h = 380, 100
        try:
            px = parent.winfo_rootx() + (parent.winfo_width()  - w) // 2
            py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        except Exception:
            px, py = 400, 300
        self.geometry(f"{w}x{h}+{px}+{py}")

        self._lbl = tk.Label(self, text="서버 연결 중...", anchor="w")
        self._lbl.pack(fill="x", padx=14, pady=(14, 4))

        self._bar = ttk.Progressbar(self, length=352, mode="determinate")
        self._bar.pack(padx=14)

        self._pct = tk.Label(self, text="0 %", anchor="e")
        self._pct.pack(fill="x", padx=14, pady=(2, 8))

    def set_progress(self, downloaded: int, total: int) -> None:
        pct = downloaded / total * 100 if total else 0
        mb_d = downloaded / 1_048_576
        mb_t = total     / 1_048_576
        self._bar["value"] = pct
        self._lbl.config(text=f"다운로드 중... {mb_d:.1f} / {mb_t:.1f} MB")
        self._pct.config(text=f"{pct:.0f} %")
        self.update_idletasks()


# ── 메인 함수 ─────────────────────────────────────────────────────────────────

def check_and_update(
    current_version: str,
    exe_name: str,
    parent: tk.Misc = None,
    silent: bool = True,
) -> None:
    """
    업데이트를 확인하고, 새 버전이 있으면 사용자에게 알린 뒤 다운로드·교체합니다.

    Args:
        current_version: 현재 버전 문자열 (예: "1.0.0")
        exe_name:        릴리즈 asset에서 찾을 exe 이름, 확장자 제외 (예: "LineageHP")
        parent:          Tkinter 부모 위젯 (messagebox·진행 창 위치 기준)
        silent:          True 이면 최신 버전일 때 별도 알림 없음
    """
    # 1. 최신 릴리즈 조회
    try:
        release = fetch_latest_release()
    except Exception as e:
        if not silent:
            messagebox.showerror("업데이트 오류", f"업데이트 서버 연결 실패:\n{e}", parent=parent)
        return

    latest_tag = release.get("tag_name", "")

    # 2. 버전 비교
    if not _is_newer(latest_tag, current_version):
        if not silent:
            messagebox.showinfo(
                "업데이트",
                f"현재 최신 버전입니다.  (v{current_version})",
                parent=parent,
            )
        return

    # 3. asset 확인
    asset  = find_asset(release, exe_name)
    notes  = (release.get("body") or "").strip()
    note_s = f"\n\n변경사항:\n{notes[:400]}" if notes else ""

    if asset is None:
        messagebox.showwarning(
            "업데이트",
            f"새 버전 {latest_tag} 가 있지만\n릴리즈에서 {exe_name}.exe 를 찾을 수 없습니다.{note_s}",
            parent=parent,
        )
        return

    # 4. 사용자 확인
    if not messagebox.askyesno(
        "업데이트 가능",
        f"새 버전이 있습니다!\n\n현재: v{current_version}  →  최신: {latest_tag}{note_s}\n\n지금 업데이트하시겠습니까?",
        parent=parent,
    ):
        return

    # 5. 다운로드
    tmp_path = os.path.join(tempfile.gettempdir(), f"{exe_name}_update.exe")
    prog = _ProgressWindow(parent) if parent else None

    try:
        req = urllib.request.Request(
            asset["browser_download_url"],
            headers={"User-Agent": "LineageAutoUpdater/1.0"},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            total      = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            with open(tmp_path, "wb") as f:
                while True:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if prog and total:
                        prog.set_progress(downloaded, total)
    except Exception as e:
        if prog:
            prog.destroy()
        messagebox.showerror("다운로드 실패", f"파일 다운로드 중 오류:\n{e}", parent=parent)
        return

    if prog:
        prog.destroy()

    # 6. 교체 (개발 환경에서는 교체 생략)
    if not getattr(sys, "frozen", False):
        messagebox.showinfo(
            "업데이트 완료 (개발 모드)",
            f"다운로드 완료:\n{tmp_path}\n\n개발 환경에서는 자동 교체를 건너뜁니다.",
            parent=parent,
        )
        return

    messagebox.showinfo(
        "업데이트",
        "다운로드 완료! 프로그램이 재시작됩니다.",
        parent=parent,
    )
    _apply_update_bat(tmp_path, sys.executable)
    try:
        if parent:
            parent.winfo_toplevel().destroy()
    except Exception:
        pass
    sys.exit(0)


def check_update_on_startup(
    root: tk.Tk,
    current_version: str,
    exe_name: str,
) -> None:
    """
    앱 시작 시 백그라운드에서 업데이트를 조용히 확인합니다.
    새 버전이 있을 때만 사용자에게 알림 창을 표시합니다.

    Args:
        root:            Tkinter 루트 창
        current_version: 현재 버전 문자열 (예: "1.0.0")
        exe_name:        exe 파일명, 확장자 제외 (예: "LineageHP")
    """
    def _worker():
        import time
        time.sleep(2)
        root.after(0, lambda: check_and_update(
            current_version, exe_name, parent=root, silent=True
        ))

    threading.Thread(target=_worker, daemon=True).start()
