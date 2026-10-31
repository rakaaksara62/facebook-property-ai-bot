"""
================================================================================
REAL ESTATE INTELLIGENCE BOT - MAIN CONTROLLER (MAIN_BOT.PY)
================================================================================
Script utama untuk menjalankan Bot Scraper Facebook Properti secara otomatis 24/7.

LOKASI PENGATURAN KONFIGURASI:
Seluruh konfigurasi dapat diatur melalui file '.env' atau di file 'config.py':
1. GROQ / GEMINI API KEY       -> Buka file .env, isi variabel GROQ_API_KEY
2. TELEGRAM TOKEN & CHAT ID    -> Buka file .env, isi TELEGRAM_TOKEN & CHAT_ID
3. DAFTAR URL GRUP FACEBOOK    -> Buka file .env, isi FACEBOOK_GROUPS
4. KATA KUNCI PROPERTI/URGENSI -> Buka file config.py (atau set di .env)

FITUR UTAMA:
- Scraping Playwright tanpa dependensi 'playwright-stealth'
- Operational Hours Scheduler:
    * Siang Mode (06:00 - 22:00) : Scraping setiap 1 jam sekali
    * Malam Mode (22:00 - 06:00) : Scraping setiap 2 jam sekali
- Randomized Delay (1-30 detik) antar grup Facebook
- Watchdog 24/7: Proteksi crash & auto-recovery tanpa henti
- Filter 2 Tingkat: Pre-filter kata kunci lokal + Analisis AI (Groq gpt-oss-120b)
- Telegram Notifier: Foto multipart memory buffer + fallback pesan HTML rapi
================================================================================
"""

import sys
import time
import signal
import logging
from datetime import datetime

# Pastikan output konsol Windows mendukung karakter Unicode/Emoji
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Konfigurasi format logging profesional
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("PropertyBot.Main")

from config import (
    validate_config,
    DAY_INTERVAL_SECONDS,
    NIGHT_INTERVAL_SECONDS,
    COOKIE_FILE,
    GROQ_MODEL
)
from storage import is_session_valid
from scraper import run_scraper_cycle

# Flag untuk graceful shutdown
IS_RUNNING = True

def handle_exit_signal(signum, frame):
    """Menangani sinyal penghentian proses (CTRL+C / SIGTERM) secara aman."""
    global IS_RUNNING
    logger.info("🛑 Sinyal berhenti diterima. Menyiapkan penghentian bot secara aman...")
    IS_RUNNING = False

# Daftarkan handler sinyal
signal.signal(signal.SIGINT, handle_exit_signal)
try:
    signal.signal(signal.SIGTERM, handle_exit_signal)
except AttributeError:
    pass  # SIGTERM mungkin tidak tersedia di beberapa platform Windows

def get_wib_datetime() -> datetime:
    """
    Mengembalikan waktu saat ini dalam zona waktu Asia/Jakarta (WIB).
    Memastikan perhitungan jadwal operasional selalu akurat meskipun server
    berada di zona waktu UTC atau menggunakan init system minimal tanpa systemd.
    """
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Jakarta"))
    except Exception:
        return datetime.now()

def get_operational_interval() -> tuple[int, str]:
    """
    Menghitung interval jeda tidur berdasarkan jam operasional WIB:
    - Mode Siang (06:00 - 22:00 WIB): 1 jam sekali (3600 detik)
    - Mode Malam (22:00 - 06:00 WIB): 2 jam sekali (7200 detik)
    """
    current_hour = get_wib_datetime().hour
    if 6 <= current_hour < 22:
        return DAY_INTERVAL_SECONDS, f"Siang Mode (06:00 - 22:00 WIB) -> Interval: {DAY_INTERVAL_SECONDS // 60} Menit (Jam sekarang: {current_hour}:00 WIB)"
    else:
        return NIGHT_INTERVAL_SECONDS, f"Malam Mode (22:00 - 06:00 WIB) -> Interval: {NIGHT_INTERVAL_SECONDS // 60} Menit (Jam sekarang: {current_hour}:00 WIB)"

