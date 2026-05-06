import logging
import sys
import re
import os
import shutil
from datetime import datetime

if os.name == 'nt':
    import ctypes

class Colors:
    # 🌈 Extended Vibrant Palette
    MAGENTA = '\033[35m'
    BRIGHT_MAGENTA = '\033[95m'
    BLUE = '\033[34m'
    BRIGHT_BLUE = '\033[94m'
    CYAN = '\033[36m'
    BRIGHT_CYAN = '\033[96m'
    GREEN = '\033[32m'
    BRIGHT_GREEN = '\033[92m'
    YELLOW = '\033[33m'
    BRIGHT_YELLOW = '\033[93m'
    RED = '\033[31m'
    BRIGHT_RED = '\033[91m'
    WHITE = '\033[97m'
    DIM = '\033[2m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

class PremiumFilter(logging.Filter):
    """Faltu logs ko filter karne ke liye."""
    def filter(self, record):
        msg = record.getMessage()
        noisy_patterns = [
            "HTTP Request:", "batchEmbedContents", "gemini-embedding",
            "ChromaDB", "collections cleared", "AFC is enabled",
            "file_cache is only supported"
        ]
        return not any(pattern in msg for pattern in noisy_patterns)

class PremiumFormatter(logging.Formatter):
    """Logs ko premium sci-fi aesthetic aur banner ke theme ke saath match karta hai."""
    def format(self, record):
        time_str = datetime.now().strftime("%H:%M:%S")
        msg = record.getMessage()
        
        if not msg: return ""

        # Sleek message formatting
        if "Wake word" in msg: 
            msg = f"{Colors.BRIGHT_GREEN}⚡ [SYSTEM]{Colors.RESET} WAKE SIGNAL DETECTED..."
        elif "Listening" in msg: 
            msg = f"{Colors.BRIGHT_MAGENTA}∿ [AUDIO]{Colors.RESET} LISTENING STREAM..."
        elif "You said:" in msg:
            cmd = msg.split("You said:")[-1].strip()
            msg = f"{Colors.BRIGHT_YELLOW}USER ❯{Colors.RESET} {Colors.WHITE}{cmd}{Colors.RESET}"
        elif "JARVIS:" in msg:
            resp = msg.split("JARVIS:")[-1].strip()
            msg = f"{Colors.BRIGHT_CYAN}JARVIS ❯{Colors.RESET} {resp}"
        elif "Agent Thought:" in msg:
            thought = msg.split("Agent Thought:")[-1].strip()
            msg = f"{Colors.DIM} └─ ⬡ Process: {thought[:90]}...{Colors.RESET}"
        else:
            msg = f"{Colors.DIM}❖ {msg}{Colors.RESET}"
        
        return f"{Colors.DIM}[{time_str}]{Colors.RESET}  {msg}"

def strip_ansi(text):
    """Remove ANSI escape sequences for length calculation."""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

def get_centered(text, width):
    """Text ki har line ko screen ke center mein align karta hai."""
    lines = text.splitlines()
    result_lines = []
    for line in lines:
        visible_len = len(strip_ansi(line))
        if visible_len < width:
            padding = (width - visible_len) // 2
            result_lines.append(' ' * padding + line)
        else:
            result_lines.append(line)
    return "\n".join(result_lines)

def get_colorful_logo(text):
    """Logo ko Cyberpunk/Synthwave color gradient deta hai."""
    colors_sequence = [
        Colors.BRIGHT_MAGENTA,
        Colors.MAGENTA,
        Colors.BRIGHT_BLUE,
        Colors.BRIGHT_CYAN,
        Colors.CYAN,
        Colors.BRIGHT_GREEN
    ]
    result = []
    lines = text.split('\n')
    
    color_idx = 0
    for line in lines:
        if line.strip():  # Agar line empty nahi hai toh color lagao
            color = colors_sequence[color_idx % len(colors_sequence)]
            result.append(f"{color}{line}{Colors.RESET}")
            color_idx += 1
        else:
            result.append(line)
            
    return "\n".join(result)

def get_system_uptime():
    """Get system uptime in a human-readable format."""
    try:
        if os.name == 'nt':
            tick_count = ctypes.windll.kernel32.GetTickCount64()
            uptime_seconds = tick_count // 1000
        else:
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.readline().split()[0])
        
        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        
        if days > 0: return f"{days}d {hours}h"
        elif hours > 0: return f"{hours}h {minutes}m"
        else: return f"{minutes}m"
    except:
        return "N/A"

def generate_bar(percent, color, length=12):
    """Dynamic colored progress bar."""
    filled = int(length * percent / 100)
    empty = length - filled
    return f"{color}{'█' * filled}{Colors.DIM}{'░' * empty}{Colors.RESET}"

