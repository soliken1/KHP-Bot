import threading
import tkinter as tk
from tkinter import scrolledtext, ttk
import sys
import io
import main  # your existing main.py

# --- Redirect print() to the UI log ---
class LogRedirector(io.TextIOBase):
    def __init__(self, widget):
        self.widget = widget

    def write(self, text):
        if text.strip():
            self.widget.configure(state="normal")
            self.widget.insert(tk.END, text + "\n")
            self.widget.see(tk.END)
            self.widget.configure(state="disabled")
        return len(text)

# --- Bot thread control ---
bot_thread = None
stop_event = threading.Event()

def start_bot():
    global bot_thread, stop_event

    # Push config values into main's config
    import config
    config.SCAN_TIMEOUT = int(timeout_var.get())
    config.MAX_RETRIES  = int(retries_var.get())
    config.CLICK_DELAY  = float(delay_var.get())

    stop_event.clear()
    btn_start.config(state="disabled")
    btn_stop.config(state="normal")
    status_var.set("Running")
    status_label.config(fg="#1D9E75")

    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

def run_bot():
    try:
        main.run(stop_event)  
    except Exception as e:
        print(f"  ✘ Bot error: {e}")
    finally:
        btn_start.config(state="normal")
        btn_stop.config(state="disabled")
        status_var.set("Stopped")
        status_label.config(fg="#E24B4A")

def stop_bot():
    stop_event.set()
    print("  → Stop requested...")

def clear_log():
    log_box.configure(state="normal")
    log_box.delete("1.0", tk.END)
    log_box.configure(state="disabled")

# --- Build UI ---
root = tk.Tk()
root.title("Game Bot")
root.resizable(False, False)
root.geometry("420x560")

frame = tk.Frame(root, padx=16, pady=16)
frame.pack(fill="both", expand=True)

# Status
status_row = tk.Frame(frame)
status_row.pack(fill="x", pady=(0, 12))
tk.Label(status_row, text="Status:", font=("Arial", 11)).pack(side="left")
status_var = tk.StringVar(value="Idle")
status_label = tk.Label(status_row, textvariable=status_var, font=("Arial", 11, "bold"), fg="#888780")
status_label.pack(side="left", padx=6)

# Config inputs
cfg_frame = tk.LabelFrame(frame, text="Config", padx=10, pady=8)
cfg_frame.pack(fill="x", pady=(0, 12))

timeout_var = tk.StringVar(value="10")
retries_var = tk.StringVar(value="5")
delay_var   = tk.StringVar(value="0.5")

def cfg_row(parent, label, var):
    row = tk.Frame(parent)
    row.pack(fill="x", pady=3)
    tk.Label(row, text=label, width=18, anchor="w").pack(side="left")
    tk.Entry(row, textvariable=var, width=8).pack(side="left")

cfg_row(cfg_frame, "Scan timeout (s)",  timeout_var)
cfg_row(cfg_frame, "Max retries",        retries_var)
cfg_row(cfg_frame, "Click delay (s)",    delay_var)

# Buttons
btn_frame = tk.Frame(frame)
btn_frame.pack(fill="x", pady=(0, 12))
btn_start = tk.Button(btn_frame, text="Start", width=18, bg="#E1F5EE", fg="#0F6E56", command=start_bot)
btn_start.pack(side="left", padx=(0, 8))
btn_stop  = tk.Button(btn_frame, text="Stop",  width=18, bg="#FAECE7", fg="#993C1D", command=stop_bot, state="disabled")
btn_stop.pack(side="left")

# Log
log_frame = tk.LabelFrame(frame, text="Log", padx=6, pady=6)
log_frame.pack(fill="both", expand=True)
log_box = scrolledtext.ScrolledText(log_frame, state="disabled", height=16, font=("Courier", 9), wrap="word")
log_box.pack(fill="both", expand=True)
tk.Button(log_frame, text="Clear", command=clear_log).pack(anchor="e", pady=(4, 0))

# Redirect print to log
sys.stdout = LogRedirector(log_box)

root.mainloop()