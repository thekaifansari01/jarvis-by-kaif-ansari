import os
import sys
import ctypes
import threading
import time
import pystray
from PIL import Image, ImageDraw

tray_icon = None
monitor_running = True

def show_console():
    hwnd = ctypes.windll.kernel32.GetConsoleWindow()
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, 9)
        ctypes.windll.user32.SetForegroundWindow(hwnd)

def hide_console():
    hwnd = ctypes.windll.kernel32.GetConsoleWindow()
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, 0)

def exit_app(icon, item):
    global monitor_running
    monitor_running = False
    hide_console()
    icon.stop()
    os._exit(0)

def minimize_monitor():
    global monitor_running
    while monitor_running:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd and ctypes.windll.user32.IsIconic(hwnd):
            hide_console()
        time.sleep(0.5)

def create_default_icon():
    """Fallback: blue circle agar custom icon nahi mila"""
    width = 64
    height = 64
    image = Image.new('RGB', (width, height), (30, 30, 30))
    draw = ImageDraw.Draw(image)
    draw.ellipse((8, 8, width-8, height-8), outline=(0, 200, 255), width=3)
    draw.ellipse((20, 20, width-20, height-20), fill=(0, 200, 255))
    draw.ellipse((width//2-8, height//2-8, width//2+8, height//2+8), fill=(255, 255, 255))
    return image

def start_tray_icon(icon_path=None):
    global tray_icon, monitor_running
    
    # 🔥 DEFAULT ICON PATH (agar parameter nahi diya to ye use karega)
    if icon_path is None:
        # Project ke root se Data/icons/jarvis_icon.png
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        icon_path = os.path.join(base_dir, "Data", "icons", "jarvis_icon.png")
    
    monitor_running = True
    monitor_thread = threading.Thread(target=minimize_monitor, daemon=True)
    monitor_thread.start()
    
    # Load icon
    if icon_path and os.path.exists(icon_path):
        try:
            icon_image = Image.open(icon_path)
            print(f"✅ Tray icon loaded from: {icon_path}")
        except Exception as e:
            print(f"⚠️ Could not load icon: {e}, using default")
            icon_image = create_default_icon()
    else:
        print("⚠️ Custom icon not found, using default blue circle")
        icon_image = create_default_icon()
    
    menu = pystray.Menu(
        pystray.MenuItem("🔓 Show Jarvis", lambda: show_console()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("🚪 Exit", exit_app)
    )
    
    tray_icon = pystray.Icon("jarvis", icon_image, "Jarvis AI Assistant", menu)
    tray_icon.run_detached()

if __name__ == "__main__":
    hwnd = ctypes.windll.kernel32.GetConsoleWindow()
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, 0)
    start_tray_icon()