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

sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "https://obs.itu.edu.tr/public/DersProgram"
OUTPUT_JSON = "dersler.json"

def clean_text(td):
    if not td: return []
    text = td.get_text(separator="|").strip()
    return [t.strip() for t in text.split("|") if t.strip()]

def parse_time_float(time_str):
    if not time_str: return None, None
    clean = time_str.replace("-", "/").replace(" ", "").strip()
    if "/" not in clean: return None, None
    try:
        p = clean.split("/")
        s = p[0].replace(":", "").replace(".", "")
        e = p[1].replace(":", "").replace(".", "")
        start = int(s[:2]) + int(s[2:]) / 60.0
        end = int(e[:2]) + int(e[2:]) / 60.0
        return start, end
    except:
        return None, None

def main():
    print("🌍 Tarayıcı başlatılıyor...")
    
    options = webdriver.ChromeOptions()
    # Hız ve stabilite için gerekli ayarlar
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled") 
    
    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)
    tum_dersler = []

    try:
        # 1. Siteye Tek Seferlik Giriş
        driver.get(BASE_URL)
        wait = WebDriverWait(driver, 30)

        print("⚙️  Lisans (LS) seçiliyor ve sistemin yüklenmesi bekleniyor...")
        seviye_select = wait.until(EC.presence_of_element_located((By.ID, "programSeviyeTipiId")))
        Select(seviye_select).select_by_value("LS")
        
        # Kritik Bekleme: İTÜ'nün AJAX ile dönem bilgisini getirmesini bekliyoruz
        time.sleep(3)

        # 2. Aktif Dönem ID'sini Tarayıcıdan Çalıyoruz
        # Bu ID olmadan yapılan sorgular boş döner.
        try:
            donem_id = driver.execute_script("return $('#programSeviyeTipiId').data('donemId') || 0;")
            # Eğer yukarıdaki çalışmazsa, backend'e soralım:
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
            
            print(f"✅ Aktif Dönem ID Tespit Edildi: {donem_id}")
        except:
            print("⚠️ Dönem ID otomatik alınamadı, manuel devam ediliyor...")
            donem_id = None # Kod yine de çalışmayı denesin

        # 3. Bölüm Listesini Al
        print("📋 Bölüm listesi taranıyor...")
        brans_element = driver.find_element(By.ID, "dersBransKoduId")
        options = Select(brans_element).options
        
        hedef_branslar = []
        for opt in options:
            val = opt.get_attribute("value")
            txt = opt.text.strip()
            if val and val != "":
                hedef_branslar.append((val, txt))
        
        print(f"🚀 Toplam {len(hedef_branslar)} bölüm bulundu. Hızlı tarama başlıyor...")

        # 4. JavaScript Enjeksiyonu ile Hızlı Tarama
        # Sayfayı yenilemeden, tarayıcının kendi jQuery'sini kullanarak veriyi çekiyoruz.
        for index, (b_id, b_name) in enumerate(hedef_branslar):
            try:
                # İTÜ'nün kendi sorgu fonksiyonunu taklit ediyoruz
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
                
                # Veriyi çek (HTML string döner)
                html_content = driver.execute_async_script(js_fetch, b_id, donem_id)
                
                if not html_content:
                    continue

                # HTML'i Parse Et
                soup = BeautifulSoup(html_content, "html.parser")
                rows = soup.find_all("tr")
                
                count = 0
                # ... (öncesi aynı)
                for row in rows:
                    cols = row.find_all("td")
                    if len(cols) < 9: continue

                    try:
                        crn = cols[0].text.strip()
                        kod = cols[1].text.strip()
                        isim = cols[2].text.strip()
                        hoca = cols[4].text.strip()
                        
                        sinif = ""
                        if len(cols) > 13: sinif = cols[13].text.strip()

                        gunler = clean_text(cols[6])
                        saatler = clean_text(cols[7])

                        # SENARYO 1: Günü Hiç Olmayanlar (Staj, Bitirme vb.)
                        if not gunler:
                            tum_dersler.append({
                                "id": crn, "kod": kod, "isim": isim, "hoca": hoca, "crn": crn, 
                                "gun": None, "raw_saat": "", "bas": None, "bit": None, "sinif": sinif
                            })
                            count += 1
                        
                        # SENARYO 2: Günü Olanlar (Normal Dersler)
                        else:
                            loop = max(len(gunler), len(saatler))
                            for i in range(loop):
                                g = gunler[i] if i < len(gunler) else gunler[-1]
                                s_raw = saatler[i] if i < len(saatler) else saatler[-1]
                                
                                # Saati hesaplamaya çalış
                                bas, bit = parse_time_float(s_raw)

                                # KRİTİK DEĞİŞİKLİK: 'if bas is not None' kontrolünü kaldırdık.
                                # Saati hesaplanamasa bile (bas=None) listeye ekliyoruz.
                                tum_dersler.append({
                                    "id": f"{crn}_{i}_{uuid.uuid4().hex[:4]}",
                                    "kod": kod, "isim": isim, "hoca": hoca, "crn": crn, 
                                    "gun": g, "raw_saat": s_raw, 
                                    "bas": bas, # Eğer hesaplanamadıysa None gidecek (Sorun yok)
                                    "bit": bit, 
                                    "sinif": sinif
                                })
                                count += 1
                    except: continue
                # ... (devamı aynı)
                
                # İlerleme Çubuğu gibi yazdır
                sys.stdout.write(f"\r[{index+1}/{len(hedef_branslar)}] {b_name} ({count} ders) taranıyor...   ")
                sys.stdout.flush()
                
                # Çok hızlı gidip sunucuyu boğmamak için mikroskobik bekleme
                time.sleep(0.05)

            except Exception:
                continue

    except Exception as e:
        print(f"\n🔥 Genel Hata: {e}")
    
    finally:
        driver.quit()
        print(f"\n\n🏁 BİTTİ. Toplam {len(tum_dersler)} ders verisi toplandı.")
        
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(tum_dersler, f, ensure_ascii=False, indent=4)
        print(f"💾 {OUTPUT_JSON} dosyasına kaydedildi.")

if __name__ == "__main__":
    main()