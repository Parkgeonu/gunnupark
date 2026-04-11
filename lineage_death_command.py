import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import os
import json
import pyautogui
import pyperclip
import keyboard as kb
import win32gui
import win32con
import win32api
import win32process
import pystray
from PIL import Image, ImageDraw, ImageGrab
from updater import check_and_update, check_update_on_startup

APP_VERSION  = "1.3.0"
APP_EXE_NAME = "LineageHP"

CONFIG_FILE = "hp_config.json"

DEFAULT_CONFIG = {
    "commands":            [".수배 캐릭터이름"],
    "death_delay":         10.0,
    "check_interval":      0.5,
    "cooldown_sec":        20.0,
    "color_threshold":     60,
    "confirm_count":       3,
    "lineage_title":       "Lineage",
    "hotkey":              "f11",
    "auto_enter_enabled":  False,
    "auto_enter_interval": 60,
    "auto_enter_text":     "",
    "auto_f5_enabled":     False,
    "auto_f5_interval":    60,
    "hp_x":    None,
    "hp_y":    None,
    "hp_x2":   None,
    "hp_color": None,
    "hp_min_pct": 5,
    "death_px_x":     None,
    "death_px_y":     None,
    "death_px_color": None,
    "death_px_enabled": False,
    "click1_x": None,
    "click1_y": None,
    "click2_x": None,
    "click2_y": None,
    "click_hours":       0,
    "click_mins":        5,
    "auto_click_enabled": False,
    "fkey_slots": [
        {"key": "F5",  "hours": 0, "mins": 5},
        {"key": "F6",  "hours": 0, "mins": 5},
        {"key": "F7",  "hours": 0, "mins": 5},
        {"key": "F8",  "hours": 0, "mins": 5},
        {"key": "F9",  "hours": 0, "mins": 5},
        {"key": "F10", "hours": 0, "mins": 5},
    ],
    "watch_delay":        30,
    "watch_px_threshold": 10,
    "watch_region":       None,
    "watch_px_x":         None,
    "watch_px_y":         None,
    "watch_px_color":     None,
    "watch_hp_min_pct":   5,
    "watch_hp_confirm":   3,
    "watch_hp_cooldown":  30,
    "watch_bar_x1": None, "watch_bar_y1": None,
    "watch_bar_x2": None, "watch_bar_y2": None,
    "watch_bar_color":    None,
    "watch_bar_color_thr": 30,
    "watch_bar_dead_px":  5,
    "watch_c1_x": None, "watch_c1_y": None,
    "watch_c2_x": None, "watch_c2_y": None,
    "watch_c3_x": None, "watch_c3_y": None,
    "watch_c1_count": 1,
    "watch_c2_count": 1,
    "watch_c3_count": 1,
    "alt_key_trigger": "F5",
    "alt_key_a":       "F6",
    "alt_key_b":       "F7",
    "alt_key_enabled": False,
    "alt_key_interval_ms": 1000,
    # RGB 트리거
    "rgb_trig_x": None, "rgb_trig_y": None,
    "rgb_trig_mode": "change",
    "rgb_trig_color": None,
    "rgb_trig_threshold": 30,
    "rgb_trig_interval_ms": 500,
    "rgb_trig_cooldown": 5,
    "rgb_actions": [
        {"enabled": False, "type": "none",
         "x": None, "y": None, "click_type": "left",
         "key": "", "delay_before": 0, "delay_after": 200}
        for _ in range(6)
    ],
}


def get_base_dir():
    import sys
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


