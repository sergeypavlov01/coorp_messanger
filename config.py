"""Константы приложения."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent

HOST = os.getenv("HOST", "192.168.0.100")
PORT = os.getenv("PORT", "8080")
WS_URL = os.getenv("WS_URL", f"ws://{HOST}:{PORT}/chat")
HISTORY_FILE = BASE_DIR / "history.json"
USERS_FILE = BASE_DIR / "users.json"
NOTIFY_SOUND = BASE_DIR / "notify.wav"

PAGE_AUTH = 0
PAGE_LIST = 1
PAGE_CHAT = 2

REFRESH_MS = 3000
MAX_HISTORY = 500
SETTINGS_ORG = "coorp_messanger"
SETTINGS_APP = "client"
DEFAULT_THEME = "dark"

THEMES = {
    "dark": {
        "window": "#1b1b26", "panel": "#26263a", "header": "#212134",
        "text": "#e8e8f0", "muted": "#9090a4", "border": "#3b3b56",
        "input_bg": "#1b1b26", "input_border": "#4a4a68",
        "btn_bg": "#1f5fa8", "btn_hover": "#2871bd",
        "list_line": "#33334a", "list_sel": "#1f5fa8",
    },
    "light": {
        "window": "#e9ecf2", "panel": "#ffffff", "header": "#dde2ec",
        "text": "#1c1c2a", "muted": "#5f6472", "border": "#c2c7d2",
        "input_bg": "#ffffff", "input_border": "#b1b6c2",
        "btn_bg": "#2c6fb5", "btn_hover": "#1f5fa8",
        "list_line": "#d3d7e0", "list_sel": "#2c6fb5",
    },
}