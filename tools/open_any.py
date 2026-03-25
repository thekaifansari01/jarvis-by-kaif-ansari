import subprocess
import traceback
import webbrowser
import getpass
import os
import time

# Username for dynamic paths
USERNAME = getpass.getuser()

# --- 1. LEGACY COMPATIBILITY (DO NOT REMOVE) ---
# Ye dictionaries zaroori hain taaki aapka processor.py error na de.
APP_PATHS = {
    "vscode": fr"C:\Users\{USERNAME}\AppData\Local\Programs\Microsoft VS Code\Code.exe",
    "pycharm": r"C:\Program Files\JetBrains\PyCharm Community Edition 2023.2.1\bin\pycharm64.exe",
    "notepad": "notepad",
    "notepad++": r"C:\Program Files\Notepad++\notepad++.exe",
    "postman": fr"C:\Users\{USERNAME}\AppData\Local\Programs\Postman\Postman.exe",
    "git bash": r"C:\Program Files\Git\git-bash.exe",
    "cmd": "cmd",
    "powershell": "powershell",
    "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "firefox": r"C:\Program Files\Mozilla Firefox\firefox.exe",
    "edge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "brave": r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    "spotify": fr"C:\Users\{USERNAME}\AppData\Roaming\Spotify\Spotify.exe",
    "vlc": r"C:\Program Files\VideoLAN\VLC\vlc.exe",
    "photos": "start ms-photos:",
    "films and tv": "start ms-filmstv:",
    "whatsapp": fr"C:\Users\{USERNAME}\AppData\Local\WhatsApp\WhatsApp.exe",
    "discord": fr"C:\Users\{USERNAME}\AppData\Local\Discord\Update.exe --processStart Discord.exe",
    "telegram": fr"C:\Users\{USERNAME}\AppData\Roaming\Telegram Desktop\Telegram.exe",
    "skype": r"C:\Program Files (x86)\Microsoft\Skype for Desktop\Skype.exe",
    "steam": r"C:\Program Files (x86)\Steam\steam.exe",
    "epic games": r"C:\Program Files (x86)\Epic Games\Launcher\Portal\Binaries\Win32\EpicGamesLauncher.exe",
    "riot client": r"C:\Riot Games\Riot Client\RiotClientServices.exe",
    "battle.net": r"C:\Program Files (x86)\Battle.net\Battle.net Launcher.exe",
    "calculator": "calc",
    "task manager": "taskmgr",
    "settings": "start ms-settings:",
    "control panel": "control"
}

WEB_URLS = {
    "youtube": "https://www.youtube.com",
    "tradingview": "https://www.tradingview.com",
    "bitcoin chart": "https://www.tradingview.com/chart/Y4L9xzbl/?symbol=BITSTAMP%3ABTCUSD",
    "gold chart": "https://www.tradingview.com/chart/Y4L9xzbl/?symbol=OANDA%3AXAUUSD", 
    "mt5": "https://mt5.fundingpips.com/terminal",
    "google": "https://www.google.com",
    "github": "https://github.com",
    "stackoverflow": "https://stackoverflow.com",
    "chatgpt": "https://chat.openai.com",
    "gmail": "https://mail.google.com",
    "linkedin": "https://www.linkedin.com",
    "instagram": "https://www.instagram.com",
    "facebook": "https://www.facebook.com",
    "twitter": "https://twitter.com",
    "medium": "https://medium.com/",
    "trello": "https://trello.com/",
    "canva": "https://www.canva.com/",
    "hackerrank": "https://www.hackerrank.com/",
    "khanacademy": "https://www.khanacademy.org/",
    "unsplash": "https://unsplash.com/",
    "cohere": "https://cohere.ai/",
    "zapier": "https://zapier.com/",
    "w3schools": "https://www.w3schools.com/",
    "mdn_web_docs": "https://developer.mozilla.org/",
    "freecodecamp": "https://www.freecodecamp.org/",
    "coursera": "https://www.coursera.org/",
    "edx": "https://www.edx.org/",
    "udemy": "https://www.udemy.com/",
    "googlescholar": "https://scholar.google.com/",
    "quora": "https://www.quora.com/",
    "notion": "https://www.notion.so/",
    "jotform": "https://www.jotform.com/",
    "dropbox": "https://www.dropbox.com/",
    "googledrive": "https://drive.google.com/",
    "onedrive": "https://onedrive.live.com/",
    "evernote": "https://www.evernote.com/",
    "claude": "https://claude.ai/",
    "duolingo": "https://www.duolingo.com/",
    "kaggle": "https://www.kaggle.com/",
    "grok": "https://grok.com/",
    "asana": "https://asana.com/",
    "slack": "https://slack.com/",
    "figma": "https://www.figma.com/",
    "vs_code": "https://code.visualstudio.com/",
    "sublime_text": "https://www.sublimetext.com/",
    "pypi": "https://pypi.org/",
    "npm": "https://www.npmjs.com/",
    "bootstrap": "https://getbootstrap.com/",
    "font_awesome": "https://fontawesome.com/",
    "gitlab": "https://about.gitlab.com/",
    "docker": "https://www.docker.com/",
    "jenkins": "https://www.jenkins.io/",
    "digitalocean": "https://www.digitalocean.com/",
    "linode": "https://www.linode.com/",
    "aws": "https://aws.amazon.com/",
    "heroku": "https://www.heroku.com/",
    "vercel": "https://vercel.com/",
    "net": "Ascendingly.netlify.app/",
    "netlify": "https://www.netlify.com/",
    "cloudflare": "https://www.cloudflare.com/",
    "twitch": "https://www.twitch.tv/",
    "pinterest": "https://www.pinterest.com/",
    "reddit": "https://www.reddit.com/",
    "hootsuite": "https://hootsuite.com/",
    "mailchimp": "https://mailchimp.com/",
    "flipkart": "https://flipkart.com/",
    "amazon": "https://amazon.com/",
    "sendgrid": "https://sendgrid.com/"
}

