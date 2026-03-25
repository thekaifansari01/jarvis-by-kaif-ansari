import subprocess
import traceback
import difflib
import os

# --- 1. LEGACY DICTIONARY (Keep this for processor.py compatibility) ---
APP_PROCESS_NAMES = {
    "vscode": "Code.exe",
    "pycharm": "pycharm64.exe",
    "notepad++": "notepad++.exe",
    "postman": "Postman.exe",
    "git bash": "git-bash.exe",
    "cmd": "cmd.exe",
    "powershell": "powershell.exe",
    "chrome": "chrome.exe",
    "firefox": "firefox.exe",
    "edge": "msedge.exe",
    "brave": "brave.exe",
    "spotify": "Spotify.exe",
    "vlc": "vlc.exe",
    "photos": "Microsoft.Photos.exe",
    "films and tv": "Video.UI.exe",
    "whatsapp": "WhatsApp.exe",
    "discord": "Discord.exe",
    "telegram": "Telegram.exe",
    "skype": "Skype.exe",
    "steam": "steam.exe",
    "epic games": "EpicGamesLauncher.exe",
    "riot client": "RiotClientServices.exe",
    "battle.net": "Battle.net Launcher.exe",
    "notepad": "notepad.exe",
    "task manager": "Taskmgr.exe",
    "settings": "SystemSettings.exe",
    "control panel": "control.exe",
    "python": "python.exe",
    "word": "WINWORD.EXE",
    "excel": "EXCEL.EXE",
    "powerpoint": "POWERPNT.EXE"
}

# --- 2. HELPER: GET RUNNING PROCESSES ---
def get_running_processes():
    """Returns a dictionary of {clean_name: exe_name} for all running apps."""
    try:
        # 'tasklist' command se saare running process nikalo
        output = subprocess.check_output("tasklist /fo csv /nh", shell=True).decode("utf-8", errors="ignore")
        processes = {}
        for line in output.splitlines():
            if not line.strip(): continue
            # Extract .exe name (e.g., "chrome.exe")
            exe_name = line.split(",")[0].replace('"', '')
            # Create a clean name (e.g., "chrome.exe" -> "chrome")
            clean_name = exe_name.lower().replace(".exe", "")
            processes[clean_name] = exe_name
        return processes
    except Exception:
        return {}

def suggest_closest_process(name, active_processes):
    """
    First checks hardcoded list, then checks currently running processes.
    """
    # 1. Check Hardcoded List first
    matches = difflib.get_close_matches(name, APP_PROCESS_NAMES.keys(), n=1, cutoff=0.7)
    if matches:
        return APP_PROCESS_NAMES[matches[0]]
    
    # 2. Check Active Running Processes (Smart Scan)
    matches_active = difflib.get_close_matches(name, active_processes.keys(), n=1, cutoff=0.6)
    if matches_active:
        return active_processes[matches_active[0]]
        
    return None

# --- 3. MAIN FUNCTION ---
def close_any_app(apps_to_close):
    closed = []
    
    # Refresh active process list once per call
    active_processes = get_running_processes()
    
    if isinstance(apps_to_close, str):
        apps_to_close = [apps_to_close]

    for name in apps_to_close:
        name_lower = name.lower().strip()
        process_to_kill = None

        # Step 1: Check Dictionary (Fastest)
        if name_lower in APP_PROCESS_NAMES:
            process_to_kill = APP_PROCESS_NAMES[name_lower]
        
        # Step 2: Check Active Processes (Smart)
        elif name_lower in active_processes:
            process_to_kill = active_processes[name_lower]
            
        # Step 3: Fuzzy Search (Agar spelling mistake ho)
        else:
            process_to_kill = suggest_closest_process(name_lower, active_processes)

        if process_to_kill:
            try:
                print(f"🛑 Killing process: {process_to_kill}")
                subprocess.run(f"taskkill /f /im \"{process_to_kill}\"", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                closed.append(name)
            except Exception as e:
                print(f"❌ Error closing {name}: {e}")
        else:
            print(f"⚠️ Could not find a running process for: {name}")

    return closed