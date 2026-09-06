import os
import time
import json
import requests
import schedule
from dotenv import load_dotenv
from google import genai
from playwright.sync_api import sync_playwright

# --- LOAD ENVIRONMENT VARIABLES ---
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Ambil API key utama
RAW_KEYS = os.getenv("GEMINI_API_KEYS", os.getenv("GEMINI_API_KEY", ""))
API_KEY = [k.strip().strip('"').strip("'") for k in RAW_KEYS.split(",") if k.strip()][0]

if not API_KEY:
    raise ValueError("❌ Tidak ada GEMINI_API_KEY yang ditemukan di file .env!")

# Inisialisasi client tunggal
client = genai.Client(api_key=API_KEY)
print("🔑 Client Gemini berhasil diinisialisasi.")

# Model target secara hierarki (Fallback Cascade)
AVAILABLE_MODELS = [
    "gemini-2.5-flash",        # Utama: Cepat, stabil, kuota longgar
    "gemini-2.5-flash-lite",   # Cadangan 1: Sangat ringan, throughput tinggi
    "gemini-3.6-flash",         # Cadangan 2: Analisis mendalam
    "gemini-3.5-flash"
]
CURRENT_MODEL_INDEX = 0

def get_current_model():
    """Mengambil model aktif saat ini."""
    return AVAILABLE_MODELS[CURRENT_MODEL_INDEX]

def switch_to_next_model():
    """Beralih ke model berikutnya jika model aktif mengalami limit atau error."""
    global CURRENT_MODEL_INDEX
    CURRENT_MODEL_INDEX = (CURRENT_MODEL_INDEX + 1) % len(AVAILABLE_MODELS)
    print(f"🔄 Berpindah ke model cadangan: [{AVAILABLE_MODELS[CURRENT_MODEL_INDEX]}]")

# ------------------------------------------------------------------
# 📌 LIST GRUP TARGET JAKARTA BARAT
# ------------------------------------------------------------------
ENV_GROUPS = os.getenv("GROUP_URLS")
if ENV_GROUPS:
    TARGET_GROUPS = [g.strip() for g in ENV_GROUPS.split(",") if g.strip()]
else:
    TARGET_GROUPS = [
        "https://www.facebook.com/groups/646266199809882",
    ]

HISTORY_FILE = "sent_posts.json"

PROPERTY_KEYWORDS = [
    "rumah", "tanah", "ruko", "dijual", "jual", "bu", "butuh uang", "cepat", 
    "kepepet", "shm", "hgb", "ajb", "over kredit", "take over", "nego", "miliar", 
    "milyar", "juta", "jt", "kavling", "lt", "lb", "luas", "hitung tanah",
    "jakbar", "jakarta barat", "cengkareng", "kalideres", "kebon jeruk", 
    "puri", "puri indah", "kembangan", "meruya", "grogol", "petamburan", 
    "tanjung duren", "palmerah", "tamansari", "tambora", "daan mogot", 
    "kedoya", "joglo", "bojong indah", "citra garden", "taman palem",
    "taman ratu", "green garden", "pos pengumben", "intercon"
]

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(list(history), f)

def is_potential_property_text(text):
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in PROPERTY_KEYWORDS)

