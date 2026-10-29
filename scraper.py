"""
================================================================================
FACEBOOK SCRAPER ENGINE (SCRAPER.PY)
================================================================================
Modul utama scraping Facebook Groups menggunakan Playwright Sync API murni:
1. Anti-deteksi handal tanpa dependensi rapuh 'playwright-stealth'.
2. Pengelolaan session login Facebook (fb_state.json) & deteksi checkpoint otomatis.
3. Pre-filter kata kunci dua tingkat (Property + Urgency) dengan regex boundary.
4. Ekstraksi terpisah: Link Postingan Asli, Link Grup Facebook, dan Foto Utama.
5. Pencegahan duplikasi deterministik menggunakan storage.py (seen_posts.json).
6. Randomized delay (1-30 detik) antar grup untuk keamanan akun Facebook.
================================================================================
"""

import os
import re
import time
import random
import logging
from playwright.sync_api import sync_playwright

from config import (
    FACEBOOK_GROUPS,
    COOKIE_FILE,
    PROPERTY_KEYWORDS,
    URGENCY_KEYWORDS,
    MIN_GROUP_DELAY,
    MAX_GROUP_DELAY,
    USE_PROXY,
    PROXY_SETTINGS
)
from storage import (
    load_seen_posts,
    save_seen_posts,
    get_post_identifier,
    save_browser_session
)
from ai_analyzer import analyze_property_post
from telegram_notifier import send_telegram_alert

logger = logging.getLogger("PropertyBot.Scraper")

def check_keyword_match(text: str, keywords: list[str]) -> bool:
    """
    Mengecek kecocokan kata kunci dengan proteksi regex word boundary untuk kata pendek.
    Mencegah false positive (misal: 'bu' tidak boleh cocok dengan 'ibu', 'kebun', atau 'dibuka').
    """
    text_lower = text.lower()
    for kw in keywords:
        kw_clean = kw.strip().lower()
        if not kw_clean:
            continue

        # Jika kata kunci pendek (<= 3 karakter, seperti 'bu' atau 'b.u'), gunakan boundary
        if len(kw_clean) <= 3:
            pattern = r'(?<!\w)' + re.escape(kw_clean) + r'(?!\w)'
            if re.search(pattern, text_lower):
                return True
        else:
            if kw_clean in text_lower:
                return True

    return False

def matches_two_tier_filter(text_content: str) -> tuple[bool, str]:
    """
    Filter Dua Tingkat:
    1. Wajib memuat minimal 1 kata kunci Properti (dijual, rumah, ruko, tanah, dll).
    2. Wajib memuat minimal 1 kata kunci Urgensi/Peluang (bu, butuh uang, lelang, murah, miring, under market).
    """
    has_property = check_keyword_match(text_content, PROPERTY_KEYWORDS)
    if not has_property:
        return False, "Tidak memuat kata kunci properti"

    has_urgency = check_keyword_match(text_content, URGENCY_KEYWORDS)
    if not has_urgency:
        return False, "Tidak memuat kata kunci urgensi/potensi deal"

    return True, "Lolos filter dua tingkat (Properti + Urgensi)"

def clean_facebook_url(url: str, fallback_group_url: str) -> str:
    """
    Membersihkan URL postingan Facebook dari query parameter pelacak (fbclid, __cft__, dll).
    """
    if not url:
        return fallback_group_url

    if url.startswith("/"):
        url = f"https://www.facebook.com{url}"

    # Bersihkan query parameter pelacak
    clean_url = url.split("?")[0].rstrip("/")

    # Pastikan format postingan valid
    if any(k in clean_url for k in ("/posts/", "/permalink/", "story_fbid")):
        return clean_url

    return fallback_group_url

