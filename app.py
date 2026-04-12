import threading
import tkinter as tk
from tkinter import scrolledtext
import sys
import io
from features import FEATURES
from config_loader import load_config, get_config, save_config

# ── Feature metadata ───────────────────────────────────────────────────────
FEATURE_META = {
    "Auto Combat": {
        "icon": "⚔",
        "desc": "Automated combat with retry & AP regen",
    },
    "Auto Epic Quest": {
        "icon": "📜",
        "desc": "Entry shop loop + quest & raid progression",
    },
    "Skip Episodes": {
        "icon": "⏭",
        "desc": "Auto-skip normal & intimate episodes",
    },
}

# ── Colors ─────────────────────────────────────────────────────────────────
BG          = "#0F1117"
BG_PANEL    = "#181C25"
BG_CARD     = "#1E2330"
BG_CARD_SEL = "#252D40"
BG_INPUT    = "#151922"
BORDER      = "#2A3045"
BORDER_SEL  = "#4A6CF7"
ACCENT      = "#4A6CF7"
ACCENT_DIM  = "#1E2D6B"
TEXT        = "#E8ECF4"
TEXT_DIM    = "#6B7591"
TEXT_MUTED  = "#3D4560"
GREEN       = "#22C97A"
GREEN_DIM   = "#0D3D26"
RED         = "#E84040"
RED_DIM     = "#3D1010"
YELLOW      = "#F0B429"

# ── Settings schema ────────────────────────────────────────────────────────
# (config_path, label, type, min, max, step)
SUPPORT_OPTIONS = ["0", "1", "2", "3", "4", "5", "6", "7"]
SUPPORT_LABELS  = ["Skip", "Fire", "Water", "Wind", "Thunder", "Light", "Dark", "Phantom"]

SETTINGS = [
    {
        "section": "GENERAL",
        "fields": [
            ("general.poll_interval", "Poll interval (s)",  "float", 0.2, 5.0,  0.1),
            ("general.confidence",    "Match confidence",   "float", 0.5, 1.0,  0.05),
        ]
    },
    {
        "section": "AUTO COMBAT",
        "fields": [
            ("auto_combat.max_attempts",  "Max attempts",      "int",   1,  100, 1),
            ("auto_combat.max_retries",   "Retries per run",   "int",   0,  10,  1),
            ("auto_combat.combat_wait",   "Combat buffer (s)", "float", 0.5, 10.0, 0.5),
        ]
    },
    {
        "section": "COMBAT SELECTION",
        "fields": [
            ("auto_combat.team_section", "Team section (1–7)",  "int", 1, 7,  1),
            ("auto_combat.team_slot",    "Team slot (1–12)",    "int", 1, 12, 1),
        ],
        "dropdowns": [
            ("auto_combat.support_slot", "Support element", SUPPORT_OPTIONS, SUPPORT_LABELS),
        ]
    },
    {
        "section": "AUTO EPIC QUEST",
        "fields": [
            ("auto_epic_quest.max_quest_iterations",      "Max quest iterations",  "int", 1, 50, 1),
            ("auto_epic_quest.beginner_raid.max_retries", "Beginner raid retries", "int", 0, 10, 1),
            ("auto_epic_quest.standard_raid.max_retries", "Standard raid retries", "int", 0, 10, 1),
        ]
    },
]


# ── Config helpers ─────────────────────────────────────────────────────────
def _get_nested(d: dict, path: str):
    for k in path.split("."):
        d = d.get(k, {})
    return d

def _set_nested(d: dict, path: str, value):
    keys = path.split(".")
    for k in keys[:-1]:
        d = d.setdefault(k, {})
    d[keys[-1]] = value


# ── Log redirector ─────────────────────────────────────────────────────────
class LogRedirector(io.TextIOBase):
    def __init__(self, widget):
        self.widget = widget

    def write(self, text):
        if text.strip():
            try:
                self.widget.configure(state="normal")
                t = text.strip()
                tag = None
                if t.startswith("  ✔") or "win" in t.lower() or "finished" in t.lower():
                    tag = "green"
                elif t.startswith("  ✘") or "error" in t.lower() or "failed" in t.lower():
                    tag = "red"
                elif t.startswith("  →") or "started" in t.lower():
                    tag = "blue"
                elif "⚡" in t or "warn" in t.lower() or "stopping" in t.lower():
                    tag = "yellow"
                if tag:
                    self.widget.insert(tk.END, text + "\n", tag)
                else:
                    self.widget.insert(tk.END, text + "\n")
                self.widget.see(tk.END)
                self.widget.configure(state="disabled")
            except Exception:
                pass
        return len(text)


