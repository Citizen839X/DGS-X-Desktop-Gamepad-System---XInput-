# =================================================================
# DGS-X - 1.1 (JSON INTEGRATION + IMPROVED SCROLL)
# =================================================================
# Copyright (C) 2026 Carlo Sitaro
# Licensed under GNU GPLv3
# =================================================================

#!/usr/bin/env python3
import evdev
from evdev import UInput, ecodes as e
import time
import subprocess
import threading
import os
import socket
import sys
import json

# --- CONFIGURATION LOGIC ---
CONFIG_PATH = os.path.expanduser("~/.config/dgs-x/config.json")

def load_settings():
    # Mouse sensitivity is kept at 25 as the gold standard
    defaults = {
        "mouse_sensitivity": 25,
        "scroll_sensitivity": 0.15,
        "invert_scroll": False,
        "deadzone": 2000,
        "accel_curve": 1.8
    }
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r") as f:
                return {**defaults, **json.load(f)}
        else:
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            with open(CONFIG_PATH, "w") as f:
                json.dump(defaults, f, indent=4)
            return defaults
    except Exception:
        return defaults

# Apply settings from JSON
settings = load_settings()
MOUSE_SENSITIVITY = settings["mouse_sensitivity"]
SCROLL_SENSITIVITY = 0.5  # Increased for higher resolution
SCROLL_CURVE = 2.0        # Exponential curve for organic feel
INVERT_SCROLL = settings["invert_scroll"]
DEADZONE = settings["deadzone"]
ACCEL_CURVE = settings["accel_curve"]

# Operational Constants
TOGGLE_DELAY = 3.0
TRIGGER_THRESHOLD = 500

state = {
    "rx": 0, "ry": 0, 
    "active": True, 
    "lt_clicked": False, "rt_clicked": False,
    "scroll_acc": 0.0,
    "scroll_speed": 0.0    # New variable for inertial velocity
}

def get_xinput_device():
    try:
        devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
        for dev in devices:
            name = dev.name.lower()
            if any(x in name for x in ["xbox", "pdp", "microsoft", "x-box", "controller", "gamepad", "generic"]):
                return dev
    except:
        pass
    return None

def apply_accel(value):
    if abs(value) < DEADZONE: return 0
    norm = (abs(value) - DEADZONE) / (32767 - DEADZONE)
    speed = (norm ** ACCEL_CURVE) * MOUSE_SENSITIVITY
    return int(speed if value > 0 else -speed)

def move_loop(ui):
    """Independent thread for smooth mouse and scroll movement"""
    while True:
        if state["active"]:
            # Mouse movement logic
            dx, dy = apply_accel(state["rx"]), apply_accel(state["ry"])
            if dx != 0 or dy != 0:
                ui.write(e.EV_REL, e.REL_X, dx)
                ui.write(e.EV_REL, e.REL_Y, dy)
            
            # Brilliant Scroll Logic: Processed in the time loop for fluidity
            if abs(state["scroll_speed"]) > 0.01:
                state["scroll_acc"] += state["scroll_speed"]
                if abs(state["scroll_acc"]) >= 1.0:
                    steps = int(state["scroll_acc"])
                    ui.write(e.EV_REL, e.REL_WHEEL, steps)
                    state["scroll_acc"] -= steps
            
            ui.syn()
        time.sleep(0.01)

def input_listener(device, ui):
    start_pressed_time = 0
    for event in device.read_loop():
        # Toggle Service (START hold)
        if event.type == e.EV_KEY and event.code == e.BTN_START:
            if event.value == 1: 
                start_pressed_time = time.time()
            else:
                if start_pressed_time > 0 and (time.time() - start_pressed_time) >= TOGGLE_DELAY:
                    state["active"] = not state["active"]
                    msg = "ENABLED" if state["active"] else "LOCKED"
                    subprocess.Popen(['notify-send', 'DGS-X', f"Status: {msg}"])
                start_pressed_time = 0

        if not state["active"]: continue

        if event.type == e.EV_ABS:
            # Right Stick - Mouse Movement
            if event.code == e.ABS_RX: state["rx"] = event.value
            elif event.code == e.ABS_RY: state["ry"] = event.value
            
            # Left Stick - Vertical Scroll logic (Velocity based)
            elif event.code in [e.ABS_Y, e.ABS_HAT0Y]: 
                if abs(event.value) > DEADZONE:
                    norm = (abs(event.value) - DEADZONE) / (32767 - DEADZONE)
                    
                    direction = -1 if event.value < 0 else 1
                    if INVERT_SCROLL:
                        direction *= -1
                    
                    # D-Pad (HAT) gets a fixed comfortable speed, Stick gets analog curve
                    input_scale = SCROLL_SENSITIVITY if event.code == e.ABS_Y else 0.4
                    state["scroll_speed"] = (norm ** SCROLL_CURVE) * input_scale * direction
                else: 
                    state["scroll_speed"] = 0.0
                    state["scroll_acc"] = 0.0
            
            # LT -> MOUSE RIGHT CLICK
            elif event.code in [e.ABS_Z, e.ABS_BRAKE]:
                is_p = event.value > TRIGGER_THRESHOLD
                if is_p != state["lt_clicked"]:
                    ui.write(e.EV_KEY, e.BTN_RIGHT, 1 if is_p else 0)
                    state["lt_clicked"] = is_p
                    ui.syn()
            
            # RT -> MOUSE LEFT CLICK
            elif event.code in [e.ABS_RZ, e.ABS_GAS]:
                is_p = event.value > TRIGGER_THRESHOLD
                if is_p != state["rt_clicked"]:
                    ui.write(e.EV_KEY, e.BTN_LEFT, 1 if is_p else 0)
                    state["rt_clicked"] = is_p
                    ui.syn()

        if event.type == e.EV_KEY:
            if event.code == e.BTN_THUMBR: ui.write(e.EV_KEY, e.BTN_MIDDLE, event.value)
            elif event.code == e.BTN_TL: ui.write(e.EV_KEY, e.BTN_SIDE, event.value)
            elif event.code == e.BTN_TR: ui.write(e.EV_KEY, e.BTN_EXTRA, event.value)
            ui.syn()

def main():
    device = get_xinput_device()
    if not device: 
        sys.exit(1)

    cap = {
        e.EV_REL: (e.REL_X, e.REL_Y, e.REL_WHEEL),
        e.EV_KEY: (e.BTN_LEFT, e.BTN_RIGHT, e.BTN_MIDDLE, e.BTN_SIDE, e.BTN_EXTRA)
    }
    ui = UInput(cap, name="DGS-X Virtual Mouse")

    # Start independent movement thread
    threading.Thread(target=move_loop, args=(ui,), daemon=True).start()
    input_listener(device, ui)

if __name__ == "__main__":
    main()