def extract_post_elements(feed_elem, group_url: str) -> tuple[str, str, str | None]:
    """
    Mengekstrak data dari elemen DOM postingan Facebook:
    - post_url  : URL permalink postingan asli
    - post_id   : ID unik untuk deduplikasi
    - photo_url : URL gambar utama listing
    """
    text_content = feed_elem.inner_text().strip()

    # 1. Ekstrak Link Postingan Asli
    post_url = group_url
    try:
        link_elements = feed_elem.query_selector_all(
            'a[href*="/posts/"], a[href*="/permalink/"], a[href*="story_fbid="]'
        )
        for link in link_elements:
            href = link.get_attribute("href")
            if href:
                post_url = clean_facebook_url(href, group_url)
                if post_url != group_url:
                    break
    except Exception as err:
        logger.debug(f"Pencarian link postingan: {err}")

    # 2. Hasilkan ID Deterministik
    post_id = get_post_identifier(post_url if post_url != group_url else "", text_content)

    # 3. Ekstrak Foto Utama Listing
    photo_url = None
    try:
        img_elements = feed_elem.query_selector_all(
            'img[src*="scontent"], img[src*="fbcdn"]'
        )
        for img in img_elements:
            src = img.get_attribute("src")
            if not src:
                continue

            # Abaikan foto profil kecil, icon, dan emoji
            is_avatar_or_icon = any(x in src for x in (
                "p32x32", "p50x50", "p60x60", "p100x100", "s100x100",
                "emoji.php", "rsrc.php", "static.xx"
            ))
            if is_avatar_or_icon:
                continue

            # Periksa ukuran jika tersedia di atribut
            w_attr = img.get_attribute("width")
            if w_attr and w_attr.isdigit() and int(w_attr) < 150:
                continue

            photo_url = src
            break
    except Exception as err:
        logger.debug(f"Pencarian foto postingan: {err}")

    return post_url, post_id, photo_url