# ── Bot control ────────────────────────────────────────────────────────────
def start_bot():
    global bot_thread, is_running
    feat = selected_feat.get()
    if not feat or feat not in FEATURES:
        set_status("Select a feature first", YELLOW)
        return
    run_fn = FEATURES[feat]
    stop_event.clear()
    is_running = True
    btn_start.config(state="disabled", bg=ACCENT_DIM, fg=TEXT_MUTED)
    btn_stop.config(state="normal", bg=RED_DIM, fg=RED)
    set_status(f"Running  ·  {feat}", GREEN)
    dot_label.config(fg=GREEN)
    bot_thread = threading.Thread(target=lambda: _run_bot(run_fn), daemon=True)
    bot_thread.start()

def _run_bot(run_fn):
    global is_running
    try:
        run_fn(stop_event)
    except Exception as e:
        print(f"  ✘ Bot error: {e}")
    finally:
        is_running = False
        root.after(0, _on_bot_stopped)

def _on_bot_stopped():
    btn_start.config(state="normal", bg=ACCENT_DIM, fg=ACCENT)
    btn_stop.config(state="disabled", bg=BG_CARD, fg=TEXT_MUTED)
    set_status("Idle", TEXT_DIM)
    dot_label.config(fg=TEXT_MUTED)

def stop_bot():
    stop_event.set()
    print("  → Stop requested...")
    set_status("Stopping…", YELLOW)

def set_status(text, color):
    status_var.set(text)
    status_val.config(fg=color)

def clear_log():
    log_box.configure(state="normal")
    log_box.delete("1.0", tk.END)
    log_box.configure(state="disabled")


# ── Settings panel ─────────────────────────────────────────────────────────
settings_open  = False
settings_vars  = {}
settings_win   = None

def toggle_settings():
    global settings_open
    if settings_open:
        _close_settings()
    else:
        _open_settings()

def _open_settings():
    global settings_open, settings_win
    settings_open = True
    btn_settings.config(fg=ACCENT)

    settings_win = tk.Toplevel(root)
    settings_win.title("Settings")
    settings_win.resizable(False, False)
    settings_win.configure(bg=BG)
    settings_win.transient(root)
    settings_win.grab_set()
    settings_win.protocol("WM_DELETE_WINDOW", _close_settings)

    root.update_idletasks()
    x = root.winfo_x() + root.winfo_width() + 8
    y = root.winfo_y()
    settings_win.geometry(f"320x500+{x}+{y}")

    # Header
    hdr = tk.Frame(settings_win, bg=BG, padx=20, pady=14)
    hdr.pack(fill="x")
    tk.Label(hdr, text="SETTINGS", font=("Consolas", 11, "bold"),
             bg=BG, fg=TEXT).pack(side="left")
    tk.Button(hdr, text="✕", font=("Consolas", 10), bg=BG, fg=TEXT_MUTED,
              bd=0, cursor="hand2", activebackground=BG, activeforeground=RED,
              command=_close_settings).pack(side="right")
    tk.Frame(settings_win, bg=BORDER, height=1).pack(fill="x")

    # ── define _apply FIRST before any widget references it ───────────────
    save_lbl_var = tk.StringVar(value="")

    def _apply():
        cfg = get_config()
        errors = []
        for path, (var, typ, mn, mx) in settings_vars.items():
            try:
                raw = float(var.get())
                val = int(raw) if typ == "int" else round(raw, 4)
                if not (mn <= val <= mx):
                    errors.append(f"{path.split('.')[-1]}: must be {mn}–{mx}")
                    continue
                _set_nested(cfg, path, val)
            except ValueError:
                errors.append(f"{path.split('.')[-1]}: invalid")

        if errors:
            save_lbl_var.set("✘ " + errors[0])
            settings_win.after(3000, lambda: save_lbl_var.set(""))
            return

        save_config()
        save_lbl_var.set("✔ Saved")
        settings_win.after(800, _close_settings)  
        print("  → Settings saved.")

    # ── Footer — packed BEFORE canvas so side="bottom" works ──────────────
    tk.Frame(settings_win, bg=BORDER, height=1).pack(fill="x", side="bottom")
    footer = tk.Frame(settings_win, bg=BG, padx=20, pady=12)
    footer.pack(fill="x", side="bottom")
    tk.Label(footer, textvariable=save_lbl_var, font=("Consolas", 8),
             bg=BG, fg=GREEN).pack(side="left")
    tk.Button(footer, text="APPLY", font=("Consolas", 9, "bold"),
              bg=ACCENT_DIM, fg=ACCENT, activebackground=ACCENT,
              activeforeground=TEXT, bd=0, padx=16, pady=8,
              cursor="hand2", command=_apply).pack(side="right")

    # ── Canvas — packed AFTER footer ──────────────────────────────────────
    canvas = tk.Canvas(settings_win, bg=BG, highlightthickness=0)
    vsb = tk.Scrollbar(settings_win, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=vsb.set)
    vsb.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)

    body = tk.Frame(canvas, bg=BG, padx=20, pady=8)
    cw = canvas.create_window((0, 0), window=body, anchor="nw")

    body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda e: canvas.itemconfig(cw, width=e.width))

    def _on_mousewheel(e):
        canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
    canvas.bind_all("<MouseWheel>", _on_mousewheel)

    # ── Build fields ───────────────────────────────────────────────────────
