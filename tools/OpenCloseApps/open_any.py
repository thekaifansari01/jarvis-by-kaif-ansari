import subprocess
import webbrowser
import getpass
import os
import json
import difflib
import winreg
import threading
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple

USERNAME = getpass.getuser()
CACHE_FILE = "Data/app_cache.json"

class SmartAppOpener:
    """Jarvis-level app opener with caching + fuzzy matching + fallback chains"""
    
    def __init__(self):
        self.cache = self._load_cache()
        self.legacy_apps = self._get_legacy_apps()
        self.web_urls = self._get_web_urls()
        self.is_indexing = False
        
    def _get_legacy_apps(self) -> Dict:
        """Fast path for common apps (keep for speed)"""
        return {
            "vscode": fr"C:\Users\{USERNAME}\AppData\Local\Programs\Microsoft VS Code\Code.exe",
            "code": fr"C:\Users\{USERNAME}\AppData\Local\Programs\Microsoft VS Code\Code.exe",
            "notepad": "notepad.exe",
            "cmd": "cmd.exe",
            "powershell": "powershell.exe",
            "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            "firefox": r"C:\Program Files\Mozilla Firefox\firefox.exe",
            "edge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            "calculator": "calc.exe",
            "task manager": "taskmgr.exe",
            "settings": "start ms-settings:",
        }
    
    def _get_web_urls(self) -> Dict:
        """Common web shortcuts"""
        return {
            "youtube": "https://youtube.com",
            "google": "https://google.com",
            "github": "https://github.com",
            "gmail": "https://mail.google.com",
            "chatgpt": "https://chat.openai.com",
        }
    
    def _load_cache(self) -> Dict:
        """Load cached app paths (built on first run)"""
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {}
    
    def _save_cache(self):
        """Save cache for instant future loads"""
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, indent=2)
    
    def _scan_registry_apps(self) -> Dict:
        """Scan Windows Registry for installed apps (FAST & RELIABLE)"""
        apps = {}
        registry_paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths"),
        ]
        
        for hkey, path in registry_paths:
            try:
                key = winreg.OpenKey(hkey, path)
                i = 0
                while True:
                    try:
                        app_name = winreg.EnumKey(key, i)
                        app_key = winreg.OpenKey(key, app_name)
                        try:
                            app_path, _ = winreg.QueryValueEx(app_key, "")
                            if app_path and os.path.exists(app_path):
                                clean_name = app_name.lower().replace(".exe", "")
                                apps[clean_name] = app_path
                                # Add common variations
                                if "code" in clean_name:
                                    apps["vscode"] = app_path
                                if "chrome" in clean_name:
                                    apps["google chrome"] = app_path
                        except:
                            pass
                        winreg.CloseKey(app_key)
                        i += 1
                    except OSError:
                        break
                winreg.CloseKey(key)
            except:
                pass
        return apps
    
    def _scan_start_menu(self) -> Dict:
        """Fallback: Scan Start Menu shortcuts (slower, but thorough)"""
        apps = {}
        start_menu_paths = [
            os.path.join(os.environ['PROGRAMDATA'], r'Microsoft\Windows\Start Menu\Programs'),
            os.path.join(os.environ['APPDATA'], r'Microsoft\Windows\Start Menu\Programs'),
        ]
        
        for path in start_menu_paths:
            if not os.path.exists(path):
                continue
            for root, dirs, files in os.walk(path):
                for file in files:
                    if file.lower().endswith(".lnk"):
                        name = file[:-4].lower()
                        shortcut_path = os.path.join(root, file)
                        apps[name] = shortcut_path
        return apps
    
    def _scan_path_env(self) -> Dict:
        """Scan executables in PATH environment variable"""
        apps = {}
        path_dirs = os.environ.get("PATH", "").split(";")
        for dir_path in path_dirs:
            if not os.path.exists(dir_path):
                continue
            try:
                for exe in os.listdir(dir_path):
                    if exe.lower().endswith(".exe"):
                        name = exe[:-4].lower()
                        apps[name] = os.path.join(dir_path, exe)
            except:
                pass
        return apps
    
    def rebuild_cache(self):
        """Build complete app index (call once at startup in background)"""
        if self.is_indexing:
            return
        self.is_indexing = True
        print("🔍 Jarvis: Scanning installed apps in background...")
        try:
            all_apps = {}
            all_apps.update(self._scan_registry_apps())
            all_apps.update(self._scan_path_env())
            all_apps.update(self._scan_start_menu())
            all_apps.update(self.legacy_apps)
            
            self.cache = all_apps
            self._save_cache()
            print(f"✅ Jarvis: {len(self.cache)} apps indexed")
        except Exception as e:
            print(f"⚠️ Cache build error: {e}")
        finally:
            self.is_indexing = False
    
    def find_best_match(self, user_input: str) -> Tuple[Optional[str], float]:
        """
        Find best matching app using fuzzy matching with confidence score.
        Returns: (app_path, confidence) where confidence 0-1
        """
        user_input = user_input.lower().strip()
        
        # Exact match first (fastest)
        if user_input in self.cache:
            return self.cache[user_input], 1.0
        
        # Fuzzy match with cutoff
        matches = difflib.get_close_matches(
            user_input, 
            self.cache.keys(), 
            n=1, 
            cutoff=0.6
        )
        if matches:
            return self.cache[matches[0]], 0.8
        
        # Partial match (e.g., "visual studio" vs "visualstudiocode")
        for app_name, app_path in self.cache.items():
            if user_input in app_name or app_name in user_input:
                return app_path, 0.7
        
        return None, 0.0
    
    def open_app(self, app_names: List[str], silent: bool = False) -> Tuple[List[str], List[str]]:
        """
        Open apps with vocal feedback sync.
        Returns: (opened_successfully, failed)
        """
        opened = []
        failed = []
        
        for name in app_names:
            # Check web URL first (fast)
            if name.lower() in self.web_urls:
                webbrowser.open(self.web_urls[name.lower()])
                opened.append(name)
                continue
            
            # Find app
            app_path, confidence = self.find_best_match(name)
            
            if app_path:
                try:
                    # Launch app
                    if app_path.startswith("start "):
                        subprocess.Popen(app_path, shell=True)
                    elif app_path.endswith(".lnk"):
                        os.startfile(app_path)
                    else:
                        subprocess.Popen([app_path], shell=False)
                    opened.append(name)
                except Exception as e:
                    print(f"❌ Failed to open {name}: {e}")
                    failed.append(name)
            else:
                # Last resort: try as generic website
                url = f"https://www.{name.lower().replace(' ', '')}.com"
                webbrowser.open(url)
                opened.append(f"{name} (web)")
        
        return opened, failed


# ==================================================================
# COMPATIBILITY LAYER (Tumhare existing processor.py ke liye)
# ==================================================================

opener = SmartAppOpener()

def start_background_cache_builder():
    """Call this from main.py to build cache without blocking startup"""
    if not opener.cache:
        threading.Thread(target=opener.rebuild_cache, daemon=True).start()

# Legacy dictionaries for compatibility
APP_PATHS = opener.legacy_apps
WEB_URLS = opener.web_urls


def open_any_app(apps_to_open, silent: bool = False):
    """
    Main function called by executor.py
    Returns list of successfully opened apps
    """
    if isinstance(apps_to_open, str):
        apps_to_open = [apps_to_open]
    
    opened, failed = opener.open_app(apps_to_open, silent)
    
    # Vocal feedback sync (pehle open karo, phir bolo)
    if not silent and (opened or failed):
        try:
            from core.voice.tts import speak
            success_names = [n for n in opened if " (web)" not in n]
            if success_names:
                print(f"Sir, {', '.join(success_names)} khol diya.")
            if failed:
                speak(f"Sir, {', '.join(failed)} nahi khul paaya.")
        except:
            pass
    
    return opened