def main():
    """Fungsi eksekusi utama dengan arsitektur Watchdog 24/7."""
    print("\n" + "=" * 70)
    print("🏢 REAL ESTATE INTELLIGENCE BOT - FACEBOOK & GROQ AI")
    print(f"🤖 AI Engine     : Groq [{GROQ_MODEL}]")
    print(f"🕒 Waktu Mulai   : {get_wib_datetime().strftime('%Y-%m-%d %H:%M:%S WIB')}")
    print("=" * 70 + "\n")

    # 1. Validasi konfigurasi awal
    is_valid, errors, warnings = validate_config()
    for w in warnings:
        logger.warning(f"⚠️ PERINGATAN: {w}")

    if not is_valid:
        for err in errors:
            logger.error(f"❌ ERROR: {err}")
        print("\nMohon perbaiki konfigurasi pada file '.env' sebelum menjalankan bot!")
        sys.exit(1)

    # 2. Periksa status sesi login Facebook
    valid_sess, sess_msg = is_session_valid(COOKIE_FILE)
    if not valid_sess:
        logger.warning(f"⚠️ Sesi Facebook: {sess_msg}")
        logger.warning("Disarankan menjalankan 'python save_session.py' untuk login awal.")
    else:
        logger.info(f"✅ Sesi Facebook: {sess_msg}")

    consecutive_errors = 0
    max_consecutive_errors = 5

    logger.info("🚀 Watchdog bot 24/7 resmi aktif! Memulai siklus pertama...\n")

    # 3. Main Loop Watchdog 24/7
    while IS_RUNNING:
        cycle_start_time = time.time()
        logger.info("=" * 60)
        logger.info(f"▶️ MEMULAI SIKLUS SCRAPING: {get_wib_datetime().strftime('%Y-%m-%d %H:%M:%S WIB')}")
        logger.info("=" * 60)

        try:
            # Eksekusi scraping
            deals_found = run_scraper_cycle()
            consecutive_errors = 0

            elapsed = time.time() - cycle_start_time
            logger.info(
                f"🏁 Siklus selesai dalam {elapsed:.1f} detik. "
                f"Total {deals_found} listing baru berhasil dikirim ke Telegram!"
            )

        except Exception as e:
            consecutive_errors += 1
            logger.critical(
                f"❌ Terjadi kesalahan pada siklus bot ({consecutive_errors}/{max_consecutive_errors}): {e}",
                exc_info=True
            )

            # Jika terjadi error terus menerus (misal koneksi internet putus total)
            if consecutive_errors >= max_consecutive_errors:
                logger.warning("Terlalu banyak kegagalan beruntun. Menjalankan cooldown 10 menit...")
                time.sleep(600)
                consecutive_errors = 0
            else:
                # Jeda singkat sebelum retry
                time.sleep(60)

        if not IS_RUNNING:
            break

        # 4. Hitung Jeda Operasional (Siang / Malam)
        sleep_seconds, mode_info = get_operational_interval()
        next_cycle_epoch = time.time() + sleep_seconds
        try:
            from zoneinfo import ZoneInfo
            next_dt = datetime.fromtimestamp(next_cycle_epoch, tz=ZoneInfo("Asia/Jakarta"))
            next_cycle_str = next_dt.strftime('%H:%M:%S WIB')
        except Exception:
            next_cycle_str = datetime.fromtimestamp(next_cycle_epoch).strftime('%H:%M:%S')

        logger.info(f"⏰ Status Jadwal: {mode_info}")
        logger.info(f"💤 Bot tidur selama {sleep_seconds // 60} menit. Siklus berikutnya pada: {next_cycle_str}\n")

        # Tidur bertahap agar responsif terhadap sinyal keluar (CTRL+C)
        sleep_chunk = 5
        slept = 0
        while slept < sleep_seconds and IS_RUNNING:
            time.sleep(sleep_chunk)
            slept += sleep_chunk

    logger.info("👋 Bot telah berhenti secara bersih. Sampai jumpa!")

if __name__ == "__main__":
    main()