def run_scraper_cycle() -> int:
    """
    Menjalankan 1 siklus scraping lengkap pada seluruh grup Facebook target.
    Mengembalikan jumlah listing properti potensial yang berhasil ditemukan dan dikirim ke Telegram.
    """
    if not FACEBOOK_GROUPS:
        logger.error("Daftar FACEBOOK_GROUPS kosong! Mohon isi di file .env terlebih dahulu.")
        return 0

    seen_posts = load_seen_posts()
    logger.info(f"Riwayat seen_posts dimuat: {len(seen_posts)} entri tersimpan.")

    deals_found = 0
    total_groups = len(FACEBOOK_GROUPS)

    # Konfigurasi Chromium Playwright (Anti-Detection murni tanpa playwright-stealth)
    launch_options = {
        "headless": True,
        "args": [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--disable-dev-shm-usage",
            "--disable-notifications",
            "--no-first-run",
            "--no-default-browser-check"
        ]
    }

    if USE_PROXY and PROXY_SETTINGS:
        launch_options["proxy"] = PROXY_SETTINGS

    with sync_playwright() as p:
        browser = p.chromium.launch(**launch_options)

        context_options = {
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "viewport": {"width": 1280, "height": 800},
            "device_scale_factor": 1,
            "locale": "id-ID",
            "timezone_id": "Asia/Jakarta"
        }

        # Muat sesi Facebook jika berkas fb_state.json tersedia
        if os.path.exists(COOKIE_FILE):
            logger.info(f"Memuat sesi autentikasi Facebook dari '{COOKIE_FILE}'...")
            context_options["storage_state"] = COOKIE_FILE
        else:
            logger.warning(
                f"Berkas '{COOKIE_FILE}' tidak ditemukan! "
                "Sangat disarankan menjalankan 'python save_session.py' agar bot tidak terhalang login wall."
            )

        context = browser.new_context(**context_options)

        # Injeksi script anti-deteksi navigator
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['id-ID', 'id', 'en-US', 'en'] });
        """)

        page = context.new_page()

        for idx_group, group_url in enumerate(FACEBOOK_GROUPS, 1):
            logger.info(f"[{idx_group}/{total_groups}] Mengakses grup target: {group_url}")

            try:
                page.goto(group_url, wait_until="domcontentloaded", timeout=45000)
                time.sleep(4)

                # Deteksi jika Facebook mengarahkan ke halaman login atau checkpoint
                current_url = page.url.lower()
                if "login" in current_url or "checkpoint" in current_url:
                    logger.error(
                        f"⚠️ TERDETEKSI LOGIN/CHECKPOINT WALL pada grup {group_url}! "
                        "Sesi login Facebook kemungkinan sudah kadaluarsa. "
                        "Silakan perbarui file 'fb_state.json' dengan menjalankan 'python save_session.py'."
                    )
                    break

                # Scroll bertahap untuk memicu pemuatan postingan di feed Facebook
                for _ in range(2):
                    page.evaluate("window.scrollBy(0, 700)")
                    time.sleep(2)

                # Ambil kontainer postingan
                feed_selectors = [
                    'div[role="feed"] > div',
                    'div[role="article"]',
                    'div[data-pagelet*="FeedUnit"]'
                ]
                feed_elements = []
                for sel in feed_selectors:
                    elements = page.query_selector_all(sel)
                    if elements:
                        feed_elements = elements
                        break

                logger.info(f"Ditemukan {len(feed_elements)} blok feed di grup.")

                # Batasi pemrosesan maksimal 6 postingan terbaru per grup agar efisien
                for elem in feed_elements[:6]:
                    try:
                        text_content = elem.inner_text().strip()
                        if len(text_content) < 40:
                            continue

                        # 1. Terapkan Pre-filter Kata Kunci Lokal (Tingkat 1)
                        is_match, reason = matches_two_tier_filter(text_content)
                        if not is_match:
                            continue

                        # 2. Ekstraksi Data Postingan (URL, ID, Foto)
                        post_url, post_id, photo_url = extract_post_elements(elem, group_url)

                        # 3. Cek Deduplikasi (Anti-Duplicate)
                        if post_id in seen_posts:
                            logger.debug(f"Postingan ID [{post_id}] sudah pernah diproses. Melewati...")
                            continue

                        logger.info(
                            f"🎯 Listing Menarik Terdeteksi! [ID: {post_id}] "
                            f"Post URL: {post_url} | Foto: {'Ada' if photo_url else 'Tidak Ada'}"
                        )

                        # 4. Analisis AI Tingkat 2 (Groq 'openai/gpt-oss-120b')
                        ai_summary = analyze_property_post(text_content)
                        if not ai_summary:
                            logger.warning(f"Gagal mendapatkan ringkasan AI untuk post {post_id}. Melewati...")
                            continue

                        # 5. Kirim Notifikasi ke Telegram
                        success = send_telegram_alert(
                            ai_summary=ai_summary,
                            post_url=post_url,
                            group_url=group_url,
                            photo_url=photo_url
                        )

                        if success:
                            deals_found += 1
                            seen_posts.add(post_id)
                            save_seen_posts(seen_posts)
                            logger.info(f"✅ Listing [{post_id}] berhasil dicatat & disimpan ke seen_posts.json.")
                            time.sleep(2)

                    except Exception as elem_err:
                        logger.warning(f"Error saat memproses satu postingan: {elem_err}")

            except Exception as grp_err:
                logger.error(f"Error saat membuka grup {group_url}: {grp_err}")

            # 6. Randomized Delay Antar Grup (1 - 30 detik)
            if idx_group < total_groups:
                delay = random.uniform(MIN_GROUP_DELAY, MAX_GROUP_DELAY)
                logger.info(f"⏳ Jeda acak {delay:.1f} detik sebelum memeriksa grup berikutnya...")
                time.sleep(delay)

        # Perbarui sesi cookies jika browser aktif
        try:
            save_browser_session(context, COOKIE_FILE)
        except Exception as sess_err:
            logger.debug(f"Penyimpanan sesi browser: {sess_err}")

        browser.close()

    return deals_found

