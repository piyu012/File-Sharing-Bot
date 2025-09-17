import os
import logging
from logging.handlers import RotatingFileHandler

# ------------ helpers ------------
def get_int(key, default=None):
    v = os.environ.get(key)
    if v is None or v == "":
        return default
    return int(v)

def get_bool(key, default=False):
    v = os.environ.get(key)
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on")

# ------------ required configs ------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
API_ID = get_int("API_ID")
API_HASH = os.environ.get("API_HASH", "")

OWNER_ID = get_int("OWNER_ID")
DB_URL = os.environ.get("DB_URL", "")
DB_NAME = os.environ.get("DB_NAME", "filebot")

CHANNEL_ID = get_int("CHANNEL_ID")
FORCE_SUB_CHANNEL = get_int("FORCE_SUB_CHANNEL", @hindi_anime_duniya)

FILE_AUTO_DELETE = get_int("FILE_AUTO_DELETE", 21600)
TG_BOT_WORKERS = get_int("TG_BOT_WORKERS", 4)
PORT = os.environ.get("PORT", "8080")

# ------------ optional texts/flags ------------
CUSTOM_CAPTION = os.environ.get("CUSTOM_CAPTION", None)
PROTECT_CONTENT = get_bool("PROTECT_CONTENT", False)
DISABLE_CHANNEL_BUTTON = get_bool("DISABLE_CHANNEL_BUTTON", False)

BOT_STATS_TEXT = os.environ.get("BOT_STATS_TEXT", "<b>BOT UPTIME :</b>\n{uptime}")
USER_REPLY_TEXT = os.environ.get("USER_REPLY_TEXT", "❌Don't Send Me Messages Directly I'm Only File Share Bot !")
START_MSG = os.environ.get(
    "START_MESSAGE",
    "Hello {mention}\n\nI Can Store Private Files In Specified Channel And Other Users Can Access It From Special Link."
)
FORCE_MSG = os.environ.get(
    "FORCE_SUB_MESSAGE",
    "Hello {mention}\n\n<b>You Need To Join In My Channel/Group To Use Me\n\nKindly Please Join Channel</b>"
)

# ------------ admins ------------
ADMINS = []
env_admins = os.environ.get("ADMINS", "").split()
for x in env_admins:
    try:
        ix = int(x)
        ADMINS.append(ix)
    except ValueError:
        raise ValueError(f"ADMINS must be space-separated integers; got '{x}'")

if OWNER_ID:
    ADMINS.append(OWNER_ID)

# deduplicate while keeping order
ADMINS = list(dict.fromkeys(ADMINS))

# ------------ logging ------------
LOG_FILE_NAME = "filesharingbot.txt"
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(levelname)s] - %(name)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    handlers=[
        RotatingFileHandler(LOG_FILE_NAME, maxBytes=50_000_000, backupCount=10),
        logging.StreamHandler()
    ]
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)

def LOGGER(name: str) -> logging.Logger:
    return logging.getLogger(name)
logging.getLogger("pyrogram").setLevel(logging.WARNING)

def LOGGER(name: str) -> logging.Logger:
    return logging.getLogger(name)