class App:
    def __init__(self, root):
        self.root          = root
        self.root.title("리니지 1 - HP 감지 자동 입력")
        self.root.geometry("600x680")
        self.root.resizable(False, False)

        self.stop_event      = threading.Event()
        self.auto_enter_stop = threading.Event()
        self.auto_f5_stop    = threading.Event()
        self.auto_click_stop = threading.Event()
        self.fkey_stop_events = [threading.Event() for _ in range(6)]
        self.fkey_running     = [False] * 6
        self.fkey_btns        = []
        self.fkey_lbls        = []
        self.watch_stop_event = threading.Event()
        self.watch_running    = False
        self.watch_btn_caps   = []
        self.watch_progress   = None
        self.lbl_watch_status = None
        self.btn_watch_start  = None
        self.btn_watch_stop   = None
        self.rgb_stop_event   = threading.Event()
        self.rgb_running      = False
        self.btn_rgb_start    = None
        self.btn_rgb_stop     = None
        self.rgb_color_box    = None
        self.alt_key_state    = 0
        self.alt_repeat_stop  = threading.Event()
        self.alt_repeat_on    = False
        self.alt_key_hook     = None
        self.monitoring      = False
        self.auto_enter_on   = False
        self.auto_f5_on      = False
        self.auto_click_on   = False
        self.tray_icon       = None
        self._settings_win   = None
        self._log_buffer     = []
        self.hp_color_box    = None   # 수배 탭 숨김 시 미초기화 방지
        self._log_popup      = None
        self._log_popup_text = None

        self.config = self._load_config()
        self._init_vars()
        self._build_ui()
        self._refresh_hp_display()
        self._setup_tray()
        self._register_hotkey()

        if self.config.get("auto_enter_enabled", False):
            self.v_auto_enter.set(True)
            self._toggle_auto_enter()

        if self.config.get("auto_click_enabled", False):
            self.v_auto_click.set(True)
            self._toggle_auto_click()

    # ─── Config ──────────────────────────────────────────────
    def _load_config(self):
        path = os.path.join(get_base_dir(), CONFIG_FILE)
        cfg  = DEFAULT_CONFIG.copy()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    if "character_name" in saved and "commands" not in saved:
                        saved["commands"] = [f".수배 {saved['character_name']}"]
                    cfg.update(saved)
            except Exception:
                pass
        return cfg

    def _save_config(self, show_msg=True):
        self._sync_from_ui()
        path = os.path.join(get_base_dir(), CONFIG_FILE)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            if show_msg:
                self._log("설정 저장 완료", "success")
        except Exception as e:
            self._log(f"설정 저장 실패: {e}", "error")
        self._register_hotkey()

    def _sync_from_ui(self):
        c = self.config
        if hasattr(self, "cmd_text"):
            c["commands"] = self.cmd_text.get("1.0", "end-1c").split("\n")
        c["death_delay"]         = self._sf(self.v_delay.get(), 10.0)
        c["check_interval"]      = self._sf(self.v_interval.get(), 0.5)
        c["cooldown_sec"]        = self._sf(self.v_cooldown.get(), 20.0)
        c["color_threshold"]     = self._si(self.v_threshold.get(), 60)
        c["confirm_count"]       = self._si(self.v_confirm.get(), 3)
        c["hp_min_pct"]          = self._si(self.v_hp_min_pct.get(), 5)
        c["death_px_enabled"]    = bool(self.v_death_px_enabled.get())
        c["lineage_title"]       = self.v_title.get().strip()
        c["hotkey"]              = self.v_hotkey.get().strip()
        c["auto_enter_enabled"]  = bool(self.v_auto_enter.get())
        c["auto_enter_interval"] = self._si(self.v_ae_interval.get(), 60)
        c["auto_enter_text"]     = self.v_ae_text.get()
        c["auto_f5_enabled"]     = bool(self.v_auto_f5.get())
        c["auto_f5_interval"]    = self._si(self.v_f5_interval.get(), 60)
        c["click_hours"]         = self._si(self.v_click_hours.get(), 0)
        c["click_mins"]          = self._si(self.v_click_mins.get(), 5)
        c["auto_click_enabled"]  = bool(self.v_auto_click.get())
        c["fkey_slots"] = [
            {"key":   self.v_fkey_key[i].get(),
             "hours": self._si(self.v_fkey_hours[i].get(), 0),
             "mins":  self._si(self.v_fkey_mins[i].get(),  0),
             "secs":  self._si(self.v_fkey_secs[i].get(),  0)}
            for i in range(6)
        ]
        c["watch_delay"]        = self._si(self.v_watch_delay.get(), 30)
        c["watch_px_threshold"] = self._si(self.v_watch_px_thr.get(), 10)
        c["watch_hp_min_pct"]   = self._si(self.v_watch_hp_min.get(),  5)
        c["watch_hp_confirm"]   = self._si(self.v_watch_hp_conf.get(), 3)
        c["watch_hp_cooldown"]  = self._si(self.v_watch_hp_cool.get(), 30)
        c["watch_bar_color_thr"] = self._si(self.v_watch_bar_cthr.get(), 30)
        c["watch_bar_dead_px"]  = self._si(self.v_watch_bar_dead.get(), 5)
        c["watch_c1_count"]     = self._si(self.v_watch_c1_count.get(), 1)
        c["watch_c2_count"]     = self._si(self.v_watch_c2_count.get(), 1)
        c["watch_c3_count"]     = self._si(self.v_watch_c3_count.get(), 1)
        c["alt_key_trigger"]      = self.v_alt_trigger.get()
        c["alt_key_a"]            = self.v_alt_key_a.get()
        c["alt_key_enabled"]      = bool(self.v_alt_enabled.get())
        c["alt_key_interval_ms"]  = self._si(self.v_alt_interval_ms.get(), 1000)
        c["rgb_trig_mode"]        = self.v_rgb_trig_mode.get()
        c["rgb_trig_threshold"]   = self._si(self.v_rgb_thr.get(), 30)
        c["rgb_trig_interval_ms"] = self._si(self.v_rgb_interval.get(), 500)
        c["rgb_trig_cooldown"]    = self._si(self.v_rgb_cooldown.get(), 5)
        # rgb_actions는 팝업 저장 시 직접 갱신됨 (enabled 상태만 동기화)
        acts = c.get("rgb_actions", [{}]*6)
        for i in range(6):
            if i < len(acts):
                acts[i]["enabled"] = bool(self.rgb_action_enabled[i].get())
        c["rgb_actions"] = acts

    # ─── Variable init ───────────────────────────────────────
    def _init_vars(self):
        cfg = self.config
        self.v_delay      = tk.StringVar(value=str(cfg["death_delay"]))
        self.v_cooldown   = tk.StringVar(value=str(cfg["cooldown_sec"]))
        self.v_interval   = tk.StringVar(value=str(cfg["check_interval"]))
        self.v_threshold  = tk.StringVar(value=str(cfg["color_threshold"]))
        self.v_confirm    = tk.StringVar(value=str(cfg["confirm_count"]))
        self.v_hp_min_pct = tk.StringVar(value=str(cfg.get("hp_min_pct", 5)))
        self.v_title      = tk.StringVar(value=cfg["lineage_title"])
        self.v_hotkey     = tk.StringVar(value=cfg.get("hotkey", "f11"))
        _dpx = cfg.get("death_px_x")
        _dpy = cfg.get("death_px_y")
        self.v_death_px_pos     = tk.StringVar(
            value=f"({_dpx},{_dpy})" if _dpx is not None else "미설정")
        self.v_death_px_color   = tk.StringVar(
            value=str(tuple(cfg["death_px_color"])) if cfg.get("death_px_color") else "미설정")
        self.v_death_px_enabled = tk.BooleanVar(
            value=cfg.get("death_px_enabled", False))
        self.v_auto_enter    = tk.BooleanVar(value=cfg.get("auto_enter_enabled", False))
        self.v_ae_interval   = tk.StringVar(value=str(cfg.get("auto_enter_interval", 60)))
        self.v_ae_text       = tk.StringVar(value=cfg.get("auto_enter_text", ""))
        self.v_auto_f5       = tk.BooleanVar(value=cfg.get("auto_f5_enabled", False))
        self.v_f5_interval   = tk.StringVar(value=str(cfg.get("auto_f5_interval", 60)))
        self.v_click_hours   = tk.StringVar(value=str(cfg.get("click_hours", 0)))
        self.v_click_mins    = tk.StringVar(value=str(cfg.get("click_mins", 5)))
        self.v_auto_click    = tk.BooleanVar(value=cfg.get("auto_click_enabled", False))
        c1x = cfg.get("click1_x")
        c1y = cfg.get("click1_y")
        c2x = cfg.get("click2_x")
        c2y = cfg.get("click2_y")
        self.v_click1_pos    = tk.StringVar(value=f"({c1x}, {c1y})" if c1x is not None else "미설정")
        self.v_click2_pos    = tk.StringVar(value=f"({c2x}, {c2y})" if c2x is not None else "미설정")
        _slots = cfg.get("fkey_slots", [{"key":"F5","hours":0,"mins":5}]*6)
        self.v_fkey_key   = [tk.StringVar(value=_slots[i].get("key",   "F5")) for i in range(6)]
        self.v_fkey_hours = [tk.StringVar(value=str(_slots[i].get("hours", 0))) for i in range(6)]
        self.v_fkey_mins  = [tk.StringVar(value=str(_slots[i].get("mins",  0))) for i in range(6)]
        self.v_fkey_secs  = [tk.StringVar(value=str(_slots[i].get("secs",  0))) for i in range(6)]
        self.v_watch_delay    = tk.StringVar(value=str(cfg.get("watch_delay", 30)))
        self.v_watch_px_thr   = tk.StringVar(value=str(cfg.get("watch_px_threshold", 10)))
        self.v_watch_hp_min   = tk.StringVar(value=str(cfg.get("watch_hp_min_pct",  5)))
        self.v_watch_hp_conf  = tk.StringVar(value=str(cfg.get("watch_hp_confirm",  3)))
        self.v_watch_hp_cool  = tk.StringVar(value=str(cfg.get("watch_hp_cooldown", 30)))
        _bx1 = cfg.get("watch_bar_x1"); _by1 = cfg.get("watch_bar_y1")
        _bx2 = cfg.get("watch_bar_x2"); _bc  = cfg.get("watch_bar_color")
        self.v_watch_bar_area = tk.StringVar(
            value=f"({_bx1},{_by1}) ~ ({_bx2},{_by1})" if _bx1 is not None else "미설정")
        self.v_watch_bar_color = tk.StringVar(
            value=f"RGB({_bc[0]},{_bc[1]},{_bc[2]})" if _bc else "미설정")
        self.v_watch_bar_px   = tk.StringVar(value="0")
        self.v_watch_bar_cthr = tk.StringVar(value=str(cfg.get("watch_bar_color_thr", 30)))
        self.v_watch_bar_dead = tk.StringVar(value=str(cfg.get("watch_bar_dead_px",   5)))
        r = cfg.get("watch_region")
        self.v_watch_region = tk.StringVar(
            value=f"({r[0]},{r[1]}) {r[2]}×{r[3]}" if r else "미설정")
        _px = cfg.get("watch_px_x")
        _py = cfg.get("watch_px_y")
        _pc = cfg.get("watch_px_color")
        self.v_watch_px_pos   = tk.StringVar(
            value=f"({_px}, {_py})" if _px is not None else "미설정")
        self.v_watch_px_color = tk.StringVar(
            value=f"RGB({_pc[0]}, {_pc[1]}, {_pc[2]})" if _pc else "미설정")
        def _wpos(k1, k2):
            x, y = cfg.get(k1), cfg.get(k2)
            return f"({x}, {y})" if x is not None else "미설정"
        self.v_watch_c1_pos = tk.StringVar(value=_wpos("watch_c1_x", "watch_c1_y"))
        self.v_watch_c2_pos = tk.StringVar(value=_wpos("watch_c2_x", "watch_c2_y"))
        self.v_watch_c3_pos = tk.StringVar(value=_wpos("watch_c3_x", "watch_c3_y"))
        self.v_watch_c1_count = tk.StringVar(value=str(cfg.get("watch_c1_count", 1)))
        self.v_watch_c2_count = tk.StringVar(value=str(cfg.get("watch_c2_count", 1)))
        self.v_watch_c3_count = tk.StringVar(value=str(cfg.get("watch_c3_count", 1)))
        _fkeys = ["F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12"]
        self.v_alt_trigger     = tk.StringVar(value=cfg.get("alt_key_trigger",    "F5"))
        self.v_alt_key_a       = tk.StringVar(value=cfg.get("alt_key_a",          "F6"))
        self.v_alt_enabled     = tk.BooleanVar(value=cfg.get("alt_key_enabled",   False))
        self.v_alt_interval_ms = tk.StringVar(value=str(cfg.get("alt_key_interval_ms", 1000)))
        # HP 표시 변수 (수배 탭 숨김으로 인한 미초기화 방지)
        _hpx = cfg.get("hp_x"); _hpy = cfg.get("hp_y")
        _hpc = cfg.get("hp_color")
        self.v_hp_pos   = tk.StringVar(
            value=f"({_hpx}, {_hpy})" if _hpx is not None else "미설정")
        self.v_hp_color = tk.StringVar(
            value=f"RGB{tuple(_hpc)}" if _hpc else "미설정")
        # RGB 트리거 변수
        _acts = cfg.get("rgb_actions", [{}]*6)
        self.v_rgb_mon_pos   = tk.StringVar(value="미설정")
        self.v_rgb_mon_color = tk.StringVar(value="---")
        self.v_rgb_trig_mode = tk.StringVar(value=cfg.get("rgb_trig_mode", "change"))
        self.v_rgb_thr       = tk.StringVar(value=str(cfg.get("rgb_trig_threshold", 30)))
        self.v_rgb_interval  = tk.StringVar(value=str(cfg.get("rgb_trig_interval_ms", 500)))
        self.v_rgb_cooldown  = tk.StringVar(value=str(cfg.get("rgb_trig_cooldown", 5)))
        self.rgb_action_enabled   = [
            tk.BooleanVar(value=_acts[i].get("enabled", False) if i < len(_acts) else False)
            for i in range(6)
        ]
        self.rgb_action_summaries = [tk.StringVar(value="없음") for _ in range(6)]

    # ─── UI Build ────────────────────────────────────────────
    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TLabelframe.Label", font=("맑은 고딕", 9, "bold"))
        for name, fg, bg, abg in [
            ("Accent.TButton", "white", "#1565c0", "#0d47a1"),
            ("Danger.TButton", "white", "#c62828", "#b71c1c"),
            ("Tray.TButton",   "white", "#37474f", "#263238"),
            ("Set.TButton",    "white", "#4a148c", "#38006b"),
        ]:
            style.configure(name, font=("맑은 고딕", 9, "bold"),
                            foreground=fg, background=bg)
            style.map(name, background=[("active", abg)])

        tk.Label(self.root,
                 text="리니지 1 \u2014 HP=0 감지 자동 입력",
                 font=("맑은 고딕", 13, "bold"), fg="#1a237e"
                 ).pack(pady=(10, 3))
        ttk.Separator(self.root).pack(fill="x", padx=10, pady=(0, 4))

        pad = ttk.Frame(self.root, padding="10 0 10 0")
        pad.pack(fill="both", expand=True)

        # ── Notebook ──
        nb = ttk.Notebook(pad)
        nb.pack(fill="both", expand=True, pady=(0, 6))

        # Tab 1 : 수배 명령어 (숨김)
        # t1 = ttk.Frame(nb, padding="8 6")
        # nb.add(t1, text="   수배 명령어   ")
        # self._build_tab_subae(t1)

        # Tab 2 : 자동 엔터
        t2 = ttk.Frame(nb, padding="8 6")
        nb.add(t2, text="   자동 엔터   ")
        self._build_tab_autoenter(t2)

        # Tab 3 : 자동 클릭
        t3 = ttk.Frame(nb, padding="8 6")
        nb.add(t3, text="   자동 클릭   ")
        self._build_tab_autoclick(t3)

        # Tab 4 : 펑션키
        t4 = ttk.Frame(nb, padding="8 6")
        nb.add(t4, text="   펑션키 자동입력   ")
        self._build_tab_fkey(t4)

        # Tab 5 : 클라이언트 감시 (숨김)
        # t5 = ttk.Frame(nb, padding="8 6")
        # nb.add(t5, text="   클라이언트 감시   ")
        # self._build_tab_watch(t5)

        # Tab 6 : RGB 트리거 감시
        t6 = ttk.Frame(nb, padding="8 6")
        nb.add(t6, text="   RGB 트리거   ")
        self._build_tab_rgb_trigger(t6)

        # ── 공통 버튼 ──
        bf = ttk.Frame(pad)
        bf.pack(fill="x", pady=(0, 4))

        self.btn_start = ttk.Button(bf, text="모니터링 시작",
                                    command=self._start_monitoring,
                                    style="Accent.TButton")
        self.btn_start.pack(side="left", padx=(0, 4))

        self.btn_stop = ttk.Button(bf, text="모니터링 중지",
                                   command=self._stop_monitoring,
                                   style="Danger.TButton", state="disabled")
        self.btn_stop.pack(side="left", padx=(0, 4))

        ttk.Button(bf, text="트레이로",
                   command=self._hide_to_tray,
                   style="Tray.TButton").pack(side="left", padx=(0, 4))

        # ttk.Button(bf, text="\u2699 감지 설정",
        #            command=self._open_settings,
        #            style="Set.TButton").pack(side="left", padx=(0, 4))

        ttk.Button(bf, text="명령어 테스트",
                   command=lambda: threading.Thread(
                       target=self._send_commands, daemon=True).start()
                   ).pack(side="left", padx=(0, 4))

        ttk.Button(bf, text="\u2191 업데이트 확인",
                   command=lambda: check_and_update(
                       APP_VERSION, APP_EXE_NAME, parent=self.root, silent=False
                   )).pack(side="left")

        # ── 상태 ──
        sf = ttk.Frame(pad)
        sf.pack(fill="x", pady=(0, 3))
        ttk.Label(sf, text="상태:").pack(side="left")
        self.v_status = tk.StringVar(value="대기 중")
        self.lbl_status = ttk.Label(sf, textvariable=self.v_status, foreground="#888")
        self.lbl_status.pack(side="left", padx=(4, 0))

        # ── 로그 ──
        lf = ttk.LabelFrame(pad, text=" 로그 ", padding="4")
        lf.pack(fill="both", expand=True)

        self.log = tk.Text(lf, height=7, state="disabled",
                           font=("Consolas", 9),
                           bg="#1e1e1e", fg="#d4d4d4",
                           relief="flat", wrap="word")
        self.log.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(lf, orient="vertical", command=self.log.yview)
        sb.pack(side="right", fill="y")
        self.log.configure(yscrollcommand=sb.set)
        for tag, col in [("info", "#4fc3f7"), ("success", "#81c784"),
                         ("warning", "#ffb74d"), ("error", "#ef5350")]:
            self.log.tag_configure(tag, foreground=col)

    # ── Tab 1: 수배 명령어 ───────────────────────────────────
    def _build_tab_subae(self, parent):
        ttk.Label(parent,
                  text="한 줄에 명령어 1개  |  빈 줄 = 엔터 키만 입력",
                  foreground="#888888", font=("맑은 고딕", 8)
                  ).pack(anchor="w", pady=(0, 3))

        cf = ttk.Frame(parent)
        cf.pack(fill="both", expand=True)

        self.cmd_text = tk.Text(cf, height=5, width=38,
                                font=("Consolas", 10),
                                bg="#1e1e1e", fg="#81c784",
                                insertbackground="white",
                                relief="flat", padx=6, pady=4)
        self.cmd_text.pack(side="left", fill="both", expand=True)
        csb = ttk.Scrollbar(cf, orient="vertical", command=self.cmd_text.yview)
        csb.pack(side="right", fill="y")
        self.cmd_text.configure(yscrollcommand=csb.set)
        self.cmd_text.insert("1.0", "\n".join(self.config.get("commands", [".수배 캐릭터이름"])))

        qf = ttk.Frame(parent)
        qf.pack(fill="x", pady=(4, 6))
        ttk.Label(qf, text="빠른 추가:").pack(side="left")
        ttk.Button(qf, text="엔터 줄 추가",
                   command=lambda: self.cmd_text.insert("end", "\n")
                   ).pack(side="left", padx=(6, 4))
        ttk.Button(qf, text="전체 지우기",
                   command=lambda: self.cmd_text.delete("1.0", "end")
                   ).pack(side="left")

        ttk.Separator(parent).pack(fill="x", pady=(2, 6))

        hf = ttk.Frame(parent)
        hf.pack(fill="x")
        ttk.Label(hf, text="HP바:").pack(side="left")
        self.v_hp_pos = tk.StringVar(value="미설정")
        ttk.Label(hf, textvariable=self.v_hp_pos).pack(side="left", padx=(4, 8))
        self.hp_color_box = tk.Canvas(hf, width=16, height=16, bd=1, relief="solid")
        self.hp_color_box.pack(side="left", padx=(0, 4))
        self.v_hp_color = tk.StringVar(value="미설정")
        ttk.Label(hf, textvariable=self.v_hp_color).pack(side="left", padx=(0, 12))
        ttk.Button(hf, text="⚙ 감지 설정에서 변경",
                   command=self._open_settings
                   ).pack(side="left")

    # ── Tab 2: 자동 엔터 ─────────────────────────────────────
    def _build_tab_autoenter(self, parent):
        # ── 자동 엔터 ──
        ae_f = ttk.LabelFrame(parent, text=" 자동 엔터 ", padding="10 8")
        ae_f.pack(fill="x", pady=(4, 8))

        r1 = ttk.Frame(ae_f)
        r1.pack(fill="x", pady=(0, 6))
        ttk.Checkbutton(r1, text="사용",
                        variable=self.v_auto_enter,
                        command=self._toggle_auto_enter
                        ).pack(side="left")
        ttk.Label(r1, text="입력 텍스트:").pack(side="left", padx=(14, 4))
        ttk.Entry(r1, textvariable=self.v_ae_text, width=22
                  ).pack(side="left")
        ttk.Label(r1, text="(비우면 엔터만)",
                  foreground="#888888", font=("맑은 고딕", 8)
                  ).pack(side="left", padx=(6, 0))

        r2 = ttk.Frame(ae_f)
        r2.pack(fill="x", pady=(0, 6))
        ttk.Label(r2, text="간격(초):").pack(side="left")
        ttk.Spinbox(r2, from_=5, to=3600, increment=5,
                    textvariable=self.v_ae_interval, width=8
                    ).pack(side="left", padx=(6, 0))

        r3 = ttk.Frame(ae_f)
        r3.pack(fill="x")
        ttk.Label(r3, text="상태:").pack(side="left")
        self.lbl_ae_status = ttk.Label(r3, text="꺼짐", foreground="#888888",
                                       font=("맑은 고딕", 9, "bold"))
        self.lbl_ae_status.pack(side="left", padx=(6, 0))

        ttk.Label(ae_f,
                  text="텍스트 있으면: 채팅창 열기 → 텍스트 입력 → 엔터  |  없으면: 엔터만",
                  foreground="#888888", font=("맑은 고딕", 8)
                  ).pack(anchor="w", pady=(6, 0))

        # ── 번갈아 키 전송 ──
        _fkeys = ["F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12"]
        alt_f = ttk.LabelFrame(parent, text=" 번갈아 키 연속 전송 ", padding="10 8")
        alt_f.pack(fill="x", pady=(4, 8))

        ar1 = ttk.Frame(alt_f)
        ar1.pack(fill="x", pady=(0, 6))
        ttk.Checkbutton(ar1, text="사용",
                        variable=self.v_alt_enabled,
                        command=self._toggle_alt_key
                        ).pack(side="left")
        ttk.Label(ar1, text="트리거 키:").pack(side="left", padx=(14, 4))
        ttk.Combobox(ar1, textvariable=self.v_alt_trigger,
                     values=_fkeys, state="readonly", width=5
                     ).pack(side="left")
        ttk.Label(ar1, text="(이 키로 시작 / 재입력 중지)",
                  foreground="#888888", font=("맑은 고딕", 8)
                  ).pack(side="left", padx=(8, 0))

        ar2 = ttk.Frame(alt_f)
        ar2.pack(fill="x", pady=(0, 6))
        ttk.Label(ar2, text="반복 키:").pack(side="left")
        ttk.Combobox(ar2, textvariable=self.v_alt_key_a,
                     values=_fkeys, state="readonly", width=5
                     ).pack(side="left", padx=(4, 0))
        ttk.Label(ar2, text="간격(ms):").pack(side="left", padx=(16, 4))
        ttk.Spinbox(ar2, from_=50, to=60000, increment=50,
                    textvariable=self.v_alt_interval_ms, width=7
                    ).pack(side="left")
        ttk.Label(ar2, text="← [트리거키 1번 + 반복키 1번] 세트 반복",
                  foreground="#888888", font=("맑은 고딕", 8)
                  ).pack(side="left", padx=(8, 0))

        ar3 = ttk.Frame(alt_f)
        ar3.pack(fill="x")
        ttk.Label(ar3, text="상태:").pack(side="left")
        self.lbl_alt_status = ttk.Label(ar3, text="꺼짐", foreground="#888888",
                                        font=("맑은 고딕", 9, "bold"))
        self.lbl_alt_status.pack(side="left", padx=(6, 0))
        ttk.Label(ar3, text="  방금:").pack(side="left", padx=(12, 0))
        self.lbl_alt_next = ttk.Label(ar3, text="-", foreground="#4fc3f7",
                                      font=("맑은 고딕", 9, "bold"))
        self.lbl_alt_next.pack(side="left", padx=(4, 0))

    # ── Tab 3: 자동 클릭 ─────────────────────────────────────
    def _build_tab_autoclick(self, parent):
        # ── 좌표 설정 ──
        coord_f = ttk.LabelFrame(parent, text=" 좌표 설정 ", padding="10 8")
        coord_f.pack(fill="x", pady=(4, 8))

        r1 = ttk.Frame(coord_f)
        r1.pack(fill="x", pady=(0, 6))
        ttk.Label(r1, text="1차 좌표:").pack(side="left")
        ttk.Label(r1, textvariable=self.v_click1_pos,
                  foreground="#4fc3f7", font=("Consolas", 9)
                  ).pack(side="left", padx=(6, 10))
        self.btn_cap1 = ttk.Button(r1, text="캡처 (3초)",
                                   command=lambda: self._start_coord_capture(1))
        self.btn_cap1.pack(side="left")

        r2 = ttk.Frame(coord_f)
        r2.pack(fill="x")
        ttk.Label(r2, text="2차 좌표:").pack(side="left")
        ttk.Label(r2, textvariable=self.v_click2_pos,
                  foreground="#4fc3f7", font=("Consolas", 9)
                  ).pack(side="left", padx=(6, 10))
        self.btn_cap2 = ttk.Button(r2, text="캡처 (3초)",
                                   command=lambda: self._start_coord_capture(2))
        self.btn_cap2.pack(side="left")

        ttk.Label(coord_f,
                  text="버튼 클릭 후 3초 안에 마우스를 원하는 위치로 이동하세요.",
                  foreground="#888888", font=("맑은 고딕", 8)
                  ).pack(anchor="w", pady=(6, 0))

        # ── 반복 간격 ──
        iv_f = ttk.LabelFrame(parent, text=" 반복 간격 ", padding="10 8")
        iv_f.pack(fill="x", pady=(0, 8))

        ir = ttk.Frame(iv_f)
        ir.pack(fill="x", pady=(0, 4))
        ttk.Spinbox(ir, from_=0, to=23, increment=1,
                    textvariable=self.v_click_hours, width=4
                    ).pack(side="left")
        ttk.Label(ir, text="시간").pack(side="left", padx=(2, 10))
        ttk.Spinbox(ir, from_=0, to=59, increment=1,
                    textvariable=self.v_click_mins, width=4
                    ).pack(side="left")
        ttk.Label(ir, text="분  마다 반복").pack(side="left", padx=(2, 0))

        ttk.Label(iv_f,
                  text="1차 좌표 클릭 → 0.5초 대기 → 2차 좌표 클릭 순서로 실행됩니다.",
                  foreground="#888888", font=("맑은 고딕", 8)
                  ).pack(anchor="w")

        # ── 제어 / 상태 ──
        ctrl_f = ttk.Frame(parent)
        ctrl_f.pack(fill="x", pady=(0, 4))

        self.btn_click_start = ttk.Button(ctrl_f, text="자동 클릭 시작",
                                          style="Accent.TButton",
                                          command=self._toggle_auto_click_on)
        self.btn_click_start.pack(side="left", padx=(0, 4))

        self.btn_click_stop = ttk.Button(ctrl_f, text="자동 클릭 중지",
                                         style="Danger.TButton", state="disabled",
                                         command=self._toggle_auto_click_off)
        self.btn_click_stop.pack(side="left")

        sf = ttk.Frame(parent)
        sf.pack(fill="x")
        ttk.Label(sf, text="상태:").pack(side="left")
        self.lbl_click_status = ttk.Label(sf, text="꺼짐", foreground="#888888",
                                          font=("맑은 고딕", 9, "bold"))
        self.lbl_click_status.pack(side="left", padx=(6, 0))

    # ── Tab 4: 펑션키 자동 입력 ──────────────────────────────
    def _build_tab_fkey(self, parent):
        FKEYS = ["F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12"]

        ttk.Label(parent,
                  text="각 슬롯마다 독립적으로 지정 시간마다 선택한 키를 리니지 창에 입력합니다.",
                  foreground="#888888", font=("맑은 고딕", 8)
                  ).pack(anchor="w", pady=(0, 6))

        gf = ttk.Frame(parent)
        gf.pack(fill="x")

        headers = ["슬롯", "키", "시간", "", "분", "", "초", "", "상태"]
        for c, h in enumerate(headers):
            ttk.Label(gf, text=h, foreground="#aaaaaa",
                      font=("맑은 고딕", 8, "bold")
                      ).grid(row=0, column=c, padx=(0, 4), pady=(0, 4), sticky="w")

        self.fkey_btns = []
        self.fkey_lbls = []

        for i in range(6):
            idx = i
            ttk.Label(gf, text=f"#{i+1}").grid(row=i+1, column=0, padx=(0, 6), pady=2, sticky="w")

            cb = ttk.Combobox(gf, textvariable=self.v_fkey_key[i],
                              values=FKEYS, width=5, state="readonly")
            cb.grid(row=i+1, column=1, padx=(0, 6), pady=2)

            ttk.Spinbox(gf, from_=0, to=23, increment=1,
                        textvariable=self.v_fkey_hours[i], width=4
                        ).grid(row=i+1, column=2, pady=2)
            ttk.Label(gf, text="시간").grid(row=i+1, column=3, padx=(2, 6), pady=2, sticky="w")

            ttk.Spinbox(gf, from_=0, to=59, increment=1,
                        textvariable=self.v_fkey_mins[i], width=4
                        ).grid(row=i+1, column=4, pady=2)
            ttk.Label(gf, text="분").grid(row=i+1, column=5, padx=(2, 6), pady=2, sticky="w")

            ttk.Spinbox(gf, from_=0, to=59, increment=1,
                        textvariable=self.v_fkey_secs[i], width=4
                        ).grid(row=i+1, column=6, pady=2)
            ttk.Label(gf, text="초").grid(row=i+1, column=7, padx=(2, 8), pady=2, sticky="w")

            btn = ttk.Button(gf, text="시작", width=5,
                             command=lambda n=idx: self._toggle_fkey_slot(n))
            btn.grid(row=i+1, column=8, padx=(0, 8), pady=2)
            self.fkey_btns.append(btn)

            lbl = ttk.Label(gf, text="꺼짐", foreground="#888888",
                            font=("맑은 고딕", 8, "bold"))
            lbl.grid(row=i+1, column=9, pady=2, sticky="w")
            self.fkey_lbls.append(lbl)

    # ─── Fkey workers ─────────────────────────────────────────
    _FK_VK = {
        "F5":  (win32con.VK_F5,  0x3F),
        "F6":  (win32con.VK_F6,  0x40),
        "F7":  (win32con.VK_F7,  0x41),
        "F8":  (win32con.VK_F8,  0x42),
        "F9":  (win32con.VK_F9,  0x43),
        "F10": (win32con.VK_F10, 0x44),
        "F11": (win32con.VK_F11, 0x57),
        "F12": (win32con.VK_F12, 0x58),
    }

    def _toggle_fkey_slot(self, i):
        if self.fkey_running[i]:
            self.fkey_stop_events[i].set()
            self.fkey_running[i] = False
            self.fkey_btns[i].configure(text="시작")
            self.fkey_lbls[i].configure(text="꺼짐", foreground="#888888")
            self._log(f"펑션키 #{i+1} 중지", "warning")
        else:
            h = self._si(self.v_fkey_hours[i].get(), 0)
            m = self._si(self.v_fkey_mins[i].get(),  0)
            s = self._si(self.v_fkey_secs[i].get(),  0)
            if h == 0 and m == 0 and s == 0:
                messagebox.showwarning("경고", f"슬롯 #{i+1}: 지연시간을 1초 이상 설정하세요.")
                return
            self.fkey_stop_events[i].clear()
            self.fkey_running[i] = True
            self.fkey_btns[i].configure(text="중지")
            key = self.v_fkey_key[i].get()
            self.fkey_lbls[i].configure(text=f"{h:02d}:{m:02d}:{s:02d}", foreground="#81c784")
            self._log(f"펑션키 #{i+1} [{key}] 시작 (간격: {h}시간 {m}분 {s}초)", "success")
            threading.Thread(target=self._fkey_worker, args=(i,), daemon=True).start()

    def _fkey_worker(self, i):
        while not self.fkey_stop_events[i].is_set():
            h        = self._si(self.v_fkey_hours[i].get(), 0)
            m        = self._si(self.v_fkey_mins[i].get(),  0)
            s        = self._si(self.v_fkey_secs[i].get(),  0)
            interval = h * 3600 + m * 60 + s
            if interval < 1:
                interval = 1
            for remaining in range(interval, 0, -1):
                if self.fkey_stop_events[i].is_set():
                    return
                rem_h = remaining // 3600
                rem_m = (remaining % 3600) // 60
                rem_s = remaining % 60
                self.root.after(0, lambda idx=i, rh=rem_h, rm=rem_m, rs=rem_s:
                    self.fkey_lbls[idx].config(
                        text=f"{rh:02d}:{rm:02d}:{rs:02d}",
                        foreground="#4fc3f7"
                    ) if idx < len(self.fkey_lbls) else None
                )
                time.sleep(1)
            if self.fkey_stop_events[i].is_set():
                return
            key = self.v_fkey_key[i].get()
            vk, scan = self._FK_VK.get(key, (win32con.VK_F5, 0x3F))
            hwnd = self._find_lineage_hwnd()
            if hwnd:
                try:
                    win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, vk, (scan << 16) | 0x0001)
                    time.sleep(0.05)
                    win32api.PostMessage(hwnd, win32con.WM_KEYUP,   vk, 0xC0000000 | (scan << 16) | 0x0001)
                    self._log(f"펑션키 #{i+1} [{key}] 입력 (간격: {h}시간 {m}분 {s}초)", "info")
                except Exception as e:
                    self._log(f"펑션키 #{i+1} 실패: {e}", "warning")
            else:
                self._log(f"펑션키 #{i+1}: 리니지 창 없음", "warning")

    # ── Tab 5: 클라이언트 감시 ───────────────────────────────
    def _build_tab_watch(self, parent):
        ttk.Label(parent,
                  text="HP 바 영역을 설정하면 HP 픽셀 수를 실시간 감시  |  픽셀 수 = 0 → 수배 명령어 자동 실행",
                  foreground="#888888", font=("맑은 고딕", 8)
                  ).pack(anchor="w", pady=(0, 4))

        # ── HP 바 영역 감시 설정 ──
        rf = ttk.LabelFrame(parent, text=" HP 바 영역 감시 ", padding="8 6")
        rf.pack(fill="x", pady=(0, 5))

        rr1 = ttk.Frame(rf);  rr1.pack(fill="x", pady=(0, 4))
        ttk.Label(rr1, text="HP 바 영역:").pack(side="left")
        ttk.Label(rr1, textvariable=self.v_watch_bar_area,
                  foreground="#4fc3f7", font=("Consolas", 9)
                  ).pack(side="left", padx=(6, 10))
        self.btn_watch_region = ttk.Button(rr1, text="HP 바 설정 (6초: 좌→우)",
                                           command=self._start_watch_region_capture)
        self.btn_watch_region.pack(side="left")

        rr2 = ttk.Frame(rf);  rr2.pack(fill="x", pady=(0, 4))
        ttk.Label(rr2, text="HP 색상:").pack(side="left")
        self.lbl_watch_bar_color = ttk.Label(rr2, textvariable=self.v_watch_bar_color,
                                             foreground="#ef9a9a", font=("Consolas", 9))
        self.lbl_watch_bar_color.pack(side="left", padx=(6, 0))
        ttk.Label(rr2, text="  감도:").pack(side="left", padx=(14, 4))
        ttk.Spinbox(rr2, from_=5, to=100, increment=5,
                    textvariable=self.v_watch_bar_cthr, width=4).pack(side="left")

        rr3 = ttk.Frame(rf);  rr3.pack(fill="x", pady=(0, 4))
        ttk.Label(rr3, text="현재 HP 픽셀 수:").pack(side="left")
        ttk.Label(rr3, textvariable=self.v_watch_bar_px,
                  foreground="#ffb74d", font=("Consolas", 11, "bold")
                  ).pack(side="left", padx=(6, 0))
        ttk.Label(rr3, text="  (감시 중 실시간 갱신)",
                  foreground="#888888", font=("맑은 고딕", 8)
                  ).pack(side="left", padx=(4, 0))

        rr4 = ttk.Frame(rf);  rr4.pack(fill="x")
        ttk.Label(rr4, text="사망 임계값(px):").pack(side="left")
        ttk.Spinbox(rr4, from_=0, to=50, increment=1,
                    textvariable=self.v_watch_bar_dead, width=4).pack(side="left", padx=(6, 0))
        ttk.Label(rr4, text="이하 =사망  확인:").pack(side="left", padx=(10, 4))
        ttk.Spinbox(rr4, from_=1, to=10, increment=1,
                    textvariable=self.v_watch_hp_conf, width=3).pack(side="left")
        ttk.Label(rr4, text="회  대기:").pack(side="left", padx=(8, 4))
        ttk.Spinbox(rr4, from_=5, to=300, increment=5,
                    textvariable=self.v_watch_hp_cool, width=5).pack(side="left")
        ttk.Label(rr4, text="초",
                  foreground="#888888", font=("맑은 고딕", 8)
                  ).pack(side="left", padx=(4, 0))

        # ── 좌표 설정 ──
        cf = ttk.LabelFrame(parent, text=" 클릭 좌표 설정 ", padding="8 6")
        cf.pack(fill="x", pady=(0, 5))
        self.watch_btn_caps = []
        count_vars = [self.v_watch_c1_count, self.v_watch_c2_count, self.v_watch_c3_count]
        for num, var, label in [
            (1, self.v_watch_c1_pos, "1차 (감지 후):  "),
            (2, self.v_watch_c2_pos, "2차 (바로 이동):"),
            (3, self.v_watch_c3_pos, "3차 (5초 후):   "),
        ]:
            row = ttk.Frame(cf)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=label, font=("Consolas", 9)).pack(side="left")
            ttk.Label(row, textvariable=var,
                      foreground="#4fc3f7", font=("Consolas", 9), width=14
                      ).pack(side="left", padx=(4, 6))
            btn = ttk.Button(row, text="캡처 (3초)",
                             command=lambda n=num: self._start_watch_capture(n))
            btn.pack(side="left")
            self.watch_btn_caps.append(btn)
            ttk.Label(row, text="  클릭 횟수:").pack(side="left")
            ttk.Spinbox(row, from_=1, to=20, increment=1,
                        textvariable=count_vars[num - 1], width=4
                        ).pack(side="left", padx=(2, 0))

        # ── 지연시간 ──
        df = ttk.Frame(parent)
        df.pack(fill="x", pady=(0, 4))
        ttk.Label(df, text="변화 없을 시 지연(초):").pack(side="left")
        ttk.Spinbox(df, from_=5, to=3600, increment=5,
                    textvariable=self.v_watch_delay, width=7
                    ).pack(side="left", padx=(6, 0))

        # ── 진행 바 + 상태 ──
        pf = ttk.LabelFrame(parent, text=" 진행 상태 ", padding="6 4")
        pf.pack(fill="x", pady=(0, 4))
        self.watch_progress = ttk.Progressbar(pf, orient="horizontal",
                                              mode="determinate",
                                              maximum=100, value=0)
        self.watch_progress.pack(fill="x", pady=(0, 3))
        self.lbl_watch_status = ttk.Label(pf, text="대기 중",
                                          foreground="#888888",
                                          font=("맑은 고딕", 9, "bold"))
        self.lbl_watch_status.pack(anchor="w")

        # ── 제어 버튼 ──
        bf = ttk.Frame(parent)
        bf.pack(fill="x")
        self.btn_watch_start = ttk.Button(bf, text="감시 시작",
                                          style="Accent.TButton",
                                          command=self._toggle_watch_on)
        self.btn_watch_start.pack(side="left", padx=(0, 4))
        self.btn_watch_stop = ttk.Button(bf, text="감시 중지",
                                         style="Danger.TButton", state="disabled",
                                         command=self._toggle_watch_off)
        self.btn_watch_stop.pack(side="left")

    # ─── Watch Bar Capture ────────────────────────────────────
    def _start_watch_region_capture(self):
        self.btn_watch_region.configure(state="disabled")
        self._log("HP 바 설정 - 3초 후 HP 바 [좌측 끝]에 마우스를 올려주세요", "warning")
        threading.Thread(target=self._watch_region_worker, daemon=True).start()

    def _watch_region_worker(self):
        for i in range(3, 0, -1):
            px, py = pyautogui.position()
            self._log(f"  좌측 {i}초... ({px},{py})", "info")
            time.sleep(1)
        x1, y1 = pyautogui.position()
        self._log(f"좌측 확정 ({x1},{y1})  →  3초 후 HP 바 [우측 끝]에 마우스를 올려주세요", "warning")
        for i in range(3, 0, -1):
            px, py = pyautogui.position()
            self._log(f"  우측 {i}초... ({px},{py})", "info")
            time.sleep(1)
        x2, y2 = pyautogui.position()
        if abs(x2 - x1) < 5:
            self._log("영역이 너무 좁습니다. 다시 설정하세요.", "error")
            self.root.after(0, lambda: self.btn_watch_region.configure(state="normal"))
            return
        # 중앙 픽셀에서 HP 색상 자동 감지
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        try:
            color = list(self._get_pixel(cx, cy))
        except Exception:
            color = [200, 50, 50]
        self.config["watch_bar_x1"]    = min(x1, x2)
        self.config["watch_bar_y1"]    = cy
        self.config["watch_bar_x2"]    = max(x1, x2)
        self.config["watch_bar_y2"]    = cy
        self.config["watch_bar_color"] = color
        # 현재 픽셀 수 바로 계산
        cur_px = self._count_watch_hp_px()
        hex_c  = "#{:02X}{:02X}{:02X}".format(*color)
        def _done():
            w = abs(x2 - x1)
            self.v_watch_bar_area.set(f"({min(x1,x2)},{cy}) ~ ({max(x1,x2)},{cy})  너비:{w}px")
            self.v_watch_bar_color.set(f"RGB({color[0]},{color[1]},{color[2]})  {hex_c}")
            self.v_watch_bar_px.set(str(cur_px if cur_px is not None else 0))
            try:
                self.lbl_watch_bar_color.configure(foreground=hex_c)
            except Exception:
                pass
            self._save_config(show_msg=False)
            self._log(f"HP 바 설정 완료  영역:너비{w}px  색:{hex_c}  현재:{cur_px}px", "success")
            self.btn_watch_region.configure(state="normal")
        self.root.after(0, _done)

    def _count_watch_hp_px(self):
        cfg   = self.config
        x1    = cfg.get("watch_bar_x1")
        y1    = cfg.get("watch_bar_y1")
        x2    = cfg.get("watch_bar_x2")
        color = cfg.get("watch_bar_color")
        if x1 is None or color is None:
            return None
        thr = max(5, self._si(self.v_watch_bar_cthr.get(), 30))
        try:
            img  = ImageGrab.grab(bbox=(x1, y1 - 3, x2, y1 + 4))
            pix  = img.load()
            w, h = img.size
            hr, hg, hb = color
            return sum(
                1 for row in range(h) for col in range(w)
                if ((pix[col, row][0]-hr)**2 +
                    (pix[col, row][1]-hg)**2 +
                    (pix[col, row][2]-hb)**2) ** 0.5 <= thr
            )
        except Exception:
            return None

    # ─── Tab 6: RGB 트리거 감시 ───────────────────────────────
    def _build_tab_rgb_trigger(self, parent):
        ttk.Label(parent,
                  text="지정 좌표의 RGB를 실시간 감시하여 조건 충족 시 액션을 순서대로 실행합니다.",
                  foreground="#888888", font=("맑은 고딕", 8)
                  ).pack(anchor="w", pady=(0, 6))

        # ── 감시 설정 ──
        sf = ttk.LabelFrame(parent, text=" 감시 설정 ", padding="8 6")
        sf.pack(fill="x", pady=(0, 6))

        # 좌표 행
        r1 = ttk.Frame(sf); r1.pack(fill="x", pady=(0, 4))
        ttk.Label(r1, text="감시 좌표:").pack(side="left")
        ttk.Label(r1, textvariable=self.v_rgb_mon_pos,
                  foreground="#81c784").pack(side="left", padx=(4, 12))
        ttk.Button(r1, text="3초 캡처",
                   command=self._rgb_capture_pos).pack(side="left")

        # 색 표시 행
        r2 = ttk.Frame(sf); r2.pack(fill="x", pady=(0, 4))
        ttk.Label(r2, text="현재 색:").pack(side="left")
        self.rgb_color_box = tk.Canvas(r2, width=18, height=18, bd=1, relief="solid",
                                       bg="#222222")
        self.rgb_color_box.pack(side="left", padx=(4, 4))
        ttk.Label(r2, textvariable=self.v_rgb_mon_color,
                  foreground="#ffb74d").pack(side="left", padx=(0, 12))

        # 모드 행
        r3 = ttk.Frame(sf); r3.pack(fill="x", pady=(0, 4))
        ttk.Label(r3, text="트리거 모드:").pack(side="left")
        ttk.Radiobutton(r3, text="색 변화 감지", variable=self.v_rgb_trig_mode,
                        value="change").pack(side="left", padx=(6, 0))
        ttk.Radiobutton(r3, text="특정 색 일치", variable=self.v_rgb_trig_mode,
                        value="match").pack(side="left", padx=(6, 0))
        self._btn_rgb_save_color = ttk.Button(r3, text="현재 색 저장 (일치 기준)",
                                               command=self._rgb_save_target_color)
        self._btn_rgb_save_color.pack(side="left", padx=(8, 0))

        # 파라미터 행
        r4 = ttk.Frame(sf); r4.pack(fill="x")
        ttk.Label(r4, text="임계값:").pack(side="left")
        ttk.Spinbox(r4, from_=0, to=255, increment=1,
                    textvariable=self.v_rgb_thr, width=5).pack(side="left", padx=(4, 12))
        ttk.Label(r4, text="체크간격(ms):").pack(side="left")
        ttk.Spinbox(r4, from_=100, to=10000, increment=100,
                    textvariable=self.v_rgb_interval, width=6).pack(side="left", padx=(4, 12))
        ttk.Label(r4, text="쿨다운(초):").pack(side="left")
        ttk.Spinbox(r4, from_=0, to=300, increment=1,
                    textvariable=self.v_rgb_cooldown, width=5).pack(side="left", padx=(4, 0))

        # ── 액션 목록 ──
        af = ttk.LabelFrame(parent, text=" 실행 액션 (트리거 시 순서대로 실행) ", padding="8 6")
        af.pack(fill="x", pady=(0, 6))

        headers = ["#", "활성", "액션 요약", ""]
        col_w   = [2, 3, 35, 8]
        for c, (h, w) in enumerate(zip(headers, col_w)):
            ttk.Label(af, text=h, foreground="#aaaaaa",
                      font=("맑은 고딕", 8, "bold"), width=w
                      ).grid(row=0, column=c, padx=(0, 4), pady=(0, 4), sticky="w")

        for i in range(6):
            idx = i
            ttk.Label(af, text=f"#{i+1}").grid(row=i+1, column=0, padx=(0, 4), pady=2, sticky="w")
            ttk.Checkbutton(af, variable=self.rgb_action_enabled[i],
                            command=lambda n=idx: self._rgb_update_summary(n)
                            ).grid(row=i+1, column=1, pady=2)
            ttk.Label(af, textvariable=self.rgb_action_summaries[i],
                      foreground="#888888", width=38, anchor="w"
                      ).grid(row=i+1, column=2, pady=2, sticky="w")
            ttk.Button(af, text="편집", width=6,
                       command=lambda n=idx: self._open_rgb_action_popup(n)
                       ).grid(row=i+1, column=3, pady=2)

        # 요약 초기화
        for i in range(6):
            self._rgb_update_summary(i)

        # ── 제어 버튼 ──
        bf = ttk.Frame(parent); bf.pack(fill="x", pady=(4, 0))
        self.btn_rgb_start = ttk.Button(bf, text="▶ 감시 시작",
                                        command=self._toggle_rgb_on,
                                        style="Accent.TButton")
        self.btn_rgb_start.pack(side="left", padx=(0, 4))
        self.btn_rgb_stop = ttk.Button(bf, text="■ 감시 중지",
                                       command=self._toggle_rgb_off,
                                       style="Danger.TButton", state="disabled")
        self.btn_rgb_stop.pack(side="left")
        self.lbl_rgb_status = ttk.Label(bf, text="대기 중", foreground="#888888")
        self.lbl_rgb_status.pack(side="left", padx=(12, 0))

    # ─── Watch Capture ────────────────────────────────────────
    def _start_watch_capture(self, num):
        if not self.watch_btn_caps or num - 1 >= len(self.watch_btn_caps):
            return
        btn = self.watch_btn_caps[num - 1]
        btn.configure(state="disabled")
        self._log(f"감시 {num}차 좌표 캡처 - 3초 안에 마우스를 이동하세요", "warning")
        threading.Thread(target=self._watch_capture_worker, args=(num,), daemon=True).start()

    def _watch_capture_worker(self, num):
        for i in range(3, 0, -1):
            x, y = pyautogui.position()
            self._log(f"  {i}초... ({x},{y})", "info")
            time.sleep(1)
        x, y = pyautogui.position()
        self.config[f"watch_c{num}_x"] = x
        self.config[f"watch_c{num}_y"] = y
        var = [self.v_watch_c1_pos, self.v_watch_c2_pos, self.v_watch_c3_pos][num - 1]
        btn = self.watch_btn_caps[num - 1] if self.watch_btn_caps and num - 1 < len(self.watch_btn_caps) else None
        def _done():
            var.set(f"({x}, {y})")
            self._save_config(show_msg=False)
            self._log(f"감시 {num}차 좌표 설정: ({x},{y})", "success")
            if btn and btn.winfo_exists():
                btn.configure(state="normal")
        self.root.after(0, _done)

    # ─── Watch Toggle / Worker ────────────────────────────────
    def _toggle_watch_on(self):
        if self.config.get("watch_bar_x1") is None:
            messagebox.showwarning("경고", "HP 바 영역을 먼저 설정하세요.\n[HP 바 설정 (6초: 좌→우)] 버튼을 클릭하세요.")
            return
        if not all(self.config.get(f"watch_c{n}_x") is not None for n in (1, 2, 3)):
            messagebox.showwarning("경고", "1~3차 좌표를 모두 캡처하세요.")
            return
        self.watch_stop_event.clear()
        self.watch_running = True
        if self.btn_watch_start:
            self.btn_watch_start.configure(state="disabled")
        if self.btn_watch_stop:
            self.btn_watch_stop.configure(state="normal")
        self._log("클라이언트 감시 시작 (화면 픽셀 변화 방식)", "success")
        threading.Thread(target=self._watch_worker, daemon=True).start()

    def _toggle_watch_off(self):
        self.watch_stop_event.set()
        self.watch_running = False
        if self.btn_watch_start:
            self.btn_watch_start.configure(state="normal")
        if self.btn_watch_stop:
            self.btn_watch_stop.configure(state="disabled")
        self._watch_set_status("중지됨", "#888888", 0)
        self._log("클라이언트 감시 중지", "warning")

    def _watch_set_status(self, text, color, pct=None):
        def _do():
            if self.lbl_watch_status and self.lbl_watch_status.winfo_exists():
                self.lbl_watch_status.configure(text=text, foreground=color)
            if pct is not None and self.watch_progress and self.watch_progress.winfo_exists():
                self.watch_progress.configure(value=pct)
        self.root.after(0, _do)

    # ─── RGB 트리거 메서드들 ───────────────────────────────────
    def _rgb_update_summary(self, idx):
        acts = self.config.get("rgb_actions", [{}]*6)
        act  = acts[idx] if idx < len(acts) else {}
        atype = act.get("type", "none")
        enabled = self.rgb_action_enabled[idx].get()
        type_map = {
            "none": "없음", "move": "마우스 이동",
            "click": "마우스 클릭", "key": "키보드 입력", "delay": "지연"
        }
        label = type_map.get(atype, "없음")
        if atype == "move":
            label += f"  →  ({act.get('x','?')}, {act.get('y','?')})"
        elif atype == "click":
            ct = {"left":"좌클릭","right":"우클릭","double":"더블클릭"}.get(act.get("click_type","left"),"좌클릭")
            label += f"  →  {ct}  ({act.get('x','?')}, {act.get('y','?')})"
        elif atype == "key":
            label += f"  →  [{act.get('key','')}]"
        elif atype == "delay":
            label += f"  →  {act.get('delay_after',0)} ms"
        prefix = "[ON] " if enabled else "[OFF] "
        self.rgb_action_summaries[idx].set(prefix + label)

    def _rgb_save_target_color(self):
        x = self.config.get("rgb_trig_x")
        y = self.config.get("rgb_trig_y")
        if x is None:
            messagebox.showwarning("경고", "먼저 감시 좌표를 캡처하세요.")
            return
        try:
            r, g, b = pyautogui.pixel(x, y)
            self.config["rgb_trig_color"] = [r, g, b]
            self._save_config(show_msg=False)
            self._log(f"RGB 일치 기준 색 저장: RGB({r},{g},{b})", "success")
        except Exception as e:
            self._log(f"색 저장 실패: {e}", "error")

    def _rgb_capture_pos(self):
        self._log("RGB 감시 좌표 캡처 — 3초 후 마우스 위치 저장", "warning")
        def _worker():
            for i in range(3, 0, -1):
                x, y = pyautogui.position()
                self._log(f"  {i}초... ({x},{y})", "info")
                time.sleep(1)
            x, y = pyautogui.position()
            self.config["rgb_trig_x"] = x
            self.config["rgb_trig_y"] = y
            self._save_config(show_msg=False)
            def _ui():
                self.v_rgb_mon_pos.set(f"({x}, {y})")
                self._log(f"RGB 감시 좌표 설정: ({x},{y})", "success")
            self.root.after(0, _ui)
        threading.Thread(target=_worker, daemon=True).start()

    def _open_rgb_action_popup(self, idx):
        acts = self.config.get("rgb_actions", [{}]*6)
        while len(acts) < 6:
            acts.append({"enabled": False, "type": "none",
                         "x": None, "y": None, "click_type": "left",
                         "key": "", "delay_before": 0, "delay_after": 200})
        act = acts[idx]

        win = tk.Toplevel(self.root)
        win.title(f"액션 #{idx+1} 편집")
        win.geometry("420x380")
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()

        pad = ttk.Frame(win, padding="14 12"); pad.pack(fill="both", expand=True)

        TYPE_OPTS = ["없음", "마우스 이동", "마우스 클릭", "키보드 입력", "지연"]
        TYPE_KEY  = ["none", "move", "click", "key", "delay"]
        cur_type  = act.get("type", "none")
        try:
            cur_label = TYPE_OPTS[TYPE_KEY.index(cur_type)]
        except ValueError:
            cur_label = "없음"

        v_type  = tk.StringVar(value=cur_label)
        v_x     = tk.StringVar(value=str(act.get("x", 0) or 0))
        v_y     = tk.StringVar(value=str(act.get("y", 0) or 0))
        v_click = tk.StringVar(value=act.get("click_type", "left"))
        v_key   = tk.StringVar(value=act.get("key", ""))
        v_dbef  = tk.StringVar(value=str(act.get("delay_before", 0)))
        v_daft  = tk.StringVar(value=str(act.get("delay_after", 200)))

        # 액션 타입
        r0 = ttk.Frame(pad); r0.pack(fill="x", pady=(0, 8))
        ttk.Label(r0, text="액션 타입:", width=14, anchor="e").pack(side="left")
        cb_type = ttk.Combobox(r0, textvariable=v_type,
                               values=TYPE_OPTS, state="readonly", width=14)
        cb_type.pack(side="left", padx=(6, 0))

        # 좌표 행
        r1 = ttk.Frame(pad); r1.pack(fill="x", pady=(0, 6))
        ttk.Label(r1, text="X:", width=14, anchor="e").pack(side="left")
        sb_x = ttk.Spinbox(r1, from_=0, to=9999, textvariable=v_x, width=6)
        sb_x.pack(side="left", padx=(6, 4))
        ttk.Label(r1, text="Y:").pack(side="left")
        sb_y = ttk.Spinbox(r1, from_=0, to=9999, textvariable=v_y, width=6)
        sb_y.pack(side="left", padx=(4, 8))

        cap_lbl = ttk.Label(r1, text="대기 중", foreground="#888888",
                            font=("맑은 고딕", 8))
        cap_lbl.pack(side="left")

        def _capture_xy():
            cap_lbl.configure(text="3초 후 캡처...", foreground="#ffb74d")
            def _w():
                for i in range(3, 0, -1):
                    cx, cy = pyautogui.position()
                    self.root.after(0, lambda i=i, cx=cx, cy=cy:
                        cap_lbl.configure(text=f"{i}초.. ({cx},{cy})"))
                    time.sleep(1)
                fx, fy = pyautogui.position()
                self.root.after(0, lambda: (
                    v_x.set(str(fx)), v_y.set(str(fy)),
                    cap_lbl.configure(text=f"완료 ({fx},{fy})", foreground="#81c784")
                ))
            threading.Thread(target=_w, daemon=True).start()

        ttk.Button(r1, text="3초 캡처", command=_capture_xy).pack(side="left", padx=(4, 0))

        # 클릭 타입
        r2 = ttk.Frame(pad); r2.pack(fill="x", pady=(0, 6))
        ttk.Label(r2, text="클릭 타입:", width=14, anchor="e").pack(side="left")
        for ct_val, ct_txt in [("left","좌클릭"),("right","우클릭"),("double","더블클릭")]:
            rb = ttk.Radiobutton(r2, text=ct_txt, variable=v_click, value=ct_val)
            rb.pack(side="left", padx=(6, 0))

        # 키 이름
        r3 = ttk.Frame(pad); r3.pack(fill="x", pady=(0, 6))
        ttk.Label(r3, text="키 이름:", width=14, anchor="e").pack(side="left")
        ent_key = ttk.Entry(r3, textvariable=v_key, width=16)
        ent_key.pack(side="left", padx=(6, 0))
        ttk.Label(r3, text="  예) enter, f1, a, space",
                  foreground="#888888", font=("맑은 고딕", 8)).pack(side="left", padx=(6, 0))

        # 지연 시간
        r4 = ttk.Frame(pad); r4.pack(fill="x", pady=(0, 6))
        ttk.Label(r4, text="실행 전 지연:", width=14, anchor="e").pack(side="left")
        sb_dbef = ttk.Spinbox(r4, from_=0, to=60000, increment=100,
                              textvariable=v_dbef, width=6)
        sb_dbef.pack(side="left", padx=(6, 4))
        ttk.Label(r4, text="ms").pack(side="left")

        r5 = ttk.Frame(pad); r5.pack(fill="x", pady=(0, 12))
        ttk.Label(r5, text="실행 후 지연:", width=14, anchor="e").pack(side="left")
        sb_daft = ttk.Spinbox(r5, from_=0, to=60000, increment=100,
                              textvariable=v_daft, width=6)
        sb_daft.pack(side="left", padx=(6, 4))
        ttk.Label(r5, text="ms").pack(side="left")

        # 필드 활성/비활성 제어
        coord_widgets  = [sb_x, sb_y]
        click_widgets  = list(r2.winfo_children())[1:]  # Radiobuttons
        key_widgets    = [ent_key]

        def _on_type_change(*_):
            sel = v_type.get()
            st_coord  = "normal" if sel in ("마우스 이동", "마우스 클릭") else "disabled"
            st_click  = "normal" if sel == "마우스 클릭" else "disabled"
            st_key    = "normal" if sel == "키보드 입력"  else "disabled"
            for w in coord_widgets:  w.configure(state=st_coord)
            for w in r2.winfo_children()[1:]:
                try: w.configure(state=st_click)
                except Exception: pass
            ent_key.configure(state=st_key)

        v_type.trace_add("write", _on_type_change)
        _on_type_change()

        # 확인/취소
        rb = ttk.Frame(pad); rb.pack(fill="x")
        def _ok():
            sel = v_type.get()
            try:
                t_key = TYPE_KEY[TYPE_OPTS.index(sel)]
            except ValueError:
                t_key = "none"
            new_act = {
                "enabled":     self.rgb_action_enabled[idx].get(),
                "type":        t_key,
                "x":           int(v_x.get()) if v_x.get().isdigit() else None,
                "y":           int(v_y.get()) if v_y.get().isdigit() else None,
                "click_type":  v_click.get(),
                "key":         v_key.get().strip(),
                "delay_before": int(v_dbef.get()) if v_dbef.get().isdigit() else 0,
                "delay_after":  int(v_daft.get()) if v_daft.get().isdigit() else 200,
            }
            acts_cfg = self.config.get("rgb_actions", [{}]*6)
            while len(acts_cfg) < 6:
                acts_cfg.append({})
            acts_cfg[idx] = new_act
            self.config["rgb_actions"] = acts_cfg
            self._save_config(show_msg=False)
            self._rgb_update_summary(idx)
            self._log(f"액션 #{idx+1} 저장: {t_key}", "success")
            win.destroy()

        ttk.Button(rb, text="확인", style="Accent.TButton", command=_ok,
                   width=8).pack(side="left", padx=(0, 6))
        ttk.Button(rb, text="취소", command=win.destroy, width=8).pack(side="left")

    def _toggle_rgb_on(self):
        if self.config.get("rgb_trig_x") is None:
            messagebox.showwarning("경고", "먼저 감시 좌표를 캡처하세요.")
            return
        self.rgb_stop_event.clear()
        self.rgb_running = True
        if self.btn_rgb_start: self.btn_rgb_start.configure(state="disabled")
        if self.btn_rgb_stop:  self.btn_rgb_stop.configure(state="normal")
        self.lbl_rgb_status.configure(text="감시 중...", foreground="#81c784")
        self._log("RGB 트리거 감시 시작", "success")
        threading.Thread(target=self._rgb_monitor_worker, daemon=True).start()

    def _toggle_rgb_off(self):
        self.rgb_stop_event.set()
        self.rgb_running = False
        if self.btn_rgb_start: self.btn_rgb_start.configure(state="normal")
        if self.btn_rgb_stop:  self.btn_rgb_stop.configure(state="disabled")
        self.lbl_rgb_status.configure(text="중지됨", foreground="#888888")
        self._log("RGB 트리거 감시 중지", "warning")

    def _rgb_monitor_worker(self):
        prev_color  = None
        last_trig   = 0.0
        while not self.rgb_stop_event.is_set():
            try:
                x = self.config.get("rgb_trig_x")
                y = self.config.get("rgb_trig_y")
                if x is None or y is None:
                    self.rgb_stop_event.wait(1)
                    continue

                r, g, b   = pyautogui.pixel(x, y)
                cur       = (r, g, b)
                hex_color = "#{:02x}{:02x}{:02x}".format(r, g, b)

                def _update_ui(hc=hex_color, cr=cur):
                    self.v_rgb_mon_color.set(f"RGB{cr}")
                    if self.rgb_color_box:
                        try: self.rgb_color_box.configure(bg=hc)
                        except Exception: pass
                self.root.after(0, _update_ui)

                thr      = int(self.v_rgb_thr.get() or 30)
                mode     = self.v_rgb_trig_mode.get()
                cooldown = float(self.v_rgb_cooldown.get() or 5)
                triggered = False

                if mode == "change" and prev_color is not None:
                    dist = sum(abs(a - b2) for a, b2 in zip(cur, prev_color))
                    triggered = dist > thr

                elif mode == "match":
                    target = self.config.get("rgb_trig_color")
                    if target:
                        dist = sum(abs(a - b2) for a, b2 in zip(cur, target))
                        triggered = dist <= thr

                prev_color = cur

                now = time.time()
                if triggered and (now - last_trig) > cooldown:
                    last_trig = now
                    self._log(f"RGB 트리거 발생! 색={cur}", "warning")
                    threading.Thread(target=self._execute_rgb_actions,
                                     daemon=True).start()

            except Exception as e:
                self._log(f"RGB 감시 오류: {e}", "error")

            interval = max(0.1, int(self.v_rgb_interval.get() or 500) / 1000)
            self.rgb_stop_event.wait(interval)

    def _execute_rgb_actions(self):
        acts = self.config.get("rgb_actions", [])
        for idx, act in enumerate(acts):
            if not act.get("enabled", False):
                continue
            atype       = act.get("type", "none")
            delay_bef   = act.get("delay_before", 0) / 1000
            delay_aft   = act.get("delay_after",  200) / 1000
            ax, ay      = act.get("x"), act.get("y")
            click_type  = act.get("click_type", "left")
            key_name    = act.get("key", "")

            try:
                if delay_bef > 0:
                    time.sleep(delay_bef)

                if atype == "move" and ax is not None:
                    pyautogui.moveTo(ax, ay, duration=0.1)
                    self._log(f"  #{ idx+1} 마우스 이동 → ({ax},{ay})", "info")

                elif atype == "click" and ax is not None:
                    if click_type == "right":
                        pyautogui.rightClick(ax, ay)
                    elif click_type == "double":
                        pyautogui.doubleClick(ax, ay)
                    else:
                        pyautogui.click(ax, ay)
                    ct = {"left":"좌클릭","right":"우클릭","double":"더블클릭"}.get(click_type,"클릭")
                    self._log(f"  #{idx+1} {ct} → ({ax},{ay})", "info")

                elif atype == "key" and key_name:
                    pyautogui.press(key_name)
                    self._log(f"  #{idx+1} 키 입력: [{key_name}]", "info")

                elif atype == "delay":
                    time.sleep(delay_aft)
                    self._log(f"  #{idx+1} 지연: {int(delay_aft*1000)}ms", "info")
                    continue  # delay 타입은 delay_after 대신 직접 처리

                if delay_aft > 0:
                    time.sleep(delay_aft)

            except Exception as e:
                self._log(f"  #{idx+1} 액션 오류: {e}", "error")

    def _watch_worker(self):
        INTERVAL = 0.5
        dead_cnt = 0

        while not self.watch_stop_event.is_set():
            self.watch_stop_event.wait(INTERVAL)
            if self.watch_stop_event.is_set():
                break

            cur_px = self._count_watch_hp_px()
            if cur_px is None:
                self._watch_set_status("HP 바 설정 없음  →  [HP 바 설정] 버튼을 먼저 클릭하세요", "#e53935", 0)
                continue

            # UI 픽셀 수 실시간 갱신
            self.root.after(0, lambda v=cur_px: self.v_watch_bar_px.set(str(v)))

            dead_px  = max(0, self._si(self.v_watch_bar_dead.get(), 5))
            need_cnt = max(1, self._si(self.v_watch_hp_conf.get(), 3))

            if cur_px > dead_px:
                dead_cnt = 0
                self._watch_set_status(f"HP 픽셀: {cur_px}px  정상", "#81c784",
                                       min(100, cur_px))
                continue

            dead_cnt += 1
            self._watch_set_status(
                f"HP 픽셀: {cur_px}px ≤ {dead_px}px  사망 감지 [{dead_cnt}/{need_cnt}]",
                "#e53935", min(100, dead_cnt / need_cnt * 100))

            if dead_cnt < need_cnt:
                continue

            dead_cnt = 0
            self._log(f"HP 픽셀 {cur_px}px 사망 확정  →  수배 명령어 실행", "warning")
            self._watch_set_status("수배 명령어 실행 중...", "#f57c00", 100)
            threading.Thread(target=self._send_commands, daemon=True).start()

            cooldown = max(5, self._si(self.v_watch_hp_cool.get(), 30))
            for remaining in range(cooldown, 0, -1):
                if self.watch_stop_event.is_set():
                    return
                self._watch_set_status(
                    f"명령어 실행 완료  →  재감시까지 {remaining}초 대기", "#ffb74d", 0)
                time.sleep(1)

            self._watch_execute_sequence()

    def _watch_execute_sequence(self):
        def _click_n(xk, yk, label, count_key):
            x, y = self.config.get(xk), self.config.get(yk)
            if x is None:
                return
            n = max(1, self.config.get(count_key, 1))
            for i in range(n):
                pyautogui.moveTo(x, y, duration=0.2)
                time.sleep(0.3)
                pyautogui.click()
                self._log(f"감시 클릭: {label} ({x},{y}) [{i+1}/{n}]", "info")
                if i < n - 1:
                    time.sleep(0.3)

        self._watch_set_status("클릭 실행 중...", "#81c784", 100)
        _click_n("watch_c1_x", "watch_c1_y", "1차", "watch_c1_count")
        time.sleep(0.5)
        _click_n("watch_c2_x", "watch_c2_y", "2차", "watch_c2_count")

        for i in range(5, 0, -1):
            if self.watch_stop_event.is_set():
                return
            self._watch_set_status(f"3차 클릭까지... {i}초", "#4fc3f7", 0)
            time.sleep(1)

        if not self.watch_stop_event.is_set():
            _click_n("watch_c3_x", "watch_c3_y", "3차", "watch_c3_count")
            self._watch_set_status("완료 - 감시 재시작", "#81c784", 0)

    # ─── Settings Popup ──────────────────────────────────────
    def _open_settings(self):
        if self._settings_win and self._settings_win.winfo_exists():
            self._settings_win.lift()
            return

        win = tk.Toplevel(self.root)
        win.title("감지 설정")
        win.geometry("520x720")
        win.resizable(True, True)
        win.minsize(480, 600)
        win.transient(self.root)
        self._settings_win = win

        pad = ttk.Frame(win, padding="12 10")
        pad.pack(fill="both", expand=True)

        # ── HP바 위치 ──
        hp_f = ttk.LabelFrame(pad, text=" HP바 영역 설정 ", padding="8 6")
        hp_f.pack(fill="x", pady=(0, 8))

        hr = ttk.Frame(hp_f)
        hr.pack(fill="x", pady=(0, 4))
        ttk.Label(hr, text="왼쪽 끝:").pack(side="left")
        ttk.Label(hr, textvariable=self.v_hp_pos,
                  foreground="#4fc3f7").pack(side="left", padx=(4, 16))
        ttk.Label(hr, text="색상:").pack(side="left")
        ttk.Label(hr, textvariable=self.v_hp_color).pack(side="left", padx=(4, 0))

        hr2 = ttk.Frame(hp_f)
        hr2.pack(fill="x", pady=(0, 6))
        ttk.Label(hr2, text="오른쪽 끝:").pack(side="left")
        self.v_hp_pos2 = tk.StringVar(value=(
            f"({self.config['hp_x2']},{self.config['hp_y']})"
            if self.config.get("hp_x2") else "미설정"
        ))
        ttk.Label(hr2, textvariable=self.v_hp_pos2,
                  foreground="#4fc3f7").pack(side="left", padx=(4, 16))
        if self.config.get("hp_x2") and self.config.get("hp_x"):
            width = self.config["hp_x2"] - self.config["hp_x"]
            ttk.Label(hr2, text=f"범위: {width}px",
                      foreground="#81c784").pack(side="left")

        bf2 = ttk.Frame(hp_f)
        bf2.pack(fill="x", pady=(0, 2))
        self.btn_capture = ttk.Button(bf2,
                                      text="① 왼쪽 끝 캡처  (HP바 시작점, 5초)",
                                      command=self._start_calibration)
        self.btn_capture.pack(fill="x", pady=(0, 3))
        self.btn_capture2 = ttk.Button(bf2,
                                       text="② 오른쪽 끝 캡처  (HP바 끝점, 5초)",
                                       command=self._start_calibration_right)
        self.btn_capture2.pack(fill="x")

        # ── 감지 설정 ──
        det_f = ttk.LabelFrame(pad, text=" 감지 설정 ", padding="8 6")
        det_f.pack(fill="x", pady=(0, 8))

        def row(parent, r, label1, var1, f1, t1, inc1,
                label2, var2, f2, t2, inc2):
            ttk.Label(parent, text=label1).grid(row=r, column=0, sticky="w", pady=2)
            ttk.Spinbox(parent, from_=f1, to=t1, increment=inc1,
                        textvariable=var1, width=7
                        ).grid(row=r, column=1, sticky="w", padx=(4, 0))
            ttk.Label(parent, text=label2).grid(row=r, column=2, sticky="w", padx=(14, 0))
            ttk.Spinbox(parent, from_=f2, to=t2, increment=inc2,
                        textvariable=var2, width=7
                        ).grid(row=r, column=3, sticky="w", padx=(4, 0))

        row(det_f, 0, "HP=0 후 대기(초):", self.v_delay,    1,   60,  1,
                       "쿨다운(초):",       self.v_cooldown, 5,  120,  5)
        row(det_f, 1, "감지 주기(초):",    self.v_interval, 0.1,  5, 0.1,
                       "색상 임계값:",     self.v_threshold, 10, 150,  5)
        row(det_f, 2, "연속 감지 횟수:",   self.v_confirm,  1,   10,  1,
                       "HP% 임계값:",      self.v_hp_min_pct, 1,  30,  1)
        ttk.Label(det_f, text="  ← HP가 이 % 이하일 때 감지",
                  foreground="#888888", font=("맑은 고딕", 7)
                  ).grid(row=2, column=4, sticky="w", padx=(4, 0))

        ttk.Label(det_f, text="리니지 창 제목:").grid(row=3, column=0, sticky="w", pady=2)
        title_cb = ttk.Combobox(det_f, textvariable=self.v_title, width=20)
        title_cb["values"] = self._get_window_titles()
        title_cb.grid(row=3, column=1, columnspan=3, sticky="w", padx=(4, 0))
        ttk.Button(det_f, text="↺",
                   command=lambda: title_cb.configure(values=self._get_window_titles()),
                   width=2
                   ).grid(row=3, column=4, padx=(4, 0))

        ttk.Label(det_f, text="트레이 단축키:").grid(row=4, column=0, sticky="w", pady=2)
        ttk.Entry(det_f, textvariable=self.v_hotkey, width=8
                  ).grid(row=4, column=1, sticky="w", padx=(4, 0))
        ttk.Label(det_f, text="(예: f11, ctrl+h)",
                  foreground="#888888"
                  ).grid(row=4, column=2, columnspan=2, sticky="w", padx=(14, 0))

        # ── 죽음 화면 보조 감지 ──
        dp_f = ttk.LabelFrame(pad, text=" 죽음 화면 보조 감지 (선택) ", padding="8 6")
        dp_f.pack(fill="x", pady=(0, 8))

        dp_info = ttk.Frame(dp_f)
        dp_info.pack(fill="x", pady=(0, 4))
        ttk.Label(dp_info, text="위치:").pack(side="left")
        ttk.Label(dp_info, textvariable=self.v_death_px_pos,
                  foreground="#ffb74d").pack(side="left", padx=(4, 16))
        ttk.Label(dp_info, text="색상:").pack(side="left")
        ttk.Label(dp_info, textvariable=self.v_death_px_color,
                  foreground="#ffb74d").pack(side="left", padx=(4, 0))

        ttk.Button(dp_f,
                   text="죽음 화면 픽셀 캡처  (캐릭터 죽은 직후 → 5초 안에 마우스 올리기)",
                   command=self._start_calibration_death
                   ).pack(fill="x", pady=(0, 4))

        dp_chk = ttk.Frame(dp_f)
        dp_chk.pack(fill="x")
        ttk.Checkbutton(dp_chk,
                        text="보조 감지 활성화  (HP바 감지 + 죽음 픽셀 감지 동시 사용)",
                        variable=self.v_death_px_enabled
                        ).pack(side="left")

        ttk.Label(dp_f,
                  text="※ 죽으면 나타나는 부활창·메시지 위의 특정 픽셀을 캡처하세요.",
                  foreground="#888888", font=("맑은 고딕", 7)
                  ).pack(anchor="w", pady=(4, 0))

        # ── 버튼 ──
        bf = ttk.Frame(pad)
        bf.pack(fill="x", pady=(4, 0))
        ttk.Button(bf, text="저장 및 닫기",
                   command=lambda: [self._save_config(), win.destroy()],
                   style="Accent.TButton"
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(bf, text="취소",
                   command=win.destroy
                   ).pack(side="left")

    # ─── System Tray ─────────────────────────────────────────
    def _create_tray_image(self):
        img  = Image.new("RGBA", (64, 64), (26, 35, 126, 255))
        draw = ImageDraw.Draw(img)
        draw.ellipse([8, 8, 56, 56], fill=(198, 40, 40))
        draw.rectangle([10, 28, 54, 36], fill=(255, 255, 255))
        return img

    def _setup_tray(self):
        menu = pystray.Menu(
            pystray.MenuItem("열기", self._show_window, default=True),
            pystray.MenuItem("로그 보기", self._show_log_popup),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("모니터링 시작",
                             lambda i, it: self.root.after(0, self._start_monitoring)),
            pystray.MenuItem("모니터링 중지",
                             lambda i, it: self.root.after(0, self._stop_monitoring)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("종료", self._quit_app),
        )
        self.tray_icon = pystray.Icon(
            "lineage_hp", self._create_tray_image(), "리니지 HP 감지", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _show_window(self, icon=None, item=None):
        self.root.after(0, self.root.deiconify)
        self.root.after(0, self.root.lift)
        self.root.after(50,  lambda: self.root.attributes("-topmost", True))
        self.root.after(200, lambda: self.root.attributes("-topmost", False))

    def _hide_to_tray(self):
        self.root.withdraw()
        if self.tray_icon:
            status = "모니터링 중" if self.monitoring else "대기 중"
            self.tray_icon.title = f"리니지 HP 감지 [{status}]"

    def _show_log_popup(self, icon=None, item=None):
        def _open():
            if self._log_popup and self._log_popup.winfo_exists():
                self._log_popup.lift()
                self._log_popup.attributes("-topmost", True)
                self._log_popup.after(200, lambda: self._log_popup.attributes("-topmost", False))
                return
            win = tk.Toplevel(self.root)
            win.title("리니지 HP 감지 - 로그")
            win.geometry("520x220")
            win.resizable(True, True)
            win.configure(bg="#1e1e1e")

            frame = tk.Frame(win, bg="#1e1e1e", padx=4, pady=4)
            frame.pack(fill="both", expand=True)

            txt = tk.Text(frame, state="disabled",
                          font=("Consolas", 9),
                          bg="#1e1e1e", fg="#d4d4d4",
                          relief="flat", wrap="word")
            txt.pack(side="left", fill="both", expand=True)
            sb = ttk.Scrollbar(frame, orient="vertical", command=txt.yview)
            sb.pack(side="right", fill="y")
            txt.configure(yscrollcommand=sb.set)

            for tag, col in [("info", "#4fc3f7"), ("success", "#81c784"),
                             ("warning", "#ffb74d"), ("error", "#ef5350")]:
                txt.tag_configure(tag, foreground=col)

            txt.configure(state="normal")
            for line, lv in self._log_buffer:
                txt.insert("end", line, lv)
            txt.see("end")
            txt.configure(state="disabled")

            self._log_popup      = win
            self._log_popup_text = txt

            def _on_close():
                self._log_popup      = None
                self._log_popup_text = None
                win.destroy()
            win.protocol("WM_DELETE_WINDOW", _on_close)

            win.attributes("-topmost", True)
            win.after(200, lambda: win.attributes("-topmost", False))
        self.root.after(0, _open)

    def _quit_app(self, icon=None, item=None):
        self.stop_event.set()
        self.auto_enter_stop.set()
        self.auto_f5_stop.set()
        self.auto_click_stop.set()
        for ev in self.fkey_stop_events:
            ev.set()
        self.watch_stop_event.set()
        self.alt_repeat_stop.set()
        self._unregister_alt_hook()
        try: kb.unhook_all_hotkeys()
        except Exception: pass
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.after(0, self.root.destroy)

    # ─── Hotkey ──────────────────────────────────────────────
    def _register_hotkey(self):
        try: kb.unhook_all_hotkeys()
        except Exception: pass
        hotkey = self.config.get("hotkey", "").strip()
        if not hotkey:
            return
        try:
            kb.add_hotkey(hotkey, self._hide_to_tray)
            self._log(f"단축키 등록: {hotkey.upper()} → 트레이로", "info")
        except Exception as e:
            self._log(f"단축키 등록 실패 ({hotkey}): {e}", "warning")

    # ─── Auto Enter ──────────────────────────────────────────
    def _toggle_auto_enter(self):
        if self.v_auto_enter.get():
            self.auto_enter_stop.clear()
            self.auto_enter_on = True
            threading.Thread(target=self._auto_enter_worker, daemon=True).start()
            iv = self._si(self.v_ae_interval.get(), 60)
            self.lbl_ae_status.configure(
                text=f"실행 중  ({iv}초마다)", foreground="#81c784")
            self._log(f"자동 엔터 시작 ({iv}초마다)", "success")
        else:
            self.auto_enter_stop.set()
            self.auto_enter_on = False
            self.lbl_ae_status.configure(text="꺼짐", foreground="#888888")
            self._log("자동 엔터 중지", "warning")

    def _auto_enter_worker(self):
        while not self.auto_enter_stop.is_set():
            interval = self._si(self.v_ae_interval.get(), 60)
            for _ in range(interval):
                if self.auto_enter_stop.is_set():
                    return
                time.sleep(1)
            if self.auto_enter_stop.is_set():
                return

            hwnd = self._find_lineage_hwnd()
            if not hwnd:
                self._log("자동 엔터: 리니지 창 없음", "warning")
                continue

            text = self.v_ae_text.get().strip()
            try:
                if text:
                    # 텍스트 있음: 채팅창 열기 → 입력 → 엔터
                    self._force_focus(hwnd)
                    time.sleep(0.3)
                    self._post_enter(hwnd)       # 채팅창 열기
                    time.sleep(0.5)
                    pyperclip.copy(text)
                    try:
                        kb.write(text, delay=0.05)
                    except Exception:
                        kb.send("ctrl+v")
                    time.sleep(0.2)
                    self._post_enter(hwnd)       # 전송
                    self._log(f"자동 엔터: '{text}' 입력", "info")
                else:
                    # 텍스트 없음: 엔터만
                    self._post_enter(hwnd)
                    self._log("자동 엔터 입력", "info")
            except Exception as e:
                self._log(f"자동 엔터 실패: {e}", "warning")

    # ─── Auto F5 ─────────────────────────────────────────────
    def _toggle_auto_f5(self):
        if self.v_auto_f5.get():
            self.auto_f5_stop.clear()
            self.auto_f5_on = True
            threading.Thread(target=self._auto_f5_worker, daemon=True).start()
            iv = self._si(self.v_f5_interval.get(), 60)
            self._log(f"자동 F5 시작 ({iv}초마다)", "success")
        else:
            self.auto_f5_stop.set()
            self.auto_f5_on = False
            self._log("자동 F5 중지", "warning")

    def _auto_f5_worker(self):
        VK_F5 = win32con.VK_F5
        while not self.auto_f5_stop.is_set():
            interval = self._si(self.v_f5_interval.get(), 60)
            for _ in range(interval):
                if self.auto_f5_stop.is_set():
                    return
                time.sleep(1)
            if self.auto_f5_stop.is_set():
                return
            hwnd = self._find_lineage_hwnd()
            if hwnd:
                try:
                    win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, VK_F5, 0x003F0001)
                    time.sleep(0.05)
                    win32api.PostMessage(hwnd, win32con.WM_KEYUP,   VK_F5, 0xC03F0001)
                    self._log("자동 F5 입력", "info")
                except Exception as e:
                    self._log(f"자동 F5 실패: {e}", "warning")
            else:
                self._log("자동 F5: 리니지 창 없음", "warning")

    # ─── Alt Key (번갈아 키 연속 전송) ──────────────────────
    def _toggle_alt_key(self):
        if self.v_alt_enabled.get():
            self._register_alt_hook()
            trigger = self.v_alt_trigger.get()
            self.root.after(0, lambda: self.lbl_alt_status.configure(
                text=f"대기 중  [{trigger}] 누르면 시작", foreground="#ffb74d"))
            self._log(f"연속 전송 활성  트리거:{trigger}  반복키:{self.v_alt_key_a.get()}", "success")
        else:
            self._unregister_alt_hook()
            self._stop_alt_repeat()
            self.root.after(0, lambda: (
                self.lbl_alt_status.configure(text="꺼짐", foreground="#888888"),
                self.lbl_alt_next.configure(text="-")
            ))
            self._log("번갈아 키 전송 비활성", "warning")

    def _register_alt_hook(self):
        self._unregister_alt_hook()
        trigger = self.v_alt_trigger.get().lower()
        try:
            self.alt_key_hook = kb.hook_key(trigger, self._alt_trigger_event, suppress=False)
        except Exception as e:
            self._log(f"번갈아 키 훅 실패: {e}", "warning")

    def _unregister_alt_hook(self):
        if self.alt_key_hook is not None:
            try:    kb.unhook(self.alt_key_hook)
            except Exception: pass
            self.alt_key_hook = None

    def _alt_trigger_event(self, event):
        if event.event_type != "down":
            return
        if self.alt_repeat_on:
            self._stop_alt_repeat()
        else:
            self._start_alt_repeat()

    def _start_alt_repeat(self):
        self.alt_repeat_stop.clear()
        self.alt_repeat_on = True
        ms      = self._si(self.v_alt_interval_ms.get(), 1000)
        trigger = self.v_alt_trigger.get()
        key_a   = self.v_alt_key_a.get()
        threading.Thread(target=self._alt_repeat_worker, daemon=True).start()
        self.root.after(0, lambda: self.lbl_alt_status.configure(
            text=f"전송 중  [{trigger}+{key_a}]  {ms}ms", foreground="#81c784"))
        self._log(f"연속 전송 시작  [{trigger}+{key_a}]  간격:{ms}ms", "success")

    def _stop_alt_repeat(self):
        self.alt_repeat_stop.set()
        self.alt_repeat_on = False
        trigger = self.v_alt_trigger.get()
        self.root.after(0, lambda: (
            self.lbl_alt_status.configure(
                text=f"대기 중  [{trigger}] 누르면 시작", foreground="#ffb74d"),
            self.lbl_alt_next.configure(text="-")
        ))
        self._log("연속 전송 중지 (트리거 키 재입력으로 재시작)", "warning")

    def _alt_repeat_worker(self):
        while not self.alt_repeat_stop.is_set():
            trigger  = self.v_alt_trigger.get()
            key_a    = self.v_alt_key_a.get()
            vk_t, sc_t = self._FK_VK.get(trigger, (win32con.VK_F5, 0x3F))
            vk_a, sc_a = self._FK_VK.get(key_a,   (win32con.VK_F6, 0x40))
            hwnd = self._find_lineage_hwnd()
            if hwnd:
                try:
                    win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, vk_t, (sc_t << 16) | 0x0001)
                    time.sleep(0.05)
                    win32api.PostMessage(hwnd, win32con.WM_KEYUP,   vk_t, 0xC0000000 | (sc_t << 16) | 0x0001)
                    time.sleep(0.05)
                    win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, vk_a, (sc_a << 16) | 0x0001)
                    time.sleep(0.05)
                    win32api.PostMessage(hwnd, win32con.WM_KEYUP,   vk_a, 0xC0000000 | (sc_a << 16) | 0x0001)
                    label = f"{trigger}+{key_a}"
                    self._log(f"전송: [{label}]", "info")
                    self.root.after(0, lambda lb=label: self.lbl_alt_next.configure(text=lb))
                except Exception as e:
                    self._log(f"연속 전송 실패: {e}", "warning")
            else:
                self._log("연속 전송: 리니지 창 없음", "warning")
            ms = max(50, self._si(self.v_alt_interval_ms.get(), 1000))
            self.alt_repeat_stop.wait(ms / 1000.0)

    # ─── Auto Click ──────────────────────────────────────────
    def _start_coord_capture(self, num):
        btn = self.btn_cap1 if num == 1 else self.btn_cap2
        btn.configure(state="disabled")
        self._log(f"{num}차 좌표 캡처 시작 - 3초 안에 마우스를 원하는 위치로 이동하세요", "warning")
        threading.Thread(target=self._coord_capture_worker, args=(num,), daemon=True).start()

    def _coord_capture_worker(self, num):
        for i in range(3, 0, -1):
            x, y = pyautogui.position()
            self._log(f"  {i}초... 위치:({x},{y})", "info")
            time.sleep(1)
        x, y = pyautogui.position()
        self.config[f"click{num}_x"] = x
        self.config[f"click{num}_y"] = y
        var = self.v_click1_pos if num == 1 else self.v_click2_pos
        btn = self.btn_cap1 if num == 1 else self.btn_cap2

        def _done():
            var.set(f"({x}, {y})")
            self._save_config(show_msg=False)
            self._log(f"{num}차 좌표 설정 완료: ({x},{y})", "success")
            if btn.winfo_exists():
                btn.configure(state="normal")
        self.root.after(0, _done)

    def _toggle_auto_click(self):
        if self.v_auto_click.get():
            self._toggle_auto_click_on()
        else:
            self._toggle_auto_click_off()

    def _toggle_auto_click_on(self):
        if self.config.get("click1_x") is None or self.config.get("click2_x") is None:
            messagebox.showwarning("경고", "1차/2차 좌표를 먼저 캡처하세요.")
            return
        hours = self._si(self.v_click_hours.get(), 0)
        mins  = self._si(self.v_click_mins.get(), 0)
        if hours == 0 and mins == 0:
            messagebox.showwarning("경고", "반복 간격을 1분 이상으로 설정하세요.")
            return
        self.auto_click_stop.clear()
        self.auto_click_on = True
        self.v_auto_click.set(True)
        threading.Thread(target=self._auto_click_worker, daemon=True).start()
        self.btn_click_start.configure(state="disabled")
        self.btn_click_stop.configure(state="normal")
        self.lbl_click_status.configure(
            text=f"실행 중  ({hours}시간 {mins}분마다)", foreground="#81c784")
        self._log(f"자동 클릭 시작 ({hours}시간 {mins}분마다)", "success")

    def _toggle_auto_click_off(self):
        self.auto_click_stop.set()
        self.auto_click_on = False
        self.v_auto_click.set(False)
        self.btn_click_start.configure(state="normal")
        self.btn_click_stop.configure(state="disabled")
        self.lbl_click_status.configure(text="꺼짐", foreground="#888888")
        self._log("자동 클릭 중지", "warning")

    def _auto_click_worker(self):
        while not self.auto_click_stop.is_set():
            hours    = self._si(self.v_click_hours.get(), 0)
            mins     = self._si(self.v_click_mins.get(), 0)
            interval = hours * 3600 + mins * 60
            for _ in range(interval):
                if self.auto_click_stop.is_set():
                    return
                time.sleep(1)
            if self.auto_click_stop.is_set():
                return
            x1 = self.config.get("click1_x")
            y1 = self.config.get("click1_y")
            x2 = self.config.get("click2_x")
            y2 = self.config.get("click2_y")
            try:
                pyautogui.moveTo(x1, y1, duration=0.2)
                time.sleep(0.2)
                pyautogui.click()
                self._log(f"자동 클릭: 1차 ({x1},{y1})", "info")
                time.sleep(0.8)
                pyautogui.moveTo(x2, y2, duration=0.2)
                time.sleep(0.3)
                pyautogui.click()
                self._log(f"자동 클릭: 2차 ({x2},{y2})", "info")
                for _ in range(30):
                    if self.auto_click_stop.is_set():
                        return
                    time.sleep(1)
                if not self.auto_click_stop.is_set():
                    hwnd = self._find_lineage_hwnd()
                    if hwnd:
                        win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_ESCAPE, 0x00010001)
                        time.sleep(0.05)
                        win32api.PostMessage(hwnd, win32con.WM_KEYUP,   win32con.VK_ESCAPE, 0xC0010001)
                        self._log("자동 클릭: ESC 입력", "info")
                    else:
                        pyautogui.press('esc')
                        self._log("자동 클릭: ESC 입력 (pyautogui)", "info")
            except Exception as e:
                self._log(f"자동 클릭 실패: {e}", "warning")

    # ─── Helpers ─────────────────────────────────────────────
    def _refresh_hp_display(self):
        x, y  = self.config.get("hp_x"), self.config.get("hp_y")
        color = self.config.get("hp_color")
        self.v_hp_pos.set(f"({x}, {y})" if x is not None else "미설정")
        if color:
            c = tuple(color)
            if self.hp_color_box:
                self.hp_color_box.configure(bg="#{:02x}{:02x}{:02x}".format(*c))
            self.v_hp_color.set(f"RGB{c}")
        else:
            if self.hp_color_box:
                self.hp_color_box.configure(bg="#555")
            self.v_hp_color.set("미설정")

    def _log(self, msg, level="info"):
        ts   = time.strftime("%H:%M:%S")
        line = f"[{ts}] {msg}\n"
        self._log_buffer.append((line, level))
        def _do():
            self.log.configure(state="normal")
            self.log.insert("end", line, level)
            self.log.see("end")
            self.log.configure(state="disabled")
            if self._log_popup and self._log_popup.winfo_exists() and self._log_popup_text:
                self._log_popup_text.configure(state="normal")
                self._log_popup_text.insert("end", line, level)
                self._log_popup_text.see("end")
                self._log_popup_text.configure(state="disabled")
        self.root.after(0, _do)

    def _set_status(self, text, color="#888888"):
        self.root.after(0, lambda: (
            self.v_status.set(text),
            self.lbl_status.configure(foreground=color)
        ))

    @staticmethod
    def _get_window_titles():
        titles = []
        def _cb(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                t = win32gui.GetWindowText(hwnd).strip()
                if t and t not in titles:
                    titles.append(t)
        win32gui.EnumWindows(_cb, None)
        return sorted(titles)

    @staticmethod
    def _sf(v, d):
        try:    return float(v)
        except: return d

    @staticmethod
    def _si(v, d):
        try:    return int(float(v))
        except: return d

    def _read_hp_pct(self):
        cfg = self.config
        x   = cfg.get("hp_x")
        y   = cfg.get("hp_y")
        if x is None or y is None:
            return None
        hp_color = cfg.get("hp_color", [200, 50, 50])
        thr      = cfg.get("hp_threshold", 30)
        x2       = cfg.get("hp_x2")
        if x2 is not None:
            try:
                img  = ImageGrab.grab(bbox=(x, y - 2, x2, y + 3))
                pix  = img.load()
                w, h = img.size
                hr, hg, hb = hp_color
                match = sum(
                    1 for row in range(h) for col in range(w)
                    if ((pix[col, row][0]-hr)**2 +
                        (pix[col, row][1]-hg)**2 +
                        (pix[col, row][2]-hb)**2) ** 0.5 <= thr
                )
                return (match / (w * h)) * 100
            except Exception:
                return None
        else:
            try:
                color = self._get_pixel(x, y)
                dist  = self._color_dist(color, hp_color)
                return 0.0 if dist > thr else 100.0
            except Exception:
                return None

    @staticmethod
    def _get_pixel(x, y):
        try:    return pyautogui.pixel(x, y)[:3]
        except: return (0, 0, 0)

    @staticmethod
    def _color_dist(a, b):
        return ((a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2) ** 0.5

    def _force_focus(self, hwnd):
        try:
            cur = win32api.GetCurrentThreadId()
            tgt = win32process.GetWindowThreadProcessId(hwnd)[0]
            win32process.AttachThreadInput(cur, tgt, True)
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
            win32gui.BringWindowToTop(hwnd)
            win32process.AttachThreadInput(cur, tgt, False)
            time.sleep(0.3)
            return True
        except Exception:
            try:
                win32gui.SetForegroundWindow(hwnd)
                time.sleep(0.3)
                return True
            except Exception as e:
                self._log(f"[경고] 포커스 실패: {e}", "warning")
                return False

    def _post_enter(self, hwnd):
        VK = win32con.VK_RETURN
        win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, VK, 0x001C0001)
        time.sleep(0.05)
        win32api.PostMessage(hwnd, win32con.WM_KEYUP,   VK, 0xC01C0001)

    def _find_lineage_hwnd(self):
        kw    = self.config.get("lineage_title", "Lineage")
        found = []
        def _cb(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                if kw.lower() in win32gui.GetWindowText(hwnd).lower():
                    found.append(hwnd)
        win32gui.EnumWindows(_cb, None)
        return found[0] if found else None

    def _focus_lineage(self):
        hwnd = self._find_lineage_hwnd()
        if not hwnd:
            self._log("[경고] 리니지 창을 찾지 못했습니다.", "warning")
            return False
        return self._force_focus(hwnd)

    def _send_commands(self):
        raw      = self.cmd_text.get("1.0", "end-1c")
        commands = raw.split("\n")
        hwnd     = self._find_lineage_hwnd()
        if not hwnd:
            self._log("[경고] 리니지 창 없음", "warning")
            return
        if not self._force_focus(hwnd):
            return
        time.sleep(0.5)

        for i, cmd in enumerate(commands):
            if cmd.strip():
                self._post_enter(hwnd)
                time.sleep(0.6)
                pyperclip.copy(cmd)
                try:
                    kb.write(cmd, delay=0.05)
                except Exception:
                    kb.send("ctrl+v")
                time.sleep(0.3)
                self._post_enter(hwnd)
                self._log(f"  [{i+1}] '{cmd}' 전송", "success")
            else:
                self._post_enter(hwnd)
                self._log(f"  [{i+1}] 엔터 입력", "info")
            time.sleep(0.4)

        self._log(f"명령어 {len(commands)}개 완료", "success")

    # ─── Calibration ─────────────────────────────────────────
    def _start_calibration(self):
        self.btn_capture.configure(state="disabled")
        self._log("HP바 왼쪽 끝 캡처 - 5초 안에 HP바 시작점(빨간 픽셀)에 마우스를 올리세요", "warning")
        threading.Thread(target=self._calibrate_worker, daemon=True).start()

    def _calibrate_worker(self):
        for i in range(5, 0, -1):
            x, y  = pyautogui.position()
            color = self._get_pixel(x, y)
            self._log(f"  {i}초... 위치:({x},{y}) 색상:RGB{color}", "info")
            time.sleep(1)
        x, y  = pyautogui.position()
        color = self._get_pixel(x, y)
        self.config["hp_x"]     = x
        self.config["hp_y"]     = y
        self.config["hp_color"] = list(color)

        def _done():
            self._refresh_hp_display()
            self._save_config(show_msg=False)
            self._log(f"[왼쪽 끝] 설정 완료: ({x},{y}) 색상:RGB{color}", "success")
            self._log("이제 ② 오른쪽 끝도 캡처하면 영역 감지가 활성화됩니다.", "info")
            if self.btn_capture.winfo_exists():
                self.btn_capture.configure(state="normal")
        self.root.after(0, _done)

    def _start_calibration_right(self):
        self.btn_capture2.configure(state="disabled")
        self._log("HP바 오른쪽 끝 캡처 - 5초 안에 HP바 끝점에 마우스를 올리세요", "warning")
        threading.Thread(target=self._calibrate_right_worker, daemon=True).start()

    def _calibrate_right_worker(self):
        for i in range(5, 0, -1):
            x, y = pyautogui.position()
            self._log(f"  {i}초... 위치:({x},{y})", "info")
            time.sleep(1)
        x, y = pyautogui.position()
        self.config["hp_x2"] = x

        def _done():
            self._refresh_hp_display()
            self._save_config(show_msg=False)
            x1 = self.config.get("hp_x", 0)
            width = x - x1
            self._log(f"[오른쪽 끝] 설정 완료: ({x},{y})  범위: {width}px", "success")
            if hasattr(self, "v_hp_pos2") and self.v_hp_pos2:
                self.v_hp_pos2.set(f"({x},{y})")
            if self.btn_capture2.winfo_exists():
                self.btn_capture2.configure(state="normal")
        self.root.after(0, _done)

    def _start_calibration_death(self):
        self._log("죽음 화면 픽셀 캡처 - 캐릭터 죽은 직후 → 5초 안에 부활창/죽음 메시지 위에 마우스 올리기", "warning")
        threading.Thread(target=self._calibrate_death_worker, daemon=True).start()

    def _calibrate_death_worker(self):
        for i in range(5, 0, -1):
            x, y  = pyautogui.position()
            color = self._get_pixel(x, y)
            self._log(f"  {i}초... 위치:({x},{y}) 색상:RGB{color}", "info")
            time.sleep(1)
        x, y  = pyautogui.position()
        color = self._get_pixel(x, y)
        self.config["death_px_x"]     = x
        self.config["death_px_y"]     = y
        self.config["death_px_color"] = list(color)

        def _done():
            self.v_death_px_pos.set(f"({x},{y})")
            self.v_death_px_color.set(str(tuple(color)))
            self._save_config(show_msg=False)
            self._log(f"[죽음 픽셀] 설정 완료: ({x},{y}) 색상:RGB{color}", "success")
            self._log("설정 창에서 '보조 감지 활성화'를 체크하면 적용됩니다.", "info")
        self.root.after(0, _done)

    # ─── Monitoring ──────────────────────────────────────────
    def _start_monitoring(self):
        if not self.config.get("hp_x"):
            messagebox.showwarning("경고",
                "HP바 위치가 설정되지 않았습니다.\n[⚙ 감지 설정]에서 HP바 위치를 먼저 캡처하세요.")
            return
        self._sync_from_ui()
        self.stop_event.clear()
        self.monitoring = True
        threading.Thread(target=self._monitor_worker, daemon=True).start()
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self._set_status("모니터링 중...", "#1565c0")
        self._log("모니터링 시작", "success")

    def _stop_monitoring(self):
        self.stop_event.set()
        self.monitoring = False
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self._set_status("대기 중", "#888888")
        self._log("모니터링 중지", "warning")

    def _monitor_worker(self):
        cfg      = self.config
        x, y     = cfg["hp_x"], cfg["hp_y"]
        x2       = cfg.get("hp_x2")
        hp_color = tuple(cfg["hp_color"])
        thr      = cfg["color_threshold"]
        conf     = cfg["confirm_count"]
        delay    = cfg["death_delay"]
        cool     = cfg["cooldown_sec"]
        interval = cfg["check_interval"]
        min_pct  = cfg.get("hp_min_pct", 5)

        use_region  = (x2 is not None) and (x2 > x + 10)

        dpx_x       = cfg.get("death_px_x")
        dpx_y       = cfg.get("death_px_y")
        dpx_color   = tuple(cfg["death_px_color"]) if cfg.get("death_px_color") else None
        use_dpx     = cfg.get("death_px_enabled", False) and all([dpx_x, dpx_y, dpx_color])

        dead_count     = 0
        death_active   = False
        cooldown_until = 0.0

        def _scan_hp():
            """HP바 영역을 스캔하여 HP 비율(0~100)을 반환. 영역 미설정시 단일픽셀 방식."""
            if use_region:
                try:
                    img = ImageGrab.grab(bbox=(x, y - 2, x2, y + 3))
                    pixels = img.load()
                    w, h   = img.size
                    match  = 0
                    hr, hg, hb = hp_color
                    for row in range(h):
                        for col in range(w):
                            pr, pg, pb = pixels[col, row][:3]
                            dist = ((pr-hr)**2 + (pg-hg)**2 + (pb-hb)**2) ** 0.5
                            if dist <= thr:
                                match += 1
                    return (match / (w * h)) * 100
                except Exception:
                    return None
            else:
                color = self._get_pixel(x, y)
                dist  = self._color_dist(color, hp_color)
                return 0.0 if dist > thr else 100.0

        while not self.stop_event.is_set():
            now = time.time()
            if now < cooldown_until:
                self._set_status(f"쿨다운 {cooldown_until-now:.0f}초...", "#888888")
                time.sleep(0.5)
                continue

            hp_pct = _scan_hp()
            if hp_pct is None:
                time.sleep(interval)
                continue

            hp_dead  = hp_pct < min_pct

            dpx_dead = False
            if use_dpx:
                try:
                    c = self._get_pixel(dpx_x, dpx_y)
                    dpx_dead = self._color_dist(c, dpx_color) <= thr
                except Exception:
                    pass

            dead = hp_dead or dpx_dead

            if dead:
                dead_count += 1
                trigger_src = []
                if hp_dead:  trigger_src.append(f"HP {hp_pct:.1f}%")
                if dpx_dead: trigger_src.append("죽음화면 감지")
                self._set_status(
                    f"감지! {' + '.join(trigger_src)}  [{dead_count}/{conf}]",
                    "#e53935"
                )
            else:
                dead_count   = 0
                death_active = False
                if use_region:
                    bar = "█" * int(hp_pct / 5)
                    self._set_status(f"HP {hp_pct:.1f}%  {bar}", "#1565c0")
                else:
                    self._set_status("모니터링 중...", "#1565c0")

            if dead_count >= conf and not death_active:
                death_active = True
                trigger_src = []
                if hp_dead:  trigger_src.append(f"HP:{hp_pct:.1f}%")
                if dpx_dead: trigger_src.append("죽음화면")
                self._log(
                    f"죽음 감지! ({' + '.join(trigger_src)}) {delay:.0f}초 대기...",
                    "warning"
                )
                start = time.time()
                while time.time() - start < delay:
                    if self.stop_event.is_set():
                        return
                    rem = delay - (time.time() - start)
                    self._set_status(f"입력까지 {rem:.1f}초...", "#f57c00")
                    time.sleep(0.3)
                if not self.stop_event.is_set():
                    self._send_commands()
                    cooldown_until = time.time() + cool

            time.sleep(interval)


    # ─── Window close ────────────────────────────────────────
    def on_close(self):
        self._hide_to_tray()


def main():
    root = tk.Tk()
    app  = App(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    check_update_on_startup(root, APP_VERSION, APP_EXE_NAME)
    root.mainloop()


if __name__ == "__main__":
    main()
