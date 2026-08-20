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

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# ------------------------------------------------------------------
# 📌 BISA INPUT BANYAK GRUP DI SINI (LIST GRUP TARGET)
# Kamu bisa isi via .env (dipisah koma) atau isi manual di dalam list ini
# ------------------------------------------------------------------
ENV_GROUPS = os.getenv("GROUP_URLS")
if ENV_GROUPS:
    TARGET_GROUPS = [g.strip() for g in ENV_GROUPS.split(",") if g.strip()]
else:
    # JIKA TIDAK PAKAI .ENV, TULIS DAFTAR LINK GRUP DI SINI:
    TARGET_GROUPS = [
        "https://www.facebook.com/groups/646266199809882",
        # "https://www.facebook.com/groups/LOKASI_GRUP_KEDUA",
        # "https://www.facebook.com/groups/LOKASI_GRUP_KETIGA",
    ]

HISTORY_FILE = "sent_posts.json"

# Inisialisasi Gemini Client
client = genai.Client(api_key=GEMINI_API_KEY)

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(list(history), f)

def analyze_post_with_gemini(post_text):
    """
    Mengirim teks postingan ke Gemini AI dengan instruksi FILTER KETAT.
    """
    prompt = f"""
    Kamu adalah seorang Investor Properti Senior & Finder Hidden Gem berpengalaman.
    Tugas utamamu adalah mendeteksi HANYA properti yang tergolong HIDDEN GEM / BUTUH UANG / DI BAWAH HARGA PASAR dari postingan grup Facebook.

    Berikut teks postingannya:
    \"\"\"{post_text}\"\"\"

    ATURAN FILTER SUPER KETAT:
    1. TOLAK BLA-BLA SALES / DEVELOPER: Jika postingan adalah iklan perumahan subsidi, promo rumah baru kpr developer, brosur sales, rumah indent, atau promo DP 0% dari perumahan baru -> Set "is_property": false ATAU berikan "score": < 5.
    2. CARI HIDDEN GEM: Hanya berikan "score" 7 sampai 10 jika postingan berasal dari OWNER LANGSUNG / RUMAH SECOND MURAH / TAKE OVER OVER KREDIT KEPEPET / JUAL BU / HARGA DI BAWAH PASAR.
    3. TULIS ALASAN PEMILIHAN YANG PERSUASIF: Jika memenuhi syarat Hidden Gem, tuliskan alasan pemilihan properti tersebut dengan sangat tajam dan profesional (misal: analisis rasio harga, poin kepepet penjual, keunggulan lokasi/dokumen, dan potensi margin).

    Tolong jawab HANYA dalam format JSON persis seperti ini:
    {{
      "is_property": true/false,
      "score": (angka 1 sampai 10, hanya berikan >= 7 untuk REAL HIDDEN GEM),
      "jenis": "Rumah" / "Tanah" / "Ruko" / "Lainnya",
      "lokasi": "Nama lokasi/daerah jika ada, atau Unknown",
      "harga": "Harga jika ada, atau Tidak dicantumkan",
      "alasan_menarik": "Penjelasan mendalam & persuasif kenapa properti ini layak disikat investor/buyer (maksimal 3 kalimat)"
    }}
    Catatan: Jangan tambahkan teks penjelasan di luar JSON.
    """

    try:
        response = client.models.generate_content(
            model='gemini-3.5-flash',
            contents=prompt
        )
        clean_json = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(clean_json)
    except Exception as e:
        print(f"⚠️ Error analisis Gemini: {e}")
        return None

def send_telegram_ai_alert(ai_data, raw_text, post_url, group_url, photo_url=None):
    """
    Mengirimkan notifikasi Telegram dengan 2 Link: Link Postingan Spesifik & Link Grup Terkait.
    """
    caption_message = (
        f"💎 **HIDDEN GEM PROPERTI DITEMUKAN!** 💎\n\n"
        f"⭐ **Skor Potensi:** `{ai_data.get('score')}/10`\n"
        f"🏠 **Jenis:** {ai_data.get('jenis')}\n"
        f"📍 **Lokasi:** {ai_data.get('lokasi')}\n"
        f"💰 **Harga:** {ai_data.get('harga')}\n\n"
        f"🧠 **Analisis Investor (AI):**\n_{ai_data.get('alasan_menarik')}_\n\n"
        f"📝 **Postingan Asli:**\n{raw_text[:300]}...\n\n"
        f"🔗 [Lihat Postingan Spesifik]({post_url})\n"
        f"🌐 [Buka Grup Facebook]({group_url})"
    )
    
    if photo_url:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        payload = {
            "chat_id": CHAT_ID,
            "photo": photo_url,
            "caption": caption_message,
            "parse_mode": "Markdown"
        }
    else:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "text": caption_message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False
        }
    
    try:
        res = requests.post(url, json=payload)
        if photo_url and res.status_code != 200:
            send_telegram_ai_alert(ai_data, raw_text, post_url, group_url, photo_url=None)
    except Exception as e:
        print(f"❌ Error kirim ke Telegram: {e}")

def run_property_bot():
    print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] 🚀 Memulai Pengecekan Rutin Multi-Grup ({len(TARGET_GROUPS)} Grup Target)...")
    sent_history = load_history()
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(storage_state="fb_state.json")
            page = context.new_page()

            # 🔄 LOOPING KE SETIAP GRUP YANG ADA DI TARGET_GROUPS
            for idx, current_group_url in enumerate(TARGET_GROUPS, 1):
                print(f"🔍 [{idx}/{len(TARGET_GROUPS)}] Mengakses Grup: {current_group_url}")
                
                try:
                    page.goto(current_group_url)
                    time.sleep(5)
                    
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
                            
                            if len(text_content) < 40:
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

                    # MENGANALISIS POSTINGAN DARI GRUP SAAT INI
                    new_alerts_count = 0
                    for item in extracted_posts:
                        line_clean = item["text"]
                        post_id = str(hash(line_clean))
                        
                        if post_id in sent_history:
                            continue
                        
                        ai_result = analyze_post_with_gemini(line_clean)
                        if ai_result and ai_result.get("is_property"):
                            if ai_result.get("score", 0) >= 7:
                                print(f"🎯 HIDDEN GEM FOUND (Skor {ai_result.get('score')}): Kirim ke Telegram...")
                                send_telegram_ai_alert(ai_result, line_clean, item["url"], item["group_url"], item["photo"])
                                new_alerts_count += 1
                        
                        sent_history.add(post_id)
                        time.sleep(12)  # Delay Rate Limit Gemini
                    
                    save_history(sent_history)
                    print(f"✅ Selesai mengecek Grup {idx}. Found: {new_alerts_count} Hidden Gem(s).")
                    
                except Exception as e:
                    print(f"⚠️ Gagal mengecek grup {current_group_url}: {e}")
                    continue

            browser.close()
            print(f"🎉 Pengecekan seluruh {len(TARGET_GROUPS)} grup selesai!")

    except Exception as e:
        print(f"❌ Terjadi kesalahan utama pada scraping: {e}")

if __name__ == "__main__":
    run_property_bot()
    schedule.every(1).hours.do(run_property_bot)
    
    print(f"\n🤖 BOT HIDDEN GEM PROPERTI MULTI-GROUP ({len(TARGET_GROUPS)} GRUP) AKTIF 24/7...")
    while True:
        schedule.run_pending()
        time.sleep(10)