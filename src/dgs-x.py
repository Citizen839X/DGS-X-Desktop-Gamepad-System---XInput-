# =================================================================
# DGS-X - 1.2
# =================================================================
# Copyright (C) 2026 Carlo Sitaro
# Licensed under GNU GPLv3
# =================================================================

import evdev
from evdev import UInput, ecodes as e
import time
import threading
import os
import socket
import sys
import json
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageDraw
import pystray
import subprocess

CONFIG_DIR = os.path.expanduser("~/.config/dgs-x")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

settings = {
    "mouse_sensitivity": 25,
    "scroll_sensitivity": 0.5,
    "invert_left_stick_y": False,
    "deadzone": 2000,
    "accel_curve": 1.8,
    "ultra_precision_mode": False
}

def load_settings():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                settings.update(json.load(f))
        except: pass

def save_settings():
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            json.dump(settings, f, indent=4)
    except: pass

state = {
    "rx": 0, "ry": 0, "lx": 0, "ly": 0,
    "active": True, "scroll_acc": 0.0,
    "lt_clicked": False, "rt_clicked": False
}

# --- FIXED: SINGLE INSTANCE & REMOTE WAKEUP ---
def manage_instance(gui_ptr):
    lock_port = 65432
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('127.0.0.1', lock_port))
        s.listen(1)
        def listen():
            while True:
                conn, _ = s.accept()
                gui_ptr.root.after(0, gui_ptr.show)
                conn.close()
        threading.Thread(target=listen, daemon=True).start()
        return s
    except socket.error:
        try:
            wake = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            wake.connect(('127.0.0.1', lock_port))
            wake.close()
        except: pass
        sys.exit(0)

# --- CORE DRIVER LOGIC (VERBATIM) ---
def apply_accel(value):
    if abs(value) < settings["deadzone"]: return 0
    norm = (abs(value) - settings["deadzone"]) / (32767 - settings["deadzone"])
    speed = (norm ** settings["accel_curve"]) * settings["mouse_sensitivity"]
    return int(speed if value > 0 else -speed)

def move_loop(ui):
    while True:
        if state["active"]:
            dx, dy = apply_accel(state["rx"]), apply_accel(state["ry"])
            if dx != 0 or dy != 0:
                ui.write(e.EV_REL, e.REL_X, dx)
                ui.write(e.EV_REL, e.REL_Y, dy)
            if abs(state["ly"]) > settings["deadzone"]:
                norm = (abs(state["ly"]) - settings["deadzone"]) / (32767 - settings["deadzone"])
                direction = -1 if state["ly"] < 0 else 1
                if settings["invert_left_stick_y"]: direction *= -1
                scroll_speed = (norm ** 2.0) * settings["scroll_sensitivity"] * direction
                state["scroll_acc"] += scroll_speed
                if abs(state["scroll_acc"]) >= 1.0:
                    steps = int(state["scroll_acc"])
                    ui.write(e.EV_REL, e.REL_WHEEL, steps)
                    state["scroll_acc"] -= steps
            ui.syn()
        time.sleep(0.01)

def input_listener(device, ui):
    start_pressed_time = 0
    try:
        for event in device.read_loop():
            if event.type == e.EV_KEY and event.code == e.BTN_START:
                if event.value == 1:
                    start_pressed_time = time.time()
                elif event.value == 0:
                    if start_pressed_time > 0 and (time.time() - start_pressed_time) >= 3.0:
                        state["active"] = not state["active"]
                        msg = "ENABLED" if state["active"] else "LOCKED"
                        subprocess.Popen(['notify-send', 'DGS-X', f"Status: {msg}"])
                    start_pressed_time = 0
                continue

            if not state["active"]:
                continue

            if event.type == e.EV_ABS:
                if event.code == e.ABS_RX: state["rx"] = event.value
                elif event.code == e.ABS_RY: state["ry"] = event.value
                elif event.code == e.ABS_Y: state["ly"] = event.value
                elif event.code in [e.ABS_Z, e.ABS_BRAKE]:
                    is_p = event.value > 500
                    if is_p != state["lt_clicked"]:
                        ui.write(e.EV_KEY, e.BTN_RIGHT, 1 if is_p else 0)
                        state["lt_clicked"] = is_p
                        ui.syn()
                elif event.code in [e.ABS_RZ, e.ABS_GAS]:
                    is_p = event.value > 500
                    if is_p != state["rt_clicked"]:
                        ui.write(e.EV_KEY, e.BTN_LEFT, 1 if is_p else 0)
                        state["rt_clicked"] = is_p
                        ui.syn()
    except:
        pass

def get_device():
    try:
        devices = [evdev.InputDevice(p) for p in evdev.list_devices()]
        for d in devices:
            if any(x in d.name.lower() for x in ["xbox", "pdp", "x-box", "generic", "controller", "gamepad"]):
                return d
    except: pass
    return None

