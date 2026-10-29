"""
================================================================================
ALL-IN-ONE SYSTEM DIAGNOSTIC (TEST_SYSTEM.PY)
================================================================================
Script ini digunakan untuk menguji kesehatan seluruh komponen bot sebelum
dijalankan dalam mode 24/7 produksi:
1. Konfigurasi .env (Keys, Token, Chat ID, Groups)
2. Sesi Cookies Facebook (fb_state.json)
3. Groq API & Model 'openai/gpt-oss-120b'
4. Telegram Bot API (Kirim pesan tes)
5. Pre-filter Kata Kunci Lokal (Filter Tingkat 1)
================================================================================
"""

import os
import sys
import time
import json
import requests

# Pastikan output konsol UTF-8
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from config import (
    validate_config,
    GROQ_API_KEY,
    GROQ_MODEL,
    TELEGRAM_TOKEN,
    CHAT_ID,
    FACEBOOK_GROUPS,
    COOKIE_FILE,
    SEEN_POSTS_FILE,
    PROPERTY_KEYWORDS,
    URGENCY_KEYWORDS
)
from storage import is_session_valid, load_seen_posts
from scraper import matches_two_tier_filter
from ai_analyzer import analyze_property_post

def run_diagnostics():
    print("\n" + "=" * 70)
    print("🔍 SISTEM DIAGNOSTIK BOT PROPERTI FACEBOOK")
    print("=" * 70 + "\n")

    passed_count = 0
    total_tests = 5

    # --------------------------------------------------------------------------
    # 1. PENGUJIAN KONFIGURASI (.ENV)
    # --------------------------------------------------------------------------
    print("👉 [1/5] Memeriksa Berkas Konfigurasi (.env)...")
    is_valid, errors, warnings = validate_config()

    if is_valid:
        print("   ✅ Format konfigurasi valid.")
        print(f"   ℹ️ Terdeteksi {len(FACEBOOK_GROUPS)} Grup Facebook target.")
        passed_count += 1
    else:
        for err in errors:
            print(f"   ❌ {err}")
    for warn in warnings:
        print(f"   ⚠️ {warn}")

    print("-" * 50)

    # --------------------------------------------------------------------------
    # 2. PENGUJIAN SESI FACEBOOK (fb_state.json)
    # --------------------------------------------------------------------------
    print("👉 [2/5] Memeriksa Berkas Sesi Facebook (fb_state.json)...")
    valid_sess, sess_msg = is_session_valid(COOKIE_FILE)
    if valid_sess:
        print(f"   ✅ {sess_msg}")
        passed_count += 1
    else:
        print(f"   ⚠️ {sess_msg}")
        print("   👉 Jalankan 'python save_session.py' untuk membuat sesi baru.")

    print("-" * 50)

    # --------------------------------------------------------------------------
    # 3. PENGUJIAN PRE-FILTER KATA KUNCI (TINGKAT 1)
    # --------------------------------------------------------------------------
    print("👉 [3/5] Menguji Logika Pre-Filter Kata Kunci (Tingkat 1)...")
    
    # Contoh postingan valid (properti + urgensi)
    sample_valid = "BU CEPAT! Jual rumah tua hitung tanah di Jakarta Barat, SHM luas 100m harga murah."
    match_val, reason_val = matches_two_tier_filter(sample_valid)

    # Contoh postingan non-properti / non-urgensi
    sample_invalid = "Dicari pembantu rumah tangga harian di kebun jeruk, butuh segera."
    match_inval, reason_inval = matches_two_tier_filter(sample_invalid)

    if match_val and not match_inval:
        print("   ✅ Logika Filter Dua Tingkat bekerja sempurna!")
        print(f"      - Sampel BU Rumah: LOLOS ({reason_val})")
        print(f"      - Sampel Bukan Properti: DITOLAK ({reason_inval})")
        passed_count += 1
    else:
        print("   ❌ Logika Filter tidak bekerja sesuai harapan.")

    print("-" * 50)

    # --------------------------------------------------------------------------
    # 4. PENGUJIAN GROQ API & MODEL 'openai/gpt-oss-120b' (TINGKAT 2)
    # --------------------------------------------------------------------------
    print(f"👉 [4/5] Menguji Koneksi Groq AI (Model: {GROQ_MODEL})...")
    if not GROQ_API_KEY:
        print("   ❌ GROQ_API_KEY kosong di .env. Pengujian AI dilewati.")
    else:
        try:
            start_t = time.time()
            test_post = (
                "JUAL CEPAT BU! Rumah 2 lantai di Kebon Jeruk Jakarta Barat. "
                "LT 120m, LB 180m, SHM, IMB. Dekat tol & mall. Harga 1.8M nego. WA 081234567890."
            )
            ai_result = analyze_property_post(test_post)
            duration = round(time.time() - start_t, 2)

            if ai_result:
                print(f"   ✅ Groq AI Merespon Sukses dalam {duration} detik!")
                print(f"   📝 Output Ringkasan AI:\n{ai_result[:180]}...\n")
                passed_count += 1
            else:
                print("   ❌ Groq AI tidak mengembalikan ringkasan yang valid.")
        except Exception as e:
            print(f"   ❌ Error saat menghubungi Groq: {e}")

    print("-" * 50)

    # --------------------------------------------------------------------------
    # 5. PENGUJIAN TELEGRAM BOT API
    # --------------------------------------------------------------------------
    print("👉 [5/5] Menguji Pengiriman Notifikasi Telegram...")
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("   ❌ TELEGRAM_TOKEN atau CHAT_ID belum disetel di .env.")
    else:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            test_payload = {
                "chat_id": CHAT_ID,
                "text": "🛠️ <b>DIAGNOSTIK SISTEM BERHASIL</b>\nKoneksi Telegram Bot API berfungsi dengan sangat baik!",
                "parse_mode": "HTML"
            }
            res = requests.post(url, json=test_payload, timeout=10)
            if res.status_code == 200:
                print("   ✅ Pesan verifikasi berhasil terkirim ke Telegram!")
                passed_count += 1
            else:
                print(f"   ❌ Gagal kirim pesan ke Telegram ({res.status_code}): {res.text}")
        except Exception as e:
            print(f"   ❌ Gagal menghubungi Telegram API: {e}")

    # --------------------------------------------------------------------------
    # RINGKASAN HASIL
    # --------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print(f"📊 SKOR DIAGNOSTIK: {passed_count}/{total_tests} PENGUJIAN LOLOS")
    if passed_count == total_tests:
        print("🎉 STATUS: SISTEM SIAP PRODUKSI (PRODUCTION READY / SIAP JUAL)!")
        print("Jalankan bot sekarang dengan perintah: python main_bot.py")
    else:
        print("⚠️ STATUS: ADA BEBERAPA KOMPONEN YANG MEMERLUKAN PERHATIAN.")
        print("Silakan periksa pesan kegagalan di atas sebelum menjalankan bot.")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    run_diagnostics()

