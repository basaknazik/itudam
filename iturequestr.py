# -*- coding: utf-8 -*-
import json
import uuid
import sys
import time
from bs4 import BeautifulSoup

# Selenium Kütüphaneleri
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from webdriver_manager.chrome import ChromeDriverManager

# Türkçe karakter sorununu çöz
sys.stdout.reconfigure(encoding='utf-8')

# --- AYARLAR ---
BASE_URL = "https://obs.itu.edu.tr/public/DersProgram"
OUTPUT_JSON = "dersler.json"

# --- YARDIMCI FONKSİYONLAR ---
def clean_text(td):
    """ HTML tablosundaki hücreleri temizler ve liste yapar """
    if not td: return []
    text = td.get_text(separator="|").strip()
    return [t.strip() for t in text.split("|") if t.strip()]

def parse_time_float(time_str):
    """ '08:30/11:29' formatını -> 8.5 ve 11.48 olarak sayıya çevirir """
    if not time_str: return None, None
    
    # Temizlik
    clean = time_str.replace("-", "/").replace(" ", "").strip()
    if "/" not in clean: return None, None
    
    try:
        p = clean.split("/")
        # Saatlerdeki : veya . işaretlerini kaldır
        s = p[0].replace(":", "").replace(".", "")
        e = p[1].replace(":", "").replace(".", "")
        
        # Matematiksel saate çevir
        start = int(s[:2]) + int(s[2:]) / 60.0
        end = int(e[:2]) + int(e[2:]) / 60.0
        return start, end
    except:
        return None, None

def main():
    print("🌍 Tarayıcı başlatılıyor...")
    
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled") 
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)
    tum_dersler = []

    try:
        # 1. Siteye Git
        driver.get(BASE_URL)
        wait = WebDriverWait(driver, 30)

        print("⚙️  Lisans (LS) seçiliyor...")
        seviye_select = wait.until(EC.presence_of_element_located((By.ID, "programSeviyeTipiId")))
        Select(seviye_select).select_by_value("LS")
        
        # Sistemin kendine gelmesi için bekle
        time.sleep(3)

        # 2. Aktif Dönem ID'sini Bul
        print("⏳ Dönem bilgisi alınıyor...")
        donem_id = None
        try:
            # Önce DOM'dan okumayı dene
            donem_id = driver.execute_script("return $('#programSeviyeTipiId').data('donemId') || 0;")
            
            # Olmazsa Backend'e sor (JS Enjeksiyonu)
            if not donem_id:
                js_donem = """
                var callback = arguments[arguments.length - 1];
                $.ajax({
                    url: '/public/DersProgram/GetAktifDonemByProgramSeviye',
                    data: { programSeviyeTipiAnahtari: 'LS' },
                    success: function(r) { callback(r.id); },
                    error: function() { callback(null); }
                });
                """
                donem_id = driver.execute_async_script(js_donem)
            
            print(f"✅ Aktif Dönem ID: {donem_id}")
        except:
            print("⚠️ Dönem ID otomatik alınamadı, manuel devam edilecek.")

        # 3. Bölüm Listesini Topla
        print("📋 Bölüm listesi okunuyor...")
        brans_element = driver.find_element(By.ID, "dersBransKoduId")
        options = Select(brans_element).options
        
        hedef_branslar = []
        for opt in options:
            val = opt.get_attribute("value")
            txt = opt.text.strip()
            if val and val != "":
                hedef_branslar.append((val, txt))
        
        print(f"🚀 Toplam {len(hedef_branslar)} bölüm taranacak. Başlıyoruz...")

        # 4. Hızlı Tarama Döngüsü (JS Enjeksiyonu)
        for index, (b_id, b_name) in enumerate(hedef_branslar):
            try:
                # İTÜ'nün veriyi çeken fonksiyonunu taklit et
                js_fetch = """
                var callback = arguments[arguments.length - 1];
                $.ajax({
                    url: '/public/DersProgram/DersProgramSearch',
                    type: 'GET',
                    data: { 
                        programSeviyeTipiAnahtari: 'LS', 
                        dersBransKoduId: arguments[0],
                        donemId: arguments[1] 
                    },
                    success: function(data) { callback(data); },
                    error: function() { callback(null); }
                });
                """
                
                # Veriyi çek (HTML gelir)
                html_content = driver.execute_async_script(js_fetch, b_id, donem_id)
                
                if not html_content:
                    continue

                # HTML'i Parse Et
                soup = BeautifulSoup(html_content, "html.parser")
                rows = soup.find_all("tr")
                
                count = 0
                for row in rows:
                    cols = row.find_all("td")
                    if len(cols) < 9: continue

                    try:
                        # Verileri Ayıkla
                        crn = cols[0].text.strip()
                        kod = cols[1].text.strip()
                        isim = cols[2].text.strip()
                        hoca = cols[4].text.strip()
                        
                        # Sınıf Kısıtlaması (Genelde 14. index)
                        sinif = ""
                        if len(cols) > 14: sinif = cols[14].text.strip()

                        gunler = clean_text(cols[6])
                        saatler = clean_text(cols[7])

                        # SENARYO 1: Günü/Saati Olmayan Dersler (Staj, Bitirme vb.)
                        if not gunler:
                            tum_dersler.append({
                                "crn": crn, 
                                "kod": kod, 
                                "isim": isim, 
                                "hoca": hoca, 
                                "gun": None, 
                                "bas": None, 
                                "bit": None, 
                                "sinif": sinif
                            })
                            count += 1
                        
                        # SENARYO 2: Normal Dersler
                        else:
                            loop = max(len(gunler), len(saatler))
                            for i in range(loop):
                                g = gunler[i] if i < len(gunler) else gunler[-1]
                                s_raw = saatler[i] if i < len(saatler) else saatler[-1]
                                
                                # Saati Hesapla
                                bas, bit = parse_time_float(s_raw)

                                # SiteBuilder uyumlu kayıt (bas None olsa bile ekle!)
                                tum_dersler.append({
                                    "crn": crn, 
                                    "kod": kod, 
                                    "isim": isim, 
                                    "hoca": hoca, 
                                    "gun": g, 
                                    "bas": bas, 
                                    "bit": bit, 
                                    "sinif": sinif
                                })
                                count += 1
                    except: continue
                
                # İlerleme Çubuğu
                sys.stdout.write(f"\r[{index+1}/{len(hedef_branslar)}] {b_name} ({count} ders) taranıyor...   ")
                sys.stdout.flush()
                
                time.sleep(0.05)

            except Exception:
                continue

    except Exception as e:
        print(f"\n🔥 Genel Hata: {e}")
    
    finally:
        driver.quit()
        print(f"\n\n🏁 BİTTİ. Toplam {len(tum_dersler)} ders verisi toplandı.")
        
        # JSON Kaydet
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(tum_dersler, f, ensure_ascii=False, indent=4)
        print(f"💾 {OUTPUT_JSON} başarıyla oluşturuldu.")

if __name__ == "__main__":
    main()