# Build fields
    cfg = get_config()
    for section_data in SETTINGS:
        tk.Label(body, text=section_data["section"], font=("Consolas", 7),
                 bg=BG, fg=TEXT_MUTED).pack(anchor="w", pady=(14, 4))
        tk.Frame(body, bg=BORDER, height=1).pack(fill="x", pady=(0, 6))

        # ── Stepper fields ─────────────────────────────────────────────────
        for path, label, typ, mn, mx, step in section_data.get("fields", []):
            current = _get_nested(cfg, path)
            var = tk.StringVar(value=str(current))
            settings_vars[path] = (var, typ, mn, mx)

            row = tk.Frame(body, bg=BG)
            row.pack(fill="x", pady=5)
            tk.Label(row, text=label, font=("Consolas", 8),
                     bg=BG, fg=TEXT_DIM, anchor="w").pack(side="left", fill="x", expand=True)

            ctrl = tk.Frame(row, bg=BG)
            ctrl.pack(side="right")

            def _make_dec(v=var, t=typ, s=step, lo=mn):
                def dec():
                    try:
                        val = round(float(v.get()) - s, 4)
                        v.set(str(int(max(lo, val)) if t == "int" else max(lo, val)))
                    except ValueError:
                        pass
                return dec

            def _make_inc(v=var, t=typ, s=step, hi=mx):
                def inc():
                    try:
                        val = round(float(v.get()) + s, 4)
                        v.set(str(int(min(hi, val)) if t == "int" else min(hi, val)))
                    except ValueError:
                        pass
                return inc

            tk.Button(ctrl, text="−", font=("Consolas", 9), bg=BG_CARD, fg=TEXT,
                      bd=0, padx=8, pady=2, cursor="hand2",
                      activebackground=BORDER, command=_make_dec()).pack(side="left")
            tk.Entry(ctrl, textvariable=var, font=("Consolas", 9),
                     bg=BG_INPUT, fg=TEXT, insertbackground=ACCENT,
                     relief="flat", width=6, justify="center",
                     highlightthickness=1, highlightbackground=BORDER,
                     highlightcolor=ACCENT).pack(side="left", padx=2)
            tk.Button(ctrl, text="+", font=("Consolas", 9), bg=BG_CARD, fg=TEXT,
                      bd=0, padx=8, pady=2, cursor="hand2",
                      activebackground=BORDER, command=_make_inc()).pack(side="left")

        # ── Dropdown fields ────────────────────────────────────────────────
        for path, label, options, option_labels in section_data.get("dropdowns", []):
            current = str(_get_nested(cfg, path))
            var = tk.StringVar(value=current)
            settings_vars[path] = (var, "int", 0, len(options) - 1)

            row = tk.Frame(body, bg=BG)
            row.pack(fill="x", pady=5)
            tk.Label(row, text=label, font=("Consolas", 8),
                     bg=BG, fg=TEXT_DIM, anchor="w").pack(side="left", fill="x", expand=True)

            # Display label (e.g. "Fire") but store value (e.g. "2")
            display_var = tk.StringVar()
            idx = options.index(current) if current in options else 0
            display_var.set(option_labels[idx])

            def _make_option_select(dv, sv, opts, lbls):
                def on_select(chosen_label):
                    i = lbls.index(chosen_label)
                    sv.set(opts[i])
                    dv.set(chosen_label)
                return on_select

            om = tk.OptionMenu(row, display_var, *option_labels,
                               command=_make_option_select(display_var, var, options, option_labels))
            om.config(font=("Consolas", 8), bg=BG_CARD, fg=TEXT,
                      activebackground=BG_CARD_SEL, activeforeground=TEXT,
                      highlightthickness=0, bd=0, width=10, anchor="w",
                      indicatoron=True, relief="flat")
            om["menu"].config(font=("Consolas", 8), bg=BG_CARD, fg=TEXT,
                              activebackground=ACCENT_DIM, activeforeground=TEXT)
            om.pack(side="right")

