import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import psutil
import subprocess
import threading
import time
import json
import os
import sys


def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


CONFIG_FILE = os.path.join(get_base_dir(), "monitor_config.json")

DEFAULT_CONFIG = {
    "game_process": "Halpas.bin",
    "game_exe_path": "",
    "pss_exe_path": "",
    "check_interval": 5,
    "auto_restart_game": False,
    "auto_restart_pss": True,
    "kill_pss_before_restart": True,
}


class LineageMonitor:
    def __init__(self, root):
        self.root = root
        self.root.title("리니지 클라이언트 감시 프로그램")
        self.root.geometry("540x540")
        self.root.resizable(False, False)
        self.config = self.load_config()
        self.monitoring = False
        self.monitor_thread = None
        self.setup_ui()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                for k, v in DEFAULT_CONFIG.items():
                    if k not in cfg:
                        cfg[k] = v
                return cfg
            except Exception:
                pass
        return DEFAULT_CONFIG.copy()

    def save_config_to_file(self):
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("오류", f"설정 저장 실패: {e}")

    def setup_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TLabelframe.Label', font=('맑은 고딕', 9, 'bold'))
        style.configure('Start.TButton', font=('맑은 고딕', 10, 'bold'))

        main_frame = ttk.Frame(self.root, padding="12")
        main_frame.grid(row=0, column=0, sticky='nsew')

        tk.Label(
            main_frame,
            text="리니지 클라이언트 감시 프로그램",
            font=("맑은 고딕", 14, "bold"),
            fg="#1a237e"
        ).grid(row=0, column=0, columnspan=3, pady=(0, 12))

        ttk.Separator(main_frame, orient='horizontal').grid(
            row=1, column=0, columnspan=3, sticky='ew', pady=(0, 10))

        settings = ttk.LabelFrame(main_frame, text=" 경로 설정 ", padding="10")
        settings.grid(row=2, column=0, columnspan=3, sticky='ew', pady=(0, 8))

        ttk.Label(settings, text="게임 프로세스 이름:").grid(
            row=0, column=0, sticky='w', pady=4)
        self.game_process_var = tk.StringVar(value=self.config["game_process"])
        ttk.Entry(settings, textvariable=self.game_process_var,
                  width=34).grid(row=0, column=1, columnspan=2, sticky='w', padx=(6, 0))

        ttk.Label(settings, text="게임 실행 경로:").grid(
            row=1, column=0, sticky='w', pady=4)
        self.game_path_var = tk.StringVar(value=self.config["game_exe_path"])
        ttk.Entry(settings, textvariable=self.game_path_var,
                  width=27).grid(row=1, column=1, sticky='w', padx=(6, 0))
        ttk.Button(settings, text="찾기", width=6,
                   command=self.browse_game).grid(row=1, column=2, padx=(4, 0))

        ttk.Label(settings, text="PSS 프로그램 경로:").grid(
            row=2, column=0, sticky='w', pady=4)
        self.pss_path_var = tk.StringVar(value=self.config["pss_exe_path"])
        ttk.Entry(settings, textvariable=self.pss_path_var,
                  width=27).grid(row=2, column=1, sticky='w', padx=(6, 0))
        ttk.Button(settings, text="찾기", width=6,
                   command=self.browse_pss).grid(row=2, column=2, padx=(4, 0))

        ttk.Label(settings, text="감시 간격 (초):").grid(
            row=3, column=0, sticky='w', pady=4)
        self.interval_var = tk.IntVar(value=self.config["check_interval"])
        ttk.Spinbox(settings, from_=1, to=60,
                    textvariable=self.interval_var, width=8).grid(
            row=3, column=1, sticky='w', padx=(6, 0))

        opts = ttk.LabelFrame(main_frame, text=" 옵션 ", padding="10")
        opts.grid(row=3, column=0, columnspan=3, sticky='ew', pady=(0, 8))

        self.restart_game_var = tk.BooleanVar(
            value=self.config["auto_restart_game"])
        ttk.Checkbutton(
            opts,
            text="게임 클라이언트 자동 재시작 (게임 종료 시)",
            variable=self.restart_game_var
        ).grid(row=0, column=0, sticky='w')

        self.restart_pss_var = tk.BooleanVar(
            value=self.config["auto_restart_pss"])
        ttk.Checkbutton(
            opts,
            text="PSS 자동 재시작 (게임 종료 시)",
            variable=self.restart_pss_var
        ).grid(row=1, column=0, sticky='w')

        self.kill_pss_var = tk.BooleanVar(
            value=self.config["kill_pss_before_restart"])
        ttk.Checkbutton(
            opts,
            text="PSS 재시작 전 기존 PSS 프로세스 종료",
            variable=self.kill_pss_var
        ).grid(row=2, column=0, sticky='w')

        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=4, column=0, columnspan=3, pady=(0, 8))

        self.start_btn = ttk.Button(
            btn_frame, text="  감시 시작  ",
            command=self.start_monitoring, style='Start.TButton')
        self.start_btn.pack(side='left', padx=5)

        self.stop_btn = ttk.Button(
            btn_frame, text="  감시 중지  ",
            command=self.stop_monitoring, state='disabled')
        self.stop_btn.pack(side='left', padx=5)

        ttk.Button(
            btn_frame, text="  설정 저장  ",
            command=self.save_settings
        ).pack(side='left', padx=5)

        sf = ttk.Frame(main_frame)
        sf.grid(row=5, column=0, columnspan=3, sticky='ew', pady=(0, 4))
        ttk.Label(sf, text="상태:").pack(side='left')
        self.status_var = tk.StringVar(value="대기 중")
        self.status_label = ttk.Label(sf, textvariable=self.status_var,
                                      foreground="#888888")
        self.status_label.pack(side='left', padx=(5, 0))

        log_frame = ttk.LabelFrame(main_frame, text=" 로그 ", padding="5")
        log_frame.grid(row=6, column=0, columnspan=3, sticky='nsew')

        self.log_text = tk.Text(
            log_frame, height=9, width=60, state='disabled',
            font=("Consolas", 9), bg="#1e1e1e", fg="#d4d4d4",
            insertbackground="white", relief='flat')
        self.log_text.pack(side='left', fill='both', expand=True)

        sb = ttk.Scrollbar(log_frame, orient='vertical',
                           command=self.log_text.yview)
        sb.pack(side='right', fill='y')
        self.log_text.configure(yscrollcommand=sb.set)

        self.log_text.tag_configure("info",    foreground="#4fc3f7")
        self.log_text.tag_configure("warning", foreground="#ffb74d")
        self.log_text.tag_configure("error",   foreground="#ef5350")
        self.log_text.tag_configure("success", foreground="#81c784")

    def browse_game(self):
        path = filedialog.askopenfilename(
            title="게임 클라이언트 선택",
            filetypes=[("실행 파일", "*.exe *.bin"), ("모든 파일", "*.*")])
        if path:
            self.game_path_var.set(path)
            self.game_process_var.set(os.path.basename(path))

    def browse_pss(self):
        path = filedialog.askopenfilename(
            title="PSS 프로그램 선택",
            filetypes=[("실행 파일", "*.exe"), ("모든 파일", "*.*")])
        if path:
            self.pss_path_var.set(path)

    def add_log(self, message, level="info"):
        def _add():
            ts = time.strftime("%H:%M:%S")
            self.log_text.configure(state='normal')
            self.log_text.insert('end', f"[{ts}] {message}\n", level)
            self.log_text.see('end')
            self.log_text.configure(state='disabled')
        self.root.after(0, _add)

    def set_status(self, text, color="#888888"):
        def _set():
            self.status_var.set(text)
            self.status_label.configure(foreground=color)
        self.root.after(0, _set)

    def save_settings(self):
        self._sync_config_from_ui()
        self.save_config_to_file()
        messagebox.showinfo("저장 완료", "설정이 저장되었습니다.")

    def _sync_config_from_ui(self):
        self.config["game_process"] = self.game_process_var.get().strip()
        self.config["game_exe_path"] = self.game_path_var.get().strip()
        self.config["pss_exe_path"] = self.pss_path_var.get().strip()
        self.config["check_interval"] = self.interval_var.get()
        self.config["auto_restart_game"] = self.restart_game_var.get()
        self.config["auto_restart_pss"] = self.restart_pss_var.get()
        self.config["kill_pss_before_restart"] = self.kill_pss_var.get()

    def is_process_running(self, process_name):
        try:
            for proc in psutil.process_iter(['name']):
                try:
                    if proc.info['name'].lower() == process_name.lower():
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception:
            pass
        return False

    def kill_process_by_name(self, process_name):
        killed = 0
        try:
            for proc in psutil.process_iter(['name', 'pid']):
                try:
                    if proc.info['name'].lower() == process_name.lower():
                        proc.kill()
                        killed += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception:
            pass
        return killed

    def start_process(self, exe_path, name):
        if not exe_path:
            self.add_log(f"[경고] {name} 경로가 설정되지 않았습니다.", "warning")
            return False
        if not os.path.exists(exe_path):
            self.add_log(f"[오류] {name} 파일 없음: {exe_path}", "error")
            return False
        try:
            cwd = os.path.dirname(exe_path)
            subprocess.Popen(
                [exe_path], cwd=cwd,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
            self.add_log(f"{name} 실행 완료", "success")
            return True
        except Exception as e:
            self.add_log(f"[오류] {name} 실행 실패: {e}", "error")
            return False

    def monitor_loop(self):
        cfg = self.config
        game_proc = cfg["game_process"]
        was_running = False

        self.add_log(f"감시 시작 -> 대상: {game_proc}", "success")

        while self.monitoring:
            is_running = self.is_process_running(game_proc)

            if is_running and not was_running:
                was_running = True
                self.set_status(f"게임 실행 중: {game_proc}", "#4caf50")
                self.add_log(f"게임 클라이언트 감지됨", "success")

            elif not is_running and was_running:
                was_running = False
                self.set_status("게임 종료 감지 - 재시작 처리 중...", "#ff5722")
                self.add_log("게임 클라이언트 종료 감지!", "warning")

                time.sleep(2)

                if cfg["auto_restart_game"] and self.monitoring:
                    self.add_log("게임 클라이언트 재시작 시도...", "info")
                    self.start_process(cfg["game_exe_path"], "게임 클라이언트")
                    time.sleep(5)

                if cfg["auto_restart_pss"] and self.monitoring:
                    pss_name = os.path.basename(cfg["pss_exe_path"]) if cfg["pss_exe_path"] else "PSS"
                    if cfg["kill_pss_before_restart"] and pss_name:
                        killed = self.kill_process_by_name(pss_name)
                        if killed:
                            self.add_log(f"기존 PSS 프로세스 {killed}개 종료", "warning")
                        time.sleep(1)
                    self.add_log("PSS 재시작 시도...", "info")
                    self.start_process(cfg["pss_exe_path"], "PSS")

                if self.monitoring:
                    self.set_status("재시작 완료 - 감시 중...", "#2196f3")

            elif not is_running:
                self.set_status("게임 미실행 - 대기 중...", "#888888")

            time.sleep(cfg["check_interval"])

        self.add_log("감시 루프 종료", "warning")

    def start_monitoring(self):
        self._sync_config_from_ui()
        if not self.config["game_process"]:
            messagebox.showwarning("경고", "게임 프로세스 이름을 입력해주세요.")
            return
        self.monitoring = True
        self.monitor_thread = threading.Thread(
            target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()
        self.start_btn.configure(state='disabled')
        self.stop_btn.configure(state='normal')
        self.set_status("감시 중...", "#2196f3")

    def stop_monitoring(self):
        self.monitoring = False
        self.start_btn.configure(state='normal')
        self.stop_btn.configure(state='disabled')
        self.set_status("감시 중지됨", "#888888")
        self.add_log("감시 중지됨", "warning")

    def on_closing(self):
        if self.monitoring:
            if messagebox.askokcancel("종료 확인", "감시가 실행 중입니다. 종료하시겠습니까?"):
                self.monitoring = False
                self.root.destroy()
        else:
            self.root.destroy()


def main():
    root = tk.Tk()
    app = LineageMonitor(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
