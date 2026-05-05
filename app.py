import streamlit as st
import json
import os
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import logging
import hashlib
import uuid
from io import BytesIO
import requests
import smtplib
import ssl
from email.mime.text import MIMEText

# ---------------------------- LOGLAMA --------------------------------
logging.basicConfig(filename='app.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# ---------------------------- CONFIG ---------------------------
CONFIG_DOSYASI = "config.json"
VARSAYILAN_CONFIG = {
    "kullanici_adi": "admin",
    "sifre": "1234",
    "oturum_suresi_dk": 30,
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
        except:
            pass
    return VARSAYILAN_CONFIG

config = load_config()
STOK_DOSYASI = config["dosya_yollari"].get("stok", "stok.json")
FIRE_DOSYASI = config["dosya_yollari"].get("fire", "fire.json")
HAREKET_DOSYASI = config["dosya_yollari"].get("hareket", "hareket.json")
BARKOD_DB_DOSYASI = config["dosya_yollari"].get("barkod_db", "barkod_db.json")
TEDARIKCI_DOSYASI = config["dosya_yollari"].get("tedarikciler", "tedarikciler.json")
KULLANICI_DOSYASI = config["dosya_yollari"].get("kullanicilar", "kullanicilar.json")
SATIS_DOSYASI = config["dosya_yollari"].get("satislar", "satislar.json")
KATEGORILER = config.get("kategoriler", ["Kuru Gıda", "Süt Ürünleri", "İçecek", "Temizlik", "Diğer"])
BIRIMLER = config.get("birimler", ["kg", "litre", "adet", "paket", "gram", "koli", "kutu", "şişe", "çuval"])
ROLLER = config.get("roller", {"patron": ["tümü"], "kasiyer": ["barkod"], "depocu": ["barkod", "stok_ekle"]})
OTURUM_SURESI = config.get("oturum_suresi_dk", 30)
SKT_UYARI_GUN = config.get("skt_uyari_gun", 3)

# ---------------------------- GÜVENLİK ---------------------------
def guvenli_html(metin):
    return (str(metin).replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#x27;"))

# ---------------------------- CSS (MOBİL UYUMLU) --------------------------------
def enerjik_css():
    st.markdown("""
    <style>
        .stApp { background-color: #0B1121 !important; }
        .main { color: #E2E8F0; }
        header[data-testid="stHeader"] { background-color: #141B2D; }
        section[data-testid="stSidebar"] { background-color: #141B2D; }
        section[data-testid="stSidebar"] .stRadio label { color: #E2E8F0 !important; font-weight: 600; }
        div[data-testid="stMetric"] {
            background: linear-gradient(145deg, #1a1f35, #0f1424);
            border: 1px solid #2D3748;
            border-radius: 20px;
            padding: 24px;
            color: #FFFFFF;
            box-shadow: 0 10px 25px rgba(0,0,0,0.6);
        }
        div[data-testid="stMetric"] label { color: #CBD5E1 !important; font-weight: 600; }
        div[data-testid="stMetric"] div[data-testid="stMetricValue"] { color: #FFFFFF !important; font-size: 2.2rem; }
        h1, h2, h3, h4, h5, h6 { color: #F1F5F9; }
        p, span, label { color: #E2E8F0; }
        .stButton > button {
            border-radius: 14px; font-weight: 700;
            background: linear-gradient(135deg, #F97316, #8B5CF6);
            color: white; border: none; padding: 0.7rem 2rem;
            box-shadow: 0 5px 15px rgba(249,115,22,0.5);
        }
        .stButton > button:hover {
            background: linear-gradient(135deg, #ea580c, #7c3aed);
            box-shadow: 0 8px 25px rgba(249,115,22,0.7);
        }
        input, select, textarea {
            background-color: #141B2D !important;
            color: #FFFFFF !important;
            border: 1px solid #4B5563 !important;
            border-radius: 10px !important;
        }
        input::placeholder { color: #9CA3AF !important; }
        .stDataFrame {
            border-radius: 18px; overflow: hidden; border: 1px solid #2D3748; background-color: #141B2D;
        }
        .stDataFrame th { background-color: #1E293B; color: #FFFFFF; }
        .stDataFrame td { background-color: #141B2D; color: #E2E8F0; }
        .custom-container {
            background-color: #141B2D; border-radius: 24px; padding: 30px;
            border: 1px solid #2D3748; box-shadow: 0 15px 30px rgba(0,0,0,0.6);
            margin-bottom: 25px;
        }
        .main-header {
            font-size: 2.3rem; font-weight: 800;
            background: linear-gradient(135deg, #F97316, #8B5CF6);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            margin-bottom: 1.5rem; padding-bottom: 0.5rem;
            border-bottom: 2px solid #F97316;
        }
        div[data-testid="stToast"] {
            background-color: #141B2D !important; color: #FFFFFF !important;
            border-left: 4px solid #F97316;
        }
        /* MOBİL UYUMLULUK */
        @media (max-width: 768px) {
            .custom-container { padding: 12px !important; margin: 8px 0 !important; }
            .main-header { font-size: 1.4rem !important; }
            .stButton > button { width: 100% !important; padding: 12px !important; font-size: 16px !important; }
            input, select, textarea { font-size: 16px !important; }
            .stDataFrame { font-size: 12px; }
        }
    </style>
    """, unsafe_allow_html=True)

# ---------------------------- DOSYA İŞLEMLERİ -----------------------
def dosya_oku(dosya_adi, varsayilan=None):
    if os.path.exists(dosya_adi):
        try:
            with open(dosya_adi, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return varsayilan if varsayilan is not None else []

def dosya_yaz(dosya_adi, veri):
    try:
        with open(dosya_adi, "w", encoding="utf-8") as f:
            json.dump(veri, f, ensure_ascii=False, indent=2)
        return True
    except:
        return False

# ---------------------------- VERİ GEÇİŞ KONTROL --------------------
def veri_gecis_kontrol():
    degisti = False
    for u in st.session_state.stok:
        for k, v in [("kategori", "Diğer"), ("min_miktar", 0), ("barkod", ""),
                     ("son_kullanma_tarihi", ""), ("alis_fiyat", 0), ("satis_fiyat", 0),
                     ("tedarikci", ""), ("raf_no", ""), ("kdv_oran", 8), ("tahmini_gunluk_satis", 1.0)]:
            if k not in u:
                u[k] = v
                degisti = True
    for s in st.session_state.fire:
        if "adet" in s and "miktar" not in s:
            s["miktar"] = s.pop("adet")
            degisti = True
        for k, v in [("miktar", 0), ("birim", "adet"), ("tedarikci", ""), ("durum", "Bekliyor"),
                     ("eklenme_tarihi", "")]:
            if k not in s:
                s[k] = v
                degisti = True
    if degisti:
        veriyi_kaydet()

# ---------------------------- MOCK VERİ -----------------------------
def mock_stok_olustur():
    return [
        {"urun_adi": "Un", "miktar": 150, "birim": "kg", "kategori": "Kuru Gıda",
         "min_miktar": 20, "barkod": "8691234567890", "son_kullanma_tarihi": "2026-12-31",
         "alis_fiyat": 18.50, "satis_fiyat": 25.90, "tedarikci": "ABC Un Fabrikası", "kdv_oran": 1,
         "raf_no": "A1", "tahmini_gunluk_satis": 5.0},
        {"urun_adi": "Şeker", "miktar": 5, "birim": "kg", "kategori": "Kuru Gıda",
         "min_miktar": 10, "barkod": "8691234567891", "son_kullanma_tarihi": "2026-05-15",
         "alis_fiyat": 22.00, "satis_fiyat": 32.50, "tedarikci": "XYZ Şeker", "kdv_oran": 8,
         "raf_no": "A2", "tahmini_gunluk_satis": 2.0},
        {"urun_adi": "Süt", "miktar": 40, "birim": "litre", "kategori": "Süt Ürünleri",
         "min_miktar": 15, "barkod": "8691234567892", "son_kullanma_tarihi": "2026-05-08",
         "alis_fiyat": 12.00, "satis_fiyat": 18.90, "tedarikci": "Sütaş", "kdv_oran": 1,
         "raf_no": "B1", "tahmini_gunluk_satis": 8.0},
        {"urun_adi": "Yumurta", "miktar": 200, "birim": "adet", "kategori": "Diğer",
         "min_miktar": 30, "barkod": "8691234567893", "son_kullanma_tarihi": "2026-05-06",
         "alis_fiyat": 2.50, "satis_fiyat": 4.50, "tedarikci": "Köy Yumurtası", "kdv_oran": 1,
         "raf_no": "C1", "tahmini_gunluk_satis": 30.0},
        {"urun_adi": "Tereyağı", "miktar": 25, "birim": "kg", "kategori": "Süt Ürünleri",
         "min_miktar": 5, "barkod": "8691234567894", "son_kullanma_tarihi": "2026-06-20",
         "alis_fiyat": 120.00, "satis_fiyat": 175.00, "tedarikci": "Sütaş", "kdv_oran": 8,
         "raf_no": "B2", "tahmini_gunluk_satis": 3.0},
    ]

def mock_fire_olustur():
    return [
        {"urun_adi": "Un", "miktar": 10, "birim": "kg", "aciliyet": "🔥 Yüksek",
         "tedarikci": "ABC Un Fabrikası", "durum": "Bekliyor",
         "eklenme_tarihi": datetime.now().strftime("%Y-%m-%d %H:%M")},
        {"urun_adi": "Şeker", "miktar": 5, "birim": "kg", "aciliyet": "⚡ Orta",
         "tedarikci": "XYZ Şeker", "durum": "Sipariş Verildi",
         "eklenme_tarihi": datetime.now().strftime("%Y-%m-%d %H:%M")},
        {"urun_adi": "Yumurta", "miktar": 50, "birim": "adet", "aciliyet": "✅ Düşük",
         "tedarikci": "Köy Yumurtası", "durum": "Bekliyor",
         "eklenme_tarihi": datetime.now().strftime("%Y-%m-%d %H:%M")},
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
def hareket_ekle(kul, islem, ad, detay=""):
    h = {"tarih": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "kullanici": kul, "islem": islem,
         "urun_adi": ad, "detay": detay}
    liste = dosya_oku(HAREKET_DOSYASI, [])
    liste.append(h)
    if len(liste) > 1000:
        liste = liste[-1000:]
    dosya_yaz(HAREKET_DOSYASI, liste)

def satis_kaydet(ad, birim, miktar, fiyat, tutar, kul):
    s = {"id": str(uuid.uuid4())[:8], "tarih": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
         "kullanici": kul, "urun_adi": ad, "birim": birim, "miktar": miktar,
         "birim_fiyat": fiyat, "toplam_tutar": tutar}
    liste = dosya_oku(SATIS_DOSYASI, [])
    liste.append(s)
    dosya_yaz(SATIS_DOSYASI, liste)

def bugunku_satis():
    liste = dosya_oku(SATIS_DOSYASI, [])
    bugun = datetime.now().strftime("%Y-%m-%d")
    return sum(s["toplam_tutar"] for s in liste if s["tarih"].startswith(bugun))

# ---------------------------- E-POSTA BİLDİRİMLERİ -------------------
def email_gonder(alici, konu, mesaj):
    """Gmail SMTP ile e‑posta gönderir."""
    try:
        smtp_sunucu = "smtp.gmail.com"
        port = 587
        gonderen = st.secrets["email"]["adres"]
        sifre = st.secrets["email"]["sifre"]
        
        msg = MIMEText(mesaj)
        msg["Subject"] = konu
        msg["From"] = gonderen
        msg["To"] = alici
        
        baglanti = smtplib.SMTP(smtp_sunucu, port)
        baglanti.starttls(context=ssl.create_default_context())
        baglanti.login(gonderen, sifre)
        baglanti.sendmail(gonderen, alici, msg.as_string())
        baglanti.quit()
        return True
    except Exception as e:
        logging.error(f"E‑posta gönderme hatası: {e}")
        return False

def skt_ve_kritik_stok_bildirimi():
    """Yaklaşan SKT ve kritik stoklar için e‑posta bildirimi (günde 1 kez)."""
    if "bildirim_gonderildi" not in st.session_state:
        st.session_state.bildirim_gonderildi = False
    
    if not st.session_state.bildirim_gonderildi:
        kritik_urunler = [u for u in st.session_state.stok 
                         if u.get("min_miktar",0) > 0 and u["miktar"] <= u["min_miktar"]]
        skt_yaklasanlar = []
        bugun = datetime.now().date()
        for u in st.session_state.stok:
            s = u.get("son_kullanma_tarihi","")
            if s:
                try:
                    k = (datetime.strptime(s, "%Y-%m-%d").date() - bugun).days
                    if 0 <= k <= SKT_UYARI_GUN:
                        skt_yaklasanlar.append(f"{u['urun_adi']} - {k} gün kaldı")
                except: pass
        
        mesaj = "🚨 Market Stok Uyarısı:\n"
        if kritik_urunler:
            mesaj += "\n⚠️ Kritik Stok:\n"
            for u in kritik_urunler:
                mesaj += f"- {u['urun_adi']}: {u['miktar']} {u['birim']} (min: {u['min_miktar']})\n"
        if skt_yaklasanlar:
            mesaj += "\n📅 SKT Yaklaşanlar:\n"
            for s in skt_yaklasanlar:
                mesaj += f"- {s}\n"
        
        alici = st.session_state.get("patron_email", "")
        if (kritik_urunler or skt_yaklasanlar) and alici:
            if email_gonder(alici, "Market Stok Uyarısı", mesaj):
                st.session_state.bildirim_gonderildi = True
                logging.info("Bildirim e‑postası gönderildi.")

# ---------------------------- VERİ BİLİMİ FONKSİYONLARI ------------
def urun_gunluk_satis_hizi(urun_adi, varsayilan=1.0):
    satislar = dosya_oku(SATIS_DOSYASI, [])
    if not satislar:
        for u in st.session_state.stok:
            if u["urun_adi"] == urun_adi:
                return u.get("tahmini_gunluk_satis", varsayilan)
        return varsayilan
    bugun = datetime.now().date()
    baslangic = bugun - timedelta(days=30)
    miktarlar = []
    for s in satislar:
        try:
            tarih = datetime.strptime(s["tarih"], "%Y-%m-%d %H:%M:%S").date()
            if s["urun_adi"] == urun_adi and baslangic <= tarih <= bugun:
                miktarlar.append(s["miktar"])
        except:
            continue
    if not miktarlar:
        for u in st.session_state.stok:
            if u["urun_adi"] == urun_adi:
                return u.get("tahmini_gunluk_satis", varsayilan)
        return varsayilan
    return sum(miktarlar) / len(miktarlar)

def bilimsel_indirim_hesapla(urun, kalan_gun):
    if kalan_gun <= 0:
        satis_fiyat = urun.get("satis_fiyat", 10)
        alis_fiyat = urun.get("alis_fiyat", 5)
        if satis_fiyat > 0:
            return min(50, int((satis_fiyat - alis_fiyat) / satis_fiyat * 100))
        return 50
    q = urun.get("miktar", 0)
    satis_fiyat = urun.get("satis_fiyat", 0)
    alis_fiyat = urun.get("alis_fiyat", 0)
    if satis_fiyat <= 0 or q <= 0:
        return 0
    m = (satis_fiyat - alis_fiyat) / satis_fiyat
    v = urun_gunluk_satis_hizi(urun["urun_adi"], varsayilan=urun.get("tahmini_gunluk_satis", 1.0))
    beklenen_satis = v * kalan_gun
    stok_fazlasi = q - beklenen_satis
    if stok_fazlasi <= 0:
        return 0
    indirim = (stok_fazlasi / q) * m * 100
    max_indirim = m * 100 * 0.8
    indirim = min(indirim, max_indirim)
    if kalan_gun <= 1:
        indirim = max(indirim, m * 100 * 0.5)
    elif kalan_gun <= 3:
        indirim = max(indirim, m * 100 * 0.2)
    return round(indirim, 1)

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
        st.session_state.kullanicilar = dosya_oku(KULLANICI_DOSYASI, [
            {"kullanici_adi": "admin", "sifre": hashlib.sha256("1234".encode()).hexdigest(), "rol": "patron",
             "ad": "Ahmet"}
        ])
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "current_user" not in st.session_state:
        st.session_state.current_user = None
    if "last_activity" not in st.session_state:
        st.session_state.last_activity = datetime.now()
    veri_gecis_kontrol()

def oturum_kontrol():
    if st.session_state.authenticated:
        if datetime.now() - st.session_state.last_activity > timedelta(minutes=OTURUM_SURESI):
            st.session_state.authenticated = False
            st.warning("⏳ Oturum doldu")
            st.rerun()
        else:
            st.session_state.last_activity = datetime.now()

# ---------------------------- GİRİŞ --------------------------
def giris_ekrani():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            '<h1 style="text-align:center; background:linear-gradient(135deg,#F97316,#8B5CF6); -webkit-background-clip:text; -webkit-text-fill-color:transparent;">🏪 Market Yönetim</h1>',
            unsafe_allow_html=True)
        st.markdown('<p style="text-align:center; color:#E2E8F0;">Akıllı Stok Takibi</p>', unsafe_allow_html=True)
        with st.form("giris", clear_on_submit=False):
            kullanici = st.text_input("👤 Kullanıcı Adı", placeholder="admin")
            sifre = st.text_input("🔒 Şifre", type="password", placeholder="••••")
            if st.form_submit_button("🚀 Giriş Yap", use_container_width=True):
                try:
                    admin_user = st.secrets["admin"]["kullanici_adi"]
                    admin_pass = st.secrets["admin"]["sifre"]
                except:
                    admin_user = config.get("kullanici_adi", "admin")
                    admin_pass = config.get("sifre", "1234")

                if kullanici == admin_user and sifre == admin_pass:
                    st.session_state.authenticated = True
                    st.session_state.current_user = {"kullanici_adi": admin_user, "rol": "patron", "ad": "Admin"}
                    st.session_state.last_activity = datetime.now()
                    st.rerun()
                else:
                    st.error("❌ Hatalı giriş!")

def cikis():
    st.session_state.authenticated = False
    st.rerun()

# ---------------------------- SAYFALAR --------------------------
def ana_sayfa():
    st.markdown('<div class="main-header">📊 Yönetim Paneli</div>', unsafe_allow_html=True)
    skt_ve_kritik_stok_bildirimi()  # Otomatik bildirim kontrolü
    kritik = [u for u in st.session_state.stok if u.get("min_miktar", 0) > 0 and u["miktar"] <= u["min_miktar"]]
    skt = []
    bugun = datetime.now().date()
    for u in st.session_state.stok:
        s = u.get("son_kullanma_tarihi", "")
        if s:
            try:
                k = (datetime.strptime(s, "%Y-%m-%d").date() - bugun).days
                if 0 <= k <= SKT_UYARI_GUN:
                    skt.append({**u, "kalan": k})
            except:
                pass
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📦 Ürün", len(st.session_state.stok))
    c2.metric("⚠️ Kritik", len(kritik))
    c3.metric("⏰ SKT", len(skt))
    c4.metric("💰 Değer",
              f"{sum(u['miktar'] * u.get('satis_fiyat', 0) for u in st.session_state.stok):,.0f} ₺")
    c5, _ = st.columns(2)
    c5.metric("🧾 Bugünkü Satış", f"{bugunku_satis():,.0f} ₺")
    if kritik:
        st.subheader("🚨 Kritik Stoklar")
        for u in kritik[:5]:
            st.error(f"{guvenli_html(u['urun_adi'])}: {u['miktar']:.2f} {u['birim']}")
    if skt:
        st.subheader("⏰ Yaklaşan SKT (Bilimsel İndirim)")
        for u in skt[:5]:
            oneri = bilimsel_indirim_hesapla(u, u['kalan'])
            st.warning(f"{guvenli_html(u['urun_adi'])}: {u['kalan']} gün → Önerilen İndirim: %{oneri}")

def barkod_sayfasi():
    st.markdown('<div class="main-header">📱 Barkod Okutma</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        barkod_manuel = st.text_input("🔢 Barkod Numarası", placeholder="Okutun veya yazın...", key="manuel_barkod")
    with c2:
        img_file = st.camera_input("📷 Mobil Kamera")
    barkod = None
    if img_file:
        try:
            import cv2, numpy as np
            img = cv2.imdecode(np.asarray(bytearray(img_file.read()), dtype=np.uint8), cv2.IMREAD_COLOR)
            detector = cv2.QRCodeDetector()
            data, _, _ = detector.detectAndDecode(img)
            if data:
                barkod = data
                st.success(f"✅ Okunan: {barkod}")
            else:
                st.warning("Barkod algılanamadı.")
        except Exception as e:
            st.error(f"Kamera hatası: {e}")
    aktif = barkod_manuel or barkod
    if aktif:
        bilgi = st.session_state.barkod_db.get(aktif, {})
        urun_adi = bilgi.get("urun_adi", "")
        if urun_adi:
            st.info(
                f"📦 **{guvenli_html(urun_adi)}** ({bilgi.get('birim', '')}) – {guvenli_html(bilgi.get('uretici', ''))}")
        else:
            st.warning("❓ Yeni barkod. Formu doldurup kaydedin.")
        with st.form("barkod_form"):
            c1, c2 = st.columns(2)
            ad = c1.text_input("Ürün Adı *", value=urun_adi)
            miktar = c1.number_input("Miktar", 0.01, format="%.2f", value=1.0)
            birim = c2.selectbox("Birim", BIRIMLER,
                                 index=BIRIMLER.index(bilgi.get("birim", "adet")) if bilgi.get(
                                     "birim") in BIRIMLER else 0)
            kategori = c2.selectbox("Kategori", KATEGORILER,
                                    index=KATEGORILER.index(bilgi.get("kategori", "Diğer")) if bilgi.get(
                                        "kategori") in KATEGORILER else 0)
            tahmini_gunluk = c1.number_input("Tahmini Günlük Satış", 0.1, format="%.1f",
                                             value=bilgi.get("tahmini_gunluk_satis", 1.0))

            skt_var = c2.checkbox("Son kullanma tarihi var mı?", value=True)
            skt = ""
            if skt_var:
                skt = c1.date_input("SKT")

            islem = c2.radio("İşlem", ["📥 Giriş", "📤 Çıkış"], horizontal=True)
            if st.form_submit_button("💾 Kaydet"):
                if not ad.strip():
                    st.error("Ad zorunlu")
                else:
                    if aktif not in st.session_state.barkod_db:
                        st.session_state.barkod_db[aktif] = {"urun_adi": ad.strip(), "birim": birim,
                                                             "kategori": kategori,
                                                             "tahmini_gunluk_satis": tahmini_gunluk}
                        dosya_yaz(BARKOD_DB_DOSYASI, st.session_state.barkod_db)
                    gercek = miktar if islem == "📥 Giriş" else -miktar
                    if skt_var:
                        skt_str = skt.strftime("%Y-%m-%d")
                    else:
                        skt_str = ""
                    for u in st.session_state.stok:
                        if u.get("barkod") == aktif:
                            u["miktar"] += gercek
                            if skt_var:
                                u["son_kullanma_tarihi"] = skt_str
                            u["tahmini_gunluk_satis"] = tahmini_gunluk
                            veriyi_kaydet()
                            st.toast("✅ Güncellendi", icon="✅", duration=5000)
                            st.rerun()
                    st.session_state.stok.append(
                        {"urun_adi": ad.strip(), "miktar": max(0, gercek), "birim": birim,
                         "kategori": kategori, "son_kullanma_tarihi": skt_str,
                         "barkod": aktif, "min_miktar": 0, "alis_fiyat": 0, "satis_fiyat": 0,
                         "tahmini_gunluk_satis": tahmini_gunluk})
                    veriyi_kaydet()
                    st.toast("✅ Eklendi", icon="✅", duration=5000)
                    st.rerun()

def stok_sayfasi():
    st.markdown('<div class="main-header">📦 Stok Yönetimi</div>', unsafe_allow_html=True)
    tab1, tab2, tab3, tab4 = st.tabs(["📋 Liste", "➕ Ekle", "✏️ Düzenle/Sil", "🔢 Stok Sayım"])
    with tab1:
        df = pd.DataFrame(st.session_state.stok)
        if not df.empty:
            def style_row(row):
                return ['background-color:#ffcccc' if row.get('min_miktar', 0) > 0 and row[
                    'miktar'] <= row['min_miktar'] else '' for _ in row]

            st.dataframe(df.style.apply(style_row, axis=1).format(precision=2), use_container_width=True)
        else:
            st.info("Ürün yok.")
    with tab2:
        with st.form("manuel_ekle"):
            barkod = st.text_input("Barkod")
            barkod_bilgi = st.session_state.barkod_db.get(barkod, {}) if barkod else {}
            c1, c2, c3 = st.columns(3)
            ad = c1.text_input("Ürün Adı *", value=barkod_bilgi.get("urun_adi", ""))
            miktar = c1.number_input("Miktar", 0.0, format="%.2f")
            birim = c2.selectbox("Birim", BIRIMLER,
                                 index=BIRIMLER.index(barkod_bilgi.get("birim", "adet")) if barkod_bilgi.get(
                                     "birim") in BIRIMLER else 0)
            kategori = c3.selectbox("Kategori", KATEGORILER,
                                    index=KATEGORILER.index(barkod_bilgi.get("kategori", "Diğer")) if barkod_bilgi.get(
                                        "kategori") in KATEGORILER else 0)
            alis = c2.number_input("Alış Fiyatı", 0.0, format="%.2f")
            satis = c3.number_input("Satış Fiyatı", 0.0, format="%.2f")
            min_m = c1.number_input("Min Stok", 0.0, format="%.2f", value=5.0)
            tahmini_gunluk = c2.number_input("Tahmini Günlük Satış", 0.1, format="%.1f", value=1.0)

            skt_var = c3.checkbox("Son kullanma tarihi var mı?", value=True)
            skt = ""
            if skt_var:
                skt = c1.date_input("SKT")

            raf = c2.text_input("Raf")
            if st.form_submit_button("💾 Kaydet"):
                if not ad.strip():
                    st.error("Ad zorunlu")
                else:
                    skt_str = skt.strftime("%Y-%m-%d") if skt_var else ""
                    if barkod and barkod not in st.session_state.barkod_db:
                        st.session_state.barkod_db[barkod] = {"urun_adi": ad.strip(), "birim": birim,
                                                              "kategori": kategori}
                        dosya_yaz(BARKOD_DB_DOSYASI, st.session_state.barkod_db)
                    st.session_state.stok.append(
                        {"urun_adi": ad.strip(), "miktar": miktar, "birim": birim,
                         "kategori": kategori, "min_miktar": min_m, "barkod": barkod.strip(),
                         "son_kullanma_tarihi": skt_str, "alis_fiyat": alis, "satis_fiyat": satis,
                         "raf_no": raf.strip(), "tahmini_gunluk_satis": tahmini_gunluk})
                    veriyi_kaydet()
                    st.toast("✅ Eklendi", icon="✅", duration=5000)
                    st.success(f"🎉 {guvenli_html(ad)} stoğa eklendi!")
                    st.rerun()
    with tab3:
        if st.session_state.stok:
            urunler = [f"{guvenli_html(u['urun_adi'])} ({u['miktar']:.2f} {u['birim']})" for u in
                       st.session_state.stok]
            secili = st.selectbox("Ürün Seç", urunler, key="duzenle_sec")
            idx = urunler.index(secili)
            urun = st.session_state.stok[idx]
            with st.form("duzenle_form"):
                c1, c2, c3 = st.columns(3)
                yeni_ad = c1.text_input("Ürün Adı", value=urun["urun_adi"])
                yeni_miktar = c1.number_input("Miktar", value=float(urun["miktar"]), min_value=0.0, format="%.2f")
                birim_index = BIRIMLER.index(urun.get("birim", "adet")) if urun.get("birim") in BIRIMLER else 0
                yeni_birim = c2.selectbox("Birim", BIRIMLER, index=birim_index)
                kat_index = KATEGORILER.index(urun.get("kategori", "Diğer")) if urun.get(
                    "kategori") in KATEGORILER else 0
                yeni_kategori = c3.selectbox("Kategori", KATEGORILER, index=kat_index)
                yeni_alis = c2.number_input("Alış Fiyatı", value=float(urun.get("alis_fiyat", 0)), format="%.2f")
                yeni_satis = c3.number_input("Satış Fiyatı", value=float(urun.get("satis_fiyat", 0)), format="%.2f")
                yeni_min = c1.number_input("Min Stok", value=float(urun.get("min_miktar", 0)), format="%.2f")
                yeni_tahmini = c2.number_input("Tahmini Günlük Satış", 0.1, format="%.1f",
                                               value=float(urun.get("tahmini_gunluk_satis", 1.0)))

                mevcut_skt = urun.get("son_kullanma_tarihi", "")
                skt_var = c3.checkbox("Son kullanma tarihi var", value=bool(mevcut_skt))
                yeni_skt = ""
                if skt_var:
                    try:
                        if mevcut_skt:
                            skt_date = datetime.strptime(mevcut_skt, "%Y-%m-%d")
                        else:
                            skt_date = datetime.now()
                    except:
                        skt_date = datetime.now()
                    yeni_skt = c1.date_input("SKT", value=skt_date)

                yeni_raf = c2.text_input("Raf", value=urun.get("raf_no", ""))
                if st.form_submit_button("💾 Güncelle"):
                    if not yeni_ad.strip():
                        st.error("Ad zorunlu")
                    else:
                        skt_str = yeni_skt.strftime("%Y-%m-%d") if skt_var else ""
                        st.session_state.stok[idx] = {
                            "urun_adi": yeni_ad.strip(), "miktar": yeni_miktar, "birim": yeni_birim,
                            "kategori": yeni_kategori, "min_miktar": yeni_min,
                            "barkod": urun.get("barkod", ""), "son_kullanma_tarihi": skt_str,
                            "alis_fiyat": yeni_alis, "satis_fiyat": yeni_satis,
                            "tedarikci": urun.get("tedarikci", ""), "raf_no": yeni_raf.strip(),
                            "kdv_oran": urun.get("kdv_oran", 8), "tahmini_gunluk_satis": yeni_tahmini
                        }
                        veriyi_kaydet()
                        st.toast("✅ Güncellendi", icon="✏️", duration=5000)
                        st.rerun()
            with st.popover("🗑️ Sil"):
                st.warning("Geri alınamaz!")
                if st.button("⚠️ Onayla", key=f"pop_sil_{idx}"):
                    silinen = st.session_state.stok.pop(idx)
                    veriyi_kaydet()
                    hareket_ekle(st.session_state.current_user["kullanici_adi"], "Silme", silinen["urun_adi"],
                                 "Ürün stoğu silindi")
                    st.toast(f"🗑️ {guvenli_html(silinen['urun_adi'])} silindi", icon="🗑️", duration=5000)
                    st.rerun()
        else:
            st.info("Ürün yok.")
    with tab4:
        st.subheader("🔢 Stok Sayım (Mobil)")
        if st.session_state.stok:
            for i, u in enumerate(st.session_state.stok):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"{guvenli_html(u['urun_adi'])} – Sistem: {u['miktar']} {u['birim']}")
                with col2:
                    with st.popover("Sayım Yap"):
                        sayim = st.number_input("Gerçek Miktar", value=float(u['miktar']), format="%.2f", key=f"sayim_{i}")
                        if st.button("Kaydet", key=f"sayim_kaydet_{i}"):
                            fark = sayim - u['miktar']
                            u['miktar'] = sayim
                            veriyi_kaydet()
                            hareket_ekle(st.session_state.current_user["kullanici_adi"], "Sayım Düzeltme", u['urun_adi'],
                                         f"Fark: {fark:+.2f} {u['birim']}")
                            st.toast(f"✅ Sayım kaydedildi (Fark: {fark:+.2f})", icon="🔢", duration=5000)
                            st.rerun()
        else:
            st.info("Ürün yok.")

def satis_sayfasi():
    st.markdown('<div class="main-header">💰 Satış (POS)</div>', unsafe_allow_html=True)
    satilabilir = [u for u in st.session_state.stok if u["miktar"] > 0]
    if not satilabilir:
        st.warning("Satılacak ürün yok")
        return
    secenekler = [
        f"{guvenli_html(u['urun_adi'])} ({u['miktar']:.2f} {u['birim']} - {u.get('satis_fiyat', 0):.2f} ₺)" for u
        in satilabilir]
    secili_str = st.selectbox("Ürün Seçin", secenekler)
    idx = secenekler.index(secili_str)
    urun = satilabilir[idx]
    fiyat = urun.get("satis_fiyat", 0)
    mevcut = urun["miktar"]
    c1, c2 = st.columns(2)
    with c1:
        miktar = st.number_input("Miktar", 0.01, float(mevcut), format="%.2f", value=1.0)
    with c2:
        st.metric("Birim Fiyat", f"{fiyat:.2f} ₺")
    kalan = mevcut - miktar
    st.metric("📦 Kalan Stok", f"{kalan:.2f} {urun['birim']}")
    toplam = miktar * fiyat
    st.markdown(f"### 🧾 Toplam: {toplam:.2f} ₺")
    if st.button("💳 Satış Yap", type="primary", use_container_width=True):
        if miktar <= 0 or miktar > mevcut:
            st.error("Geçersiz miktar")
        else:
            for u in st.session_state.stok:
                if u["urun_adi"] == urun["urun_adi"] and u.get("barkod") == urun.get("barkod"):
                    u["miktar"] = round(u["miktar"] - miktar, 2)
                    yeni = u["miktar"]
                    min_m = u.get("min_miktar", 0)
                    if yeni <= min_m and min_m > 0:
                        if not any(
                                f["urun_adi"] == u["urun_adi"] and f["durum"] == "Bekliyor" for f in
                                st.session_state.fire):
                            st.session_state.fire.append(
                                {"urun_adi": u["urun_adi"], "miktar": min_m - yeni + 1, "birim": u["birim"],
                                 "aciliyet": "🔥 Yüksek", "tedarikci": u.get("tedarikci", ""),
                                 "durum": "Bekliyor",
                                 "eklenme_tarihi": datetime.now().strftime("%Y-%m-%d %H:%M")})
                            st.warning(
                                f"⚠️ {guvenli_html(u['urun_adi'])} kritik stok altına düştü! Otomatik sipariş fişi eklendi.")
                    break
            satis_kaydet(urun["urun_adi"], urun["birim"], miktar, fiyat, toplam,
                         st.session_state.current_user["kullanici_adi"] if st.session_state.current_user else "kasiyer")
            hareket_ekle(st.session_state.current_user["kullanici_adi"], "Satış", urun["urun_adi"],
                         f"{miktar} {urun['birim']} satıldı, tutar: {toplam:.2f} ₺")
            veriyi_kaydet()
            st.toast(f"✅ Satış: {toplam:.2f} ₺", icon="💵", duration=5000)
            st.rerun()

def tedarikci_sayfasi():
    st.markdown('<div class="main-header">🏭 Tedarikçi Yönetimi</div>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["📋 Liste", "➕ Ekle"])
    with tab1:
        if st.session_state.tedarikciler:
            for t in st.session_state.tedarikciler:
                st.markdown(f"**{guvenli_html(t['ad'])}** – Güven: {t.get('guven_puani', 0):.1f}/10 – Tel: {t.get('tel', '')}")
        else:
            st.info("Henüz tedarikçi eklenmemiş.")
    with tab2:
        with st.form("tedarikci_ekle"):
            ad = st.text_input("Firma Adı")
            guven = st.slider("Güven Puanı", 0.0, 10.0, 5.0)
            tel = st.text_input("Telefon")
            if st.form_submit_button("Ekle"):
                st.session_state.tedarikciler.append({
                    "ad": ad, "guven_puani": guven, "tel": tel
                })
                dosya_yaz(TEDARIKCI_DOSYASI, st.session_state.tedarikciler)
                st.toast("Tedarikçi eklendi", icon="🏭", duration=5000)
                st.rerun()

def stok_analizi():
    st.markdown('<div class="main-header">📈 Stok Analizi</div>', unsafe_allow_html=True)
    if not st.session_state.stok:
        st.info("Henüz ürün yok.")
        return
    df = pd.DataFrame(st.session_state.stok)
    # Kâr marjı raporu
    st.subheader("💵 Kâr Marjı Raporu")
    df["kar_marji"] = df.apply(
        lambda r: ((r['satis_fiyat'] - r['alis_fiyat']) / r['satis_fiyat'] * 100) 
        if r['satis_fiyat'] > 0 else 0, axis=1
    )
    st.dataframe(df[["urun_adi", "satis_fiyat", "alis_fiyat", "kar_marji"]].style.format(
        {"kar_marji": "{:.1f}%"}
    ), use_container_width=True)
    # Stok devir hızı
    st.subheader("🔄 Stok Devir Hızı")
    for u in st.session_state.stok:
        hiz = urun_gunluk_satis_hizi(u["urun_adi"], varsayilan=u.get("tahmini_gunluk_satis", 1.0))
        st.write(f"{u['urun_adi']}: {hiz:.2f} {u['birim']}/gün")

def siparis_sayfasi():
    st.markdown('<div class="main-header">🔥 Sipariş Panosu</div>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["📋 Liste", "➕ Ekle"])
    with tab1:
        df = pd.DataFrame(st.session_state.fire)
        if not df.empty:
            for i, row in df.iterrows():
                c1, c2 = st.columns([4, 1])
                with c1:
                    renk = "🟢" if "Düşük" in row['aciliyet'] else "🟡" if "Orta" in row['aciliyet'] else "🔴"
                    st.write(
                        f"{renk} **{guvenli_html(row['urun_adi'])}** – {row['miktar']} {row['birim']} – {row['durum']}")
                with c2:
                    if st.button("🗑️ Sil", key=f"sil_fire_{i}"):
                        st.session_state.fire.pop(i)
                        veriyi_kaydet()
                        st.toast("Sipariş silindi", icon="🗑️", duration=5000)
                        st.rerun()
        else:
            st.info("Sipariş yok.")
    with tab2:
        with st.form("fire_ekle"):
            ad = st.text_input("Ürün")
            miktar = st.number_input("Miktar", 0.01, format="%.2f")
            if st.form_submit_button("Ekle"):
                st.session_state.fire.append(
                    {"urun_adi": ad, "miktar": miktar, "birim": "adet", "aciliyet": "⚡ Orta",
                     "durum": "Bekliyor", "eklenme_tarihi": datetime.now().strftime("%Y-%m-%d %H:%M")})
                veriyi_kaydet()
                st.toast("Sipariş eklendi", icon="🔥", duration=5000)
                st.rerun()

def fire_analizi():
    st.markdown('<div class="main-header">📉 Fire Analizi</div>', unsafe_allow_html=True)
    if st.session_state.fire:
        kat_fire = {}
        for f in st.session_state.fire:
            kat = next(
                (u.get("kategori", "Diğer") for u in st.session_state.stok if u["urun_adi"] == f["urun_adi"]), "Diğer")
            kat_fire[kat] = kat_fire.get(kat, 0) + f["miktar"]
        fig = px.pie(names=list(kat_fire.keys()), values=list(kat_fire.values()), title="Kategori Bazlı Fire",
                     hole=0.3)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Fire kaydı yok.")

def satis_raporu():
    st.markdown('<div class="main-header">📊 Satış Raporu</div>', unsafe_allow_html=True)
    satislar = dosya_oku(SATIS_DOSYASI, [])
    if not satislar:
        st.info("Henüz satış yok.")
        return
    df = pd.DataFrame(satislar)
    df["tarih"] = pd.to_datetime(df["tarih"])
    df["gun"] = df["tarih"].dt.date
    df["ay"] = df["tarih"].dt.strftime("%Y-%m")
    c1, c2, c3 = st.columns(3)
    with c1:
        aralik = st.date_input("Tarih Aralığı", value=(df["gun"].min(), df["gun"].max()), key="rapor_tarih")
    with c2:
        tip = st.radio("Kırılım", ["Günlük", "Aylık", "Ürün Bazlı", "Kâr Marjı"], horizontal=True)
    if len(aralik) == 2:
        df = df[(df["gun"] >= aralik[0]) & (df["gun"] <= aralik[1])]
    if tip == "Günlük":
        rpr = df.groupby("gun")["toplam_tutar"].sum().reset_index()
        rpr.columns = ["Tarih", "Toplam Satış (₺)"]
        st.dataframe(rpr, use_container_width=True)
        fig = px.bar(rpr, x="Tarih", y="Toplam Satış (₺)", title="Günlük Satışlar",
                     color_discrete_sequence=["#f97316"])
        st.plotly_chart(fig, use_container_width=True)
    elif tip == "Aylık":
        rpr = df.groupby("ay")["toplam_tutar"].sum().reset_index()
        rpr.columns = ["Ay", "Toplam Satış (₺)"]
        st.dataframe(rpr, use_container_width=True)
        fig = px.line(rpr, x="Ay", y="Toplam Satış (₺)", markers=True, title="Aylık Trend",
                      color_discrete_sequence=["#8b5cf6"])
        st.plotly_chart(fig, use_container_width=True)
    elif tip == "Ürün Bazlı":
        rpr = df.groupby("urun_adi").agg(Adet=("miktar", "sum"), Ciro=("toplam_tutar", "sum")).reset_index()
        st.dataframe(rpr, use_container_width=True)
        colA, colB = st.columns(2)
        with colA:
            fig1 = px.pie(rpr, values="Ciro", names="urun_adi", title="Ciro Dağılımı", hole=0.3)
            st.plotly_chart(fig1, use_container_width=True)
        with colB:
            fig2 = px.bar(rpr, x="urun_adi", y="Adet", title="Satış Adedi", color_discrete_sequence=["#10b981"])
            st.plotly_chart(fig2, use_container_width=True)
    else:  # Kâr Marjı
        st.subheader("Ürün Bazlı Kâr Marjı")
        df_kar = pd.DataFrame(st.session_state.stok)
        df_kar["kar_marji"] = df_kar.apply(
            lambda r: ((r['satis_fiyat'] - r['alis_fiyat']) / r['satis_fiyat'] * 100) 
            if r['satis_fiyat'] > 0 else 0, axis=1
        )
        st.dataframe(df_kar[["urun_adi", "satis_fiyat", "alis_fiyat", "kar_marji"]].style.format(
            {"kar_marji": "{:.1f}%"}
        ), use_container_width=True)

def yedekleme_sayfasi():
    st.markdown('<div class="main-header">💾 Yedekleme</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        yedek = {"stok": st.session_state.stok, "fire": st.session_state.fire,
                 "barkod_db": st.session_state.barkod_db, "tedarikciler": st.session_state.tedarikciler}
        st.download_button("📥 JSON İndir", json.dumps(yedek, ensure_ascii=False, indent=2), "yedek.json",
                           use_container_width=True)
    with c2:
        dosya = st.file_uploader("Yedek yükle", type="json")
        if dosya:
            icerik = json.load(dosya)
            st.session_state.stok = icerik.get("stok", [])
            st.session_state.fire = icerik.get("fire", [])
            st.session_state.barkod_db = icerik.get("barkod_db", {})
            st.session_state.tedarikciler = icerik.get("tedarikciler", [])
            veriyi_kaydet()
            st.toast("✅ Yüklendi", duration=5000)
            st.rerun()

def ayarlar_sayfasi():
    st.markdown('<div class="main-header">⚙️ Ayarlar</div>', unsafe_allow_html=True)
    with st.form("ayarlar_form"):
        eposta = st.text_input("Patron E‑posta (bildirimler için)", 
                               value=st.session_state.get("patron_email", ""))
        if st.form_submit_button("💾 Kaydet"):
            st.session_state.patron_email = eposta
            st.toast("✅ Ayarlar güncellendi", icon="⚙️", duration=5000)
            st.rerun()

def veriyi_kaydet():
    dosya_yaz(STOK_DOSYASI, st.session_state.stok)
    dosya_yaz(FIRE_DOSYASI, st.session_state.fire)
    dosya_yaz(TEDARIKCI_DOSYASI, st.session_state.tedarikciler)

# ---------------------------- ANA UYGULAMA --------------------------
def main():
    st.set_page_config(page_title="Market Yönetim", page_icon="🏪", layout="wide", initial_sidebar_state="expanded")
    enerjik_css()
    pd.set_option('display.float_format', '{:.2f}'.format)
    oturumu_baslat()
    oturum_kontrol()
    if not st.session_state.authenticated:
        giris_ekrani()
        return
    with st.sidebar:
        st.markdown('<h2 style="color:white;">🏪 Market</h2>', unsafe_allow_html=True)
        st.markdown('<p style="color:#F97316;">v2.0 Tüm Özellikler</p>', unsafe_allow_html=True)
        if st.session_state.current_user:
            st.markdown(
                f'<div style="background:rgba(249,115,22,0.2);border-radius:12px;padding:12px;"><p style="color:white;">👤 {st.session_state.current_user.get("ad", "Kullanıcı")}</p></div>',
                unsafe_allow_html=True)
        sayfa = st.radio("Menü",
                         ["🏠 Ana Panel", "📱 Barkod", "💵 Satış", "📦 Stok", "🔥 Sipariş", 
                          "🏭 Tedarikçi", "📈 Stok Analizi", "📉 Fire Analizi",
                          "📊 Satış Raporu", "💾 Yedekleme", "⚙️ Ayarlar"],
                         label_visibility="collapsed")
        if st.button("🚪 Çıkış", use_container_width=True): cikis()
    if sayfa == "🏠 Ana Panel":
        ana_sayfa()
    elif sayfa == "📱 Barkod":
        barkod_sayfasi()
    elif sayfa == "💵 Satış":
        satis_sayfasi()
    elif sayfa == "📦 Stok":
        stok_sayfasi()
    elif sayfa == "🔥 Sipariş":
        siparis_sayfasi()
    elif sayfa == "🏭 Tedarikçi":
        tedarikci_sayfasi()
    elif sayfa == "📈 Stok Analizi":
        stok_analizi()
    elif sayfa == "📉 Fire Analizi":
        fire_analizi()
    elif sayfa == "📊 Satış Raporu":
        satis_raporu()
    elif sayfa == "💾 Yedekleme":
        yedekleme_sayfasi()
    elif sayfa == "⚙️ Ayarlar":
        ayarlar_sayfasi()

if __name__ == "__main__":
    main()
