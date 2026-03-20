import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import json
import os

try:
    import win32api
    import win32gui
    import win32con
    import keyboard
except ImportError:
    import sys, subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pywin32", "keyboard"])
    import win32api, win32gui, win32con, keyboard

try:
    import pystray
    from PIL import Image, ImageDraw, ImageFont
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False

CONFIG_FILE = "lineage_helper_config.json"
VK_F7 = 0x76


def _make_tray_image():
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 63, 63], fill=(26, 35, 126))
    d.rectangle([8, 8, 55, 55], outline=(144, 202, 249), width=2)
    d.text((14, 18), "L1", fill=(255, 255, 255))
    return img


class LineageHelperGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("리니지 1 헬퍼")
        self.root.geometry("520x630")
        self.root.resizable(False, False)

        self.config = self._load_config()

        self.party_assist_active = False
        self.party_assist_stop  = threading.Event()
        self.f7_held  = False
        self.f7_stop  = threading.Event()

        self.mouse_lock_stop = threading.Event()
        self.mouse_lock_x = self.config.get("mouse_lock_x", 0)
        self.mouse_lock_y = self.config.get("mouse_lock_y", 0)
        self.in_capture_mode = False

        self.tray_icon   = None
        self.log_popup   = None
        self.popup_log_text = None

        self._build_ui()
        threading.Thread(target=self._register_hotkeys, daemon=True).start()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── 설정 ────────────────────────────────────────
    def _load_config(self):
        default = {
            "lineage_title": "TESTSERVER",
            "pa_key": "F1",
            "pa_interval": 0.5,
            "mouse_lock_enabled": False,
            "mouse_lock_x": 0,
            "mouse_lock_y": 0,
            "capture_key": "F8",
            "click_lock_enabled": False,
            "click_interval": 1.0,
        }
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    return {**default, **json.load(f)}
            except Exception:
                pass
        return default

    def _save_config_file(self):
        data = {
            "lineage_title": self.title_var.get(),
            "pa_key": self.pa_key_var.get(),
            "pa_interval": self.pa_interval_var.get(),
            "mouse_lock_enabled": bool(self.mouse_lock_var.get()),
            "mouse_lock_x": self.mouse_lock_x,
            "mouse_lock_y": self.mouse_lock_y,
            "capture_key": self.capture_key_var.get().strip() or "F8",
            "click_lock_enabled": bool(self.click_lock_var.get()),
            "click_interval": self.click_interval_var.get(),
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ── 창 목록 ─────────────────────────────────────
    def _get_window_titles(self):
        titles = []
        def cb(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                t = win32gui.GetWindowText(hwnd)
                if t.strip():
                    titles.append(t)
        win32gui.EnumWindows(cb, None)
        return sorted(set(titles))

    def _find_hwnd(self):
        hwnd = win32gui.FindWindow(None, self.title_var.get())
        return hwnd if hwnd else None

    # ── UI ──────────────────────────────────────────
    def _build_ui(self):
        hdr = tk.Frame(self.root, bg="#1a237e", pady=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text="리니지 1 헬퍼", font=("맑은 고딕", 15, "bold"),
                 bg="#1a237e", fg="white").pack()
        tk.Label(hdr, text="F6 누르는 동안: 파티어시 + F7  |  F6 떼면 중지  |  X → 트레이",
                 font=("맑은 고딕", 9), bg="#1a237e", fg="#90caf9").pack()

        body = tk.Frame(self.root, padx=14, pady=10)
        body.pack(fill="both", expand=True)

        # 창 제목
        tf = tk.LabelFrame(body, text="리니지 창 제목", padx=8, pady=6,
                           font=("맑은 고딕", 9, "bold"))
        tf.pack(fill="x", pady=(0, 6))
        tr = tk.Frame(tf); tr.pack(fill="x")
        self.title_var = tk.StringVar(value=self.config["lineage_title"])
        self.title_cb = ttk.Combobox(tr, textvariable=self.title_var,
                                     values=self._get_window_titles(), width=34)
        self.title_cb.pack(side="left")
        tk.Button(tr, text="↺", command=self._refresh_titles,
                  relief="groove", width=3).pack(side="left", padx=5)

        # 파티어시
        pf = tk.LabelFrame(body, text="파티어시 설정 (F6 연동)", padx=8, pady=6,
                           font=("맑은 고딕", 9, "bold"), fg="#1565c0")
        pf.pack(fill="x", pady=(0, 6))
        pr1 = tk.Frame(pf); pr1.pack(fill="x", pady=2)
        tk.Label(pr1, text="전송 키:", width=12, anchor="w").pack(side="left")
        self.pa_key_var = tk.StringVar(value=self.config["pa_key"])
        tk.Entry(pr1, textvariable=self.pa_key_var, width=10).pack(side="left", padx=4)
        tk.Label(pr1, text="예: F1, F2, space, enter", fg="gray",
                 font=("맑은 고딕", 8)).pack(side="left", padx=4)
        pr2 = tk.Frame(pf); pr2.pack(fill="x", pady=2)
        tk.Label(pr2, text="전송 간격(초):", width=12, anchor="w").pack(side="left")
        self.pa_interval_var = tk.DoubleVar(value=self.config["pa_interval"])
        tk.Spinbox(pr2, from_=0.1, to=10.0, increment=0.1,
                   textvariable=self.pa_interval_var, format="%.1f", width=8).pack(side="left", padx=4)

        # 마우스 위치 고정
        mf = tk.LabelFrame(body, text="타겟 마우스 위치 고정 (F6 실행시 적용)", padx=8, pady=6,
                           font=("맑은 고딕", 9, "bold"), fg="#6a1b9a")
        mf.pack(fill="x", pady=(0, 6))
        mr1 = tk.Frame(mf); mr1.pack(fill="x", pady=2)
        self.mouse_lock_var = tk.BooleanVar(value=self.config.get("mouse_lock_enabled", False))
        tk.Checkbutton(mr1, text="마우스 위치 고정 사용",
                       variable=self.mouse_lock_var, font=("맑은 고딕", 9)).pack(side="left")
        mr2 = tk.Frame(mf); mr2.pack(fill="x", pady=4)
        self.capture_btn = tk.Button(mr2, text="클릭으로 위치 지정",
                                     command=self._start_pos_capture,
                                     bg="#7b1fa2", fg="white", relief="groove",
                                     font=("맑은 고딕", 9, "bold"))
        self.capture_btn.pack(side="left")
        tk.Label(mr2, text="  단축키:", fg="gray",
                 font=("맑은 고딕", 8)).pack(side="left", padx=(10, 2))
        self.capture_key_var = tk.StringVar(value=self.config.get("capture_key", "F8"))
        self.capture_key_cb = ttk.Combobox(
            mr2, textvariable=self.capture_key_var, width=10,
            values=["마우스 좌클릭", "F8", "F9", "F10", "F11", "F12",
                    "F1", "F2", "F3", "F4", "F5"],
            state="normal", font=("맑은 고딕", 8))
        self.capture_key_cb.pack(side="left")
        mr3 = tk.Frame(mf); mr3.pack(fill="x", pady=2)
        tk.Label(mr3, text="저장 위치:", font=("맑은 고딕", 9)).pack(side="left")
        self.pos_lbl = tk.Label(mr3, text=f"X={self.mouse_lock_x},  Y={self.mouse_lock_y}",
                                fg="#6a1b9a", font=("맑은 고딕", 9, "bold"))
        self.pos_lbl.pack(side="left", padx=6)
        self.lock_status_lbl = tk.Label(mr3, text="● 대기", fg="#9e9e9e",
                                        font=("맑은 고딕", 9, "bold"))
        self.lock_status_lbl.pack(side="left", padx=10)
        mr4 = tk.Frame(mf); mr4.pack(fill="x", pady=2)
        self.click_lock_var = tk.BooleanVar(value=self.config.get("click_lock_enabled", False))
        tk.Checkbutton(mr4, text="저장 위치 좌클릭 반복 - 캐릭터 고정 (타겟 유지)",
                       variable=self.click_lock_var, font=("맑은 고딕", 9),
                       fg="#4a148c").pack(side="left")
        mr5 = tk.Frame(mf); mr5.pack(fill="x", pady=2)
        tk.Label(mr5, text="클릭 간격(초):", width=12, anchor="w").pack(side="left")
        self.click_interval_var = tk.DoubleVar(value=self.config.get("click_interval", 1.0))
        tk.Spinbox(mr5, from_=0.1, to=30.0, increment=0.5,
                   textvariable=self.click_interval_var, format="%.1f", width=8).pack(side="left", padx=4)
        tk.Label(mr5, text="(F6 누르는 동안 반복 클릭)", fg="gray",
                 font=("맑은 고딕", 8)).pack(side="left", padx=4)

        # F6 버튼
        self.f6_btn = tk.Button(body,
                                text="누르는 동안 실행 [F6]  →  파티어시 + F7 키 누르기",
                                bg="#1976D2", fg="white",
                                font=("맑은 고딕", 10, "bold"), relief="groove", height=2)
        self.f6_btn.pack(fill="x", pady=(4, 4))
        self.f6_btn.bind("<ButtonPress-1>",   lambda e: self._on_f6_press())
        self.f6_btn.bind("<ButtonRelease-1>", lambda e: self._on_f6_release())

        # 상태
        sf = tk.Frame(body); sf.pack(fill="x", pady=(0, 6))
        self.pa_lbl = tk.Label(sf, text="파티어시: ● 대기", fg="#9e9e9e",
                               font=("맑은 고딕", 9, "bold"), width=18, anchor="w")
        self.pa_lbl.pack(side="left")
        self.f7_lbl = tk.Label(sf, text="F7 누르기: ● 대기", fg="#9e9e9e",
                               font=("맑은 고딕", 9, "bold"), anchor="w")
        self.f7_lbl.pack(side="left")

        # 저장
        tk.Button(body, text="설정 저장", command=self._save_settings,
                  bg="#546E7A", fg="white", relief="groove",
                  font=("맑은 고딕", 9)).pack(fill="x", pady=4)

        # 로그
        lf = tk.LabelFrame(body, text="로그", padx=6, pady=4, font=("맑은 고딕", 9))
        lf.pack(fill="both", expand=True)
        self.log_text = tk.Text(lf, height=5, state="disabled",
                                font=("Consolas", 8), bg="#f5f5f5")
        sb = tk.Scrollbar(lf, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=sb.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    # ── 트레이 ──────────────────────────────────────
    def _on_close(self):
        if HAS_TRAY:
            self.root.withdraw()
            self._start_tray()
        else:
            self._quit_app()

    def _start_tray(self):
        if self.tray_icon:
            return
        menu = pystray.Menu(
            pystray.MenuItem("로그 보기", lambda: self.root.after(0, self._toggle_log_popup)),
            pystray.MenuItem("메인 창 열기", lambda: self.root.after(0, self._show_main_window)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("종료", lambda: self.root.after(0, self._quit_app)),
        )
        self.tray_icon = pystray.Icon(
            "lineage_helper", _make_tray_image(), "리니지 1 헬퍼", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _show_main_window(self):
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    # ── 로그 팝업 ────────────────────────────────────
    def _toggle_log_popup(self):
        if self.log_popup and self.log_popup.winfo_exists():
            self.log_popup.destroy()
            self.log_popup = None
            self.popup_log_text = None
        else:
            self._show_log_popup()

    def _show_log_popup(self):
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        pw, ph = 380, 220
        px = sw - pw - 10
        py = sh - ph - 50

        popup = tk.Toplevel()
        popup.title("리니지 헬퍼 - 로그")
        popup.geometry(f"{pw}x{ph}+{px}+{py}")
        popup.attributes("-topmost", True)
        popup.resizable(True, True)
        popup.configure(bg="#1a237e")

        hdr2 = tk.Frame(popup, bg="#1a237e", pady=4)
        hdr2.pack(fill="x")
        tk.Label(hdr2, text="리니지 헬퍼 로그", font=("맑은 고딕", 9, "bold"),
                 bg="#1a237e", fg="white").pack(side="left", padx=8)
        tk.Button(hdr2, text="메인창", command=self._show_main_window,
                  bg="#1565c0", fg="white", relief="flat",
                  font=("맑은 고딕", 8), padx=6).pack(side="right", padx=4)

        lf = tk.Frame(popup, padx=4, pady=4)
        lf.pack(fill="both", expand=True)
        log_widget = tk.Text(lf, state="disabled",
                             font=("Consolas", 8), bg="#f5f5f5")
        sb = tk.Scrollbar(lf, command=log_widget.yview)
        log_widget.configure(yscrollcommand=sb.set)
        log_widget.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # 기존 로그 복사
        existing = self.log_text.get("1.0", tk.END)
        log_widget.config(state="normal")
        log_widget.insert(tk.END, existing)
        log_widget.see(tk.END)
        log_widget.config(state="disabled")

        self.popup_log_text = log_widget
        self.log_popup = popup

        def on_close():
            self.log_popup = None
            self.popup_log_text = None
            popup.destroy()
        popup.protocol("WM_DELETE_WINDOW", on_close)

    # ── 로그 ────────────────────────────────────────
    def _log(self, msg):
        line = f"[{time.strftime('%H:%M:%S')}] {msg}\n"
        def _do():
            for w in [self.log_text, self.popup_log_text]:
                if w and w.winfo_exists():
                    w.config(state="normal")
                    w.insert(tk.END, line)
                    w.see(tk.END)
                    w.config(state="disabled")
        self.root.after(0, _do)

    def _refresh_titles(self):
        self.title_cb["values"] = self._get_window_titles()
        self._log("창 목록 새로고침")

    # ── 위치 캡처 ────────────────────────────────────
    def _start_pos_capture(self):
        if self.in_capture_mode:
            return
        self.in_capture_mode = True
        self.capture_btn.config(text="화면 클릭하세요...", bg="#e53935", state="disabled")
        self._log("위치 지정 모드: 타겟 캐릭터 위치를 클릭하세요")
        threading.Thread(target=self._capture_click, daemon=True).start()

    def _capture_click(self):
        while win32api.GetAsyncKeyState(win32con.VK_LBUTTON) & 0x8000:
            time.sleep(0.01)
        time.sleep(0.15)
        while True:
            if win32api.GetAsyncKeyState(win32con.VK_LBUTTON) & 0x8000:
                x, y = win32api.GetCursorPos()
                self.mouse_lock_x = x
                self.mouse_lock_y = y
                self.root.after(0, lambda: self._on_pos_captured(x, y))
                break
            time.sleep(0.01)

    def _on_pos_captured(self, x, y):
        self.in_capture_mode = False
        self.pos_lbl.config(text=f"X={x},  Y={y}")
        self.capture_btn.config(text="클릭으로 위치 지정", bg="#7b1fa2", state="normal")
        self._log(f"위치 저장 완료: X={x}, Y={y}")

    # ── 핫키 ────────────────────────────────────────
    def _register_hotkeys(self):
        try:
            keyboard.on_press_key("F6",
                lambda e: self.root.after(0, self._on_f6_press), suppress=False)
            keyboard.on_release_key("F6",
                lambda e: self.root.after(0, self._on_f6_release))
            cap_key = self.capture_key_var.get().strip() or "F8"
            if cap_key == "마우스 좌클릭":
                threading.Thread(target=self._mouse_capture_monitor, daemon=True).start()
            else:
                keyboard.on_press_key(cap_key,
                    lambda e: self.root.after(0, self._start_pos_capture), suppress=False)
            self._log(f"핫키 등록 완료 (F6, 캡처:{cap_key})")
        except Exception as e:
            self._log(f"핫키 등록 실패: {e}")

    def _mouse_capture_monitor(self):
        prev = False
        while True:
            cur = bool(win32api.GetAsyncKeyState(win32con.VK_LBUTTON) & 0x8000)
            if cur and not prev and not self.in_capture_mode:
                self.root.after(0, self._start_pos_capture)
            prev = cur
            time.sleep(0.01)

    # ── F6 ──────────────────────────────────────────
    def _on_f6_press(self):
        if not self.party_assist_active:
            hwnd = self._find_hwnd()
            if not hwnd:
                messagebox.showwarning("경고",
                    f"리니지 창을 찾을 수 없습니다.\n창 제목: {self.title_var.get()}")
                return
            try:
                interval = float(self.pa_interval_var.get())
            except Exception:
                interval = 0.5
            self.party_assist_active = True
            self.party_assist_stop.clear()
            self.f7_held = True
            self.f7_stop.clear()
            self.f6_btn.config(bg="#e53935", text="실행 중... [F6 떼면 중지]")
            self.pa_lbl.config(text="파티어시: ● 실행 중", fg="#2e7d32")
            self.f7_lbl.config(text="F7 누르기: ● 누르는 중", fg="#c62828")
            self._log(f"F6 시작 - 파티어시({self.pa_key_var.get()}/{interval}s) + F7")
            threading.Thread(target=self._pa_worker, args=(hwnd, interval), daemon=True).start()
            threading.Thread(target=self._f7_worker, args=(hwnd,), daemon=True).start()
            if self.mouse_lock_var.get() or self.click_lock_var.get():
                self.mouse_lock_stop.clear()
                self.lock_status_lbl.config(text="● 고정 중", fg="#6a1b9a")
                if self.mouse_lock_var.get():
                    threading.Thread(target=self._mouse_lock_worker, daemon=True).start()
                    self._log(f"마우스 고정: X={self.mouse_lock_x}, Y={self.mouse_lock_y}")
                if self.click_lock_var.get():
                    threading.Thread(target=self._click_lock_worker, daemon=True).start()
                    self._log(f"클릭 고정: X={self.mouse_lock_x}, Y={self.mouse_lock_y}, 간격={self.click_interval_var.get():.1f}s")

    def _on_f6_release(self):
        if self.party_assist_active:
            self.party_assist_stop.set()
            self.party_assist_active = False
        if self.f7_held:
            self.f7_held = False
            self.f7_stop.set()
        self.mouse_lock_stop.set()
        self.f6_btn.config(bg="#1976D2",
                           text="누르는 동안 실행 [F6]  →  파티어시 + F7 키 누르기")
        self.pa_lbl.config(text="파티어시: ● 대기", fg="#9e9e9e")
        self.f7_lbl.config(text="F7 누르기: ● 대기", fg="#9e9e9e")
        self.lock_status_lbl.config(text="● 대기", fg="#9e9e9e")
        self._log("F6 중지")

    # ── 워커 ────────────────────────────────────────
    def _pa_worker(self, hwnd, interval):
        while not self.party_assist_stop.is_set():
            try:
                if not win32gui.IsWindow(hwnd):
                    self._log("리니지 창이 닫혔습니다.")
                    break
                self._post_key(hwnd, self.pa_key_var.get().strip())
            except Exception as e:
                self._log(f"파티어시 오류: {e}")
                break
            self.party_assist_stop.wait(interval)

    def _f7_worker(self, hwnd):
        while not self.f7_stop.is_set():
            try:
                if not win32gui.IsWindow(hwnd):
                    break
                win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, VK_F7, 0x00410001)
                time.sleep(0.05)
                win32api.PostMessage(hwnd, win32con.WM_KEYUP,   VK_F7, 0xC0410001)
                time.sleep(0.05)
            except Exception as e:
                self._log(f"F7 오류: {e}")
                break

    def _mouse_lock_worker(self):
        x, y = self.mouse_lock_x, self.mouse_lock_y
        while not self.mouse_lock_stop.is_set():
            try:
                win32api.SetCursorPos((x, y))
                time.sleep(0.01)
            except Exception:
                break

    def _click_lock_worker(self):
        x, y = self.mouse_lock_x, self.mouse_lock_y
        while not self.mouse_lock_stop.is_set():
            try:
                interval = float(self.click_interval_var.get())
                win32api.SetCursorPos((x, y))
                time.sleep(0.05)
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                time.sleep(0.05)
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            except Exception as e:
                self._log(f"클릭 고정 오류: {e}")
                break
            self.mouse_lock_stop.wait(interval)

    def _post_key(self, hwnd, key_name):
        key_map = {
            "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73,
            "F5": 0x74, "F6": 0x75, "F7": 0x76, "F8": 0x77,
            "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B,
            "Enter": 0x0D, "enter": 0x0D,
            "Space": 0x20, "space": 0x20,
            "Esc": 0x1B, "esc": 0x1B,
            "Tab": 0x09, "tab": 0x09,
        }
        vk = key_map.get(key_name)
        if vk is None and len(key_name) == 1:
            vk = ord(key_name.upper())
        if vk:
            win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, vk, 0)
            time.sleep(0.03)
            win32api.PostMessage(hwnd, win32con.WM_KEYUP, vk, 0)

    def _save_settings(self):
        try:
            self._save_config_file()
            self._log("설정 저장 완료")
        except Exception as e:
            messagebox.showerror("오류", f"저장 실패: {e}")

    def _quit_app(self):
        self.party_assist_stop.set()
        self.f7_stop.set()
        self.mouse_lock_stop.set()
        if self.tray_icon:
            self.tray_icon.stop()
        if self.log_popup:
            try:
                self.log_popup.destroy()
            except Exception:
                pass
        try:
            keyboard.unhook_all()
        except Exception:
            pass
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = LineageHelperGUI(root)
    root.mainloop()
