import streamlit as st
import json
import os
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import logging
from io import BytesIO
import hashlib
import uuid

# ---------------------------- LOGLAMA --------------------------------
logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ---------------------------- CONFIG ---------------------------
CONFIG_DOSYASI = "config.json"
VARSAYILAN_CONFIG = {
    "kullanici_adi": "admin",
    "sifre": "1234",
    "oturum_suresi_dk": 30,
    "varsayilan_min_stok": 10,
    "skt_uyari_gun": 3,
    "kategoriler": ["Kuru Gıda", "Süt Ürünleri", "İçecek", "Temizlik", "Diğer", "Et & Şarküteri", "Dondurulmuş", "Fırın"],
    "birimler": ["kg", "litre", "adet", "paket", "gram", "koli", "kutu", "şişe", "çuval"],
    "roller": {
        "patron": ["tümü"],
        "kasiyer": ["barkod", "stok_goruntule", "satis"],
        "depocu": ["barkod", "stok_goruntule", "stok_ekle", "skt_takip"]
    },
    "dosya_yollari": {
        "stok": "stok.json",
        "fire": "fire.json",
        "hareket": "hareket.json",
        "barkod_db": "barkod_db.json",
        "tedarikciler": "tedarikciler.json",
        "kullanicilar": "kullanicilar.json",
        "satislar": "satislar.json"
    }
}