def analyze_post_with_gemini(post_text):
    """
    Menganalisis listing properti dengan sistem Model Fallback Cascade.
    """
    prompt = f"""
    Kamu adalah seorang Investor Properti Senior & Finder Hidden Gem yang berfokus di area JAKARTA BARAT.
    Tugasmu menganalisis postingan Facebook dan HANYA meloloskan properti yang berstatus HIDDEN GEM / BUTUH UANG (BU) / DI BAWAH HARGA PASAR di wilayah Jakarta Barat dan sekitarnya.

    Berikut teks postingannya:
    \"\"\"{post_text}\"\"\"

    ATURAN EVALUASI & FILTER:
    1. VALIDASI LOKASI: Prioritaskan area Jakarta Barat (Cengkareng, Kalideres, Kebon Jeruk, Kembangan, Puri, Meruya, Tanjung Duren, Grogol, Palmerah, Joglo, Daan Mogot, Tambora, Tamansari). Jika lokasi tidak jelas/di luar Jakbar, beri score < 5 atau "is_property": false.
    2. TOLAK SPAM/DEVELOPER: Iklan sales rumah baru, promo KPR komersil, brosur subsidi luar kota -> score < 5 atau "is_property": false.
    3. DETEKSI LEGALITAS: Ambil status surat legalitas (SHM, HGB, AJB, Girik, atau Tidak Disebutkan).
    4. KRITERIA SKOR TINGGI (7 - 10): Owner langsung BU, rumah tua hitung tanah, take over kepepet, peluang flipping tinggi.
    5. ANALISIS INVESTOR: Tulis analisis tajam maksimal 3 kalimat (alasan margin, cash flow sewa, atau bargain price).

    Format output WAJIB HANYA JSON murni (tanpa markdown fences):
    {{
      "is_property": true,
      "score": 8,
      "jenis": "Rumah",
      "lokasi": "Nama kawasan/daerah di Jakarta Barat",
      "legalitas": "SHM / HGB / AJB / Tidak Disebutkan",
      "harga": "Harga tertera atau Tidak dicantumkan",
      "alasan_menarik": "Analisis tajam investor (maksimal 3 kalimat)"
    }}
    """

    # Coba model-model yang tersedia secara berurutan
    for _ in range(len(AVAILABLE_MODELS)):
        active_model = get_current_model()
        print(f"🤖 Mengirim analisis ke Gemini menggunakan model [{active_model}]...")

        try:
            response = client.models.generate_content(
                model=active_model,
                contents=prompt
            )
            raw_text = response.text.strip()
            clean_json = raw_text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_json)

        except Exception as e:
            err_msg = str(e)
            print(f"❌ Model [{active_model}] kendala: {err_msg[:200]}")
            
            # Jika terkena rate-limit / model overload / model unavail
            if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg or "503" in err_msg or "404" in err_msg:
                switch_to_next_model()
                time.sleep(2)
            else:
                time.sleep(1)

    return None

def send_telegram_ai_alert(ai_data, raw_text, post_url, group_url, photo_url=None):
    clean_raw = raw_text[:280].replace("*", "").replace("_", "").replace("`", "")
    alasan = str(ai_data.get('alasan_menarik', '-')).replace("*", "").replace("_", "")

    caption_message = (
        f"💎 *HIDDEN GEM JAKARTA BARAT DITEMUKAN!* 💎\n\n"
        f"⭐ *Skor Potensi:* `{ai_data.get('score')}/10`\n"
        f"🏠 *Jenis:* {ai_data.get('jenis', 'Unknown')}\n"
        f"📍 *Lokasi:* {ai_data.get('lokasi', 'Unknown')}\n"
        f"📄 *Legalitas:* {ai_data.get('legalitas', 'Tidak Disebutkan')}\n"
        f"💰 *Harga:* {ai_data.get('harga', 'Unknown')}\n\n"
        f"🧠 *Analisis Investor (AI):*\n_{alasan}_\n\n"
        f"📝 *Postingan Asli:*\n{clean_raw}...\n\n"
        f"🔗 [Lihat Postingan Spesifik]({post_url})\n"
        f"🌐 [Buka Grup Facebook]({group_url})"
    )
    
    # 1. Kirim foto jika ada
    if photo_url:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
            payload = {
                "chat_id": CHAT_ID,
                "photo": photo_url,
                "caption": caption_message,
                "parse_mode": "Markdown"
            }
            res = requests.post(url, json=payload, timeout=15)
            if res.status_code == 200:
                return
            else:
                print(f"⚠️ Gagal kirim foto ({res.status_code}). Beralih ke teks biasa...")
        except Exception as e:
            print(f"⚠️ Exception kirim foto: {e}. Beralih ke teks biasa...")

    # 2. Kirim pesan teks Markdown
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "text": caption_message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False
        }
        res = requests.post(url, json=payload, timeout=15)
        
        # 3. Fallback jika parsing Markdown bermasalah
        if res.status_code != 200:
            plain_text = caption_message.replace("*", "").replace("_", "").replace("`", "")
            payload_plain = {
                "chat_id": CHAT_ID,
                "text": plain_text,
                "disable_web_page_preview": False
            }
            requests.post(url, json=payload_plain, timeout=15)
    except Exception as e:
        print(f"❌ Error fatal kirim ke Telegram: {e}")

