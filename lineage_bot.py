#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
리니지1 자동 복귀 도우미 v3.0
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import time
import queue
import sys
import os
from datetime import datetime


def _ensure_packages():
    import importlib, subprocess
    needed = {
        'pyautogui': 'pyautogui',
        'keyboard':  'keyboard',
        'PIL':       'Pillow',
        'numpy':     'numpy',
        'cv2':       'opencv-python',
        'win32gui':  'pywin32',
    }
    for mod, pkg in needed.items():
        if importlib.util.find_spec(mod) is None:
            print(f"[설치] {pkg}...")
            subprocess.run([sys.executable, '-m', 'pip', 'install', pkg], check=True)

_ensure_packages()

import pyautogui
import keyboard
from PIL import ImageGrab
import numpy as np
import cv2
import win32gui
from updater import check_and_update, check_update_on_startup

APP_VERSION  = "3.0.0"
APP_EXE_NAME = "LineageBot"

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05

# ─── 색상 테마 ────────────────────────────────────────────────────────────
BG  = '#181824'
BG2 = '#22223a'
BG3 = '#2a2a44'
FG  = '#e0e0f0'
ACC = '#f0c830'
GRN = '#40e080'
RED = '#e06040'
BLU = '#6080e0'
YEL = '#e0d040'


# ─── 설정 클래스 ─────────────────────────────────────────────────────────
class Cfg:
    def __init__(self):
        self.home_x     = 0        # 홈 복귀 클릭 화면 좌표 X
        self.home_y     = 0        # 홈 복귀 클릭 화면 좌표 Y
        self.range_px   = 300      # 화면 특징점 모드 범위 (px)
        self.check_sec  = 5.0      # 확인 간격 (초)
        self.mode       = 'screen' # 'screen' | 'timer'
        self.home_frame = None     # 홈 화면 스냅샷 (screen 모드)
        self.hwnd       = None     # 게임 창 핸들


# ─── 워커 스레드 ──────────────────────────────────────────────────────────
class Worker(threading.Thread):
    def __init__(self, cfg, log_q):
        super().__init__(daemon=True)
        self.cfg    = cfg
        self.log_q  = log_q
        self.active = True

    def log(self, s):
        self.log_q.put(str(s))

    def focus_game(self):
        if self.cfg.hwnd:
            try:
                if win32gui.IsWindow(self.cfg.hwnd):
                    win32gui.SetForegroundWindow(self.cfg.hwnd)
                    time.sleep(0.15)
            except Exception:
                pass

    def grab_screen(self):
        try:
            if self.cfg.hwnd and win32gui.IsWindow(self.cfg.hwnd):
                r = win32gui.GetWindowRect(self.cfg.hwnd)
                return np.array(ImageGrab.grab(bbox=r))
            return np.array(ImageGrab.grab())
        except Exception:
            return None

    # ── 화면 특징점 이동량 ────────────────────────────────────────────────
    def screen_displacement(self):
        if self.cfg.home_frame is None:
            return 0.0
        cur = self.grab_screen()
        if cur is None:
            return 0.0
        try:
            rg = cv2.cvtColor(self.cfg.home_frame, cv2.COLOR_RGB2GRAY)
            cg = cv2.cvtColor(cur,                  cv2.COLOR_RGB2GRAY)
            orb = cv2.ORB_create(600)
            kp1, d1 = orb.detectAndCompute(rg, None)
            kp2, d2 = orb.detectAndCompute(cg, None)
            if d1 is None or d2 is None or len(d1) < 6 or len(d2) < 6:
                return 0.0
            bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
            matches = sorted(bf.match(d1, d2), key=lambda m: m.distance)
            good = [m for m in matches[:25] if m.distance < 60]
            if len(good) < 4:
                return 0.0
            p1 = np.float32([kp1[m.queryIdx].pt for m in good])
            p2 = np.float32([kp2[m.trainIdx].pt for m in good])
            return float(np.median(np.linalg.norm(p2 - p1, axis=1)))
        except Exception:
            return 0.0

    # ── 홈 복귀 클릭 ─────────────────────────────────────────────────────
    def return_home(self):
        self.log(f"▶ 홈 복귀 클릭 → ({self.cfg.home_x}, {self.cfg.home_y})")
        self.focus_game()
        pyautogui.click(self.cfg.home_x, self.cfg.home_y)
        time.sleep(0.6)

    # ── 메인 루프 ─────────────────────────────────────────────────────────
    def run(self):
        self.log(f"● 시작 | 모드:{self.cfg.mode} | 간격:{self.cfg.check_sec:.1f}s")
        t_check = 0.0

        while self.active:
            now = time.time()

            if now - t_check >= self.cfg.check_sec:
                t_check = now
                need_ret = False

                if self.cfg.mode == 'screen':
                    d  = self.screen_displacement()
                    th = self.cfg.range_px * 0.75
                    if d > 8:
                        self.log(f"화면 이동: {d:.1f}px  (임계: {th:.0f}px)")
                    need_ret = d > th
                else:
                    need_ret = True

                if need_ret:
                    self.log("⚠ 범위 이탈! 홈 복귀 중...")
                    self.return_home()
                    time.sleep(1.5)
                    if self.cfg.mode == 'screen':
                        new_f = self.grab_screen()
                        if new_f is not None:
                            self.cfg.home_frame = new_f
                            self.log("기준 화면 갱신")

            time.sleep(0.05)

        self.log("● 종료")


