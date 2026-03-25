import logging
import sys
from rich.logging import RichHandler
from rich.console import Console
from rich.theme import Theme
from modules.config import CONFIG

# Custom Theme for Jarvis - Defines colors for different log levels
jarvis_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "critical": "bold white on red",
    "success": "bold green"
})

# Console setup (Enables Emojis and Colors)
console = Console(theme=jarvis_theme)

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[
        # RichHandler handles timestamps, highlighting, and formatting automatically
        RichHandler(console=console, rich_tracebacks=True, markup=True, show_path=False)
    ]
)

logger = logging.getLogger("rich")

# File Logging (Backup in plain text, strictly for errors/history)
try:
    file_handler = logging.FileHandler(CONFIG["LOG_FILE"], encoding='utf-8')
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(file_handler)
except Exception:
    pass # If log file fails, we still have the console