"""
================================================================================
REAL ESTATE INTELLIGENCE BOT - KONFIGURASI UTAMA (CONFIG.PY)
================================================================================
File ini memuat seluruh konfigurasi bot. Anda dapat mengaturnya langsung di file
ini atau melalui file '.env' (Sangat Direkomendasikan).

PETUNJUK PENGISIAN KONFIGURASI:
1. GROQ_API_KEY
   - Dapatkan secara gratis di https://console.groq.com/keys
   - Model default: 'openai/gpt-oss-120b' (Sangat cerdas & cepat)
   - Masukkan di .env: GROQ_API_KEY=gsk_xxx

2. GEMINI_API_KEYS (Opsional / Fallback)
   - Dapatkan di https://aistudio.google.com/app/apikey
   - Masukkan di .env: GEMINI_API_KEYS=key1,key2

3. TELEGRAM NOTIFICATION
   - TELEGRAM_TOKEN: Dapatkan dari @BotFather di Telegram
   - CHAT_ID: ID Chat/Channel/Grup tujuan alert (Gunakan @userinfobot atau sejenisnya)
   - Masukkan di .env:
     TELEGRAM_TOKEN=1234567890:ABCdef...
     CHAT_ID=-1001234567890

4. FACEBOOK_GROUPS
   - Daftar URL grup Facebook target (pisahkan dengan koma).
   - Masukkan di .env:
     FACEBOOK_GROUPS=https://facebook.com/groups/123/,https://facebook.com/groups/456/

5. KATA KUNCI PROPERTI & URGENSI
   - Filter Tingkat 1 mengharuskan sebuah postingan memiliki MINIMAL 1 KATA KUNCI PROPERTI
     DAN MINIMAL 1 KATA KUNCI URGENSI agar lolos ke tahap analisis AI.
   - Atur di bawah pada PROPERTY_KEYWORDS dan URGENCY_KEYWORDS atau via .env.
================================================================================
"""

import os
import sys
from dotenv import load_dotenv

# Paksa encoding UTF-8 untuk stdout & stderr di Windows agar emoji tidak error
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Load file .env
load_dotenv(override=True)

# ------------------------------------------------------------------------------
# 1. API KEYS (GROQ & GEMINI)
# ------------------------------------------------------------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip()

# Gemini Multi-key (Opsional untuk fallback/dashboard)
raw_gemini_keys = os.getenv("GEMINI_API_KEYS", os.getenv("GEMINI_API_KEY", ""))
GEMINI_API_KEYS = [k.strip().strip('"').strip("'") for k in raw_gemini_keys.split(",") if k.strip()]

# ------------------------------------------------------------------------------
# 2. TELEGRAM SETTINGS
# ------------------------------------------------------------------------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
CHAT_ID = os.getenv("CHAT_ID", "").strip()

# ------------------------------------------------------------------------------
# 3. DAFTAR URL GRUP FACEBOOK TARGET
# ------------------------------------------------------------------------------
raw_groups = os.getenv("FACEBOOK_GROUPS", "")
FACEBOOK_GROUPS = [url.strip() for url in raw_groups.split(",") if url.strip()]

# ------------------------------------------------------------------------------
# 4. KATA KUNCI DUA TINGKAT (PROPERTY & URGENCY KEYWORDS)
# ------------------------------------------------------------------------------
# Default kata kunci properti
DEFAULT_PROPERTY_KEYWORDS = [
    "dijual", "jual", "rumah", "ruko", "tanah",
    "kavling", "kost", "kosan", "gudang", "apartemen",
    "over kredit", "take over", "gedung", "pabrik"
]

# Default kata kunci urgensi / peluang cuan
DEFAULT_URGENCY_KEYWORDS = [
    "bu", "butuh uang", "b.u", "lelang", "murah",
    "miring", "under market", "dibawah pasar", "turun harga",
    "cepat", "butuh dana", "obral", "rugi", "direposisi",
    "termurah", "hit tanah", "hitung tanah"
]

# Baca override dari .env jika pengguna menentukan custom
env_property_kw = os.getenv("PROPERTY_KEYWORDS", "")
if env_property_kw:
    PROPERTY_KEYWORDS = [kw.strip().lower() for kw in env_property_kw.split(",") if kw.strip()]
else:
    PROPERTY_KEYWORDS = [kw.lower() for kw in DEFAULT_PROPERTY_KEYWORDS]

env_urgency_kw = os.getenv("URGENCY_KEYWORDS", "")
if env_urgency_kw:
    URGENCY_KEYWORDS = [kw.strip().lower() for kw in env_urgency_kw.split(",") if kw.strip()]
else:
    URGENCY_KEYWORDS = [kw.lower() for kw in DEFAULT_URGENCY_KEYWORDS]

# ------------------------------------------------------------------------------
# 5. JADWAL OPERASIONAL & INTERVAL (DETIK)
# ------------------------------------------------------------------------------
# Mode Siang (06:00 - 22:00): 1 jam sekali (3600 detik)
DAY_INTERVAL_SECONDS = int(os.getenv("DAY_INTERVAL_SECONDS", 3600))

# Mode Malam (22:00 - 06:00): 2 jam sekali (7200 detik)
NIGHT_INTERVAL_SECONDS = int(os.getenv("NIGHT_INTERVAL_SECONDS", 7200))

# Jeda acak (detik) antar grup Facebook untuk menghindari rate limit Facebook
MIN_GROUP_DELAY = float(os.getenv("MIN_GROUP_DELAY", 1.0))
MAX_GROUP_DELAY = float(os.getenv("MAX_GROUP_DELAY", 30.0))

# ------------------------------------------------------------------------------
# 6. FILE STORAGE & CACHE
# ------------------------------------------------------------------------------
COOKIE_FILE = os.getenv("COOKIE_FILE", "fb_state.json")
SEEN_POSTS_FILE = os.getenv("SEEN_POSTS_FILE", "seen_posts.json")
MAX_SEEN_POSTS = int(os.getenv("MAX_SEEN_POSTS", 5000))

# ------------------------------------------------------------------------------
# 7. PROXY SETTINGS (OPSIONAL)
# ------------------------------------------------------------------------------
USE_PROXY = os.getenv("USE_PROXY", "false").lower() in ("true", "1", "yes")
PROXY_SERVER = os.getenv("PROXY_SERVER", "")

PROXY_SETTINGS = {
    "server": PROXY_SERVER
} if USE_PROXY and PROXY_SERVER else None

# ------------------------------------------------------------------------------
# 8. VALIDASI KONFIGURASI SISTEM
# ------------------------------------------------------------------------------
def validate_config(strict=False):
    """
    Memeriksa kelengkapan konfigurasi penting.
    Mengembalikan (is_valid, list_error, list_warning).
    """
    errors = []
    warnings = []

    if not GROQ_API_KEY:
        errors.append("GROQ_API_KEY belum disetel di file .env! Bot memerlukan Groq untuk AI filter.")

    if not TELEGRAM_TOKEN:
        errors.append("TELEGRAM_TOKEN belum disetel di file .env!")

    if not CHAT_ID:
        errors.append("CHAT_ID Telegram belum disetel di file .env!")

    if not FACEBOOK_GROUPS:
        errors.append("FACEBOOK_GROUPS kosong di .env! Masukkan minimal 1 URL grup Facebook.")

    if not os.path.exists(COOKIE_FILE):
        warnings.append(
            f"File sesi '{COOKIE_FILE}' belum ditemukan. Silakan jalankan 'python save_session.py' untuk login."
        )

    is_valid = len(errors) == 0
    return is_valid, errors, warnings