# ─── 메인 애플리케이션 ────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("리니지1 자동 복귀 도우미 v3.0")
        self.geometry("620x640")
        self.resizable(False, False)
        self.configure(bg=BG)
        self.cfg      = Cfg()
        self.log_q    = queue.Queue()
        self.worker   = None
        self.hwnd_map = {}
        self._build_ui()
        self._bind_hotkeys()
        self._refresh_wins()
        self._poll_log()
        self._poll_mouse()

    # ── 헬퍼 ─────────────────────────────────────────────────────────────
    def _lbl(self, p, t, **kw):
        return tk.Label(p, text=t,
                        bg=kw.pop('bg', BG), fg=kw.pop('fg', FG),
                        font=kw.pop('font', ('맑은 고딕', 9)), **kw)

    def _sec(self, p, t):
        tk.Frame(p, bg='#2c2c50', height=1).pack(fill=tk.X, pady=(10, 0))
        self._lbl(p, f"  {t}", fg='#7878a8',
                  font=('맑은 고딕', 8, 'bold')).pack(anchor='w', padx=2, pady=(0, 2))

    def _card(self, p):
        f = tk.Frame(p, bg=BG2)
        f.pack(fill=tk.X, padx=6, pady=2)
        return f

    # ── UI 구성 ───────────────────────────────────────────────────────────
    def _build_ui(self):
        wrap = tk.Frame(self, bg=BG, padx=14, pady=8)
        wrap.pack(fill=tk.BOTH, expand=True)

        self._lbl(wrap, "리니지1 자동 복귀 도우미",
                  fg=ACC, font=('맑은 고딕', 17, 'bold')).pack(pady=(0, 4))

        # ─ 게임 창 선택 ───────────────────────────────────────────────────
        self._sec(wrap, "게임 창 선택")
        wf = self._card(wrap)
        self.win_var = tk.StringVar()
        self.win_cb = ttk.Combobox(wf, textvariable=self.win_var,
                                   state='readonly', width=38,
                                   font=('맑은 고딕', 9))
        self.win_cb.pack(side=tk.LEFT, padx=8, pady=6)
        tk.Button(wf, text="새로고침", command=self._refresh_wins,
                  bg=BG3, fg=FG, relief='flat', font=('맑은 고딕', 9),
                  padx=8, activebackground='#3a3a5a').pack(side=tk.LEFT, padx=4)

        # ─ 홈 위치 ────────────────────────────────────────────────────────
        self._sec(wrap, "홈 위치 (복귀 목적지)")
        hf = self._card(wrap)
        self.home_lbl = self._lbl(hf, "미설정  —  아래 버튼으로 설정하세요",
                                  fg='#ff8060', bg=BG2, font=('Consolas', 10))
        self.home_lbl.pack(side=tk.LEFT, padx=10, pady=7)
        tk.Button(hf, text="테스트 클릭", command=self._test_click,
                  bg=BG3, fg=YEL, relief='flat',
                  font=('맑은 고딕', 8), padx=6,
                  activebackground='#3a3a5a').pack(side=tk.RIGHT, padx=6, pady=5)

        # 홈 위치 설정 버튼 행
        bf2 = self._card(wrap)
        tk.Button(bf2, text="  창 중심 자동 설정  ",
                  command=self._set_window_center,
                  bg='#1a4060', fg='white', relief='flat',
                  font=('맑은 고딕', 10, 'bold'), padx=12, pady=6,
                  activebackground='#256080').pack(side=tk.LEFT, padx=8, pady=6)
        self._lbl(bf2, "←  선택한 창 중앙 좌표를 홈으로 설정",
                  fg='#606080', bg=BG2, font=('맑은 고딕', 8)).pack(side=tk.LEFT)
        tk.Button(bf2, text="화면 클릭 설정 [F1]",
                  command=self._pick_home,
                  bg='#282890', fg='white', relief='flat',
                  font=('맑은 고딕', 9), padx=8, pady=6,
                  activebackground='#3838c0').pack(side=tk.RIGHT, padx=8, pady=6)

        # ─ 감지 모드 ─────────────────────────────────────────────────────
        self._sec(wrap, "감지 모드")
        df = self._card(wrap)
        self.mode_var = tk.StringVar(value='screen')
        modes = [
            ("화면 특징점 감지", 'screen', "화면 변화량이 범위 초과 시 복귀"),
            ("타이머 복귀",      'timer',  "설정 간격마다 무조건 복귀 클릭"),
        ]
        for txt, val, desc in modes:
            col = tk.Frame(df, bg=BG2)
            col.pack(side=tk.LEFT, padx=16, pady=6)
            ttk.Radiobutton(col, text=txt, variable=self.mode_var, value=val,
                            command=lambda: setattr(self.cfg, 'mode',
                                                    self.mode_var.get())).pack(anchor='w')
            self._lbl(col, desc, fg='#606078', bg=BG2,
                      font=('맑은 고딕', 7)).pack(anchor='w')

        # ─ 이동 감지 범위 ─────────────────────────────────────────────────
        self._sec(wrap, "이동 감지 범위  (화면 특징점 모드)")
        rf = self._card(wrap)
        self.range_var = tk.IntVar(value=300)
        self.range_lbl = self._lbl(rf, "300 px", fg=BLU, bg=BG2,
                                   font=('Consolas', 10, 'bold'), width=8)
        self.range_lbl.pack(side=tk.RIGHT, padx=10)
        ttk.Scale(rf, from_=50, to=1000, variable=self.range_var,
                  orient=tk.HORIZONTAL, length=390,
                  command=self._on_range).pack(side=tk.LEFT, padx=8, pady=8)

        # ─ 복귀 확인 간격 ─────────────────────────────────────────────────
        self._sec(wrap, "복귀 확인 간격")
        tf = self._card(wrap)
        self._lbl(tf, "확인 간격:", bg=BG2).grid(
            row=0, column=0, padx=8, pady=6, sticky='w')
        self.chk_var = tk.DoubleVar(value=5.0)
        self.chk_lbl = self._lbl(tf, "5.0 s", fg=BLU, bg=BG2,
                                  font=('Consolas', 10, 'bold'), width=6)
        self.chk_lbl.grid(row=0, column=2, padx=6)
        ttk.Scale(tf, from_=3.0, to=60.0, variable=self.chk_var,
                  orient=tk.HORIZONTAL, length=330,
                  command=lambda v: (
                      self.chk_lbl.config(text=f"{float(v):.1f} s"),
                      setattr(self.cfg, 'check_sec', float(v))
                  )).grid(row=0, column=1, padx=4)

        # ─ 시작 / 종료 버튼 ──────────────────────────────────────────────
        bf = tk.Frame(wrap, bg=BG)
        bf.pack(pady=10)
        self.btn = tk.Button(bf, text="  시작  [F5]  ",
                             command=self._toggle,
                             bg='#1a5c1a', fg='white',
                             font=('맑은 고딕', 14, 'bold'),
                             relief='flat', padx=22, pady=10,
                             activebackground='#258025')
        self.btn.pack(side=tk.LEFT, padx=12)
        tk.Button(bf, text="  종료  [F10]  ",
                  command=self._quit,
                  bg='#5c1a1a', fg='white',
                  font=('맑은 고딕', 14, 'bold'),
                  relief='flat', padx=22, pady=10,
                  activebackground='#802525').pack(side=tk.LEFT, padx=12)
        tk.Button(bf, text=" \u2191 업데이트 확인 ",
                  command=lambda: check_and_update(
                      APP_VERSION, APP_EXE_NAME, parent=self, silent=False
                  ),
                  bg='#1a3a5c', fg='white',
                  font=('맑은 고딕', 9),
                  relief='flat', padx=8, pady=4,
                  activebackground='#256080').pack(side=tk.LEFT, padx=4)

        # ─ 상태 & 마우스 ──────────────────────────────────────────────────
        self.st_lbl = self._lbl(wrap, "● 대기중",
                                fg='#606070', font=('맑은 고딕', 11, 'bold'))
        self.st_lbl.pack(pady=2)
        self.mouse_lbl = self._lbl(wrap, "마우스: (0, 0)",
                                   fg='#505060', font=('Consolas', 8))
        self.mouse_lbl.pack()

        # ─ 로그 ──────────────────────────────────────────────────────────
        self._sec(wrap, "로그")
        self.log_box = scrolledtext.ScrolledText(
            wrap, height=5, bg='#0a0a18', fg=GRN,
            font=('Consolas', 8), state=tk.DISABLED, relief='flat')
        self.log_box.pack(fill=tk.X, padx=6, pady=(2, 4))
        self._lbl(wrap,
                  "F1 = 화면 클릭 위치 설정   |   F5 = 시작 / 정지   |   F10 = 종료",
                  fg='#404050', font=('맑은 고딕', 8)).pack(pady=2)

    # ── 이벤트 핸들러 ─────────────────────────────────────────────────────
    def _on_range(self, v):
        val = int(float(v))
        self.range_lbl.config(text=f"{val} px")
        self.cfg.range_px = val

    def _poll_log(self):
        try:
            while True:
                msg = self.log_q.get_nowait()
                self.log_box.config(state=tk.NORMAL)
                ts = datetime.now().strftime('%H:%M:%S')
                self.log_box.insert(tk.END, f"[{ts}] {msg}\n")
                self.log_box.see(tk.END)
                self.log_box.config(state=tk.DISABLED)
        except queue.Empty:
            pass
        self.after(100, self._poll_log)

    def _poll_mouse(self):
        try:
            x, y = pyautogui.position()
            self.mouse_lbl.config(text=f"마우스 위치: ({x}, {y})")
        except Exception:
            pass
        self.after(200, self._poll_mouse)

    def _refresh_wins(self):
        wins = []
        def cb(hwnd, extra):
            if win32gui.IsWindowVisible(hwnd):
                t = win32gui.GetWindowText(hwnd)
                if t.strip():
                    wins.append((hwnd, t))
            return True
        win32gui.EnumWindows(cb, None)
        self.hwnd_map = {t: h for h, t in wins}
        self.win_cb['values'] = list(self.hwnd_map.keys())
        for h, t in wins:
            if any(k in t.lower() for k in ['lineage', '리니지', 'l1.exe']):
                self.win_var.set(t)
                break

    def _test_click(self):
        if self.cfg.home_x == 0 and self.cfg.home_y == 0:
            messagebox.showinfo("안내", "홈 위치를 먼저 설정하세요.")
            return
        self.log_q.put(f"테스트 클릭: ({self.cfg.home_x}, {self.cfg.home_y})")
        threading.Thread(
            target=lambda: (time.sleep(0.3),
                            pyautogui.click(self.cfg.home_x, self.cfg.home_y)),
            daemon=True).start()

    # ── 창 중심 자동 설정 ─────────────────────────────────────────────────
    def _set_window_center(self):
        hwnd = self.hwnd_map.get(self.win_var.get())
        if not hwnd or not win32gui.IsWindow(hwnd):
            messagebox.showwarning("경고",
                "게임 창을 먼저 선택하세요.\n(새로고침 후 목록에서 리니지 창 선택)")
            return
        try:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            cx = (left + right) // 2
            cy = (top + bottom) // 2
            self.cfg.home_x = cx
            self.cfg.home_y = cy
            w = right - left
            h = bottom - top
            self.home_lbl.config(
                text=f"창 중심  X={cx}   Y={cy}   (창 크기 {w}×{h})", fg=GRN)
            self.log_q.put(f"창 중심 홈 설정: ({cx}, {cy})  창: {w}×{h}px")
        except Exception as e:
            self.log_q.put(f"창 정보 읽기 실패: {e}")

    # ── 화면 클릭 홈 설정 오버레이 ───────────────────────────────────────
    def _pick_home(self):
        self.withdraw()
        self.after(300, self._show_home_overlay)

    def _show_home_overlay(self):
        ov = tk.Toplevel(self)
        ov.attributes('-alpha', 0.35)
        ov.attributes('-fullscreen', True)
        ov.attributes('-topmost', True)
        ov.configure(bg='navy', cursor='crosshair')
        tk.Label(ov,
                 text="클 릭  →  홈 위치 설정\n\n(ESC = 취소)",
                 font=('맑은 고딕', 26, 'bold'),
                 fg='yellow', bg='navy')\
            .place(relx=0.5, rely=0.5, anchor='center')

        def on_click(e):
            x, y = e.x_root, e.y_root
            ov.destroy()
            self.deiconify()
            self.cfg.home_x = x
            self.cfg.home_y = y
            self.home_lbl.config(text=f"X = {x}   Y = {y}", fg=GRN)
            self.log_q.put(f"홈 위치 설정: ({x}, {y})")

        ov.bind('<Button-1>', on_click)
        ov.bind('<Escape>', lambda e: (ov.destroy(), self.deiconify()))
        ov.focus_force()

    # ── 핫키 등록 ─────────────────────────────────────────────────────────
    def _bind_hotkeys(self):
        try:
            keyboard.add_hotkey('f1',  lambda: self.after(0, self._pick_home),
                                suppress=False)
            keyboard.add_hotkey('f5',  lambda: self.after(0, self._toggle),
                                suppress=False)
            keyboard.add_hotkey('f10', lambda: self.after(0, self._quit),
                                suppress=False)
        except Exception as e:
            self.log_q.put(f"핫키 등록 실패: {e}")

    # ── 시작 / 정지 ───────────────────────────────────────────────────────
    def _toggle(self):
        if self.worker and self.worker.active:
            self.worker.active = False
            self.worker = None
            self.btn.config(text="  시작  [F5]  ", bg='#1a5c1a')
            self.st_lbl.config(text="● 정지됨", fg=RED)
        else:
            if self.cfg.home_x == 0 and self.cfg.home_y == 0:
                messagebox.showwarning("경고",
                    "홈 위치를 먼저 설정하세요!\n"
                    "[창 중심 자동 설정] 버튼 또는 F1을 이용하세요.")
                return

            self.cfg.mode = self.mode_var.get()
            self.cfg.hwnd = self.hwnd_map.get(self.win_var.get())

            if self.cfg.mode == 'screen':
                try:
                    if self.cfg.hwnd and win32gui.IsWindow(self.cfg.hwnd):
                        r = win32gui.GetWindowRect(self.cfg.hwnd)
                        self.cfg.home_frame = np.array(ImageGrab.grab(bbox=r))
                    else:
                        self.cfg.home_frame = np.array(ImageGrab.grab())
                    self.log_q.put("홈 화면 스냅샷 저장 완료")
                except Exception as e:
                    self.log_q.put(f"스냅샷 오류: {e}")
                    self.cfg.home_frame = None

            self.worker = Worker(self.cfg, self.log_q)
            self.worker.start()
            self.btn.config(text="  정지  [F5]  ", bg='#5c1a1a')
            self.st_lbl.config(text="● 실행중", fg=GRN)

    # ── 종료 ──────────────────────────────────────────────────────────────
    def _quit(self):
        if self.worker:
            self.worker.active = False
        try:
            keyboard.unhook_all()
        except Exception:
            pass
        self.destroy()

    def run(self):
        self.protocol("WM_DELETE_WINDOW", self._quit)
        check_update_on_startup(self, APP_VERSION, APP_EXE_NAME)
        self.mainloop()


if __name__ == '__main__':
    App().run()
