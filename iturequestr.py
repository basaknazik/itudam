# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup
import sys
import json
import uuid
import time

# Konsolun Türkçe karakterleri doğru basması için
sys.stdout.reconfigure(encoding='utf-8')

# --- AYARLAR ---
BASE_URL = "https://obs.itu.edu.tr/public/DersProgram/DersProgramSearch?programSeviyeTipiAnahtari=LS&dersBransKoduId={}"
OUTPUT_JSON = "dersler.json"

def parse_time_float(time_str):
    """ '08:30/11:29' formatını -> 8.5 ve 11.48 olarak sayıya çevirir """
    if not time_str or "/" not in time_str:
        return None, None
    try:
        clean = time_str.replace(":", "").strip()
        p = clean.split("/")
        start = int(p[0][:2]) + int(p[0][2:]) / 60.0
        end = int(p[1][:2]) + int(p[1][2:]) / 60.0
        return start, end
    except:
        return None, None

def clean_text(td):
    """ Hücredeki <br> etiketlerini temizleyip liste yapar """
    if not td: return []
    # <br> etiketlerini '|' karakterine çevirip oradan bölüyoruz
    text = td.get_text(separator="|").strip()
    return [t.strip() for t in text.split("|") if t.strip()]

def scrape_branch(branch_id):
    """ Belirli bir branş ID'si için dersleri çeker """
    target_url = BASE_URL.format(branch_id)
    print(f"🌍 ID {branch_id} taranıyor...")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        r = requests.get(target_url, headers=headers, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print(f"   ⚠️ ID {branch_id} için bağlantı hatası: {e}")
        return []

    soup = BeautifulSoup(r.content, "html.parser")
    table = soup.find("table", {"class": "table-bordered"})

    if not table:
        print(f"   ⚠️ ID {branch_id} için tablo bulunamadı (Boş olabilir).")
        return []

    rows = table.find("tbody").find_all("tr")
    page_courses = []

    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 9: continue

        # --- VERİLERİ ÇEK ---
        crn = cols[0].text.strip()
        kod = cols[1].text.strip()
        isim = cols[2].text.strip()
        hoca = cols[4].text.strip()

        # Çok satırlı sütunlar (Gün, Saat)
        gunler = clean_text(cols[6])
        saatler = clean_text(cols[7])

        if not gunler: continue

        loop_len = max(len(gunler), len(saatler))

        for i in range(loop_len):
            gun = gunler[i] if i < len(gunler) else gunler[-1]
            saat_raw = saatler[i] if i < len(saatler) else saatler[-1]
            
            bas, bit = parse_time_float(saat_raw)

            if bas is not None:
                ders_objesi = {
                    "id": f"{crn}_{i}_{uuid.uuid4().hex[:4]}",
                    "kod": kod,
                    "isim": isim,
                    "hoca": hoca,
                    "crn": crn,
                    "gun": gun,
                    "raw_saat": saat_raw,
                    "bas": bas,
                    "bit": bit
                }
                page_courses.append(ders_objesi)
    
    print(f"   ✅ ID {branch_id} tamamlandı. ({len(page_courses)} blok bulundu)")
    return page_courses

def main():
    tum_dersler = []
    
    # 1'den 50'ye kadar (51 dahil değil) döngü
    start_id = 1
    end_id = 50

    print(f"🚀 Tarama başlıyor: {start_id} - {end_id} arası ID'ler taranacak.")

    for i in range(start_id, end_id + 1):
        dersler = scrape_branch(i)
        tum_dersler.extend(dersler)
        # Sunucuyu çok yormamak için kısa bir bekleme
        time.sleep(0.5)

    print("-" * 40)
    print(f"🏁 TÜM İŞLEMLER BİTTİ.")
    print(f"📊 Toplam {len(tum_dersler)} ders bloğu toplandı.")

    # JSON Kaydet
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(tum_dersler, f, ensure_ascii=False, indent=4)

    print(f"💾 Dosya kaydedildi: {OUTPUT_JSON}")

if __name__ == "__main__":
    main()