def print_banner():
    """Ultra-Sleek Colorful Dynamic Banner."""
    size = shutil.get_terminal_size((80, 24))
    width = size.columns
    height = size.lines

    # Fixed Width Decorative Lines for perfect centering (fails to break on resize)
    separator = "━" * 70

    logo_raw = f"""
      
       ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
       ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
       ██║███████║██████╔╝██║   ██║██║███████╗
  ██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
  ╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
   ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
"""
    
    logo_gradient = get_colorful_logo(logo_raw)
    
    # ==================== COLORFUL HUD STATS ====================
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory().percent
        
        # Dynamic colors based on usage
        cpu_color = Colors.BRIGHT_RED if cpu > 80 else Colors.BRIGHT_YELLOW if cpu > 50 else Colors.BRIGHT_GREEN
        ram_color = Colors.BRIGHT_RED if ram > 80 else Colors.BRIGHT_MAGENTA if ram > 50 else Colors.BRIGHT_CYAN
        
        stats_block = f"""
{Colors.BRIGHT_CYAN}[ C O R E   O N L I N E ]{Colors.RESET}
{Colors.DIM}{separator}{Colors.RESET}
{Colors.DIM}SYS.INFO │{Colors.RESET} CPU: {cpu_color}{cpu:04.1f}% [{generate_bar(cpu, cpu_color)}]{Colors.RESET} {Colors.DIM}│{Colors.RESET} RAM: {ram_color}{ram:04.1f}% [{generate_bar(ram, ram_color)}]{Colors.RESET} {Colors.DIM}│{Colors.RESET} UP: {Colors.BRIGHT_GREEN}{get_system_uptime()}{Colors.RESET}
{Colors.DIM}{separator}{Colors.RESET}
"""
    except ImportError:
        stats_block = f"""
{Colors.BRIGHT_CYAN}[ C O R E   O N L I N E ]{Colors.RESET}
{Colors.DIM}{separator}{Colors.RESET}
{Colors.DIM}SYS.INFO │{Colors.RESET} PLATFORM: {Colors.BRIGHT_BLUE}{sys.platform.upper()}{Colors.RESET} {Colors.DIM}│{Colors.RESET} PYTHON: {Colors.BRIGHT_YELLOW}{sys.version.split()[0]}{Colors.RESET} {Colors.DIM}│{Colors.RESET} ENGINE: {Colors.BRIGHT_MAGENTA}CLAUDE v3.0{Colors.RESET}
{Colors.DIM}{separator}{Colors.RESET}
"""
    
    # ==================== COMMAND PROMPT ====================
    prompt = f"""
{Colors.BRIGHT_GREEN} ❯ SYSTEM SECURED & INITIALIZED{Colors.RESET}
{Colors.BRIGHT_CYAN} ❯ AWAITING VOICE OR TERMINAL INPUT...{Colors.RESET}
"""
    
    # Combine everything
    full_banner = f"{logo_gradient}\n{stats_block}\n{prompt}"
    
    # Center it perfectly vertically and horizontally
    banner_lines = full_banner.count('\n') + 1
    top_padding = max(0, (height // 2) - (banner_lines // 2) - 2)
    
    os.system('cls' if os.name == 'nt' else 'clear')
    print("\n" * top_padding)
    print(get_centered(full_banner, width))
    print("\n" * 1)

def disable_quickedit():
    """Terminal freeze hone se rokne ke liye."""
    if os.name != 'nt': return
    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-10)
        mode = ctypes.c_uint32()
        kernel32.GetConsoleMode(handle, ctypes.byref(mode))
        mode.value &= ~0x0040  # Disable QuickEdit
        mode.value |= 0x0080   # Enable Extended Flags
        kernel32.SetConsoleMode(handle, mode)
    except: pass

def fix_windows_unicode():
    """Windows CMD mein Unicode (UTF-8) symbols theek se render karne ke liye"""
    if os.name == 'nt':
        os.system('chcp 65001 > nul')

def setup_premium_terminal():
    """Logging handlers set up karna."""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    console = logging.StreamHandler(sys.stdout)
    console.addFilter(PremiumFilter())
    console.setFormatter(PremiumFormatter())
    root_logger.addHandler(console)
    
    for lib in ['urllib3', 'requests', 'google', 'http', 'asyncio']:
        logging.getLogger(lib).setLevel(logging.WARNING)

def init_terminal():
    """Call this in main.py to launch the interface."""
    fix_windows_unicode()
    disable_quickedit()
    setup_premium_terminal()
    print_banner()

if __name__ == "__main__":
    init_terminal()