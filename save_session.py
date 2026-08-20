from playwright.sync_api import sync_playwright
import time

def run_login_and_save():
    print("🚀 Membuka Chrome untuk Login Facebook...")
    
    with sync_playwright() as p:
        # Membuka browser visual
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # Buka Facebook
        page.goto("https://www.facebook.com")
        
        print("\n" + "="*50)
        print("👉 SILAKAN LOGIN KE AKUN FB TUMBAL KAMU DI BROWSER YANG TERBUKA.")
        print("👉 Waktu kamu 60 detik untuk login...")
        print("="*50 + "\n")
        
        # Beri waktu 60 detik bagi kamu untuk ketik email & password FB di browser yang muncul
        time.sleep(60)
        
        # Simpan sesi login ke file 'fb_state.json'
        context.storage_state(path="fb_state.json")
        print("\n✅ SESI LOGIN BERHASIL DISIMPAN KE 'fb_state.json'!")
        
        browser.close()

if __name__ == "__main__":
    run_login_and_save()