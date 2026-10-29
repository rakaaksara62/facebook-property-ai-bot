import os
import sys
import time
from dotenv import load_dotenv
from google import genai

# Pastikan output UTF-8 di Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Load .env
load_dotenv(override=True)

# Cek variabel .env
raw_keys = os.getenv("GEMINI_API_KEYS") or os.getenv("GEMINI_API_KEY") or ""
api_keys = [k.strip().strip('"').strip("'") for k in raw_keys.split(",") if k.strip()]

print("\n" + "=" * 60)
print("🔍 DIAGNOSTIK GEMINI MULTI-KEY POOL")
print("=" * 60)

if not api_keys:
    print("❌ ERROR: Tidak ada API key yang terdeteksi di file .env!")
    print("Pastikan di .env tertulis:")
    print('GEMINI_API_KEYS="key1,key2,key3"')
    exit(1)

print(f"📋 Terdeteksi {len(api_keys)} API Key di dalam file .env.\n")

# Uji coba setiap key secara eksplisit
for idx, key in enumerate(api_keys, 1):
    masked = f"{key[:6]}...{key[-4:]}" if len(key) > 10 else "****"
    print(f"--- [KEY {idx}/{len(api_keys)}] Menguji: {masked} ---")
    
    start_time = time.time()
    try:
        # Inisialisasi client spesifik untuk key ini
        client = genai.Client(api_key=key)
        
        # Kirim request nyata agar tercatat di dashboard masing-masing akun
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents="Katakan 'Halo Investor' dalam 2 kata saja."
        )
        
        duration = round((time.time() - start_time) * 1000, 2)
        reply = response.text.strip().replace("\n", " ") if response.text else "OK"
        
        print(f"  ✅ STATUS : BERHASIL (200 OK)")
        print(f"  ⏱️ LATENCY: {duration} ms")
        print(f"  💬 RESPON : \"{reply}\"")
        print(f"  📊 USAGE  : Request ini pasti tercatat di Google AI Studio akun Key #{idx}!\n")
        
    except Exception as e:
        duration = round((time.time() - start_time) * 1000, 2)
        print(f"  ❌ STATUS : GAGAL")
        print(f"  ⏱️ LATENCY: {duration} ms")
        print(f"  ⚠️ ERROR  : {e}\n")
    
    # Jeda 2 detik antar testing
    time.sleep(2)

print("=" * 60)
print("🏁 Pengujian seluruh API Key selesai.")
print("=" * 60 + "\n")
