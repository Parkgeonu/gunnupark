import tkinter as tk
from tkinter import ttk, messagebox
import random


class ListLadderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("사다리 게임")
        self.root.geometry("520x780")
        self.root.resizable(False, True)

        self.names_entries = []
        self.prize_entries = []

        self._build_ui()

    # ─── UI ──────────────────────────────────────────────────
    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")

        # ── 1. 참가자 설정 ──
        sf = tk.LabelFrame(self.root, text="1. 참가자 설정", padx=10, pady=8,
                           font=("맑은 고딕", 9, "bold"))
        sf.pack(pady=(10, 4), padx=10, fill="x")

        r = tk.Frame(sf)
        r.pack(fill="x")
        tk.Label(r, text="참가 인원:").pack(side="left")
        self.count_var = tk.StringVar(value="2")
        tk.Entry(r, textvariable=self.count_var, width=6).pack(side="left", padx=5)
        tk.Button(r, text="입력창 생성", command=self._generate_entries,
                  bg="#d0d0d0", relief="groove").pack(side="left", padx=4)
        tk.Button(r, text="+ 참가자 추가", command=self._add_one_entry,
                  bg="#b3e5fc", relief="groove").pack(side="left", padx=4)
        tk.Button(r, text="- 참가자 제거", command=self._remove_one_entry,
                  bg="#ffcdd2", relief="groove").pack(side="left", padx=4)

        # ── 2. 참가자 이름 입력 (스크롤) ──
        nf = tk.LabelFrame(self.root, text="2. 참가자 이름 입력", padx=8, pady=6,
                           font=("맑은 고딕", 9, "bold"))
        nf.pack(pady=4, padx=10, fill="both", expand=True)

        self.name_canvas = tk.Canvas(nf, height=160, highlightthickness=0)
        n_sb = tk.Scrollbar(nf, orient="vertical", command=self.name_canvas.yview)
        self.name_inner = tk.Frame(self.name_canvas)
        self.name_inner.bind(
            "<Configure>",
            lambda e: self.name_canvas.configure(
                scrollregion=self.name_canvas.bbox("all")))
        self.name_canvas.create_window((0, 0), window=self.name_inner, anchor="nw")
        self.name_canvas.configure(yscrollcommand=n_sb.set)
        self.name_canvas.pack(side="left", fill="both", expand=True)
        n_sb.pack(side="right", fill="y")

        # ── 3. 당첨 상품 목록 ──
        pf = tk.LabelFrame(self.root, text="3. 당첨 상품 목록", padx=8, pady=6,
                           font=("맑은 고딕", 9, "bold"))
        pf.pack(pady=4, padx=10, fill="x")

        self.prize_canvas = tk.Canvas(pf, height=110, highlightthickness=0)
        p_sb = tk.Scrollbar(pf, orient="vertical", command=self.prize_canvas.yview)
        self.prize_inner = tk.Frame(self.prize_canvas)
        self.prize_inner.bind(
            "<Configure>",
            lambda e: self.prize_canvas.configure(
                scrollregion=self.prize_canvas.bbox("all")))
        self.prize_canvas.create_window((0, 0), window=self.prize_inner, anchor="nw")
        self.prize_canvas.configure(yscrollcommand=p_sb.set)
        self.prize_canvas.pack(side="left", fill="both", expand=True)
        p_sb.pack(side="right", fill="y")

        # 기본 상품 1개
        self._add_prize_row("당첨")

        pb = tk.Frame(pf)
        pb.pack(fill="x", pady=(4, 0))
        tk.Button(pb, text="+ 상품 추가", command=lambda: self._add_prize_row(),
                  bg="#c8e6c9", relief="groove").pack(side="left")
        tk.Label(pb, text="  ※ 상품 수 < 참가자 수",
                 fg="gray", font=("맑은 고딕", 8)).pack(side="left")

        # ── 4. 실행 버튼 ──
        tk.Button(self.root, text="🎲  결과 확인 (전체 공개)",
                  command=self._run_ladder,
                  bg="#ff9800", fg="white",
                  font=("맑은 고딕", 11, "bold"), height=2,
                  relief="groove"
                  ).pack(pady=8, fill="x", padx=10)

        # ── 5. 결과 ──
        rf = tk.LabelFrame(self.root, text="4. 최종 결과", padx=8, pady=6,
                           font=("맑은 고딕", 9, "bold"))
        rf.pack(pady=4, padx=10, fill="both", expand=True)

        self.result_text = tk.Text(rf, height=10, state="disabled",
                                   font=("맑은 고딕", 10))
        res_sb = tk.Scrollbar(rf, orient="vertical", command=self.result_text.yview)
        self.result_text.configure(yscrollcommand=res_sb.set)
        self.result_text.pack(side="left", fill="both", expand=True)
        res_sb.pack(side="right", fill="y")

        self.result_text.tag_configure(
            "winner", foreground="#c62828",
            font=("맑은 고딕", 10, "bold"))
        self.result_text.tag_configure(
            "header", foreground="#1565c0",
            font=("맑은 고딕", 10, "bold"))

    # ─── 참가자 관리 ─────────────────────────────────────────
    def _generate_entries(self):
        for w in self.name_inner.winfo_children():
            w.destroy()
        self.names_entries.clear()
        try:
            count = int(self.count_var.get())
            if count < 2:
                raise ValueError
        except ValueError:
            messagebox.showerror("오류", "2명 이상의 숫자를 입력해주세요.")
            return
        for i in range(count):
            self._add_name_row()

    def _add_one_entry(self):
        self._add_name_row()

    def _remove_one_entry(self):
        if not self.names_entries:
            return
        last_entry = self.names_entries[-1]
        row = last_entry.master
        self.names_entries.remove(last_entry)
        row.destroy()
        self._renumber(self.name_inner, self.names_entries, "번:")

    def _add_name_row(self, default=""):
        row = tk.Frame(self.name_inner)
        row.pack(fill="x", pady=1, padx=2)

        idx  = len(self.names_entries) + 1
        lbl  = tk.Label(row, text=f"{idx}번:", width=5, anchor="e")
        lbl.pack(side="left")
        ent  = tk.Entry(row, width=22)
        ent.insert(0, default)
        ent.pack(side="left", padx=4)

        def remove():
            self.names_entries.remove(ent)
            row.destroy()
            self._renumber(self.name_inner, self.names_entries, "번:")
        tk.Button(row, text="✕", command=remove,
                  bg="#ffcdd2", relief="groove", width=2).pack(side="left")
        self.names_entries.append(ent)

    # ─── 상품 관리 ───────────────────────────────────────────
    def _add_prize_row(self, default=""):
        row = tk.Frame(self.prize_inner)
        row.pack(fill="x", pady=1, padx=2)

        idx = len(self.prize_entries) + 1
        tk.Label(row, text=f"상품 {idx}:", width=7, anchor="e").pack(side="left")
        ent = tk.Entry(row, width=22)
        ent.insert(0, default)
        ent.pack(side="left", padx=4)

        def remove():
            self.prize_entries.remove(ent)
            row.destroy()
            self._renumber(self.prize_inner, self.prize_entries, ":", prefix="상품 ")
        tk.Button(row, text="✕", command=remove,
                  bg="#ffcdd2", relief="groove", width=2).pack(side="left")
        self.prize_entries.append(ent)

    # ─── 번호 재정렬 ─────────────────────────────────────────
    def _renumber(self, container, entry_list, suffix, prefix=""):
        for i, child in enumerate(container.winfo_children(), 1):
            labels = [w for w in child.winfo_children()
                      if isinstance(w, tk.Label)]
            if labels:
                labels[0].config(text=f"{prefix}{i}{suffix}")

    # ─── 사다리 실행 ─────────────────────────────────────────
    def _run_ladder(self):
        names  = [e.get().strip() for e in self.names_entries if e.get().strip()]
        prizes = [e.get().strip() for e in self.prize_entries if e.get().strip()]

        if len(names) < 2:
            messagebox.showerror("오류", "참가자를 2명 이상 입력해주세요.")
            return
        if not prizes:
            messagebox.showerror("오류", "상품을 1개 이상 입력해주세요.")
            return
        if len(prizes) >= len(names):
            messagebox.showerror(
                "오류",
                f"상품 수({len(prizes)})가 참가자 수({len(names)}) 이상입니다.\n"
                f"상품은 참가자보다 적어야 합니다.")
            return

        # 셔플 및 결과 배정
        shuffled = random.sample(names, len(names))
        pool     = prizes + ["꽝"] * (len(shuffled) - len(prizes))
        random.shuffle(pool)
        final    = dict(zip(shuffled, pool))

        # 파일 저장
        try:
            with open("ladder_results.txt", "w", encoding="utf-8") as f:
                f.write("=== 사다리 전체 결과 ===\n")
                for n, r in final.items():
                    f.write(f"{n} : {r}\n")
        except Exception:
            pass

        # 화면 출력
        self.result_text.config(state="normal")
        self.result_text.delete("1.0", tk.END)

        winners = [(n, r) for n, r in final.items() if r != "꽝"]
        losers  = [(n, r) for n, r in final.items() if r == "꽝"]

        self.result_text.insert(tk.END, f"🎉 당첨자  ({len(winners)}명) 🎉\n", "header")
        for name, res in winners:
            self.result_text.insert(tk.END, f"  ▶ {name}  →  {res}\n", "winner")

        self.result_text.insert(tk.END, f"\n--- 꽝  ({len(losers)}명) ---\n", "header")
        for name, res in losers:
            self.result_text.insert(tk.END, f"  {name}  →  {res}\n")

        self.result_text.insert(tk.END, f"\n=== 전체 명단 ({len(final)}명) ===\n", "header")
        for name, res in final.items():
            tag = "winner" if res != "꽝" else ""
            self.result_text.insert(tk.END, f"  {name}  :  {res}\n", tag)

        self.result_text.config(state="disabled")
        if winners:
            winner_lines = "\n".join([f"  {name}  →  당첨" for name, res in winners])
            messagebox.showinfo("당첨 결과", f"당첨자 {len(winners)}명\n\n{winner_lines}\n\n꽝 {len(losers)}명")


if __name__ == "__main__":
    root = tk.Tk()
    app  = ListLadderGUI(root)
    root.mainloop()