# --- 2. NEW SMART SEARCH FUNCTION ---
def find_app_in_start_menu(app_name):
    """Auto-detects installed apps from Start Menu shortcuts."""
    search_paths = [
        os.path.join(os.environ['PROGRAMDATA'], r'Microsoft\Windows\Start Menu\Programs'),
        os.path.join(os.environ['APPDATA'], r'Microsoft\Windows\Start Menu\Programs')
    ]
    app_name = app_name.lower().replace(" ", "")
    
    for path in search_paths:
        if not os.path.exists(path): continue
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.lower().endswith(".lnk"):
                    filename_clean = file.lower().replace(".lnk", "").replace(" ", "")
                    if app_name in filename_clean:
                        return os.path.join(root, file)
    return None

# --- 3. MAIN EXECUTION LOGIC ---
def open_any_app(apps_to_open):
    """
    Priority Order:
    1. APP_PATHS (Manual Dictionary - Fastest)
    2. WEB_URLS (Manual Dictionary)
    3. Start Menu Search (Dynamic Discovery)
    4. System Run (CMD commands)
    5. Generic Website Fallback (.com)
    """
    opened = []
    
    # Ensure input is a list
    if isinstance(apps_to_open, str):
        apps_to_open = [apps_to_open]

    for name in apps_to_open:
        name_lower = name.lower().strip()
        found = False

        # --- CHECK 1: Existing Dictionaries (Compatibility) ---
        if name_lower in APP_PATHS:
            try:
                subprocess.Popen(APP_PATHS[name_lower], shell=True)
                opened.append(name)
                found = True
            except Exception as e:
                print(f"❌ Error opening {name} from PATHS: {e}")

        elif name_lower in WEB_URLS:
            try:
                webbrowser.open(WEB_URLS[name_lower])
                opened.append(name)
                found = True
            except Exception as e:
                print(f"❌ Error opening {name} from WEB: {e}")

        # --- CHECK 2: Smart Auto-Discovery (New Feature) ---
        if not found:
            shortcut = find_app_in_start_menu(name_lower)
            if shortcut:
                try:
                    os.startfile(shortcut)
                    print(f"✅ Auto-Found: {shortcut}")
                    opened.append(name)
                    found = True
                except Exception as e:
                    print(f"❌ Error launching shortcut: {e}")

        # --- CHECK 3: System Command / Generic Web ---
        if not found:
            try:
                # Try running as a direct command (e.g. 'calc', 'notepad')
                subprocess.Popen(name_lower, shell=True)
                opened.append(name)
                found = True
            except:
                # Last Resort: Try as a website
                if "." not in name_lower:
                    url = f"https://www.{name_lower}.com"
                else:
                    url = f"https://{name_lower}"
                
                webbrowser.open(url)
                print(f"🌍 Opened as Generic URL: {url}")
                opened.append(name)

    return opened