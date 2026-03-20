import sys
import time
import threading
import tkinter as tk
from tkinter import ttk
import keyboard
import pyautogui

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0


class LineageMacro:
    def __init__(self):
        self.enabled = False
        self.executing = False
        self.target_x = 0
        self.target_y = 0

        self.f6_wait    = 0.10
        self.skill_wait = 0.25
        self.click_wait = 0.15

        self._build_ui()
        self._setup_hooks()

    def _build_ui(self):
        root = tk.Tk()
        self.root = root
        root.title("리니지1 파티어시 매크로")
        root.geometry("370x310")
        root.resizable(False, False)
        root.attributes('-topmost', True)

        BG = "#1e1e2e"
        FG = "#cdd6f4"
        self._BTN_ON  = "#a6e3a1"
        self._BTN_OFF = "#f38ba8"

        root.configure(bg=BG)

        tk.Label(root, text="리니지1  파티어시 스킬 매크로",
                 font=("맑은 고딕", 12, "bold"),
                 bg=BG, fg=FG).pack(pady=(12, 6))

        sf = tk.Frame(root, bg=BG)
        sf.pack()
        tk.Label(sf, text="상태:", font=("맑은 고딕", 10), bg=BG, fg=FG).pack(side=tk.LEFT)
        self.status_var = tk.StringVar(value="비활성화")
        self.status_lbl = tk.Label(sf, textvariable=self.status_var,
                                   font=("맑은 고딕", 10, "bold"),
                                   bg=BG, fg=self._BTN_OFF, width=24, anchor=tk.W)
        self.status_lbl.pack(side=tk.LEFT, padx=4)

        self.btn = tk.Button(root, text="▶  시작   ( Insert )",
                             command=self.toggle,
                             bg=self._BTN_ON, fg="#1e1e2e",
                             font=("맑은 고딕", 11, "bold"),
                             relief=tk.FLAT, bd=0,
                             padx=20, pady=8,
                             cursor="hand2")
        self.btn.pack(pady=8)

        df = tk.LabelFrame(root, text="딜레이 설정 (초)",
                           font=("맑은 고딕", 9),
                           bg=BG, fg=FG, padx=10, pady=6)
        df.pack(fill=tk.X, padx=14, pady=2)

        self._slider(df, "F6 후 대기  :", 0.05, 0.5,  self.f6_wait,
                     lambda v: self._set('f6_wait', v),    0, BG, FG)
        self._slider(df, "스킬키 후 대기:", 0.10, 1.0, self.skill_wait,
                     lambda v: self._set('skill_wait', v), 1, BG, FG)
        self._slider(df, "클릭 후 대기  :", 0.05, 0.5, self.click_wait,
                     lambda v: self._set('click_wait', v), 2, BG, FG)

        hf = tk.LabelFrame(root, text="단축키",
                           font=("맑은 고딕", 9),
                           bg=BG, fg=FG, padx=10, pady=5)
        hf.pack(fill=tk.X, padx=14, pady=8)
        tk.Label(hf, text=(
            "Insert  매크로 켜기 / 끄기\n"
            "F6      파티어시  →  F9 클릭 → F10 클릭 → F11 클릭\n"
            "(F6 누를 때 마우스가 가리키는 위치가 스킬 타겟)"
        ), font=("맑은 고딕", 9), bg=BG, fg=FG, justify=tk.LEFT).pack(anchor=tk.W)

    def _slider(self, parent, label, mn, mx, init, cmd, row, bg, fg):
        tk.Label(parent, text=label, font=("맑은 고딕", 9),
                 width=13, anchor=tk.W, bg=bg, fg=fg).grid(row=row, column=0, sticky=tk.W)
        var = tk.DoubleVar(value=init)
        val_lbl = tk.Label(parent, text=f"{init:.2f}", font=("맑은 고딕", 9),
                           width=4, bg=bg, fg=fg)
        val_lbl.grid(row=row, column=2, padx=(4, 0))

        def on_move(v):
            fv = round(float(v), 2)
            cmd(fv)
            val_lbl.config(text=f"{fv:.2f}")

        ttk.Scale(parent, from_=mn, to=mx, variable=var,
                  orient=tk.HORIZONTAL, length=145,
                  command=on_move).grid(row=row, column=1, padx=4)

    def _set(self, attr, val):
        setattr(self, attr, val)

    def _setup_hooks(self):
        keyboard.add_hotkey('insert', self.toggle, suppress=False)
        keyboard.add_hotkey('f6',  self.on_f6,  suppress=False)

    def toggle(self):
        self.enabled = not self.enabled
        if self.enabled:
            self.status_var.set("활성화  -  F6 대기 중")
            self.status_lbl.config(fg=self._BTN_ON)
            self.btn.config(text="■  중지   ( Insert )", bg=self._BTN_OFF)
        else:
            self.status_var.set("비활성화")
            self.status_lbl.config(fg=self._BTN_OFF)
            self.btn.config(text="▶  시작   ( Insert )", bg=self._BTN_ON)

    def on_f6(self):
        if not self.enabled or self.executing:
            return
        self.target_x, self.target_y = pyautogui.position()
        threading.Thread(target=self._skill_sequence, daemon=True).start()

    def _skill_sequence(self):
        self.executing = True
        x, y = self.target_x, self.target_y
        try:
            self.root.after(0, lambda: self.status_var.set(f"스킬 사용 중... ({x}, {y})"))
            time.sleep(self.f6_wait)

            for key in ('f9', 'f10', 'f11'):
                keyboard.send(key)
                time.sleep(self.skill_wait)
                pyautogui.click(x, y)
                time.sleep(self.click_wait)

            self.root.after(0, lambda: self.status_var.set("완료  -  F6 대기 중"))
        except Exception as e:
            self.root.after(0, lambda err=e: self.status_var.set(f"오류: {err}"))
        finally:
            self.executing = False

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self.root.mainloop()

    def _close(self):
        keyboard.unhook_all()
        self.root.destroy()


if __name__ == "__main__":
    app = LineageMacro()
    app.run()
