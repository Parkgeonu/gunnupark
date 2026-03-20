# -*- coding: utf-8 -*-
import threading
import time
import tkinter as tk
from tkinter import messagebox

import pyautogui
from pynput import keyboard as pynput_kb

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0


class MacroApp:
    def __init__(self, root):
        self.root = root
        self.root.title("좌표 클릭 매크로")
        self.root.geometry("430x318")
        self.root.resizable(False, False)
        self.root.configure(bg="#f4f4f4")

        self.running = False
        self.capturing = None  # None | 1 | 2

        self.x1 = tk.StringVar(value="0")
        self.y1 = tk.StringVar(value="0")
        self.x2 = tk.StringVar(value="0")
        self.y2 = tk.StringVar(value="0")
        self.delay_ms = tk.StringVar(value="500")
        self.status = tk.StringVar(value="준비")

        self._build_ui()
        self._start_listener()

    # ── Keyboard listener ───────────────────────────────────────────────
    def _start_listener(self):
        def _on_press(key):
            if key == pynput_kb.Key.insert:
                self.root.after(0, self._toggle)
            elif key == pynput_kb.Key.delete and self.capturing is not None:
                x, y = pyautogui.position()
                num, self.capturing = self.capturing, None
                self.root.after(0, lambda: self._apply_coords(num, x, y))

        self.kb_listener = pynput_kb.Listener(on_press=_on_press)
        self.kb_listener.start()

    # ── UI ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        hdr = tk.Frame(self.root, bg="#1f2d3d", pady=9)
        hdr.pack(fill="x")
        tk.Label(hdr, text="좌표 클릭 매크로",
                 font=("맑은 고딕", 13, "bold"),
                 bg="#1f2d3d", fg="white").pack()

        body = tk.Frame(self.root, bg="#f4f4f4", padx=14, pady=8)
        body.pack(fill="both", expand=True)

        self.btn_cap = {}
        for idx, vx, vy in [(1, self.x1, self.y1), (2, self.x2, self.y2)]:
            grp = tk.LabelFrame(body, text=f"  {idx}번 좌표  ",
                                font=("맑은 고딕", 9, "bold"),
                                bg="#f4f4f4", fg="#1f2d3d", padx=8, pady=5)
            grp.pack(fill="x", pady=(0, 6))

            tk.Label(grp, text="X :", bg="#f4f4f4").grid(row=0, column=0)
            tk.Entry(grp, textvariable=vx, width=7,
                     font=("Consolas", 10), justify="center").grid(
                row=0, column=1, padx=3)
            tk.Label(grp, text="Y :", bg="#f4f4f4").grid(row=0, column=2)
            tk.Entry(grp, textvariable=vy, width=7,
                     font=("Consolas", 10), justify="center").grid(
                row=0, column=3, padx=3)

            btn = tk.Button(grp, text="DEL 키로 설정",
                            font=("맑은 고딕", 8),
                            bg="#2980b9", fg="white", relief="flat",
                            padx=6, pady=2, cursor="hand2",
                            command=lambda n=idx: self._start_capture(n))
            btn.grid(row=0, column=4, padx=(10, 0))
            self.btn_cap[idx] = btn

        fd = tk.LabelFrame(body, text="  딜레이 (ms)  ",
                           font=("맑은 고딕", 9, "bold"),
                           bg="#f4f4f4", fg="#1f2d3d", padx=8, pady=5)
        fd.pack(fill="x", pady=(0, 8))
        tk.Label(fd, text="클릭 후 대기 :", bg="#f4f4f4",
                 font=("맑은 고딕", 9)).pack(side="left")
        tk.Entry(fd, textvariable=self.delay_ms, width=7,
                 font=("Consolas", 10), justify="center").pack(
            side="left", padx=8)
        tk.Label(fd, text="ms", bg="#f4f4f4", fg="#888",
                 font=("맑은 고딕", 9)).pack(side="left")

        self.btn_run = tk.Button(body, text="▶  매크로 시작",
                                  font=("맑은 고딕", 11, "bold"),
                                  bg="#27ae60", fg="white", relief="flat",
                                  pady=6, cursor="hand2",
                                  command=self._toggle)
        self.btn_run.pack(fill="x")

        hint = tk.Frame(body, bg="#f4f4f4")
        hint.pack(fill="x", pady=(4, 0))
        tk.Label(hint, text="INS : 시작 / 중지     DEL : 좌표 캡처",
                 bg="#f4f4f4", fg="#999",
                 font=("맑은 고딕", 8)).pack()

        sb = tk.Frame(self.root, bg="#dfe6e9", pady=3)
        sb.pack(fill="x", side="bottom")
        tk.Label(sb, textvariable=self.status,
                 bg="#dfe6e9", fg="#636e72",
                 font=("맑은 고딕", 8)).pack()

    # ── Coordinate capture ──────────────────────────────────────────────
    def _start_capture(self, num):
        self.capturing = num
        for i in (1, 2):
            self.btn_cap[i].config(bg="#2980b9", text="DEL 키로 설정")
        self.btn_cap[num].config(bg="#c0392b", text="대기 중...")
        self.status.set(
            f"{num}번 좌표 설정 대기 – 마우스를 원하는 위치로 이동 후 DEL 키를 누르세요")

    def _apply_coords(self, num, x, y):
        (self.x1 if num == 1 else self.x2).set(str(x))
        (self.y1 if num == 1 else self.y2).set(str(y))
        self.btn_cap[num].config(bg="#2980b9", text="DEL 키로 설정")
        self.status.set(f"{num}번 좌표 설정 완료 : ({x}, {y})")

    # ── Macro control ───────────────────────────────────────────────────
    def _toggle(self):
        if self.running:
            self.running = False
            self.btn_run.config(text="▶  매크로 시작", bg="#27ae60")
            self.status.set("매크로 중지됨")
            return

        try:
            int(self.x1.get()); int(self.y1.get())
            int(self.x2.get()); int(self.y2.get())
            if int(self.delay_ms.get()) < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("입력 오류",
                                 "좌표와 딜레이는 0 이상의 정수여야 합니다.")
            return

        self.running = True
        self.btn_run.config(text="■  매크로 중지", bg="#c0392b")
        self.status.set(
            "매크로 실행 중...  (좌상단 모서리로 마우스 이동 = 긴급 정지)")
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while self.running:
            try:
                x1, y1 = int(self.x1.get()), int(self.y1.get())
                x2, y2 = int(self.x2.get()), int(self.y2.get())
                wait = int(self.delay_ms.get()) / 1000.0

                pyautogui.moveTo(x1, y1, duration=0.15)
                pyautogui.click()
                time.sleep(wait)

                if not self.running:
                    break

                pyautogui.moveTo(x2, y2, duration=0.15)
                pyautogui.click()
                time.sleep(wait)

            except pyautogui.FailSafeException:
                self.root.after(0, self._failsafe)
                break
            except Exception as exc:
                self.root.after(0, lambda e=exc: self._error(e))
                break

    def _failsafe(self):
        self.running = False
        self.btn_run.config(text="▶  매크로 시작", bg="#27ae60")
        self.status.set("긴급 정지 (마우스 좌상단 이동)")

    def _error(self, exc):
        self.running = False
        self.btn_run.config(text="▶  매크로 시작", bg="#27ae60")
        self.status.set(f"오류: {exc}")

    def on_close(self):
        self.running = False
        self.kb_listener.stop()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = MacroApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