def _close_settings():
    global settings_open, settings_win
    settings_open = False
    btn_settings.config(fg=TEXT_DIM)
    settings_vars.clear()
    if settings_win:
        settings_win.destroy()
        settings_win = None


# ── Feature cards ──────────────────────────────────────────────────────────
card_widgets = {}

def build_feature_cards(parent):
    features = list(FEATURES.keys())
    cols = 2
    for i, name in enumerate(features):
        meta = FEATURE_META.get(name, {"icon": "◆", "desc": ""})
        r, c = divmod(i, cols)

        card = tk.Frame(parent, bg=BG_CARD, cursor="hand2",
                        highlightthickness=1, highlightbackground=BORDER)
        card.grid(row=r, column=c, padx=5, pady=5, sticky="nsew")
        parent.columnconfigure(c, weight=1)

        inner = tk.Frame(card, bg=BG_CARD, padx=12, pady=10)
        inner.pack(fill="both", expand=True)

        icon_lbl = tk.Label(inner, text=meta["icon"], font=("Segoe UI Emoji", 18),
                            bg=BG_CARD, fg=ACCENT)
        icon_lbl.pack(anchor="w")

        name_lbl = tk.Label(inner, text=name, font=("Consolas", 10, "bold"),
                            bg=BG_CARD, fg=TEXT, anchor="w")
        name_lbl.pack(anchor="w", pady=(4, 0))

        desc_lbl = tk.Label(inner, text=meta["desc"], font=("Consolas", 8),
                            bg=BG_CARD, fg=TEXT_DIM, anchor="w",
                            wraplength=160, justify="left")
        desc_lbl.pack(anchor="w", pady=(2, 0))

        all_w = [card, inner, icon_lbl, name_lbl, desc_lbl]
        card_widgets[name] = (card, inner, all_w)

        def _bind(n, cd, aw):
            def on_enter(e):
                if selected_feat.get() != n:
                    cd.config(highlightbackground=ACCENT_DIM)
            def on_leave(e):
                if selected_feat.get() != n:
                    cd.config(highlightbackground=BORDER)
            def on_click(e):
                select_feature(n)
            for w in aw:
                w.bind("<Enter>", on_enter)
                w.bind("<Leave>", on_leave)
                w.bind("<Button-1>", on_click)

        _bind(name, card, all_w)

    if features:
        select_feature(features[0])

def select_feature(name):
    for n, (card, inner, widgets) in card_widgets.items():
        bg = BG_CARD_SEL if n == name else BG_CARD
        hl = BORDER_SEL  if n == name else BORDER
        card.config(bg=bg, highlightbackground=hl)
        inner.config(bg=bg)
        for w in widgets:
            w.config(bg=bg)
    selected_feat.set(name)


# ── Root ───────────────────────────────────────────────────────────────────
root = tk.Tk()
root.title("KHPBot")
root.resizable(False, False)
root.geometry("520x680")
root.configure(bg=BG)

# State (must be after root)
bot_thread    = None
stop_event    = threading.Event()
selected_feat = tk.StringVar()
is_running    = False

# ── Header ─────────────────────────────────────────────────────────────────
header = tk.Frame(root, bg=BG, padx=20, pady=14)
header.pack(fill="x")

