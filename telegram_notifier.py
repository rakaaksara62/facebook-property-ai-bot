"""
================================================================================
TELEGRAM NOTIFICATION MODULE (TELEGRAM_NOTIFIER.PY)
================================================================================
Modul ini menangani perakitan format pesan dan pengiriman notifikasi ke Telegram:
1. Format Pesan Rapi & Singkat dengan HTML resmi Telegram (bukan Markdown).
2. Tautan aktif ganda:
   - 🔗 Buka Postingan Asli
   - 👥 Buka Grup Facebook
3. Unduh foto postingan ke memory buffer (io.BytesIO) menggunakan User-Agent browser,
   lalu upload multipart ('files={"photo": ...}') agar tidak dicekal CDN Facebook.
4. Fallback 3 Tingkat yang tangguh:
   - Tingkat 1: Kirim Foto Multipart + Caption HTML.
   - Tingkat 2: Kirim Teks HTML via sendMessage (jika foto gagal/tidak ada).
   - Tingkat 3: Kirim Teks Polos tanpa tag HTML (jika Telegram menolak entitas HTML).
================================================================================
"""

import io
import re
import logging
import requests
from config import TELEGRAM_TOKEN, CHAT_ID

logger = logging.getLogger("PropertyBot.Telegram")

# Header penyamaran browser untuk mengunduh gambar dari CDN Facebook (fbcdn.net / scontent)
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.facebook.com/",
}

def build_telegram_message(ai_summary: str, post_url: str, group_url: str) -> str:
    """
    Merakit pesan Telegram berformat HTML rapi dengan tautan aktif terpisah:
    - Postingan Asli
    - Grup Facebook
    """
    # Bersihkan link agar aman di atribut href
    safe_post_url = post_url.replace('"', '&quot;').replace("'", '&apos;') if post_url else ""
    safe_group_url = group_url.replace('"', '&quot;').replace("'", '&apos;') if group_url else ""

    header = "🚨 <b>HOT PROPERTY DEAL DETECTED</b> 🚨\n\n"
    footer = "\n\n"

    if safe_post_url and safe_post_url != safe_group_url:
        footer += f"🔗 <a href='{safe_post_url}'>Buka Postingan Asli</a>\n"
    else:
        footer += "🔗 <i>(Link postingan spesifik tidak tersedia)</i>\n"

    if safe_group_url:
        footer += f"👥 <a href='{safe_group_url}'>Buka Grup Facebook</a>"

    return f"{header}{ai_summary}{footer}"

def send_telegram_alert(ai_summary: str, post_url: str, group_url: str, photo_url: str | None = None) -> bool:
    """
    Fungsi utama pengiriman notifikasi properti ke Telegram dengan strategi 3-tingkat fallback.
    """
    if not TELEGRAM_TOKEN or not CHAT_ID:
        logger.error("TELEGRAM_TOKEN atau CHAT_ID belum disetel di .env!")
        return False

    message_html = build_telegram_message(ai_summary, post_url, group_url)

    # --------------------------------------------------------------------------
    # TINGKAT 1: Coba kirim FOTO via Multipart Upload Memory Buffer
    # --------------------------------------------------------------------------
    if photo_url:
        try:
            logger.info("Mengunduh foto listing ke memory buffer...")
            img_res = requests.get(photo_url, headers=BROWSER_HEADERS, timeout=15)
            
            # Pastikan respon gambar valid (> 1KB untuk menghindari 1x1 tracking pixel)
            if img_res.status_code == 200 and len(img_res.content) > 1024:
                # Batasan Telegram: caption sendPhoto maksimal 1024 karakter
                if len(message_html) <= 1024:
                    caption_text = message_html
                    needs_followup_text = False
                else:
                    caption_text = message_html[:1015] + "..."
                    needs_followup_text = True

                files = {
                    "photo": ("property.jpg", io.BytesIO(img_res.content), "image/jpeg")
                }
                data = {
                    "chat_id": CHAT_ID,
                    "caption": caption_text,
                    "parse_mode": "HTML"
                }

                url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
                resp = requests.post(url, data=data, files=files, timeout=25)

                if resp.status_code == 200:
                    logger.info("✅ Berhasil mengirimkan foto & caption listing ke Telegram!")
                    if needs_followup_text:
                        # Kirim sisa teks lengkap jika pesan melebihi batas caption 1024 karakter
                        send_text_message(message_html)
                    return True
                else:
                    logger.warning(
                        f"Gagal upload foto ke Telegram (Status {resp.status_code}): {resp.text}. "
                        "Beralih ke fallback teks HTML..."
                    )
            else:
                logger.warning(
                    f"Gagal mengunduh gambar dari CDN Facebook (HTTP {img_res.status_code}). "
                    "Beralih ke fallback teks HTML..."
                )
        except Exception as e:
            logger.warning(f"Terjadi kesalahan saat memproses gambar ({e}). Beralih ke fallback teks HTML...")

    # --------------------------------------------------------------------------
    # TINGKAT 2 & 3: Fallback ke Pengiriman Pesan Teks
    # --------------------------------------------------------------------------
    return send_text_message(message_html)

def send_text_message(message_html: str) -> bool:
    """
    Mengirim pesan teks ke Telegram:
    - Percobaan 1: Menggunakan format 'HTML'.
    - Percobaan 2: Jika gagal (misal parse error), hapus tag HTML dan kirim sebagai 'Teks Polos'.
    """
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    # Percobaan 1: Format HTML
    payload_html = {
        "chat_id": CHAT_ID,
        "text": message_html,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }

    try:
        res = requests.post(url, json=payload_html, timeout=15)
        if res.status_code == 200:
            logger.info("✅ Berhasil mengirimkan notifikasi teks HTML ke Telegram!")
            return True
        else:
            logger.warning(f"Gagal mengirim pesan HTML ({res.status_code}): {res.text}. Mencoba teks polos...")
    except Exception as e:
        logger.warning(f"Exception saat kirim pesan HTML: {e}. Mencoba teks polos...")

    # Percobaan 2: Fallback Teks Polos (Hapus semua tag HTML)
    try:
        clean_plain_text = re.sub(r'<[^>]+>', '', message_html)
        payload_plain = {
            "chat_id": CHAT_ID,
            "text": clean_plain_text,
            "disable_web_page_preview": False
        }
        res_plain = requests.post(url, json=payload_plain, timeout=15)
        if res_plain.status_code == 200:
            logger.info("✅ Berhasil mengirimkan notifikasi teks polos ke Telegram (Fallback Sukses)!")
            return True
        else:
            logger.error(f"❌ Gagal total mengirim pesan teks polos: {res_plain.text}")
            return False
    except Exception as err2:
        logger.error(f"❌ Gagal total mengirim notifikasi Telegram: {err2}")
        return False

