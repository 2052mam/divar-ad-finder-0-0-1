# config.py

TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_ID = ""

NOTIFY_EMAIL = "arminaali.aaa@gmail.com"
SMTP_HOST = "localhost"
SMTP_PORT = 587
SMTP_USER = "divar@testt.reservira.ir"
SMTP_PASS = "Armin@2001"
SMTP_USE_SSL = False

DATABASE_PATH = "/home/qwamjoow/testt.reservira.ir/divar.db"
MAX_NOTIFY_PER_RUN = 12
REQUEST_DELAY = 1.0

# ---- New settings ----
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "12345678"

TRIAL_DAYS = 3                     # trial length for new signups
SEARCH_COOLDOWN_SECONDS = 4        # per-user cooldown between /search calls
MAX_PARALLEL_DIVAR_REQUESTS = 5    # concurrency cap for Divar API calls

# How many Divar result pages should be fetched in normal search.
# Divar's web UI returns many listings by paginating; one API call usually returns only one page.
SEARCH_RESULT_PAGES = 6            # about 6 * ~23 = ~135+ listings when filters match