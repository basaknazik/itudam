# -*- coding: utf-8 -*-
import json
import os

# --- AYARLAR ---
INPUT_JSON = "dersler.json"
OUTPUT_HTML = "index.html"

# Günleri İngilizce/Kısaltma -> Türkçe Standart formatına çeviren fonksiyon
def tr_gun_yap(gun_adi):
    if not gun_adi: return None
    g = str(gun_adi).lower().strip()
    
    mapping = {
        "monday": "Pazartesi", "mon": "Pazartesi", "pazartesi": "Pazartesi",
        "tuesday": "Salı", "tue": "Salı", "salı": "Salı",
        "wednesday": "Çarşamba", "wed": "Çarşamba", "çarşamba": "Çarşamba",
        "thursday": "Perşembe", "thu": "Perşembe", "perşembe": "Perşembe",
        "friday": "Cuma", "fri": "Cuma", "cuma": "Cuma",
        "saturday": "Cumartesi", "sunday": "Pazar"
    }
    
    return mapping.get(g, None)

def process_data():
    if not os.path.exists(INPUT_JSON):
        print(f"❌ HATA: {INPUT_JSON} dosyası bulunamadı! JSON dosyasının kodla aynı klasörde olduğundan emin ol.")
        return None, None

    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        try:
            raw_data = json.load(f)
        except json.JSONDecodeError:
            print("❌ HATA: JSON dosyası bozuk veya formatı hatalı.")
            return None, None

    courses_map = {}
    subjects = set()

    for item in raw_data:
        # Başlık satırını atla
        raw_crn = str(item.get("crn") or item.get("CRN") or "").strip()
        if raw_crn.upper() == "CRN" or not raw_crn:
            continue

        crn = raw_crn
        kod = (item.get("kod") or item.get("code") or item.get("DersKodu") or "").strip()
        isim = (item.get("isim") or item.get("title") or item.get("name") or item.get("DersAdi") or "").strip()
        hoca = (item.get("hoca") or item.get("instructor") or item.get("OgretimUyesi") or "").strip()
        
        # Sınıf "Detay" veya "Detail" kontrolü (4. Sınıf filtresi için)
        raw_sinif = str(item.get("sinif") or item.get("Sinif") or item.get("Class") or "").strip()
        is_senior = "Detay" in raw_sinif or "Detail" in raw_sinif

        if crn not in courses_map:
            courses_map[crn] = {
                "id": crn, 
                "k": kod, 
                "n": isim, 
                "i": hoca, 
                "s": [],        
                "t": "SABIT",
                "lv4": is_senior 
            }
            subj = kod.split(" ")[0]
            if len(subj) > 1: subjects.add(subj)
        else:
            if is_senior:
                courses_map[crn]["lv4"] = True

        # Gün ve Saat İşleme
        raw_gun = item.get("gun") or item.get("day") or item.get("Gun")
        gun_tr = tr_gun_yap(raw_gun) 

        bas = item.get("bas") or item.get("start") or item.get("BaslangicSaati")
        bit = item.get("bit") or item.get("end") or item.get("BitisSaati")

        if gun_tr and bas is not None:
            try:
                b_val = float(bas)
                e_val = float(bit)
                courses_map[crn]["s"].append({ "d": gun_tr, "b": b_val, "e": e_val })
            except (ValueError, TypeError):
                pass 

    clean_data = list(courses_map.values())
    sorted_subjects = sorted(list(subjects))
    
    print(f"📊 İşlenen Ders Sayısı: {len(clean_data)}")
    
    return json.dumps(clean_data, ensure_ascii=False), json.dumps(sorted_subjects, ensure_ascii=False)