left_hdr = tk.Frame(header, bg=BG)
left_hdr.pack(side="left")

dot_label = tk.Label(left_hdr, text="●", font=("Consolas", 10), bg=BG, fg=TEXT_MUTED)
dot_label.pack(side="left", padx=(0, 8))
tk.Label(left_hdr, text="KHPBot", font=("Consolas", 16, "bold"),
         bg=BG, fg=TEXT).pack(side="left")
tk.Label(left_hdr, text="v1.0", font=("Consolas", 9), bg=BG, fg=TEXT_MUTED).pack(
    side="left", padx=(8, 0), pady=(4, 0))

btn_settings = tk.Button(header, text="⚙", font=("Consolas", 13),
                         bg=BG, fg=TEXT_DIM, bd=0, cursor="hand2",
                         activebackground=BG, activeforeground=ACCENT,
                         command=toggle_settings)
btn_settings.pack(side="right")

status_row = tk.Frame(header, bg=BG)
status_row.pack(side="left", padx=(20, 0))
tk.Label(status_row, text="STATUS", font=("Consolas", 7),
         bg=BG, fg=TEXT_MUTED).pack(side="left")
status_var = tk.StringVar(value="Idle")
status_val = tk.Label(status_row, textvariable=status_var,
                      font=("Consolas", 9, "bold"), bg=BG, fg=TEXT_DIM)
status_val.pack(side="left", padx=(8, 0))

tk.Frame(root, bg=BORDER, height=1).pack(fill="x")

# ── Content ────────────────────────────────────────────────────────────────
content = tk.Frame(root, bg=BG, padx=20, pady=16)
content.pack(fill="both", expand=True)

tk.Label(content, text="FEATURE", font=("Consolas", 7),
         bg=BG, fg=TEXT_MUTED).pack(anchor="w", pady=(0, 8))

cards_frame = tk.Frame(content, bg=BG)
cards_frame.pack(fill="x")
build_feature_cards(cards_frame)

tk.Frame(content, bg=BORDER, height=1).pack(fill="x", pady=16)

tk.Label(content, text="CONTROLS", font=("Consolas", 7),
         bg=BG, fg=TEXT_MUTED).pack(anchor="w", pady=(0, 8))

btn_row = tk.Frame(content, bg=BG)
btn_row.pack(fill="x")

btn_start = tk.Button(btn_row, text="▶  START", font=("Consolas", 10, "bold"),
                      bg=ACCENT_DIM, fg=ACCENT, activebackground=ACCENT,
                      activeforeground=TEXT, bd=0, padx=20, pady=10,
                      cursor="hand2", command=start_bot)
btn_start.pack(side="left", padx=(0, 8))

btn_stop = tk.Button(btn_row, text="■  STOP", font=("Consolas", 10, "bold"),
                     bg=BG_CARD, fg=TEXT_MUTED, activebackground=RED_DIM,
                     activeforeground=RED, bd=0, padx=20, pady=10,
                     cursor="hand2", state="disabled", command=stop_bot)
btn_stop.pack(side="left")

tk.Frame(content, bg=BORDER, height=1).pack(fill="x", pady=16)

# Log
log_hdr = tk.Frame(content, bg=BG)
log_hdr.pack(fill="x", pady=(0, 6))
tk.Label(log_hdr, text="LOG", font=("Consolas", 7),
         bg=BG, fg=TEXT_MUTED).pack(side="left")
tk.Button(log_hdr, text="CLEAR", font=("Consolas", 7),
          bg=BG, fg=TEXT_MUTED, activebackground=BG_CARD,
          activeforeground=TEXT, bd=0, cursor="hand2",
          command=clear_log).pack(side="right")

log_box = scrolledtext.ScrolledText(
    content, state="disabled", height=12,
    font=("Consolas", 8), wrap="word",
    bg=BG_PANEL, fg=TEXT, insertbackground=ACCENT,
    selectbackground=ACCENT_DIM, relief="flat", borderwidth=0
)
log_box.pack(fill="both", expand=True)
log_box.tag_config("green",  foreground=GREEN)
log_box.tag_config("red",    foreground=RED)
log_box.tag_config("blue",   foreground=ACCENT)
log_box.tag_config("yellow", foreground=YELLOW)

sys.stdout = LogRedirector(log_box)
root.mainloop()