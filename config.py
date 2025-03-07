import os
import logging
from logging.handlers import RotatingFileHandler
from environs import Env

# Create new Env instance and force reload
env = Env()
env.read_env(override=True)  # Force reading the .env file and override existing variables

# Configure detailed logging
LOG_DIRECTORY = "logs"
os.makedirs(LOG_DIRECTORY, exist_ok=True)

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler(
            os.path.join(LOG_DIRECTORY, "bot.log"),
            maxBytes=10485760,  # 10MB
            backupCount=5
        )
    ]
)
logger = logging.getLogger("OnlinePBX_Bot")

# Bot configuration
TELEGRAM_BOT_TOKEN = env.str("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = env.str("TELEGRAM_CHANNEL_ID")

# Webhook configuration
WEBHOOK_HOST = env.str("WEBHOOK_HOST").strip("'").split('#')[0].strip()  # Clean up any quotes or comments
WEBHOOK_LISTEN = '0.0.0.0'
WEBHOOK_PORT = 5000
WEBHOOK_URL_BASE = f"https://{WEBHOOK_HOST}"
WEBHOOK_URL_PATH = f"/webhook/{TELEGRAM_BOT_TOKEN}"
HISTORY_URL = env.str("HISTORY_URL")
AUTH_KEY = env.str("AUTH_KEY")
AUTH_URL = env.str("AUTH_URL")

# API configuration

# Data storage
DATA_DIRECTORY = "data"
os.makedirs(DATA_DIRECTORY, exist_ok=True)
LAST_CHECK_FILE = os.path.join(DATA_DIRECTORY, "last_check_time.txt")
LAST_CALL_UUID_FILE = os.path.join(DATA_DIRECTORY, "last_call_uuid.txt")

# Message formatting
CALL_ICONS = {
    "inbound": "📥",
    "outbound": "📤",
    "internal": "🔄",
    "unknown": "📞"
}

HANGUP_CAUSES = {
    "NORMAL_CLEARING": "Normal Hangup",
    "USER_BUSY": "User Busy",
    "NO_ANSWER": "No Answer",
    "CALL_REJECTED": "Call Rejected",
    "ORIGINATOR_CANCEL": "Caller Cancelled",
    "UNALLOCATED_NUMBER": "Invalid Number",
    "NO_USER_RESPONSE": "No Response",
    "NORMAL_UNSPECIFIED": "Normal Unspecified",
    "NORMAL_TEMPORARY_FAILURE": "Temporary Failure",
    "RECOVERY_ON_TIMER_EXPIRE": "Timeout",
    "REQUESTED_CHAN_UNAVAIL": "Channel Unavailable"
}