# HTML ŞABLONU (JS Tarafına Otomatik Düzeltici Eklendi)
html_template = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ITU DAM</title>
    <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
    
    <style>
        :root { --bg: #121212; --panel: #1e1e1e; --border: #333; --blue: #4db8ff; --orange: #ffaa00; --red: #ff4d4d; --green: #4caf50; --purple: #9d46ff; --sidebar-width: 400px; }
        * { box-sizing: border-box; }
        body, html { margin: 0; padding: 0; width: 100%; height: 100%; overflow: hidden; font-family: 'Inter', sans-serif; background: var(--bg); color: #e0e0e0; }
        
        /* GİRİŞ EKRANI */
        #login-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: #0f0f0f; z-index: 9999; display: flex; justify-content: center; align-items: center; transition: opacity 0.6s ease, visibility 0.6s; }
        .login-box { width: 360px; padding: 40px; background: #1a1a1a; border: 1px solid #333; border-radius: 12px; text-align: center; box-shadow: 0 30px 60px rgba(0,0,0,0.5); }
        .login-logo { font-size: 40px; font-weight: 800; color: var(--blue); letter-spacing: -2px; margin-bottom: 5px; }
        .login-sub { font-size: 12px; color: #666; margin-bottom: 30px; font-family: 'JetBrains Mono'; }
        
        .btn-login-main { width: 100%; padding: 12px; background: white; color: black; border: none; border-radius: 6px; font-weight: bold; font-size: 14px; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 10px; transition: transform 0.2s, background 0.2s; }
        .btn-login-main:hover { background: #e0e0e0; transform: scale(1.02); }
        
        /* ANA UYGULAMA (GİZLİ BAŞLAR) */
        #app { display: flex; width: 100%; height: 100%; opacity: 0; transition: opacity 1s ease; }
        
        /* SIDEBAR & UI ELEMENTS */
        #sidebar { width: var(--sidebar-width); min-width: var(--sidebar-width); background: var(--panel); border-right: 1px solid var(--border); display: flex; flex-direction: column; z-index: 50; }
        
        /* User Profile Area in Sidebar */
        #user-profile-bar { padding: 10px 15px; background: #151515; border-bottom: 1px solid #333; display:flex; align-items:center; gap:10px; font-size:12px; }
        #user-avatar { width: 24px; height: 24px; border-radius: 50%; border: 1px solid var(--blue); }
        #user-name { flex-grow: 1; font-weight: bold; color: #ddd; }
        #logout-btn { color: var(--red); cursor: pointer; font-size: 10px; border: 1px solid #333; padding: 2px 6px; border-radius: 4px; }

        .header { padding: 15px; border-bottom: 1px solid var(--border); background: #181818; }
        .title { font-size: 18px; font-weight: 700; color: var(--blue); margin-bottom: 10px; display: flex; justify-content: space-between; }
        .db-stat { font-size: 10px; color: #666; font-weight: normal; font-family: monospace; }
        .tabs { display: flex; gap: 5px; background: #252526; padding: 3px; border-radius: 6px; margin-bottom: 10px; }
        .tab { flex: 1; padding: 8px; text-align: center; cursor: pointer; border-radius: 4px; font-size: 12px; font-weight: 600; color: #888; transition: 0.2s; }
        .tab.active { background: #333; color: white; box-shadow: 0 2px 4px rgba(0,0,0,0.2); }
        .panel { display: none; } .panel.active { display: block; }
        
        input, select, button { width: 100%; padding: 10px; background: #2a2a2a; border: 1px solid #444; color: white; border-radius: 6px; outline: none; margin-bottom: 8px; }
        input:focus, select:focus { border-color: var(--blue); }
        button { cursor: pointer; font-weight: bold; border: none; transition: 0.2s; }
        .btn-find { background: var(--green); color: white; } .btn-find:hover { opacity: 0.9; }
        .checkbox-row { display: flex; align-items: center; font-size: 12px; color: #ccc; margin-bottom: 8px; cursor: pointer; }
        .checkbox-row input { width: auto; margin: 0 8px 0 0; }
        
        #content-area { flex-grow: 1; overflow-y: auto; padding: 10px; background: #1a1a1a; display: flex; flex-direction: column; }
        .section-title { font-size: 11px; font-weight: bold; color: #666; margin: 10px 0 5px 0; padding-left: 5px; border-bottom: 1px solid #333; }
        .empty-state { text-align: center; color: #555; margin-top: 30px; font-size: 12px; }
        
        .card { background: #252526; margin-bottom: 8px; border-radius: 6px; border-left: 3px solid #555; display: flex; flex-direction: column; overflow: hidden; animation: slideIn 0.2s ease; }
        @keyframes slideIn { from { opacity: 0; transform: translateX(-5px); } to { opacity: 1; transform: translateX(0); } }
        .card.RESULT { border-left-color: var(--green); } .card.SABIT { border-left-color: var(--blue); } .card.ADAY { border-left-color: var(--orange); } .card.CONFLICT { border-left-color: var(--red); background: #2d1818; }
        
        .card-header-row { display: flex; justify-content: space-between; align-items: center; padding: 8px 10px; background: rgba(255,255,255,0.03); border-bottom: 1px solid #333; }
        .card-body-row { padding: 8px 10px; }
        .card-footer-row { display: flex; justify-content: space-between; align-items: center; padding: 5px 10px; background: rgba(0,0,0,0.2); }
        .c-code { font-weight: 700; font-size: 13px; color: #fff; }
        .c-crn { font-family: 'JetBrains Mono'; font-size: 10px; color: #888; background: #151515; padding: 2px 4px; border-radius: 3px; margin-left: 5px;}
        .c-name { font-size: 11px; color: #ccc; margin-bottom: 2px; line-height: 1.3; }
        .c-prof { font-size: 10px; color: #888; font-style: italic; }
        
        .btn-toggle { font-size: 10px; padding: 3px 8px; border-radius: 3px; cursor: pointer; text-transform: uppercase; font-weight: bold; border: 1px solid #444; background: transparent; color: #aaa; transition: 0.2s; }
        .card.SABIT .btn-toggle { color: var(--blue); border-color: var(--blue); } .card.ADAY .btn-toggle { color: var(--orange); border-color: var(--orange); }
        .btn-del { background: transparent; border: none; color: #666; cursor: pointer; font-size: 16px; font-weight: bold; } .btn-del:hover { color: var(--red); }
        .btn-add-mini { background: var(--green); color: white; border: none; padding: 4px 10px; border-radius: 4px; font-size: 11px; cursor: pointer; }
        
        #footer { padding: 15px; border-top: 1px solid var(--border); background: #181818; }
        .bm-btn { display: block; width: 100%; text-align: center; padding: 10px; background: #252526; border: 2px dashed var(--purple); color: var(--purple); border-radius: 6px; text-decoration: none; font-weight: bold; font-size: 12px; transition: 0.2s; }
        .bm-btn:hover { background: rgba(157, 70, 255, 0.1); transform: translateY(-2px); }
        
        #main { flex-grow: 1; display: flex; flex-direction: column; min-width: 0; }
        #network { height: 35%; border-bottom: 1px solid var(--border); }
        #schedule { height: 65%; padding: 15px; overflow: auto; background: #141414; }
        .grid { display: grid; grid-template-columns: 40px repeat(5, 1fr); grid-template-rows: 30px repeat(26, 1fr); gap: 1px; min-width: 800px; }
        .g-head { background: #222; text-align: center; padding: 5px; font-weight: bold; font-size: 12px; position: sticky; top:0; z-index: 10; border-bottom: 2px solid #333; }
        .g-time { text-align: right; padding-right: 5px; color: #666; font-size: 10px; border-right: 1px solid #333; }
        .g-line { grid-column: 2 / 7; border-bottom: 1px solid #222; }
        .box { background: #253341; border-left: 3px solid var(--blue); font-size: 10px; padding: 2px 4px; overflow: hidden; position: relative; cursor: pointer; box-shadow: 0 2px 4px rgba(0,0,0,0.4); transition: 0.1s; border-radius: 3px; }
        .box:hover { z-index: 100 !important; transform: scale(1.05); box-shadow: 0 5px 10px rgba(0,0,0,0.6); }
        .box.ADAY { background: #3d2e14; border-left-color: var(--orange); } .box.CONFLICT { background: #3d1414; border-left-color: var(--red); border: 1px solid var(--red); }
        #loading { display: none; text-align: center; padding: 10px; font-size: 12px; color: var(--blue); }
        
        #cloud-sync { font-size:10px; color:#666; margin-left:5px; }
    </style>
</head>
<body>

<div id="login-overlay">
    <div class="login-box">
        <div class="login-logo">DAM</div>
        <div class="login-sub">Dersimi alabilecek miyim?</div>
        
        <button id="btn-google-login" class="btn-login-main">
            <svg width="20" height="20" viewBox="0 0 24 24"><path fill="currentColor" d="M21.35 11.1h-9.17v2.73h6.51c-.33 3.81-3.5 5.44-6.5 5.44C8.36 19.27 5 16.25 5 12c0-4.1 3.2-7.27 7.2-7.27c3.09 0 4.9 1.97 4.9 1.97L19 4.72S16.56 2 12.1 2C6.42 2 2.03 6.8 2.03 12.5S6.42 23 12.1 23c5.83 0 8.84-4.15 8.84-11.9z"/></svg>
            Google ile Giriş
        </button>
        
        <div class="login-footer">
            <span id="login-status">Sistem hazır. Giriş bekleniyor.</span>
        </div>
    </div>
</div>

<div id="app">
    <div id="sidebar">
        <div id="user-profile-bar" style="display:none">
            <img id="user-avatar" src="">
            <span id="user-name">Kullanıcı</span>
            <span id="logout-btn" onclick="appLogout()">Çıkış</span>
        </div>

        <div class="header">
            <div class="title">
                Hoşgeldin <span id="cloud-sync">☁️</span>
                <span class="db-stat" id="db-stat">...</span>
            </div>
            
            <div class="tabs">
                <div class="tab active" onclick="setMode('search')">🔍 Ara</div>
                <div class="tab" onclick="setMode('filter')">⚡ Akıllı Filtre</div>
            </div>

            <div id="panel-search" class="panel active">
                <input type="text" id="inp-search" placeholder="Ders Kodu, CRN veya Adı..." autocomplete="off">
            </div>

            <div id="panel-filter" class="panel">
                <select id="sel-subj"><option value="ALL">Tümü</option></select>
                <label class="checkbox-row"><input type="checkbox" id="chk-clean" checked> Sadece Çakışmayanlar</label>

                <label class="checkbox-row" style="color: var(--orange); font-weight:500;">
                    <input type="checkbox" id="chk-senior"> 🎓 4. Sınıf / Bitirme Derslerini Göster
                </label>
                <button class="btn-find" onclick="runFilter()">🔍 LİSTELE</button>
                <div id="loading">İşleniyor...</div>
            </div>
        </div>

        <div id="content-area">
            <div id="area-results" style="display:none; margin-bottom: 20px;">
                <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #444; margin-bottom:5px;">
                    <div class="section-title" style="border:none; margin:0; color:var(--green)">SONUÇLAR</div>
                    <button style="background:none; border:none; color:#666; font-size:10px; cursor:pointer;" onclick="clearResults()">TEMİZLE X</button>
                </div>
                <div id="list-results"></div>
            </div>

            <div id="area-program">
                <div class="section-title">PROGRAMIM</div>
                <div id="list-program"></div>
            </div>
        </div>

        <div id="footer">
            <a href="#" id="bm-link" class="bm-btn">⚡ CRN Doldur (Sürükle)</a>
        </div>
    </div>

    <div id="main">
        <div id="network"></div>
        <div id="schedule">
            <div class="grid" id="grid"></div>
        </div>
    </div>
</div>

<script type="module">
    import { initializeApp } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-app.js";
    import { getAuth, signInWithPopup, GoogleAuthProvider, signOut, onAuthStateChanged } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-auth.js";
    import { getFirestore, doc, setDoc, getDoc } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-firestore.js";

    // --- SENİN FIREBASE CONFIG BURADA OLMALI ---
    const firebaseConfig = {
        apiKey: "AIzaSyC7tlSzzYkbI3L66esuBTepTawbTKGJHXI",
        authDomain: "dam-itu.firebaseapp.com",
        projectId: "dam-itu",
        storageBucket: "dam-itu.firebasestorage.app",
        messagingSenderId: "468727035557",
        appId: "1:468727035557:web:86da59562d6952c728ff4c",
        measurementId: "G-QPZ0MD160H"
    };

    if(typeof firebaseConfig === 'undefined') {
        console.error("Firebase Config bulunamadı!");
        document.getElementById('login-status').innerHTML = "<b style='color:red'>HATA: Config Eksik!</b>";
    } else {
        const app = initializeApp(firebaseConfig);
        const auth = getAuth(app);
        const db = getFirestore(app);
        const provider = new GoogleAuthProvider();

        // İngilizce günleri Türkçeye çeviren yardımcı fonksiyon (Migration)
        function normalizeProgDays(prog) {
            if (!prog) return {};
            const map = {
                "Monday": "Pazartesi", "Mon": "Pazartesi",
                "Tuesday": "Salı", "Tue": "Salı",
                "Wednesday": "Çarşamba", "Wed": "Çarşamba",
                "Thursday": "Perşembe", "Thu": "Perşembe",
                "Friday": "Cuma", "Fri": "Cuma"
            };
            Object.values(prog).forEach(c => {
                if(c.s) {
                    c.s.forEach(slot => {
                        // Eğer gün İngilizce ise Türkçeye çevir
                        if (map[slot.d]) {
                            slot.d = map[slot.d];
                        }
                    });
                }
            });
            return prog;
        }

        // Login
        document.getElementById('btn-google-login').addEventListener('click', () => {
            document.getElementById('login-status').innerText = "Google'a bağlanılıyor...";
            signInWithPopup(auth, provider).catch((error) => {
                alert("Giriş Hatası: " + error.message);
                document.getElementById('login-status').innerText = "Giriş başarısız.";
            });
        });

        // Logout
        window.appLogout = () => {
            signOut(auth).then(() => location.reload());
        };

        // --- OPTİMİZASYON 1: AKILLI YÜKLEME (Hybrid Loading) ---
        onAuthStateChanged(auth, async (user) => {
            if (user) {
                // UI Hazırlıkları
                document.getElementById('login-overlay').style.opacity = '0';
                setTimeout(() => document.getElementById('login-overlay').style.visibility = 'hidden', 600);
                document.getElementById('app').style.opacity = '1';
                setTimeout(() => { if(window.NETWORK) window.NETWORK.fit(); }, 600);

                document.getElementById('user-profile-bar').style.display = 'flex';
                document.getElementById('user-avatar').src = user.photoURL;
                document.getElementById('user-name').innerText = user.displayName;

                const syncLabel = document.getElementById('cloud-sync');
                
                // ADIM 1: Önce Işık Hızıyla LocalStorage'dan Oku (Firebase'i bekleme)
                const localKey = `itu_dam_data_${user.uid}`;
                const localData = localStorage.getItem(localKey);
                
                if (localData) {
                    try {
                        let parsed = JSON.parse(localData);
                        window.MY_PROG = normalizeProgDays(parsed); // Düzeltmeyi burada yapıyoruz
                        console.log("⚡ Veri yerel hafızadan yüklendi ve günler düzeltildi.");
                        window.refreshUI();
                    } catch(e) { console.error("Local data bozuk"); }
                }

                // ADIM 2: Arka Planda Sessizce Firebase'i Kontrol Et (Senkronizasyon)
                syncLabel.innerText = "☁️ Senkronize ediliyor...";
                const docRef = doc(db, "users", user.uid);
                
                try {
                    const docSnap = await getDoc(docRef);
                    if (docSnap.exists()) {
                        let cloudData = docSnap.data().program || {};
                        cloudData = normalizeProgDays(cloudData); // Düzeltmeyi burada da yapıyoruz
                        
                        // Eğer Local'deki veri ile Cloud farklıysa, Cloud'u esas al (veya birleştir)
                        // Şimdilik Cloud'u esas alıyoruz, çünkü en güvenlisi o.
                        if (JSON.stringify(cloudData) !== JSON.stringify(window.MY_PROG)) {
                            window.MY_PROG = cloudData;
                            window.refreshUI();
                            // Local'i de güncelle ki bir sonraki giriş hızlı olsun
                            localStorage.setItem(localKey, JSON.stringify(window.MY_PROG));
                            console.log("☁️ Veri buluttan güncellendi ve günler düzeltildi.");
                        }
                    }
                    syncLabel.innerText = "☁️ Hazır";
                } catch(e) {
                    console.error("Firebase okuma hatası:", e);
                    syncLabel.innerText = "⚠️ Offline Mod";
                }

                // --- OPTİMİZASYON 2: GECİKMELİ KAYIT (DEBOUNCE) ---
                // Kullanıcı her tıkladığında değil, durduğunda kaydet.
                let saveTimeout;
                window.triggerSave = () => {
                    syncLabel.innerText = "⏳ Kaydedilecek...";
                    
                    // 1. Önce LocalStorage'a hemen yaz (Veri kaybını önler)
                    localStorage.setItem(localKey, JSON.stringify(window.MY_PROG));
                    
                    // 2. Firebase kaydını 3 saniye ertele (Fren Mekanizması)
                    clearTimeout(saveTimeout);
                    saveTimeout = setTimeout(async () => {
                        syncLabel.innerText = "🔄 Buluta yazılıyor...";
                        try {
                            await setDoc(doc(db, "users", user.uid), { 
                                program: window.MY_PROG,
                                updated: new Date(),
                                // Gizlilik dostu meta veri (isteğe bağlı)
                                // email: user.email 
                            });
                            syncLabel.innerText = "☁️ Kaydedildi";
                            setTimeout(() => syncLabel.innerText = "☁️ Hazır", 2000);
                        } catch(e) {
                            console.error("Kayıt hatası:", e);
                            syncLabel.innerText = "⚠️ Kayıt Hatası";
                        }
                    }, 3000); // 3 Saniye bekleme süresi
                };

            }
        });
    }
</script>

<script>
    // --- CORE UYGULAMA MANTIĞI ---
    const RAW_DB = {db_placeholder};
    const SUBJ_LIST = {subj_placeholder};
    
    window.MY_PROG = {};
    let RESULT_LIST = [];
    let SHOWING_RESULTS = false; 
    window.NETWORK = null;
    const DAYS = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma"];

    // Placeholder save function (Firebase yüklenene kadar hata vermesin)
    window.triggerSave = function() {}; 

    // --- INIT FONKSİYONU ---
    function init() {
        const sel = document.getElementById('sel-subj');
        const frag = document.createDocumentFragment();
        SUBJ_LIST.forEach(s => {
            const opt = document.createElement('option');
            opt.value = s; opt.innerText = s;
            frag.appendChild(opt);
        });
        sel.appendChild(frag);
        document.getElementById('db-stat').innerText = `v14 • ${RAW_DB.length}`;
        
        // --- 4. SINIF FİLTRESİ AYARI ---
        // 1. Önce tercihi oku
        const isSeniorPref = localStorage.getItem("dam_show_senior") === "true";
        // 2. Checkbox'ı ayarla
        const chk = document.getElementById('chk-senior');
        if(chk) {
            chk.checked = isSeniorPref;
            // 3. Listener ekle (Değişken çakışması olmasın diye buraya aldık)
            chk.addEventListener('change', (e) => {
                localStorage.setItem("dam_show_senior", e.target.checked);
                runFilter(); 
            });
        }
        
        refreshUI();
    }

    // Fonksiyonları window'a sabitleyelim (Garanti yöntem)
    window.setMode = function(mode) {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
        if (mode === 'search') {
            document.querySelectorAll('.tab')[0].classList.add('active');
            document.getElementById('panel-search').classList.add('active');
        } else {
            document.querySelectorAll('.tab')[1].classList.add('active');
            document.getElementById('panel-filter').classList.add('active');
        }
    }

    let debounce;
    document.getElementById('inp-search').addEventListener('input', (e) => {
        clearTimeout(debounce);
        const val = e.target.value.toUpperCase().trim();
        if (val.length < 2) { if(RESULT_LIST.length > 0) clearResults(); return; }
        debounce = setTimeout(() => {
            const hits = [];
            for (let i = 0; i < RAW_DB.length; i++) {
                const c = RAW_DB[i];
                // Arama Mantığı
                if (!window.MY_PROG[c.id] && (c.k.includes(val) || c.id.includes(val) || c.n.toUpperCase().includes(val))) {
                    hits.push(c);
                    if (hits.length >= 50) break;
                }
            }
            showResults(hits);
        }, 300);
    });

    window.runFilter = function() {
        const subj = document.getElementById('sel-subj').value;
        const clean = document.getElementById('chk-clean').checked;
        
        // Checkbox güvenli seçim
        const chkSenior = document.getElementById('chk-senior');
        const showSenior = chkSenior ? chkSenior.checked : false;

        const loader = document.getElementById('loading');
        loader.style.display = 'block';

        setTimeout(() => {
            let hits = [];
            if (subj === "ALL") hits = RAW_DB; else hits = RAW_DB.filter(c => c.k.startsWith(subj));
            
            // Zaten ekli olanları gizle
            hits = hits.filter(c => !window.MY_PROG[c.id]);

            // --- 4. SINIF FİLTRESİ ---
            // Senior GÖSTERME (Checkbox False ise) -> Senior olanları filtrele
            if (!showSenior) {
                hits = hits.filter(c => c.lv4 !== true);
            }

            if (clean) {
                 // Çakışma kontrolü TÜM programdaki derslerle yapılıyor
                 const fixed = Object.values(window.MY_PROG); 
                 if (fixed.length > 0) {
                     hits = hits.filter(cand => {
                         for (let s1 of cand.s) for (let f of fixed) for (let s2 of f.s) 
                             if (s1.d === s2.d && Math.max(s1.b, s2.b) < Math.min(s1.e, s2.e)) return false;
                         return true;
                     });
                 }
            }
            
            showResults(hits.slice(0, 1000));
            loader.style.display = 'none';
        }, 50);
    }

    function showResults(data) {
        RESULT_LIST = data;
        document.getElementById('area-results').style.display = 'block';
        renderResultList();
    }

    window.clearResults = function() {
        RESULT_LIST = [];
        document.getElementById('area-results').style.display = 'none';
        document.getElementById('inp-search').value = "";
    }

    window.add = function(id) {
        const c = RAW_DB.find(x => x.id === id);
        if (c) {
            window.MY_PROG[id] = JSON.parse(JSON.stringify(c));
            RESULT_LIST = RESULT_LIST.filter(x => x.id !== id);
            if(RESULT_LIST.length === 0) window.clearResults(); else renderResultList();
            window.refreshUI();
            window.triggerSave();
        }
    }

    window.remove = function(id) { 
        delete window.MY_PROG[id]; 
        window.refreshUI(); 
        window.triggerSave(); 
    }

    window.toggleType = function(id) {
        if (window.MY_PROG[id]) { 
            window.MY_PROG[id].t = window.MY_PROG[id].t === "SABIT" ? "ADAY" : "SABIT"; 
            window.refreshUI(); 
            window.triggerSave(); 
        }
    }

    window.refreshUI = function() {
        renderProgramList();
        const confs = analyzeConflicts();
        drawNetwork(confs);
        drawSchedule(confs);
        updateBookmarklet();
    }

    function createCard(c, context) {
        const el = document.createElement('div');
        el.className = `card ${context === 'RESULT' ? 'RESULT' : c.t}`;
        el.id = `card-${c.id}`;
        let headerContent = `<div><span class="c-code">${c.k}</span> <span class="c-crn">${c.id}</span></div>` + 
            (context === 'RESULT' ? `<button class="c-action c-add" onclick="add('${c.id}')">+ EKLE</button>` : `<button class="c-action c-del" onclick="remove('${c.id}')">×</button>`);
        let footerContent = context === 'RESULT' ? '' : `<div class="card-footer-row"><button class="btn-toggle" onclick="toggleType('${c.id}')">${c.t}</button></div>`;
        el.innerHTML = `<div class="card-header-row">${headerContent}</div><div class="card-body-row"><div class="c-name">${c.n}</div><div class="c-prof">👨‍🏫 ${c.i}</div></div>${footerContent}`;
        return el;
    }

    function renderResultList() {
        const div = document.getElementById('list-results'); div.innerHTML = "";
        RESULT_LIST.forEach(c => div.appendChild(createCard(c, 'RESULT')));
    }

    function renderProgramList() {
        const div = document.getElementById('list-program'); div.innerHTML = "";
        const list = Object.values(window.MY_PROG).sort((a,b) => a.k.localeCompare(b.k));
        if (list.length === 0) div.innerHTML = '<div class="empty-state">Henüz ders eklenmedi.</div>';
        list.forEach(c => div.appendChild(createCard(c, 'PROGRAM')));
    }

    function analyzeConflicts() {
        const confs = []; const arr = Object.values(window.MY_PROG);
        document.querySelectorAll('.card').forEach(e => e.classList.remove('CONFLICT'));
        for (let i = 0; i < arr.length; i++) for (let j = i + 1; j < arr.length; j++) {
            let hit = false;
            for (let s1 of arr[i].s) for (let s2 of arr[j].s) 
                if (s1.d === s2.d && Math.max(s1.b, s2.b) < Math.min(s1.e, s2.e)) hit = true;
            if (hit) {
                confs.push(arr[i].id, arr[j].id);
                const c1 = document.getElementById(`card-${arr[i].id}`);
                const c2 = document.getElementById(`card-${arr[j].id}`);
                if(c1) c1.classList.add('CONFLICT'); if(c2) c2.classList.add('CONFLICT');
            }
        }
        return [...new Set(confs)];
    }

    function drawSchedule(confs) {
        const grid = document.getElementById('grid'); grid.innerHTML = '<div class="g-head"></div>';
        DAYS.forEach(d => grid.innerHTML += `<div class="g-head">${d}</div>`);
        for(let i=0; i<26; i++) {
            let h = 8 + Math.floor(i/2), m = i%2===0 ? "00" : "30", row = i + 2;
            if(m==="00") grid.innerHTML += `<div class="g-time" style="grid-row:${row}">${h}:${m}</div>`;
            grid.innerHTML += `<div class="g-line" style="grid-row:${row}"></div>`;
        }
        let allSlots = [];
        Object.values(window.MY_PROG).forEach(c => { c.s.forEach(s => allSlots.push({...s, ...c})); });
        allSlots.sort((a,b) => (a.b - b.b) || a.id.localeCompare(b.id));
        let placed = [];
        allSlots.forEach(slot => {
            const dayIdx = DAYS.indexOf(slot.d); if(dayIdx === -1) return;
            let overlap = 0;
            placed.forEach(p => { if(p.d === slot.d && Math.max(p.b, slot.b) < Math.min(p.e, slot.e)) overlap++; });
            const start = Math.round((slot.b - 8) * 2) + 2, end = Math.round((slot.e - 8) * 2) + 2, col = dayIdx + 2;
            const isConf = confs.includes(slot.id);
            const div = document.createElement('div');
            div.className = `box ${slot.t} ${isConf ? 'CONFLICT' : ''}`;
            div.style.gridRow = `${start} / ${end}`; div.style.gridColumn = col;
            div.style.marginLeft = (overlap * 10) + "px"; div.style.marginTop = (overlap * 10) + "px";
            div.style.width = `calc(100% - ${overlap * 10}px)`; div.style.zIndex = 10 + overlap;
            div.innerHTML = `<div style="font-weight:bold">${slot.k}</div><div style="opacity:0.8">${slot.n.substring(0,15)}</div>`;
            grid.appendChild(div); placed.push(slot);
        });
    }

    function drawNetwork(confs) {
        const nodes = [], edges = []; const arr = Object.values(window.MY_PROG);
        arr.forEach(c => {
            const isConf = confs.includes(c.id), isSabit = c.t === "SABIT";
            let bg = isConf ? (isSabit ? "#ff4d4d" : "#ffaa00") : (isSabit ? "#2e7d32" : "#4caf50");
            nodes.push({ id: c.id, label: c.k, color: { background: bg, border: "#fff" }, shape: isSabit ? "ellipse" : "circle", font:{color:"white", face:"Inter"} });
        });
        for(let i=0; i<arr.length; i++) for(let j=i+1; j<arr.length; j++) {
            let hit = false;
            for (let s1 of arr[i].s) for (let s2 of arr[j].s) 
                if (s1.d === s2.d && Math.max(s1.b, s2.b) < Math.min(s1.e, s2.e)) hit = true;
            if (hit) edges.push({from:arr[i].id, to:arr[j].id, color:{color:"#ff4d4d"}, dashes:true});
        }
        if(window.NETWORK) window.NETWORK.destroy();
        window.NETWORK = new vis.Network(document.getElementById('network'), {nodes:new vis.DataSet(nodes), edges:new vis.DataSet(edges)}, {physics:{stabilization:false}, interaction:{hover:true}});
    }

    function updateBookmarklet() {
        const list = Object.values(window.MY_PROG).filter(c => c.t === "SABIT").map(c => `"${c.id}"`).join(",");
        const code = `javascript: !function(){var e=[${list}];let t=document.querySelectorAll("input[type='number']"),n=0;t.forEach(t=>{(function e(t){let n=window.getComputedStyle(t);if("none"===n.display||"hidden"===n.visibility)return!1;let l=t.parentElement;for(;l;){let i=window.getComputedStyle(l);if("none"===i.display||"hidden"===i.visibility)return!1;l=l.parentElement}return!0})(t)&&n<e.length&&(t.value=e[n],t.dispatchEvent(new Event("input",{bubbles:!0})),n++)}),setTimeout(function(){let e=document.querySelector('button[type="submit"]:not([disabled])');e&&e.click(),setTimeout(function(){let e=document.querySelector(".card-footer.d-flex.justify-content-end");if(e){let t=e.getElementsByTagName("button");t.length>1&&t[1].click()}},50)},50)}();`;
        const btn = document.getElementById('bm-link');
        btn.href = code;
        btn.innerText = list.length ? `⚡ ${Object.values(window.MY_PROG).filter(c=>c.t==="SABIT").length} CRN Hazır` : "⚠️ Liste Boş";
    }

    // Başlat
    init();
</script>
</body>
</html>
"""

# --- 3. INŞAAT ---
def build():
    data_json, subj_json = process_data()
    if not data_json: return
    
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_template.replace("{db_placeholder}", data_json).replace("{subj_placeholder}", subj_json))
    
    print(f"✅ {OUTPUT_HTML} oluşturuldu!")

if __name__ == "__main__":
    build()
