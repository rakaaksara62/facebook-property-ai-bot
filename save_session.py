"""
================================================================================
FACEBOOK SESSION SAVER (SAVE_SESSION.PY)
================================================================================
Script interaktif untuk login manual ke akun Facebook dan menyimpan sesi cookies
ke dalam berkas 'fb_state.json'.

Keunggulan:
- Tidak lagi menggunakan batas waktu kaku 60 detik (fleksibel untuk 2FA / OTP).
- Cukup tekan ENTER di terminal setelah Anda berhasil masuk ke beranda Facebook.
- Memvalidasi keberadaan cookie otentikasi Facebook (c_user/xs) sebelum menyimpan.
================================================================================
"""

import os
import sys
import json
from playwright.sync_api import sync_playwright

COOKIE_FILE = "fb_state.json"

# Pastikan output UTF-8
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

def login_and_save_session():
    print("\n" + "=" * 65)
    print("🔑 FACEBOOK INTERACTIVE SESSION SAVER")
    print("=" * 65)
    print("1. Jendela browser Chromium akan terbuka otomatis.")
    print("2. Silakan login ke akun Facebook Anda (termasuk verifikasi 2FA jika ada).")
    print("3. Setelah berhasil masuk ke Beranda Facebook, KEMBALI KE TERMINAL INI")
    print("   dan TEKAN ENTER untuk menyimpan sesi cookies.")
    print("=" * 65 + "\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-default-browser-check"
            ]
        )
        
        context_args = {
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "viewport": {"width": 1280, "height": 800},
            "locale": "id-ID"
        }

        # Muat sesi lama jika ada untuk memperpanjang
        if os.path.exists(COOKIE_FILE):
            try:
                context_args["storage_state"] = COOKIE_FILE
                print(f"ℹ️ Memuat sesi sebelumnya dari '{COOKIE_FILE}'...")
            except Exception:
                pass

        context = browser.new_context(**context_args)
        page = context.new_page()

        print("🌐 Membuka Facebook...")
        page.goto("https://www.facebook.com", timeout=60000)

        # Tunggu konfirmasi dari pengguna di terminal
        print("\n👉 SILAKAN LOGIN DI JENDELA BROWSER.")
        try:
            input("👉 Jika sudah berhasil masuk ke Facebook, TEKAN [ENTER] DI SINI...")
        except EOFError:
            pass

        # Verifikasi cookie sesi
        cookies = context.cookies()
        has_auth = any(c.get("name") in ("c_user", "xs", "fr") for c in cookies)

        # Simpan sesi
        temp_file = f"{COOKIE_FILE}.tmp"
        context.storage_state(path=temp_file)
        if os.path.exists(temp_file):
            os.replace(temp_file, COOKIE_FILE)

        print("\n" + "-" * 50)
        if has_auth:
            print(f"🎉 SUKSES! Sesi login terverifikasi dan disimpan ke '{COOKIE_FILE}'.")
            print(f"📊 Jumlah cookie tersimpan: {len(cookies)} item.")
            print("🚀 Anda sekarang dapat menjalankan bot utama: 'python main_bot.py'")
        else:
            print(f"⚠️ PERINGATAN: Sesi disimpan ke '{COOKIE_FILE}', namun cookie otentikasi")
            print("   (c_user/xs) tidak terdeteksi. Pastikan Anda benar-benar login.")
        print("-" * 50 + "\n")

        browser.close()

if __name__ == "__main__":
    login_and_save_session()