class DGSXGui:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("DGS-X v1.2 - Control Panel")
        self.root.geometry("480x620")
        self.root.withdraw()
        self.root.protocol("WM_DELETE_WINDOW", self.hide)

        # STYLE ENGINE
        style = ttk.Style()
        style.theme_use('clam')
        
        # Check for Dark Mode (simple background luminance check)
        bg_color = self.root.cget("background")
        is_dark = True # Default to Dark for XFCE/Gaming setups
        try:
            # Attempt to detect if system is dark based on window background
            rgb = self.root.winfo_rgb(bg_color)
            if (rgb[0] + rgb[1] + rgb[2]) / 3 > 32767: is_dark = False
        except: pass

        # Xbox Green & Palette
        xbox_green = "#107C10"
        bg_main = "#1e1e1e" if is_dark else "#f0f0f0"
        fg_main = "#ffffff" if is_dark else "#000000"
        
        self.root.configure(bg=bg_main)
        
        # Configure Styles
        style.configure("TFrame", background=bg_main)
        style.configure("TLabel", background=bg_main, foreground=fg_main)
        style.configure("TCheckbutton", background=bg_main, foreground=fg_main, font=('Helvetica', 10))
        
        # Accent: Xbox Green for Scale and Buttons
        style.configure("Horizontal.TScale", troughcolor="#333333" if is_dark else "#cccccc", background=bg_main)
        style.map("TCheckbutton", 
                  indicatorcolor=[('selected', xbox_green), ('!selected', '#555555')],
                  background=[('active', bg_main)])
        
        style.configure("TButton", padding=10, font=('Helvetica', 10, 'bold'))
        style.map("TButton", 
                  background=[('active', xbox_green), ('!active', '#333333' if is_dark else "#dddddd")],
                  foreground=[('active', '#ffffff'), ('!active', fg_main)])

        # GUI Layout
        f = ttk.Frame(self.root, padding="20")
        f.pack(fill="both", expand=True)

        self.start_v = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text="Load DGS-X on startup", variable=self.start_v).pack(anchor="w", pady=(0, 20))

        ttk.Label(f, text="Left Stick: Scrolling Sensitivity", font=('Helvetica', 11, 'bold')).pack(anchor="w")
        self.sc_s = ttk.Scale(f, from_=1, to=100, orient="horizontal")
        self.sc_s.set(int(settings["scroll_sensitivity"] * 100))
        self.sc_s.pack(fill="x", pady=(5, 5))

        self.u_v = tk.BooleanVar(value=settings.get("ultra_precision_mode", False))
        ttk.Checkbutton(f, text="Enable Ultra-Precision Mode", variable=self.u_v).pack(anchor="w", pady=5)

        self.inv_v = tk.BooleanVar(value=settings["invert_left_stick_y"])
        ttk.Checkbutton(f, text="Invert Left Stick Y axis (Reverse Scrolling)", variable=self.inv_v).pack(anchor="w", pady=(0, 20))

        ttk.Label(f, text="Right Stick: Cursor Precision", font=('Helvetica', 11, 'bold')).pack(anchor="w")
        self.m_s = ttk.Scale(f, from_=1, to=100, orient="horizontal")
        self.m_s.set(settings["mouse_sensitivity"])
        self.m_s.pack(fill="x", pady=(5, 15))

        ttk.Button(f, text="Save & Apply Settings", command=self.apply).pack(side="bottom", fill="x", pady=20)

    def show(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def hide(self):
        self.root.withdraw()

    def apply(self):
        settings["mouse_sensitivity"] = int(self.m_s.get())
        settings["scroll_sensitivity"] = self.sc_s.get() / 100.0
        settings["ultra_precision_mode"] = self.u_v.get()
        settings["invert_left_stick_y"] = self.inv_v.get()
        save_settings()
        messagebox.showinfo("DGS-X", "Settings saved!")

# --- EXECUTION ---
if __name__ == "__main__":
    load_settings()
    gui = DGSXGui()
    _lock = manage_instance(gui)

    def start_driver():
        dev = None
        while not dev:
            dev = get_device()
            if not dev: time.sleep(5)
        ui = UInput({e.EV_REL: (e.REL_X, e.REL_Y, e.REL_WHEEL), e.EV_KEY: (e.BTN_LEFT, e.BTN_RIGHT)}, name="DGS-X")
        threading.Thread(target=move_loop, args=(ui,), daemon=True).start()
        input_listener(dev, ui)

    threading.Thread(target=start_driver, daemon=True).start()

    def run_tray():
        img = Image.new('RGB', (64, 64), (45, 45, 45))
        draw = ImageDraw.Draw(img)
        draw.ellipse((16, 16, 48, 48), fill=(0, 255, 127))
        pystray.Icon("DGS-X", img, "DGS-X", menu=pystray.Menu(
            pystray.MenuItem("Settings", lambda: gui.show()),
            pystray.MenuItem("Exit", lambda: os._exit(0))
        )).run()

    threading.Thread(target=run_tray, daemon=True).start()
    gui.root.mainloop()
