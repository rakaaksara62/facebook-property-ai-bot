"""
================================================================================
STORAGE & CACHE MANAGER (STORAGE.PY)
================================================================================
Modul ini mengelola penyimpanan permanen bot:
1. seen_posts.json : Riwayat ID postingan yang sudah diproses agar tidak duplikat.
                     Menggunakan penulisan atomik (.tmp -> rename) & batas maks 5000 item.
2. fb_state.json   : Sesi login & cookie browser Facebook dari Playwright.
3. Hashing Post ID : Menggunakan SHA-256 deterministik untuk postingan tanpa ID url,
                     menghindari bug hash() bawaan Python yang berubah setiap restart.
================================================================================
"""

import os
import json
import re
import hashlib
import logging
from config import COOKIE_FILE, SEEN_POSTS_FILE, MAX_SEEN_POSTS

logger = logging.getLogger("PropertyBot.Storage")

def get_post_identifier(post_url: str, text_content: str) -> str:
    """
    Menghasilkan ID unik deterministik untuk postingan Facebook.
    1. Mencoba mengekstrak ID numerik asli dari URL postingan (/posts/<id> atau story_fbid).
    2. Jika tidak ada, membuat hash SHA-256 dari teks postingan.
    Ini menjamin bahwa ID post tetap konsisten meskipun script di-restart!
    """
    if post_url:
        # Coba ekstrak ID dari URL /posts/123456789 atau /permalink/123456789
        match = re.search(r'/(?:posts|permalink)/(\d+)', post_url)
        if match:
            return f"fb_{match.group(1)}"
        
        # Coba ekstrak dari story_fbid parameter
        match_fbid = re.search(r'story_fbid=(\d+)', post_url)
        if match_fbid:
            return f"fb_{match_fbid.group(1)}"

    # Fallback: Buat SHA-256 dari teks postingan (bersihkan spasi berlebih)
    normalized_text = " ".join(text_content.strip().split())
    text_sample = normalized_text[:300].encode('utf-8')
    sha_hash = hashlib.sha256(text_sample).hexdigest()[:16]
    return f"hash_{sha_hash}"

def load_seen_posts() -> set:
    """
    Membaca riwayat seen_posts.json dan mengembalikan dalam bentuk set Python.
    Jika file tidak ada atau rusak, mengembalikan set kosong tanpa error.
    """
    if not os.path.exists(SEEN_POSTS_FILE):
        return set()

    try:
        with open(SEEN_POSTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                # Konversi semua entri ke string
                return set(str(item) for item in data)
            elif isinstance(data, dict):
                return set(str(k) for k in data.keys())
    except Exception as e:
        logger.error(f"Gagal membaca '{SEEN_POSTS_FILE}' (file mungkin korup): {e}")

    return set()

def save_seen_posts(seen_set: set, max_items: int = MAX_SEEN_POSTS) -> bool:
    """
    Menyimpan seen_posts secara atomik (.tmp -> replace).
    Menjaga ukuran file tetap optimal dengan membatasi jumlah maksimal item terbaru.
    """
    try:
        # Batasi ukuran jika melebihi batas maksimal agar tidak membengkak
        posts_list = list(seen_set)
        if len(posts_list) > max_items:
            posts_list = posts_list[-max_items:]

        temp_file = f"{SEEN_POSTS_FILE}.tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(posts_list, f, indent=2, ensure_ascii=False)

        # Atomic replacement di filesystem Windows & POSIX
        if os.path.exists(temp_file):
            os.replace(temp_file, SEEN_POSTS_FILE)
        return True
    except Exception as e:
        logger.error(f"Gagal menyimpan ke '{SEEN_POSTS_FILE}': {e}")
        return False

def is_session_valid(cookie_path: str = COOKIE_FILE) -> tuple[bool, str]:
    """
    Memeriksa apakah berkas fb_state.json ada dan berisi cookies Facebook.
    """
    if not os.path.exists(cookie_path):
        return False, f"File sesi '{cookie_path}' tidak ditemukan."

    try:
        with open(cookie_path, "r", encoding="utf-8") as f:
            state = json.load(f)
            cookies = state.get("cookies", [])
            if not cookies:
                return False, f"File sesi '{cookie_path}' tidak memiliki data cookie."
            
            # Cek apakah ada cookie esensial Facebook (c_user atau xs)
            has_auth = any(c.get("name") in ("c_user", "xs", "fr") for c in cookies)
            if not has_auth:
                return False, "Cookie sesi tidak memuat data login Facebook (c_user/xs)."
            
            return True, f"Sesi valid dengan {len(cookies)} cookies tersimpan."
    except Exception as e:
        return False, f"Format JSON sesi '{cookie_path}' rusak: {e}"

def save_browser_session(context, cookie_path: str = COOKIE_FILE) -> bool:
    """
    Menyimpan context storage state Playwright ke file sesi fb_state.json secara aman.
    """
    try:
        temp_cookie_file = f"{cookie_path}.tmp"
        context.storage_state(path=temp_cookie_file)
        if os.path.exists(temp_cookie_file):
            os.replace(temp_cookie_file, cookie_path)
            logger.info(f"Sesi login Facebook berhasil diperbarui di '{cookie_path}'.")
            return True
    except Exception as e:
        logger.error(f"Gagal menyimpan storage state ke '{cookie_path}': {e}")
    return False