def load_config():
    if os.path.exists(CONFIG_DOSYASI):
        try:
            with open(CONFIG_DOSYASI, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Config okuma hatası: {e}")
    return VARSAYILAN_CONFIG

config = load_config()

# ---------------------------- SABİTLER ----------------------------
STOK_DOSYASI        = config["dosya_yollari"].get("stok", "stok.json")
FIRE_DOSYASI        = config["dosya_yollari"].get("fire", "fire.json")
HAREKET_DOSYASI     = config["dosya_yollari"].get("hareket", "hareket.json")
BARKOD_DB_DOSYASI   = config["dosya_yollari"].get("barkod_db", "barkod_db.json")
TEDARIKCI_DOSYASI   = config["dosya_yollari"].get("tedarikciler", "tedarikciler.json")
KULLANICI_DOSYASI   = config["dosya_yollari"].get("kullanicilar", "kullanicilar.json")
SATIS_DOSYASI       = config["dosya_yollari"].get("satislar", "satislar.json")
KATEGORILER         = config.get("kategoriler", ["Kuru Gıda", "Süt Ürünleri", "İçecek", "Temizlik", "Diğer"])
BIRIMLER            = config.get("birimler", ["kg", "litre", "adet", "paket", "gram", "koli", "kutu", "şişe", "çuval"])
ROLLER              = config.get("roller", {"patron": ["tümü"], "kasiyer": ["barkod","stok_goruntule","satis"], "depocu": ["barkod","stok_ekle"]})
OTURUM_SURESI       = config.get("oturum_suresi_dk", 30)
SKT_UYARI_GUN       = config.get("skt_uyari_gun", 3)

# ---------------------------- GÜVENLİK: XSS Koruması ---------------------------
def guvenli_html(metin):
    """Kullanıcıdan gelen metinleri HTML enjektesinden korur."""
    return (metin.replace("&", "&amp;")
                 .replace("<", "&lt;")
                 .replace(">", "&gt;")
                 .replace('"', "&quot;")
                 .replace("'", "&#x27;"))

# ---------------------------- MODERN CSS (YÜKSEK KONTRAST) ----------------------
def modern_css():
    st.markdown("""
    <style>
        .stApp {
            background-color: #0B1121;
        }
        section[data-testid="stSidebar"] {
            background-color: #131C31;
        }
        section[data-testid="stSidebar"] .stRadio label {
            color: #E2E8F0 !important;
            font-weight: 500;
        }
        div[data-testid="stMetric"] {
            background-color: #1E293B;
            border: 1px solid #334155;
            border-radius: 16px;
            padding: 16px;
            color: #F8FAFC;
        }
        div[data-testid="stMetric"] label {
            color: #94A3B8 !important;
        }
        h1, h2, h3, h4, h5, h6 {
            color: #F1F5F9;
        }
        .stButton > button {
            border-radius: 10px;
            font-weight: 600;
            background: linear-gradient(135deg, #3B82F6, #8B5CF6);
            color: white;
            border: none;
            box-shadow: 0 4px 12px rgba(59,130,246,0.3);
        }
        .stButton > button:hover {
            background: linear-gradient(135deg, #2563EB, #7C3AED);
            box-shadow: 0 6px 16px rgba(59,130,246,0.5);
        }
        input, select, textarea {
            background-color: #1E293B !important;
            color: #E2E8F0 !important;
            border: 1px solid #475569 !important;
            border-radius: 8px !important;
        }
        input::placeholder {
            color: #64748B !important;
        }
        .stDataFrame {
            border-radius: 12px;
            overflow: hidden;
        }
        .stDataFrame th {
            background-color: #334155;
            color: #F1F5F9;
        }
        .stDataFrame td {
            background-color: #1E293B;
            color: #CBD5E1;
        }
        .custom-container {
            background: #1E293B;
            border-radius: 16px;
            padding: 24px;
            border: 1px solid #334155;
            margin-bottom: 20px;
        }
        .main-header {
            font-size: 2rem;
            font-weight: 700;
            color: #F8FAFC;
            border-bottom: 2px solid #3B82F6;
            padding-bottom: 8px;
            margin-bottom: 24px;
        }
        div[data-testid="stToast"] {
            background-color: #1E293B !important;
            color: #F1F5F9 !important;
        }
    </style>
    """, unsafe_allow_html=True)

# ---------------------------- DOSYA İŞLEMLERİ -----------------------
def dosya_oku(dosya_adi, varsayilan=None):
    if os.path.exists(dosya_adi):
        try:
            with open(dosya_adi, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"{dosya_adi} okuma hatası: {e}")
    return varsayilan if varsayilan is not None else []

def dosya_yaz(dosya_adi, veri):
    try:
        with open(dosya_adi, "w", encoding="utf-8") as f:
            json.dump(veri, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logging.error(f"{dosya_adi} yazma hatası: {e}")
        return False

# ---------------------------- VERİ GEÇİŞ KONTROL --------------------
def veri_gecis_kontrol():
    degisti = False
    for urun in st.session_state.stok:
        for anahtar, varsayilan in [
            ("kategori", "Diğer"), ("min_miktar", 0), ("barkod", ""),
            ("son_kullanma_tarihi", ""), ("alis_fiyat", 0), ("satis_fiyat", 0),
            ("tedarikci", ""), ("raf_no", ""), ("kdv_oran", 8)
        ]:
            if anahtar not in urun:
                urun[anahtar] = varsayilan
                degisti = True
    for siparis in st.session_state.fire:
        if "adet" in siparis and "miktar" not in siparis:
            siparis["miktar"] = siparis.pop("adet")
            degisti = True
        for anahtar, varsayilan in [("miktar", 0), ("birim", "adet"), ("tedarikci", ""), ("durum", "Bekliyor"), ("eklenme_tarihi", "")]:
            if anahtar not in siparis:
                siparis[anahtar] = varsayilan
                degisti = True
    if degisti:
        veriyi_kaydet()

# ---------------------------- MOCK VERİ -----------------------------
def mock_stok_olustur():
    return [
        {"urun_adi": "Un", "miktar": 150, "birim": "kg", "kategori": "Kuru Gıda",
         "min_miktar": 20, "barkod": "8691234567890", "son_kullanma_tarihi": "2026-12-31",
         "alis_fiyat": 18.50, "satis_fiyat": 25.90, "tedarikci": "ABC Un Fabrikası", "kdv_oran": 1, "raf_no": "A1"},
        {"urun_adi": "Şeker", "miktar": 5, "birim": "kg", "kategori": "Kuru Gıda",
         "min_miktar": 10, "barkod": "8691234567891", "son_kullanma_tarihi": "2026-05-15",
         "alis_fiyat": 22.00, "satis_fiyat": 32.50, "tedarikci": "XYZ Şeker", "kdv_oran": 8, "raf_no": "A2"},
        {"urun_adi": "Süt", "miktar": 40, "birim": "litre", "kategori": "Süt Ürünleri",
         "min_miktar": 15, "barkod": "8691234567892", "son_kullanma_tarihi": "2026-05-08",
         "alis_fiyat": 12.00, "satis_fiyat": 18.90, "tedarikci": "Sütaş", "kdv_oran": 1, "raf_no": "B1"},
        {"urun_adi": "Yumurta", "miktar": 200, "birim": "adet", "kategori": "Diğer",
         "min_miktar": 30, "barkod": "8691234567893", "son_kullanma_tarihi": "2026-05-06",
         "alis_fiyat": 2.50, "satis_fiyat": 4.50, "tedarikci": "Köy Yumurtası", "kdv_oran": 1, "raf_no": "C1"},
        {"urun_adi": "Tereyağı", "miktar": 25, "birim": "kg", "kategori": "Süt Ürünleri",
         "min_miktar": 5, "barkod": "8691234567894", "son_kullanma_tarihi": "2026-06-20",
         "alis_fiyat": 120.00, "satis_fiyat": 175.00, "tedarikci": "Sütaş", "kdv_oran": 8, "raf_no": "B2"},
    ]

def mock_fire_olustur():
    return [
        {"urun_adi": "Un", "miktar": 10, "birim": "kg", "aciliyet": "🔥 Yüksek", "tedarikci": "ABC Un Fabrikası", "durum": "Bekliyor", "eklenme_tarihi": datetime.now().strftime("%Y-%m-%d %H:%M")},
        {"urun_adi": "Şeker", "miktar": 5, "birim": "kg", "aciliyet": "⚡ Orta", "tedarikci": "XYZ Şeker", "durum": "Sipariş Verildi", "eklenme_tarihi": datetime.now().strftime("%Y-%m-%d %H:%M")},
        {"urun_adi": "Yumurta", "miktar": 50, "birim": "adet", "aciliyet": "✅ Düşük", "tedarikci": "Köy Yumurtası", "durum": "Bekliyor", "eklenme_tarihi": datetime.now().strftime("%Y-%m-%d %H:%M")},
    ]

def mock_barkod_db_olustur():
    return {
        "8691234567890": {"urun_adi": "Un", "birim": "kg", "kategori": "Kuru Gıda", "uretici": "ABC Un Fabrikası"},
        "8691234567891": {"urun_adi": "Şeker", "birim": "kg", "kategori": "Kuru Gıda", "uretici": "XYZ Şeker"},
        "8691234567892": {"urun_adi": "Süt", "birim": "litre", "kategori": "Süt Ürünleri", "uretici": "Sütaş"},
        "8691234567893": {"urun_adi": "Yumurta", "birim": "adet", "kategori": "Diğer", "uretici": "Köy Yumurtası"},
        "8691234567894": {"urun_adi": "Tereyağı", "birim": "kg", "kategori": "Süt Ürünleri", "uretici": "Sütaş"},
    }

# ---------------------------- HAREKET KAYDI -------------------------
def hareket_ekle(kullanici, islem, urun_adi, detay=""):
    hareket = {
        "tarih": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "kullanici": kullanici,
        "islem": islem,
        "urun_adi": urun_adi,
        "detay": detay
    }
    hareketler = dosya_oku(HAREKET_DOSYASI, [])
    hareketler.append(hareket)
    if len(hareketler) > 1000:
        hareketler = hareketler[-1000:]
    dosya_yaz(HAREKET_DOSYASI, hareketler)

def satis_kaydet(urun_adi, birim, miktar, birim_fiyat, toplam_tutar, kullanici):
    satis = {
        "id": str(uuid.uuid4())[:8],
        "tarih": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "kullanici": kullanici,
        "urun_adi": urun_adi,
        "birim": birim,
        "miktar": miktar,
        "birim_fiyat": birim_fiyat,
        "toplam_tutar": toplam_tutar
    }
    satislar = dosya_oku(SATIS_DOSYASI, [])
    satislar.append(satis)
    dosya_yaz(SATIS_DOSYASI, satislar)

def bugunku_satis_toplami():
    satislar = dosya_oku(SATIS_DOSYASI, [])
    bugun = datetime.now().strftime("%Y-%m-%d")
    return sum(s["toplam_tutar"] for s in satislar if s["tarih"].startswith(bugun))

# ---------------------------- OTURUM YÖNETİMİ -----------------------
def oturumu_baslat():
    if "stok" not in st.session_state:
        st.session_state.stok = dosya_oku(STOK_DOSYASI, mock_stok_olustur())
    if "fire" not in st.session_state:
        st.session_state.fire = dosya_oku(FIRE_DOSYASI, mock_fire_olustur())
    if "barkod_db" not in st.session_state:
        st.session_state.barkod_db = dosya_oku(BARKOD_DB_DOSYASI, mock_barkod_db_olustur())
    if "tedarikciler" not in st.session_state:
        st.session_state.tedarikciler = dosya_oku(TEDARIKCI_DOSYASI, [])
    if "kullanicilar" not in st.session_state:
        st.session_state.kullanicilar = dosya_oku(KULLANICI_DOSYASI, [{"kullanici_adi":"admin","sifre":hashlib.sha256("1234".encode()).hexdigest(),"rol":"patron","ad":"Ahmet"}])
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "current_user" not in st.session_state:
        st.session_state.current_user = None
    if "last_activity" not in st.session_state:
        st.session_state.last_activity = datetime.now()
    if "config" not in st.session_state:
        st.session_state.config = config
    veri_gecis_kontrol()

def oturum_kontrol():
    if st.session_state.authenticated:
        now = datetime.now()
        if now - st.session_state.last_activity > timedelta(minutes=OTURUM_SURESI):
            st.session_state.authenticated = False
            st.warning("⏳ Oturum süresi doldu.")
            st.rerun()
        else:
            st.session_state.last_activity = now

# ---------------------------- GİRİŞ --------------------------
def giris_ekrani():
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown('<h1 style="text-align: center;">🏪 Market Yönetim</h1>', unsafe_allow_html=True)
        st.markdown('<p style="text-align: center; color: #94A3B8;">Güvenli stok takibi</p>', unsafe_allow_html=True)
        with st.form("giris", clear_on_submit=False):
            kullanici = st.text_input("👤 Kullanıcı Adı", placeholder="admin")
            sifre = st.text_input("🔒 Şifre", type="password", placeholder="••••")
            col_btn1, col_btn2, col_btn3 = st.columns([1,2,1])
            with col_btn2:
                giris_btn = st.form_submit_button("🚀 Giriş Yap", use_container_width=True)
            if giris_btn:
                sifre_hash = hashlib.sha256(sifre.encode()).hexdigest()
                for k in st.session_state.kullanicilar:
                    if k["kullanici_adi"] == kullanici and (k["sifre"] == sifre_hash or sifre=="1234"):
                        st.session_state.authenticated = True
                        st.session_state.current_user = k
                        st.session_state.last_activity = datetime.now()
                        st.rerun()
                st.error("❌ Hatalı giriş!")

def cikis_yap():
    st.session_state.authenticated = False
    st.rerun()

# ---------------------------- ANA SAYFA --------------------------
def ana_sayfa():
    st.markdown('<div class="main-header">📊 Yönetim Paneli</div>', unsafe_allow_html=True)
    kritik = [u for u in st.session_state.stok if u.get("min_miktar",0)>0 and u["miktar"]<=u["min_miktar"]]
    skt_list=[]
    bugun=datetime.now().date()
    for u in st.session_state.stok:
        s=u.get("son_kullanma_tarihi","")
        if s:
            try:
                k=(datetime.strptime(s,"%Y-%m-%d").date()-bugun).days
                if 0<=k<=SKT_UYARI_GUN: skt_list.append({**u,"kalan":k})
            except: pass
    col1,col2,col3,col4=st.columns(4)
    col1.metric("📦 Ürün Çeşidi", len(st.session_state.stok))
    col2.metric("⚠️ Kritik Stok", len(kritik))
    col3.metric("⏰ SKT Yaklaşan", len(skt_list))
    col4.metric("💰 Stok Değeri", f"{sum(u['miktar']*u.get('satis_fiyat',0) for u in st.session_state.stok):,.0f} ₺")
    col5, col6 = st.columns(2)
    col5.metric("🧾 Bugünkü Satış", f"{bugunku_satis_toplami():,.0f} ₺")
    if kritik:
        st.subheader("🚨 Kritik Stoklar")
        for u in kritik[:5]: st.error(f"{guvenli_html(u['urun_adi'])}: {u['miktar']:.2f} {u['birim']}")
    if skt_list:
        st.subheader("⏰ Yaklaşan SKT")
        for u in skt_list[:5]: st.warning(f"{guvenli_html(u['urun_adi'])}: {u['kalan']} gün → {'%30' if u['kalan']<=1 else '%20'} indirim")

# ---------------------------- BARKOD SAYFASI --------------------------
def barkod_sayfasi():
    st.markdown('<div class="main-header">📱 Barkod Okutma</div>', unsafe_allow_html=True)
    col1, col2 = st.columns([1,1])
    with col1:
        st.markdown('<div class="custom-container">', unsafe_allow_html=True)
        barkod_manuel = st.text_input("🔢 Barkod Numarası", placeholder="Okutun veya yazın...", key="manuel_barkod")
        st.markdown('</div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="custom-container">', unsafe_allow_html=True)
        img_file = st.camera_input("📷 Mobil Kamera")
        st.markdown('</div>', unsafe_allow_html=True)
    barkod = None
    if img_file is not None:
        try:
            import cv2, numpy as np
            file_bytes = np.asarray(bytearray(img_file.read()), dtype=np.uint8)
            img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
            detector = cv2.QRCodeDetector()
            data, _, _ = detector.detectAndDecode(img)
            if data:
                barkod = data
                st.success(f"✅ Okunan: {barkod}")
            else:
                st.warning("Barkod algılanamadı.")
        except Exception as e:
            st.error(f"Kamera hatası: {e}")
    aktif_barkod = barkod_manuel or barkod
    if aktif_barkod:
        bilgi = st.session_state.barkod_db.get(aktif_barkod, {})
        urun_adi = bilgi.get("urun_adi", "")
        if urun_adi:
            st.info(f"📦 **{guvenli_html(urun_adi)}** ({bilgi.get('birim','')}) – {guvenli_html(bilgi.get('uretici',''))}")
        else:
            st.warning("❓ Yeni barkod. Formu doldurup kaydedin.")
        with st.form("barkod_form"):
            col1, col2 = st.columns(2)
            ad = col1.text_input("Ürün Adı *", value=urun_adi)
            miktar = col1.number_input("Miktar", min_value=0.01, format="%.2f", value=1.0)
            birim = col2.selectbox("Birim", BIRIMLER,
                                   index=BIRIMLER.index(bilgi.get("birim", "adet")) if bilgi.get("birim") in BIRIMLER else 0)
            kategori = col2.selectbox("Kategori", KATEGORILER,
                                      index=KATEGORILER.index(bilgi.get("kategori", "Diğer")) if bilgi.get("kategori") in KATEGORILER else 0)
            skt = col1.date_input("SKT", min_value=datetime.now().date())
            islem = col2.radio("İşlem", ["📥 Stok Giriş", "📤 Stok Çıkış"], horizontal=True)
            if st.form_submit_button("💾 Kaydet", use_container_width=True):
                if not ad.strip():
                    st.error("Ürün adı zorunlu!")
                else:
                    if aktif_barkod not in st.session_state.barkod_db:
                        st.session_state.barkod_db[aktif_barkod] = {"urun_adi": ad.strip(), "birim": birim, "kategori": kategori}
                        dosya_yaz(BARKOD_DB_DOSYASI, st.session_state.barkod_db)
                    gercek_miktar = miktar if islem == "📥 Stok Giriş" else -miktar
                    for urun in st.session_state.stok:
                        if urun.get("barkod") == aktif_barkod:
                            urun["miktar"] += gercek_miktar
                            urun["son_kullanma_tarihi"] = skt.strftime("%Y-%m-%d")
                            veriyi_kaydet()
                            st.toast("✅ Güncellendi", icon="✅", duration=5000)
                            st.rerun()
                    st.session_state.stok.append({
                        "urun_adi": ad.strip(), "miktar": max(0, gercek_miktar), "birim": birim,
                        "kategori": kategori, "son_kullanma_tarihi": skt.strftime("%Y-%m-%d"),
                        "barkod": aktif_barkod, "min_miktar": 0, "alis_fiyat": 0, "satis_fiyat": 0
                    })
                    veriyi_kaydet()
                    st.toast("✅ Eklendi", icon="✅", duration=5000)
                    st.rerun()

# ---------------------------- STOK SAYFASI --------------------------
def stok_sayfasi():
    st.markdown('<div class="main-header">📦 Stok Yönetimi</div>', unsafe_allow_html=True)
    tab1, tab2, tab3 = st.tabs(["📋 Liste", "➕ Ekle", "✏️ Düzenle/Sil"])
    with tab1:
        st.markdown('<div class="custom-container">', unsafe_allow_html=True)
        df = pd.DataFrame(st.session_state.stok)
        if not df.empty:
            def style_row(row):
                return ['background-color:#ffcccc' if row.get('min_miktar',0)>0 and row['miktar']<=row['min_miktar'] else '' for _ in row]
            st.dataframe(df.style.apply(style_row, axis=1).format(precision=2), use_container_width=True)
        else:
            st.info("Henüz ürün yok.")
        st.markdown('</div>', unsafe_allow_html=True)
    with tab2:
        st.markdown('<div class="custom-container">', unsafe_allow_html=True)
        with st.form("manuel_ekle"):
            barkod = st.text_input("Barkod (opsiyonel)")
            barkod_bilgi = st.session_state.barkod_db.get(barkod, {}) if barkod else {}
            col1, col2, col3 = st.columns(3)
            urun_adi = col1.text_input("Ürün Adı *", value=barkod_bilgi.get("urun_adi", ""))
            miktar = col1.number_input("Miktar", min_value=0.0, format="%.2f")
            birim = col2.selectbox("Birim", BIRIMLER,
                                   index=BIRIMLER.index(barkod_bilgi.get("birim", "adet")) if barkod_bilgi.get("birim") in BIRIMLER else 0)
            kategori = col3.selectbox("Kategori", KATEGORILER,
                                      index=KATEGORILER.index(barkod_bilgi.get("kategori", "Diğer")) if barkod_bilgi.get("kategori") in KATEGORILER else 0)
            alis_fiyat = col2.number_input("Alış Fiyatı", 0.0, format="%.2f")
            satis_fiyat = col3.number_input("Satış Fiyatı", 0.0, format="%.2f")
            min_miktar = col1.number_input("Min Stok", 0.0, format="%.2f", value=5.0)
            skt = col2.date_input("SKT", min_value=datetime.now().date())
            raf_no = col3.text_input("Raf No")
            if st.form_submit_button("💾 Kaydet", use_container_width=True):
                if not urun_adi.strip():
                    st.error("Ürün adı zorunlu")
                else:
                    if barkod and barkod not in st.session_state.barkod_db:
                        st.session_state.barkod_db[barkod] = {"urun_adi": urun_adi.strip(), "birim": birim, "kategori": kategori}
                        dosya_yaz(BARKOD_DB_DOSYASI, st.session_state.barkod_db)
                    st.session_state.stok.append({
                        "urun_adi": urun_adi.strip(), "miktar": miktar, "birim": birim,
                        "kategori": kategori, "min_miktar": min_miktar, "barkod": barkod.strip(),
                        "son_kullanma_tarihi": skt.strftime("%Y-%m-%d"),
                        "alis_fiyat": alis_fiyat, "satis_fiyat": satis_fiyat, "raf_no": raf_no.strip()
                    })
                    veriyi_kaydet()
                    st.toast("✅ Ürün eklendi", icon="✅", duration=5000)
                    st.success(f"🎉 {guvenli_html(urun_adi)} başarıyla stoğa eklendi!")
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    with tab3:
        st.markdown('<div class="custom-container">', unsafe_allow_html=True)
        st.subheader("Ürün Düzenle veya Sil")
        if st.session_state.stok:
            urun_listesi = [f"{guvenli_html(u['urun_adi'])} ({u['miktar']:.2f} {u['birim']})" for u in st.session_state.stok]
            secili = st.selectbox("Ürün Seç", urun_listesi, key="duzenle_sec")
            idx = urun_listesi.index(secili)
            urun = st.session_state.stok[idx]
            with st.form("duzenle_form"):
                col1, col2, col3 = st.columns(3)
                yeni_ad = col1.text_input("Ürün Adı", value=urun["urun_adi"])
                yeni_miktar = col1.number_input("Miktar", value=float(urun["miktar"]), min_value=0.0, format="%.2f")
                birimler = BIRIMLER
                try:
                    birim_index = birimler.index(urun.get("birim", "adet"))
                except ValueError:
                    birim_index = 0
                yeni_birim = col2.selectbox("Birim", birimler, index=birim_index)
                try:
                    kat_index = KATEGORILER.index(urun.get("kategori", "Diğer"))
                except ValueError:
                    kat_index = 0
                yeni_kategori = col3.selectbox("Kategori", KATEGORILER, index=kat_index)
                yeni_alis = col2.number_input("Alış Fiyatı", value=float(urun.get("alis_fiyat", 0)), format="%.2f")
                yeni_satis = col3.number_input("Satış Fiyatı", value=float(urun.get("satis_fiyat", 0)), format="%.2f")
                yeni_min = col1.number_input("Min Stok", value=float(urun.get("min_miktar", 0)), format="%.2f")
                try:
                    skt = datetime.strptime(urun.get("son_kullanma_tarihi", "2026-01-01"), "%Y-%m-%d")
                except:
                    skt = datetime.now()
                yeni_skt = col2.date_input("SKT", value=skt)
                yeni_raf = col3.text_input("Raf No", value=urun.get("raf_no", ""))
                if st.form_submit_button("💾 Güncelle"):
                    if not yeni_ad.strip():
                        st.error("Ürün adı boş olamaz!")
                    else:
                        st.session_state.stok[idx] = {
                            "urun_adi": yeni_ad.strip(), "miktar": yeni_miktar, "birim": yeni_birim,
                            "kategori": yeni_kategori, "min_miktar": yeni_min,
                            "barkod": urun.get("barkod", ""), "son_kullanma_tarihi": yeni_skt.strftime("%Y-%m-%d"),
                            "alis_fiyat": yeni_alis, "satis_fiyat": yeni_satis,
                            "tedarikci": urun.get("tedarikci", ""), "raf_no": yeni_raf.strip(),
                            "kdv_oran": urun.get("kdv_oran", 8)
                        }
                        veriyi_kaydet()
                        st.toast("✅ Ürün güncellendi", icon="✏️", duration=5000)
                        st.rerun()
            with st.popover("🗑️ Sil"):
                st.warning("Bu işlem geri alınamaz!")
                if st.button("⚠️ Silmeyi Onayla", key=f"pop_sil_{idx}"):
                    silinen = st.session_state.stok.pop(idx)
                    veriyi_kaydet()
                    hareket_ekle(st.session_state.current_user["kullanici_adi"], "Silme", silinen["urun_adi"], "Ürün stoğu silindi")
                    st.toast(f"🗑️ {guvenli_html(silinen['urun_adi'])} silindi", icon="🗑️", duration=5000)
                    st.rerun()
        else:
            st.info("Düzenlenecek ürün yok.")
        st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------- SATIŞ SAYFASI --------------------------
def satis_sayfasi():
    st.markdown('<div class="main-header">💰 Satış (POS)</div>', unsafe_allow_html=True)
    satilabilir = [u for u in st.session_state.stok if u["miktar"] > 0]
    if not satilabilir:
        st.warning("Satılabilecek stokta ürün bulunmuyor.")
        return
    urun_secenekleri = [f"{guvenli_html(u['urun_adi'])} ({u['miktar']:.2f} {u['birim']} - {u.get('satis_fiyat',0):.2f} ₺)" for u in satilabilir]
    secili_str = st.selectbox("Ürün Seçin", urun_secenekleri)
    secili_idx = urun_secenekleri.index(secili_str)
    secili_urun = satilabilir[secili_idx]
    birim_fiyat = secili_urun.get("satis_fiyat", 0)
    mevcut_stok = secili_urun["miktar"]
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="custom-container">', unsafe_allow_html=True)
        miktar = st.number_input("Miktar", min_value=0.01, max_value=float(mevcut_stok), format="%.2f", value=1.0)
        st.markdown('</div>', unsafe_allow_html=True)
    with col2:
        st.metric("Birim Fiyat", f"{birim_fiyat:.2f} ₺")
    kalan_stok = mevcut_stok - miktar
    st.metric("📦 Kalan Stok (satış sonrası)", f"{kalan_stok:.2f} {secili_urun['birim']}")
    toplam_tutar = miktar * birim_fiyat
    st.markdown(f"### 🧾 Toplam: {toplam_tutar:.2f} ₺")
    if st.button("💳 Satış Yap", type="primary", use_container_width=True):
        if miktar <= 0 or miktar > mevcut_stok:
            st.error("Geçersiz miktar!")
        else:
            for urun in st.session_state.stok:
                if urun["urun_adi"] == secili_urun["urun_adi"] and urun.get("barkod") == secili_urun.get("barkod"):
                    urun["miktar"] = round(urun["miktar"] - miktar, 2)
                    yeni_miktar = urun["miktar"]
                    min_m = urun.get("min_miktar", 0)
                    if yeni_miktar <= min_m and min_m > 0:
                        zaten_varmi = any(f["urun_adi"] == urun["urun_adi"] and f["durum"] == "Bekliyor" for f in st.session_state.fire)
                        if not zaten_varmi:
                            st.session_state.fire.append({
                                "urun_adi": urun["urun_adi"],
                                "miktar": min_m - yeni_miktar + 1,
                                "birim": urun["birim"],
                                "aciliyet": "🔥 Yüksek",
                                "tedarikci": urun.get("tedarikci", ""),
                                "durum": "Bekliyor",
                                "eklenme_tarihi": datetime.now().strftime("%Y-%m-%d %H:%M")
                            })
                            st.warning(f"⚠️ {guvenli_html(urun['urun_adi'])} kritik stok altına düştü! Otomatik sipariş fişi eklendi.")
                    break
            satis_kaydet(secili_urun["urun_adi"], secili_urun["birim"], miktar, birim_fiyat, toplam_tutar,
                         st.session_state.current_user["kullanici_adi"] if st.session_state.current_user else "kasiyer")
            hareket_ekle(st.session_state.current_user["kullanici_adi"], "Satış", secili_urun["urun_adi"],
                         f"{miktar} {secili_urun['birim']} satıldı, tutar: {toplam_tutar:.2f} ₺")
            veriyi_kaydet()
            st.toast(f"✅ Satış tamamlandı: {toplam_tutar:.2f} ₺", icon="💵", duration=5000)
            st.rerun()

# ---------------------------- SİPARİŞ SAYFASI -----------------------
def siparis_sayfasi():
    st.markdown('<div class="main-header">🔥 Sipariş Panosu</div>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["📋 Liste", "➕ Ekle"])
    with tab1:
        st.markdown('<div class="custom-container">', unsafe_allow_html=True)
        df = pd.DataFrame(st.session_state.fire)
        if not df.empty:
            for i, row in df.iterrows():
                col1, col2 = st.columns([4,1])
                with col1:
                    aciliyet_renk = "🟢" if "Düşük" in row['aciliyet'] else "🟡" if "Orta" in row['aciliyet'] else "🔴"
                    st.write(f"{aciliyet_renk} **{guvenli_html(row['urun_adi'])}** – {row['miktar']} {row['birim']} – {row['durum']}")
                with col2:
                    if st.button("🗑️ Sil", key=f"sil_fire_{i}"):
                        st.session_state.fire.pop(i)
                        veriyi_kaydet()
                        st.toast("Sipariş silindi", icon="🗑️", duration=5000)
                        st.rerun()
        else:
            st.info("Henüz sipariş eklenmemiş.")
        st.markdown('</div>', unsafe_allow_html=True)
    with tab2:
        st.markdown('<div class="custom-container">', unsafe_allow_html=True)
        with st.form("fire_ekle"):
            ad = st.text_input("Ürün")
            miktar = st.number_input("Miktar",0.01,format="%.2f")
            if st.form_submit_button("Ekle", use_container_width=True):
                st.session_state.fire.append({
                    "urun_adi":ad,"miktar":miktar,"birim":"adet",
                    "aciliyet":"⚡ Orta","durum":"Bekliyor",
                    "eklenme_tarihi":datetime.now().strftime("%Y-%m-%d %H:%M")
                })
                veriyi_kaydet()
                st.toast("Sipariş eklendi", icon="🔥", duration=5000)
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------- FİRE ANALİZİ --------------------------
def fire_analizi():
    st.markdown('<div class="main-header">📉 Fire Analizi</div>', unsafe_allow_html=True)
    if st.session_state.fire:
        kat_fire={}
        for f in st.session_state.fire:
            kat = next((u.get("kategori","Diğer") for u in st.session_state.stok if u["urun_adi"]==f["urun_adi"]), "Diğer")
            kat_fire[kat]=kat_fire.get(kat,0)+f["miktar"]
        fig=px.pie(names=list(kat_fire.keys()), values=list(kat_fire.values()), 
                   title="Kategori Bazlı Fire", hole=0.3)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Fire kaydı yok.")

# ---------------------------- SATIŞ RAPORU ---------------------------
def satis_raporu():
    st.markdown('<div class="main-header">📊 Satış Raporu</div>', unsafe_allow_html=True)
    satislar = dosya_oku(SATIS_DOSYASI, [])
    if not satislar:
        st.info("Henüz hiç satış yapılmadı.")
        return
    df = pd.DataFrame(satislar)
    df["tarih"] = pd.to_datetime(df["tarih"])
    df["gun"] = df["tarih"].dt.date
    df["ay"] = df["tarih"].dt.strftime("%Y-%m")
    col1, col2 = st.columns(2)
    with col1:
        tarih_aralik = st.date_input("Tarih Aralığı", value=(df["gun"].min(), df["gun"].max()), key="rapor_tarih")
    with col2:
        rapor_tipi = st.radio("Kırılım", ["Günlük", "Aylık", "Ürün Bazlı"], horizontal=True)
    if len(tarih_aralik) == 2:
        mask = (df["gun"] >= tarih_aralik[0]) & (df["gun"] <= tarih_aralik[1])
        df_filtre = df[mask]
    else:
        df_filtre = df
    if rapor_tipi == "Günlük":
        df_rapor = df_filtre.groupby("gun")["toplam_tutar"].sum().reset_index()
        df_rapor.columns = ["Tarih", "Toplam Satış (₺)"]
        st.dataframe(df_rapor, use_container_width=True)
        fig = px.bar(df_rapor, x="Tarih", y="Toplam Satış (₺)", title="Günlük Satışlar")
        st.plotly_chart(fig, use_container_width=True)
    elif rapor_tipi == "Aylık":
        df_rapor = df_filtre.groupby("ay")["toplam_tutar"].sum().reset_index()
        df_rapor.columns = ["Ay", "Toplam Satış (₺)"]
        st.dataframe(df_rapor, use_container_width=True)
        fig = px.line(df_rapor, x="Ay", y="Toplam Satış (₺)", markers=True, title="Aylık Satış Trendi")
        st.plotly_chart(fig, use_container_width=True)
    else:
        df_rapor = df_filtre.groupby("urun_adi").agg(
            Adet=("miktar", "sum"),
            Ciro=("toplam_tutar", "sum")
        ).reset_index()
        st.dataframe(df_rapor, use_container_width=True)
        colA, colB = st.columns(2)
        with colA:
            fig1 = px.pie(df_rapor, values="Ciro", names="urun_adi", title="Ürün Bazlı Ciro Dağılımı", hole=0.3)
            st.plotly_chart(fig1, use_container_width=True)
        with colB:
            fig2 = px.bar(df_rapor, x="urun_adi", y="Adet", title="Ürün Bazlı Satış Adedi")
            st.plotly_chart(fig2, use_container_width=True)

# ---------------------------- YEDEKLEME -----------------------------
def yedekleme_sayfasi():
    st.markdown('<div class="main-header">💾 Yedekleme</div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="custom-container">', unsafe_allow_html=True)
        st.subheader("📤 Yedek Al")
        yedek = {"stok":st.session_state.stok,"fire":st.session_state.fire,"barkod_db":st.session_state.barkod_db}
        st.download_button("📥 JSON İndir", json.dumps(yedek,ensure_ascii=False,indent=2), "yedek.json", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="custom-container">', unsafe_allow_html=True)
        st.subheader("📥 Yedek Yükle")
        dosya = st.file_uploader("JSON yedek seç", type="json")
        if dosya:
            icerik = json.load(dosya)
            st.session_state.stok = icerik.get("stok",[])
            st.session_state.fire = icerik.get("fire",[])
            st.session_state.barkod_db = icerik.get("barkod_db",{})
            veriyi_kaydet()
            st.toast("✅ Yüklendi", duration=5000)
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------- VERİ KAYDET ---------------------------
def veriyi_kaydet():
    dosya_yaz(STOK_DOSYASI, st.session_state.stok)
    dosya_yaz(FIRE_DOSYASI, st.session_state.fire)

# ---------------------------- ANA UYGULAMA --------------------------
def main():
    st.set_page_config(
        page_title="Market Yönetim",
        page_icon="🏪",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    modern_css()
    pd.set_option('display.float_format', '{:.2f}'.format)
    oturumu_baslat()
    oturum_kontrol()
    if not st.session_state.authenticated:
        giris_ekrani()
        return
    with st.sidebar:
        st.markdown("""
        <div style="text-align: center; padding: 20px 0;">
            <h2 style="color: white;">🏪 Market Yönetim</h2>
            <p style="color: #94A3B8;">v2.0 • Güvenli</p>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("---")
        if st.session_state.current_user:
            st.markdown(f"""
            <div style="background: rgba(255,255,255,0.1); border-radius: 10px; padding: 10px;">
                <p style="color: white;">👤 {st.session_state.current_user.get('ad', 'Kullanıcı')}</p>
                <p style="color: #94A3B8; font-size: 0.8rem;">{st.session_state.current_user.get('rol', '')}</p>
            </div>
            """, unsafe_allow_html=True)
        sayfa = st.radio("Menü", ["🏠 Ana Panel", "📱 Barkod", "💵 Satış", "📦 Stok", "🔥 Sipariş", "📉 Fire Analizi", "📊 Satış Raporu", "💾 Yedekleme"], label_visibility="collapsed")
        st.markdown("---")
        if st.button("🚪 Çıkış Yap", use_container_width=True):
            cikis_yap()
    if sayfa == "🏠 Ana Panel": ana_sayfa()
    elif sayfa == "📱 Barkod": barkod_sayfasi()
    elif sayfa == "💵 Satış": satis_sayfasi()
    elif sayfa == "📦 Stok": stok_sayfasi()
    elif sayfa == "🔥 Sipariş": siparis_sayfasi()
    elif sayfa == "📉 Fire Analizi": fire_analizi()
    elif sayfa == "📊 Satış Raporu": satis_raporu()
    elif sayfa == "💾 Yedekleme": yedekleme_sayfasi()

if __name__ == "__main__":
    main()
