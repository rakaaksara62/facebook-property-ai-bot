"""
================================================================================
PROPERTY BOT & AI ENGINE DASHBOARD (DASHBOARD.PY)
================================================================================
Dashboard monitoring berbasis Streamlit untuk memantau performa, kuota, latency,
status sesi Facebook, dan statistik listing properti secara visual.
Jalankan dengan perintah: streamlit run dashboard.py
================================================================================
"""

import os
import sys
import time
import json
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

# Setup encoding
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

load_dotenv(override=True)

from config import (
    GROQ_API_KEY,
    GROQ_MODEL,
    GEMINI_API_KEYS,
    COOKIE_FILE,
    SEEN_POSTS_FILE,
    FACEBOOK_GROUPS,
    TELEGRAM_TOKEN,
    CHAT_ID
)
from storage import is_session_valid, load_seen_posts

st.set_page_config(
    page_title="AI Property Bot & Groq Monitor",
    page_icon="🏢",
    layout="wide"
)

st.title("🏢 Real Estate Intelligence Bot - Control Dashboard")
st.caption("Pemantau status kesehatan sistem bot scraper, Groq AI, sesi Facebook, dan aktivitas notifikasi.")

# ------------------------------------------------------------------------------
# 1. METRIK UTAMA
# ------------------------------------------------------------------------------
seen_posts = load_seen_posts()
valid_sess, sess_desc = is_session_valid(COOKIE_FILE)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Facebook Target Groups", f"{len(FACEBOOK_GROUPS)} Grup")
col2.metric("Total Listing Diproses", f"{len(seen_posts)} Post")
col3.metric("AI Engine Utama", f"Groq ({GROQ_MODEL.split('/')[-1]})")
col4.metric("Status Sesi FB", "🟢 Valid" if valid_sess else "🔴 Kadaluarsa")

st.markdown("---")

# ------------------------------------------------------------------------------
# 2. STATUS GROQ AI ENGINE
# ------------------------------------------------------------------------------
st.subheader("⚡ Status Groq AI Engine (Model: openai/gpt-oss-120b)")

def test_groq():
    if not GROQ_API_KEY:
        return {"status": "❌ Missing Key", "latency": "-", "message": "GROQ_API_KEY belum disetel"}
    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        start = time.time()
        res = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": "Ping"}],
            max_tokens=20
        )
        duration = round((time.time() - start) * 1000, 2)
        return {
            "status": "🟢 Healthy",
            "latency": f"{duration} ms",
            "message": f"Model responsif ({res.model})"
        }
    except Exception as e:
        return {"status": "⚠️ Error", "latency": "-", "message": str(e)[:100]}

groq_res = test_groq()

groq_col1, groq_col2, groq_col3 = st.columns(3)
groq_col1.metric("Groq Status", groq_res["status"])
groq_col2.metric("Latency", groq_res["latency"])
groq_col3.info(f"**Detail:** {groq_res['message']}")

# ------------------------------------------------------------------------------
# 3. STATUS GOOGLE GEMINI POOL (JIKA TERSEDIA)
# ------------------------------------------------------------------------------
if GEMINI_API_KEYS:
    st.markdown("---")
    st.subheader("🔑 Google Gemini Fallback Pool Status")

    def test_gemini_key(key):
        from google import genai
        client = genai.Client(api_key=key)
        start_time = time.time()
        try:
            res = client.models.generate_content(
                model='gemini-2.5-flash',
                contents="ping"
            )
            lat = round((time.time() - start_time) * 1000, 2)
            return {"status": "🟢 Healthy", "latency": f"{lat} ms", "msg": "OK"}
        except Exception as e:
            err = str(e)
            return {"status": "🔴 Error", "latency": "-", "msg": err[:80]}

    gem_results = []
    for idx, k in enumerate(GEMINI_API_KEYS, 1):
        masked = f"{k[:6]}...{k[-4:]}" if len(k) > 10 else "****"
        chk = test_gemini_key(k)
        gem_results.append({
            "No": idx,
            "Key": masked,
            "Status": chk["status"],
            "Latency": chk["latency"],
            "Catatan": chk["msg"]
        })

    st.dataframe(pd.DataFrame(gem_results), use_container_width=True, hide_index=True)

# ------------------------------------------------------------------------------
# 4. KESEHATAN SISTEM & AKUN FACEBOOK
# ------------------------------------------------------------------------------
st.markdown("---")
st.subheader("🛡️ Informasi Keamanan & Sesi Facebook")

col_info1, col_info2 = st.columns(2)

with col_info1:
    st.markdown("### 📋 Detail Sesi Facebook")
    st.write(f"- **Berkas Cookie:** `{COOKIE_FILE}`")
    st.write(f"- **Kondisi:** {sess_desc}")
    if not valid_sess:
        st.warning("⚠️ Sesi Facebook belum aktif. Silakan buka terminal dan jalankan:\n`python save_session.py`")
    else:
        st.success("✅ Sesi autentikasi Facebook siap digunakan untuk scraping.")

with col_info2:
    st.markdown("### ✈️ Integrasi Telegram Alert")
    if TELEGRAM_TOKEN and CHAT_ID:
        masked_token = f"{TELEGRAM_TOKEN[:8]}...{TELEGRAM_TOKEN[-5:]}"
        st.write(f"- **Telegram Bot:** `{masked_token}`")
        st.write(f"- **Chat ID Tujuan:** `{CHAT_ID}`")
        st.success("✅ Notifikasi Telegram terkonfigurasi dengan format HTML & Multipart Buffer.")
    else:
        st.error("❌ Telegram token atau Chat ID belum terisi di file .env.")

if st.button("🔄 Segarkan Data Diagnostik"):
    st.rerun()
