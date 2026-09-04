import os
import time
import json
import streamlit as st
import pandas as pd
from dotenv import load_dotenv
from google import genai

# Konfigurasi Halaman Streamlit
st.set_page_config(
    page_title="Gemini Multi-Key Monitor | Jakarta Barat Bot",
    page_icon="⚡",
    layout="wide"
)

# Load file environment
load_dotenv()

HISTORY_FILE = "sent_posts.json"

st.title("⚡ Gemini Multi-Key & Property Bot Monitor")
st.caption("Dashboard pemantau status kesehatan API Key, latency, estimasi kapasitas pool, dan aktivitas bot.")

# 1. AMBIL KEYS DARI .ENV
raw_keys = os.getenv("GEMINI_API_KEYS", os.getenv("GEMINI_API_KEY", ""))
api_keys = [k.strip() for k in raw_keys.split(",") if k.strip()]

if not api_keys:
    st.error("⚠️ Tidak ada `GEMINI_API_KEYS` atau `GEMINI_API_KEY` yang ditemukan di file `.env`.")
    st.stop()

# 2. METRIK RINGKASAN POOL
col1, col2, col3, col4 = st.columns(4)

total_keys = len(api_keys)
col1.metric("Total API Keys", f"{total_keys} Key(s)")
col2.metric("Pool RPM Capacity", f"{total_keys * 15} RPM")
col3.metric("Est. Pool RPD Capacity", f"~{total_keys * 1500:,} Req/Hari")

# Baca history postingan tersimpan
processed_count = 0
if os.path.exists(HISTORY_FILE):
    try:
        with open(HISTORY_FILE, "r") as f:
            data = json.load(f)
            processed_count = len(data)
    except Exception:
        processed_count = 0

col4.metric("Postingan Diproses", f"{processed_count} Post")

st.markdown("---")

# 3. PENGUJIAN STATUS TIAP API KEY
st.subheader("🔑 Status Kesehatan API Key (Real-time Health Check)")

def mask_key(k):
    if len(k) <= 10:
        return "****"
    return f"{k[:6]}...{k[-4:]}"

def test_api_key(key):
    """Menguji respon langsung dari Gemini API."""
    client = genai.Client(api_key=key)
    start_time = time.time()
    try:
        response = client.models.generate_content(
            model='gemini-3.6-flash',
            contents="ping"
        )
        latency = round((time.time() - start_time) * 1000, 2)
        return {
            "status": "🟢 Healthy",
            "latency": f"{latency} ms",
            "code": 200,
            "message": "Model responsive"
        }
    except Exception as e:
        latency = round((time.time() - start_time) * 1000, 2)
        err = str(e)
        if "429" in err or "RESOURCE_EXHAUSTED" in err:
            return {
                "status": "🔴 Rate Limited (429)",
                "latency": f"{latency} ms",
                "code": 429,
                "message": "Quota limit reached / Cooldown required"
            }
        elif "API_KEY_INVALID" in err or "400" in err:
            return {
                "status": "❌ Invalid Key",
                "latency": f"{latency} ms",
                "code": 400,
                "message": "API key is not valid"
            }
        else:
            return {
                "status": "⚠️ Error",
                "latency": f"{latency} ms",
                "code": 500,
                "message": err[:80]
            }

if st.button("🔄 Jalankan Diagnosa Ulang Sekarang"):
    st.rerun()

results = []
progress_bar = st.progress(0)

for idx, key in enumerate(api_keys):
    check = test_api_key(key)
    results.append({
        "No": idx + 1,
        "Key Masked": mask_key(key),
        "Status": check["status"],
        "Latency": check["latency"],
        "HTTP Code": check["code"],
        "Catatan": check["message"]
    })
    progress_bar.progress((idx + 1) / total_keys)

progress_bar.empty()

df = pd.DataFrame(results)
st.dataframe(df, use_container_width=True, hide_index=True)

# 4. STATISTIK SISTEM & BOT INSIGHT
st.markdown("---")
st.subheader("📊 Statistik Beban & Rekomendasi")

healthy_keys = sum(1 for r in results if "🟢" in r["Status"])
rate_limited_keys = sum(1 for r in results if "🔴" in r["Status"])

col_sub1, col_sub2 = st.columns(2)

with col_sub1:
    st.info(f"""
    **Kondisi Pool Saat Ini:**
    * **Aktif / Siap Pakai:** `{healthy_keys} / {total_keys}` Key
    * **Cooldown / Limit 429:** `{rate_limited_keys}` Key
    """)

with col_sub2:
    if rate_limited_keys > 0:
        st.warning(
            "Terdapat Key yang menyentuh batas RPM/RPD. Sistem rotasi bot di `main_bot.py` "
            "akan otomatis mengalihkan request ke key berikutnya."
        )
    else:
        st.success("Seluruh API Key siap dan memiliki throughput maksimal.")