def run_property_bot():
    print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] 🚀 Memulai Pengecekan Rutin ({len(TARGET_GROUPS)} Grup Target)...")
    sent_history = load_history()
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu"
                ]
            )
            context = browser.new_context(
                storage_state="fb_state.json",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            for idx, current_group_url in enumerate(TARGET_GROUPS, 1):
                print(f"🔍 [{idx}/{len(TARGET_GROUPS)}] Mengakses Grup: {current_group_url}")
                
                try:
                    page.goto(current_group_url, timeout=90000)
                    time.sleep(6)
                    
                    # Scroll feed untuk memuat postingan terbaru
                    for _ in range(3):
                        page.mouse.wheel(0, 1500)
                        time.sleep(3)
                    
                    post_elements = page.query_selector_all('div[role="feed"] > div, div[data-ad-preview="message"]')
                    extracted_posts = []
                    
                    for post_el in post_elements:
                        try:
                            msg_el = post_el.query_selector('div[data-ad-preview="message"], div[dir="auto"]')
                            raw_text = msg_el.inner_text().strip() if msg_el else post_el.inner_text().strip()

                            cleaned_lines = [
                                line.strip() for line in raw_text.split('\n') 
                                if line.strip().lower() != 'facebook' and len(line.strip()) > 3
                            ]
                            text_content = "\n".join(cleaned_lines)
                            
                            # Batasi teks maksimal 1.500 karakter untuk membuang noise DOM
                            text_content = text_content[:1500].strip()
                            
                            # Pra-filter lokal kata kunci
                            if len(text_content) < 40 or not is_potential_property_text(text_content):
                                continue
                            
                            link_el = post_el.query_selector('a[href*="/groups/"][href*="/posts/"], a[href*="permalink"]')
                            post_url = link_el.get_attribute('href') if link_el else current_group_url
                            if post_url and not post_url.startswith("http"):
                                post_url = f"https://www.facebook.com{post_url}"
                                
                            img_el = post_el.query_selector('img[src*="scontent"], img[src*="fbcdn"]')
                            photo_url = None
                            if img_el:
                                src = img_el.get_attribute('src')
                                if src and "emoji" not in src and "t39.30808-1" not in src:
                                    photo_url = src
                            
                            extracted_posts.append({
                                "text": text_content,
                                "url": post_url,
                                "group_url": current_group_url,
                                "photo": photo_url
                            })
                        except Exception:
                            continue

                    # Proses analisis
                    new_alerts_count = 0
                    for item in extracted_posts:
                        line_clean = item["text"]
                        post_id = str(hash(line_clean))
                        
                        if post_id in sent_history:
                            continue
                        
                        ai_result = analyze_post_with_gemini(line_clean)
                        if ai_result and ai_result.get("is_property"):
                            if ai_result.get("score", 0) >= 7:
                                print(f"🎯 HIDDEN GEM FOUND (Skor {ai_result.get('score')}): Mengirim ke Telegram...")
                                send_telegram_ai_alert(ai_result, line_clean, item["url"], item["group_url"], item["photo"])
                                new_alerts_count += 1
                        
                        sent_history.add(post_id)
                        save_history(sent_history)
                        
                        # Jeda 5 detik agar laju RPM tetap dingin di sisi Google
                        time.sleep(5)
                    
                    print(f"✅ Selesai mengecek Grup {idx}. Ditemukan: {new_alerts_count} Hidden Gem.")
                    
                except Exception as e:
                    print(f"⚠️ Gagal mengecek grup {current_group_url}: {e}")
                    continue

            browser.close()
            print(f"🎉 Pengecekan seluruh {len(TARGET_GROUPS)} grup selesai!")

    except Exception as e:
        print(f"❌ Terjadi kesalahan utama pada scraping: {e}")

def safe_job():
    """Wrapper pelindung agar jadwal rutin tidak terputus bila terjadi error."""
    try:
        run_property_bot()
    except Exception as e:
        print(f"⚠️ Kesalahan saat eksekusi rutin: {e}")

if __name__ == "__main__":
    safe_job()
    schedule.every(1).hours.do(safe_job)
    
    print(f"\n🤖 BOT HIDDEN GEM PROPERTI JAKARTA BARAT ({len(TARGET_GROUPS)} GRUP) AKTIF 24/7...")
    while True:
        schedule.run_pending()
        time.sleep(10)