import os
import sys
import json
from dotenv import load_dotenv
from groq import Groq

# Pastikan output UTF-8 di Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Load .env
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    print("❌ Error: GROQ_API_KEY tidak ditemukan di .env!")
    exit(1)

client = Groq(api_key=GROQ_API_KEY)

# List model yang diuji
TEST_MODELS = [
    "openai/gpt-oss-120b",
    "allam-2-7b",
    "llama-3.3-70b-versatile"
]

sample_post = """
BU CEPAT! Jual rumah tua hitung tanah di area Kembangan Jakarta Barat. 
Luas Tanah 120m, SHM, lokasi strategis dekat pintu tol. 
Harga 650 juta nego alus sampai jadi. Hubungi WA 08123456789.
"""

system_prompt = (
    "Kamu adalah analis properti. Filter listing rumah/tanah BU/miring di Jakarta Barat.\n"
    "Beri score 1-10.\n"
    "Output WAJIB JSON murni (tanpa markdown block):\n"
    "{\n"
    '  "is_property": true,\n'
    '  "score": 8,\n'
    '  "jenis": "Rumah/Tanah/Ruko",\n'
    '  "lokasi": "Area Jakbar",\n'
    '  "legalitas": "SHM/HGB/AJB/Lainnya",\n'
    '  "harga": "Harga/Tidak ada",\n'
    '  "alasan_menarik": "1 kalimat ringkas"\n'
    "}"
)

print("⚡ Memulai tes koneksi Groq API...\n")

for model_name in TEST_MODELS:
    print(f"👉 Meminta respons dari model: [{model_name}]...")
    try:
        # Note: reasoning models seperti gpt-oss-120b butuh max_tokens lebih tinggi
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Post:\n{sample_post}"}
            ],
            temperature=0.1,
            max_tokens=600
        )
        
        result_text = response.choices[0].message.content.strip()
        print(f"✅ Model [{model_name}] BERHASIL!")
        print("📄 Hasil Output:")
        print(result_text)
        print("-" * 50)
        break  # Jika model berhasil, tes selesai

    except Exception as e:
        print(f"❌ Model [{model_name}] GAGAL: {e}")
        print("-" * 50)
