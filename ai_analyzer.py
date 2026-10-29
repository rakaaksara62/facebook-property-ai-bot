"""
================================================================================
AI ANALYZER MODULE (AI_ANALYZER.PY)
================================================================================
Modul ini bertugas menganalisis konten postingan properti menggunakan Groq API
dengan model 'openai/gpt-oss-120b'.

Fitur Unggulan:
1. Prompt teroptimasi untuk menghasilkan ringkasan bernilai tinggi bagi agen & investor.
2. Sanitasi HTML ketat untuk kompatibilitas penuh dengan Telegram HTML parse mode.
3. Fallback cerdas: Jika model utama error/limit, otomatis beralih ke model cadangan.
================================================================================
"""

import re
import html
import logging
from groq import Groq
from config import GROQ_API_KEY, GROQ_MODEL, GEMINI_API_KEYS

logger = logging.getLogger("PropertyBot.AI")

# Inisialisasi klien Groq
groq_client = None
if GROQ_API_KEY:
    try:
        groq_client = Groq(api_key=GROQ_API_KEY)
    except Exception as e:
        logger.error(f"Gagal menginisialisasi Groq client: {e}")

# Model fallback jika model utama tidak tersedia atau rate-limited
FALLBACK_GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "allam-2-7b"
]

def clean_telegram_html(raw_text: str) -> str:
    """
    Membersihkan dan memastikan tag HTML yang dihasilkan AI aman 100%
    untuk parser HTML Telegram.
    
    Telegram hanya mendukung: <b>, <strong>, <i>, <em>, <u>, <ins>,
    <s>, <strike>, <del>, <span>, <tg-spoiler>, <a href="...">,
    <code>, <pre>, <blockquote>.
    Semua tag lain (seperti <ul>, <li>, <p>, <div>, dll) harus diubah atau dihilangkan.
    """
    if not raw_text:
        return ""

    text = raw_text.strip()

    # 1. Hapus markdown code block wrapper seperti ```html ... ``` atau ``` ... ```
    text = re.sub(r'^```(?:html|json)?\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*```$', '', text)

    # 2. Ubah tag list <li> menjadi bullet point simbol '• '
    text = re.sub(r'<li[^>]*>(.*?)</li>', r'• \1\n', text, flags=re.DOTALL | re.IGNORECASE)

    # 3. Ubah tag paragraf <p> menjadi baris baru
    text = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n', text, flags=re.DOTALL | re.IGNORECASE)

    # 4. Hapus tag wadah yang tidak didukung Telegram
    unsupported_tags = [
        r'</?ul[^>]*>', r'</?ol[^>]*>', r'</?div[^>]*>',
        r'</?span(?!\s+class="tg-spoiler")[^>]*>',
        r'</?h[1-6][^>]*>', r'</?table[^>]*>', r'</?tr[^>]*>', r'</?td[^>]*>', r'</?th[^>]*>'
    ]
    for pattern in unsupported_tags:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)

    # 5. Ubah <br> atau <br/> menjadi newline
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)

    # 6. Konversi Markdown tebal/miring umum jika AI masih mengeluarkan markdown
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'(?<!\*)\*(?!\*)(.*?)(?<!\*)\*(?!\*)', r'<i>\1</i>', text)
    text = re.sub(r'_(.*?)_', r'<i>\1</i>', text)

    # 7. Bersihkan baris kosong berlebih
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()

def analyze_property_post(post_text: str) -> str | None:
    """
    Menganalisis teks postingan properti dengan Groq model 'openai/gpt-oss-120b'.
    Mengembalikan ringkasan HTML yang siap dikirim ke Telegram, atau None jika gagal.
    """
    if not groq_client:
        logger.error("Groq client belum terkonfigurasi. Pastikan GROQ_API_KEY ada di .env.")
        return None

    system_prompt = (
        "Kamu adalah AI Real Estate Analyst senior spesialis pasar properti Indonesia "
        "(fokus listing BU / Butuh Uang, Lelang, dan Harga Miring di Jakarta & sekitarnya).\n"
        "Tugasmu: Menganalisis teks postingan properti dan menghasilkan ringkasan yang SANGAT TAJAM, "
        "PADAT, dan BERNILAI TINGGI untuk agen properti & investor pemburu peluang cuan.\n\n"
        "ATURAN FORMAT OUTPUT (WAJIB DIIKUTI):\n"
        "- Gunakan bahasa Indonesia profesional, ringkas, dan persuasif.\n"
        "- Gunakan format Telegram HTML HANYA dengan tag <b> dan <i> serta emoji yang relevan.\n"
        "- DILARANG menggunakan tag <ul>, <ol>, <li>, <p>, atau markdown code block (```).\n"
        "- Gunakan tanda pemisah baris simbol '•' untuk detail poin.\n"
        "- Struktur Output Persis Seperti Ini:\n"
        "📍 <b>Tipe & Lokasi:</b> [Tipe properti] - [Lokasi spesifik/Area]\n"
        "💰 <b>Harga:</b> [Harga yang tertera, sebutkan jika ada estimasi harga pasar/nego/BU]\n"
        "📐 <b>Spesifikasi:</b> [LT/LB, Legalitas SHM/HGB/AJB, Fasilitas/Akses utama]\n"
        "🎯 <b>Potensi Deal:</b> [1-2 kalimat tajam analisismu mengapa unit ini peluang emas/cuan]\n"
        "📞 <b>Kontak:</b> [Nama & Nomor WA/HP penjual jika ada, jika tidak ada tulis 'Cek postingan asli']"
    )

    models_to_try = [GROQ_MODEL] + [m for m in FALLBACK_GROQ_MODELS if m != GROQ_MODEL]

    for model_name in models_to_try:
        try:
            logger.info(f"Mengirim teks postingan ke Groq AI model: [{model_name}]...")
            # Note: gpt-oss-120b adalah reasoning model, max_tokens 1200 diperlukan agar reasoning tidak memotong output
            response = groq_client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Postingan Properti:\n{post_text}"}
                ],
                temperature=0.2,
                max_tokens=1200
            )

            raw_summary = response.choices[0].message.content
            if raw_summary and len(raw_summary.strip()) > 20:
                cleaned_summary = clean_telegram_html(raw_summary)
                logger.info(f"✅ Analisis AI dengan model [{model_name}] berhasil!")
                return cleaned_summary
            else:
                logger.warning(f"Model [{model_name}] menghasilkan respon kosong atau terlalu pendek.")

        except Exception as e:
            logger.warning(f"Gagal memproses dengan model [{model_name}]: {e}")
            continue

    # Fallback terakhir jika Groq gagal total: Coba Gemini jika API key tersedia
    if GEMINI_API_KEYS:
        logger.info("Mencoba fallback analisis dengan Google Gemini AI...")
        gemini_summary = _analyze_with_gemini_fallback(post_text, system_prompt)
        if gemini_summary:
            return clean_telegram_html(gemini_summary)

    logger.error("Seluruh opsi AI gagal memproses postingan ini.")
    return None

def _analyze_with_gemini_fallback(post_text: str, system_prompt: str) -> str | None:
    """Fallback ke Gemini AI jika Groq sedang down atau limit."""
    try:
        from google import genai
        for key in GEMINI_API_KEYS:
            try:
                client = genai.Client(api_key=key)
                prompt = f"{system_prompt}\n\nPostingan Properti:\n{post_text}"
                res = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt
                )
                if res.text:
                    return res.text
            except Exception as e:
                logger.warning(f"Gemini fallback key error: {e}")
                continue
    except Exception as e:
        logger.warning(f"Modul Google GenAI tidak tersedia: {e}")
    return None

