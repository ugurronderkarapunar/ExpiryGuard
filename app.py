import streamlit as st
import json
import os
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import logging
import hashlib
import uuid
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from fpdf import FPDF

# WhatsApp için pywhatkit'i deneyelim, yoksa hata vermeyelim
try:
    import pywhatkit as pwk
    WHATSAPP_AKTIF = True
except ImportError:
    WHATSAPP_AKTIF = False

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
        "kasiyer": ["barkod", "satis"],
        "depocu": ["barkod", "stok", "stok_ekle", "skt_takip"]
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

def load_config() -> dict:
    if os.path.exists(CONFIG_DOSYASI):
        try:
            with open(CONFIG_DOSYASI, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
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
ROLLER = config.get("roller", {"patron": ["tümü"], "kasiyer": ["barkod", "satis"], "depocu": ["barkod", "stok"]})
OTURUM_SURESI = config.get("oturum_suresi_dk", 30)
SKT_UYARI_GUN = config.get("skt_uyari_gun", 3)

# ---------------------------- GÜVENLİ HTML ---------------------------
def guvenli_html(metin: str) -> str:
    return (str(metin).replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#x27;"))

# ---------------------------- TEMA YÖNETİMİ ---------------------------
def tema_degistir() -> None:
    st.session_state.tema = st.session_state.get("tema_secimi", "Koyu")

# ---------------------------- MODERN CSS ------------------------------
def enerjik_css(tema: str) -> None:
    if tema == "Koyu":
        bg = "#0B1121"; card = "#141B2D"; text = "#E2E8F0"; header_bg = "#141B2D"
        metric_bg = "linear-gradient(145deg, #1a1f35, #0f1424)"; input_bg = "#141B2D"
    else:
        bg = "#F8FAFC"; card = "#FFFFFF"; text = "#1E293B"; header_bg = "#F1F5F9"
        metric_bg = "linear-gradient(145deg, #E2E8F0, #CBD5E1)"; input_bg = "#FFFFFF"
    st.markdown(f"""
    <style>
        .stApp {{ background-color: {bg} !important; }}
        .main {{ color: {text}; }}
        header[data-testid="stHeader"] {{ background-color: {header_bg}; }}
        section[data-testid="stSidebar"] {{ background-color: {header_bg}; }}
        section[data-testid="stSidebar"] .stRadio label {{ color: {text} !important; font-weight: 600; }}
        div[data-testid="stMetric"] {{
            background: {metric_bg}; border: 1px solid #94A3B8; border-radius: 20px; padding: 24px;
            color: {text}; box-shadow: 0 10px 25px rgba(0,0,0,0.1);
        }}
        div[data-testid="stMetric"] label {{ color: #64748B !important; font-weight: 600; }}
        div[data-testid="stMetric"] div[data-testid="stMetricValue"] {{ color: {text} !important; font-size: 2.2rem; }}
        h1, h2, h3, h4, h5, h6 {{ color: {text}; font-weight: 700; }}
        p, span, label {{ color: {text}; }}
        .stButton > button {{
            border-radius: 14px; font-weight: 700;
            background: linear-gradient(135deg, #F97316, #8B5CF6);
            color: white; border: none; padding: 0.7rem 2rem;
            box-shadow: 0 5px 15px rgba(249,115,22,0.5);
        }}
        .stButton > button:hover {{
            background: linear-gradient(135deg, #ea580c, #7c3aed); box-shadow: 0 8px 25px rgba(249,115,22,0.7);
        }}
        input, select, textarea {{
            background-color: {input_bg} !important; color: {text} !important;
            border: 1px solid #94A3B8 !important; border-radius: 10px !important;
        }}
        .stDataFrame {{
            border-radius: 18px; overflow: hidden; border: 1px solid #94A3B8; background-color: {card};
        }}
        .stDataFrame th {{ background-color: #E2E8F0; color: #1E293B; }}
        .stDataFrame td {{ background-color: {card}; color: {text}; }}
        .custom-container {{
            background-color: {card}; border-radius: 24px; padding: 30px;
            border: 1px solid #94A3B8; box-shadow: 0 15px 30px rgba(0,0,0,0.1); margin-bottom: 25px;
        }}
        .main-header {{
            font-size: 2.3rem; font-weight: 800;
            background: linear-gradient(135deg, #F97316, #8B5CF6);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            margin-bottom: 1.5rem; padding-bottom: 0.5rem; border-bottom: 2px solid #F97316;
        }}
        div[data-testid="stToast"] {{
            background-color: {card} !important; color: {text} !important; border-left: 4px solid #F97316;
        }}
        .sticky-alert {{
            position: fixed; top: 0; left: 0; width: 100%;
            background: #EF4444; color: white; text-align: center;
            padding: 10px; font-weight: bold; z-index: 9999;
        }}
        @media (max-width: 768px) {{
            .custom-container {{ padding: 12px !important; margin: 8px 0 !important; }}
            .main-header {{ font-size: 1.4rem !important; }}
            .stButton > button {{ width: 100% !important; padding: 12px !important; font-size: 16px !important; }}
            input, select, textarea {{ font-size: 16px !important; }}
        }}
    </style>
    """, unsafe_allow_html=True)

# ---------------------------- DOSYA İŞLEMLERİ -----------------------
def dosya_oku(dosya_adi: str, varsayilan=None):
    if os.path.exists(dosya_adi):
        try:
            with open(dosya_adi, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return varsayilan if varsayilan is not None else []

def dosya_yaz(dosya_adi: str, veri) -> bool:
    try:
        with open(dosya_adi, "w", encoding="utf-8") as f:
            json.dump(veri, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

# ---------------------------- VERİ GEÇİŞ KONTROL --------------------
def veri_gecis_kontrol() -> None:
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
def mock_stok_olustur() -> list:
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

def mock_fire_olustur() -> list:
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

def mock_barkod_db_olustur() -> dict:
    return {
        "8691234567890": {"urun_adi": "Un", "birim": "kg", "kategori": "Kuru Gıda", "uretici": "ABC Un Fabrikası"},
        "8691234567891": {"urun_adi": "Şeker", "birim": "kg", "kategori": "Kuru Gıda", "uretici": "XYZ Şeker"},
        "8691234567892": {"urun_adi": "Süt", "birim": "litre", "kategori": "Süt Ürünleri", "uretici": "Sütaş"},
        "8691234567893": {"urun_adi": "Yumurta", "birim": "adet", "kategori": "Diğer", "uretici": "Köy Yumurtası"},
        "8691234567894": {"urun_adi": "Tereyağı", "birim": "kg", "kategori": "Süt Ürünleri", "uretici": "Sütaş"},
    }

# ---------------------------- HAREKET KAYDI -------------------------
def hareket_ekle(kul: str, islem: str, ad: str, detay: str = "") -> None:
    h = {"tarih": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "kullanici": kul, "islem": islem,
         "urun_adi": ad, "detay": detay}
    liste = dosya_oku(HAREKET_DOSYASI, [])
    liste.append(h)
    if len(liste) > 1000:
        liste = liste[-1000:]
    dosya_yaz(HAREKET_DOSYASI, liste)

def satis_kaydet(ad: str, birim: str, miktar: float, fiyat: float, tutar: float, kul: str) -> None:
    s = {"id": str(uuid.uuid4())[:8], "tarih": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
         "kullanici": kul, "urun_adi": ad, "birim": birim, "miktar": miktar,
         "birim_fiyat": fiyat, "toplam_tutar": tutar}
    liste = dosya_oku(SATIS_DOSYASI, [])
    liste.append(s)
    dosya_yaz(SATIS_DOSYASI, liste)

# ---------------------------- SATIŞ İSTATİSTİKLERİ -------------------
def gunluk_ciro(tarih=None) -> float:
    if tarih is None:
        tarih = datetime.now().strftime("%Y-%m-%d")
    liste = dosya_oku(SATIS_DOSYASI, [])
    return sum(s["toplam_tutar"] for s in liste if s["tarih"].startswith(tarih))

def haftalik_ciro(baslangic_tarihi=None) -> float:
    if baslangic_tarihi is None:
        baslangic_tarihi = datetime.now().date() - timedelta(days=datetime.now().weekday())
    bitis = baslangic_tarihi + timedelta(days=6)
    liste = dosya_oku(SATIS_DOSYASI, [])
    toplam = 0
    for s in liste:
        try:
            tarih = datetime.strptime(s["tarih"], "%Y-%m-%d %H:%M:%S").date()
            if baslangic_tarihi <= tarih <= bitis:
                toplam += s["toplam_tutar"]
        except:
            pass
    return toplam

def aylik_ciro(yil=None, ay=None) -> float:
    if yil is None:
        yil = datetime.now().year
    if ay is None:
        ay = datetime.now().month
    liste = dosya_oku(SATIS_DOSYASI, [])
    toplam = 0
    for s in liste:
        try:
            tarih = datetime.strptime(s["tarih"], "%Y-%m-%d %H:%M:%S")
            if tarih.year == yil and tarih.month == ay:
                toplam += s["toplam_tutar"]
        except:
            pass
    return toplam

def en_cok_satanlar(n=5, gun=7) -> list:
    satislar = dosya_oku(SATIS_DOSYASI, [])
    if not satislar:
        return []
    df = pd.DataFrame(satislar)
    df["tarih"] = pd.to_datetime(df["tarih"])
    baslangic = datetime.now() - timedelta(days=gun)
    df = df[df["tarih"] >= baslangic]
    if df.empty:
        return []
    populer = df.groupby("urun_adi")["miktar"].sum().sort_values(ascending=False).head(n)
    return populer.index.tolist()

# ---------------------------- WHATSAPP -------------------------------
def whatsapp_gonder(telefon_no: str, mesaj: str) -> bool:
    if not WHATSAPP_AKTIF:
        return False
    try:
        suanki_zaman = datetime.now()
        saat = suanki_zaman.hour
        dakika = suanki_zaman.minute + 2
        if dakika >= 60:
            saat += 1
            dakika -= 60
        pwk.sendwhatmsg(telefon_no, mesaj, saat, dakika, wait_time=15, tab_close=True)
        return True
    except Exception as e:
        logging.error(f"WhatsApp gönderme hatası: {e}")
        return False

def kritik_stok_whatsapp_bildirimi() -> None:
    if "whatsapp_bildirim_gonderildi" not in st.session_state:
        st.session_state.whatsapp_bildirim_gonderildi = False
    if not st.session_state.whatsapp_bildirim_gonderildi:
        patron_tel = st.session_state.get("patron_telefon", "")
        if not patron_tel:
            return
        kritik_urunler = [u for u in st.session_state.stok 
                         if u.get("min_miktar", 0) > 0 and u["miktar"] <= u["min_miktar"]]
        if kritik_urunler:
            mesaj = "🚨 *KRİTİK STOK UYARISI*\n\n"
            for u in kritik_urunler[:5]:
                mesaj += f"📦 {u['urun_adi']}: {u['miktar']} {u['birim']} (min: {u['min_miktar']})\n"
            if len(kritik_urunler) > 5:
                mesaj += f"\n... ve {len(kritik_urunler)-5} ürün daha"
            if whatsapp_gonder(f"+90{patron_tel}", mesaj):
                st.session_state.whatsapp_bildirim_gonderildi = True
                logging.info("WhatsApp bildirimi gönderildi.")

# ---------------------------- E-POSTA --------------------------------
def email_gonder(alici: str, konu: str, mesaj: str) -> bool:
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

def email_gonder_pdf(alici: str, konu: str, mesaj: str, pdf_icerik: bytes, dosya_adi: str) -> bool:
    try:
        smtp_sunucu = "smtp.gmail.com"
        port = 587
        gonderen = st.secrets["email"]["adres"]
        sifre = st.secrets["email"]["sifre"]
        msg = MIMEMultipart()
        msg["Subject"] = konu
        msg["From"] = gonderen
        msg["To"] = alici
        msg.attach(MIMEText(mesaj))
        part = MIMEBase("application", "octet-stream")
        part.set_payload(pdf_icerik)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename={dosya_adi}")
        msg.attach(part)
        baglanti = smtplib.SMTP(smtp_sunucu, port)
        baglanti.starttls(context=ssl.create_default_context())
        baglanti.login(gonderen, sifre)
        baglanti.sendmail(gonderen, alici, msg.as_string())
        baglanti.quit()
        return True
    except Exception as e:
        logging.error(f"PDF e‑posta hatası: {e}")
        return False

def tedarikciye_siparis_gonder(urun: dict, tedarikci_eposta: str) -> bool:
    if not tedarikci_eposta:
        return False
    konu = f"Otomatik Sipariş: {urun['urun_adi']} kritik stokta"
    mesaj = f"""
    Sayın {urun.get('tedarikci', 'Tedarikçi')},
    
    {urun['urun_adi']} ürününün stoğu kritik seviyeye düşmüştür.
    
    Mevcut stok: {urun['miktar']} {urun['birim']}
    Minimum stok: {urun.get('min_miktar', 0)} {urun['birim']}
    Önerilen sipariş miktarı: {urun.get('min_miktar', 10) - urun['miktar'] + 5} {urun['birim']}
    
    Lütfen en kısa sürede tedarik sağlayınız.
    
    Market Yönetim Sistemi
    """
    return email_gonder(tedarikci_eposta, konu, mesaj)

# ---------------------------- VERİ BİLİMİ FONKSİYONLARI ------------
def urun_gunluk_satis_hizi(urun_adi: str, varsayilan: float = 1.0) -> float:
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
        except Exception:
            continue
    if not miktarlar:
        for u in st.session_state.stok:
            if u["urun_adi"] == urun_adi:
                return u.get("tahmini_gunluk_satis", varsayilan)
        return varsayilan
    return sum(miktarlar) / len(miktarlar)

def bilimsel_indirim_hesapla(urun: dict, kalan_gun: int) -> float:
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
def oturumu_baslat() -> None:
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
    if "son_islem_mesaji" not in st.session_state:
        st.session_state.son_islem_mesaji = ""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "current_user" not in st.session_state:
        st.session_state.current_user = None
    if "last_activity" not in st.session_state:
        st.session_state.last_activity = datetime.now()
    if "tema" not in st.session_state:
        st.session_state.tema = "Koyu"
    if "patron_email" not in st.session_state:
        st.session_state.patron_email = ""
    if "patron_telefon" not in st.session_state:
        st.session_state.patron_telefon = ""
    veri_gecis_kontrol()

def oturum_kontrol() -> None:
    if st.session_state.authenticated:
        if datetime.now() - st.session_state.last_activity > timedelta(minutes=OTURUM_SURESI):
            st.session_state.authenticated = False
            st.warning("⏳ Oturum doldu")
            st.rerun()
        else:
            st.session_state.last_activity = datetime.now()

# ---------------------------- GİRİŞ --------------------------
def giris_ekrani() -> None:
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
                except Exception:
                    admin_user = config.get("kullanici_adi", "admin")
                    admin_pass = config.get("sifre", "1234")
                if kullanici == admin_user and sifre == admin_pass:
                    st.session_state.authenticated = True
                    st.session_state.current_user = {"kullanici_adi": admin_user, "rol": "patron", "ad": "Admin"}
                    st.session_state.last_activity = datetime.now()
                    st.rerun()
                else:
                    st.error("❌ Hatalı giriş!")
def cikis() -> None:
    st.session_state.authenticated = False
    st.rerun()

# ---------------------------- YETKİLENDİRME -------------------------
def izinli_sayfalar(kullanici: dict) -> dict:
    if not kullanici:
        return {}
    rol = kullanici.get("rol", "")
    izinler = ROLLER.get(rol, [])
    if "tümü" in izinler:
        return SAYFALAR
    yetki_sayfa = {
        "barkod": ["📱 Barkod"],
        "satis": ["💵 Satış"],
        "stok": ["📦 Stok", "📈 Stok Analizi", "📉 Fire Analizi"],
        "stok_ekle": ["📦 Stok", "🔥 Sipariş"],
        "skt_takip": ["🏠 Ana Panel"],
    }
    izinli = {}
    for anahtar, fonksiyon in SAYFALAR.items():
        for yetki in izinler:
            if anahtar in yetki_sayfa.get(yetki, []):
                izinli[anahtar] = fonksiyon
                break
    return izinli

# ---------------------------- ANA SAYFA ------------------------------
def ana_sayfa() -> None:
    st.markdown('<div class="main-header">📊 Yönetim Paneli</div>', unsafe_allow_html=True)
    kritik_stok_whatsapp_bildirimi()
    kritik = [u for u in st.session_state.stok if u.get("min_miktar", 0) > 0 and u["miktar"] <= u["min_miktar"]]

    # HIZLI İSTATİSTİKLER
    bugun = datetime.now().date()
    bugunku = gunluk_ciro(bugun.strftime("%Y-%m-%d"))
    dun = gunluk_ciro((bugun - timedelta(days=1)).strftime("%Y-%m-%d"))
    delta_gun = bugunku - dun

    bu_hafta_baslangic = bugun - timedelta(days=bugun.weekday())
    gecen_hafta_baslangic = bu_hafta_baslangic - timedelta(days=7)
    bu_hafta = haftalik_ciro(bu_hafta_baslangic)
    gecen_hafta = haftalik_ciro(gecen_hafta_baslangic)
    delta_hafta = bu_hafta - gecen_hafta

    bu_ay = aylik_ciro(bugun.year, bugun.month)
    gecen_ay_tarih = bugun.replace(day=1) - timedelta(days=1)
    gecen_ay = aylik_ciro(gecen_ay_tarih.year, gecen_ay_tarih.month)
    delta_ay = bu_ay - gecen_ay

    st.subheader("📈 Hızlı İstatistikler")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Bugünkü Ciro", f"{bugunku:,.0f} ₺", delta=f"{delta_gun:+,.0f} ₺")
    c2.metric("Dünkü Ciro", f"{dun:,.0f} ₺")
    c3.metric("Bu Hafta", f"{bu_hafta:,.0f} ₺", delta=f"{delta_hafta:+,.0f} ₺")
    c4.metric("Bu Ay", f"{bu_ay:,.0f} ₺", delta=f"{delta_ay:+,.0f} ₺")
    c5.metric("Haftalık Büyüme", f"%{0 if gecen_hafta == 0 else (delta_hafta/gecen_hafta*100):.1f}")

    st.markdown("---")

    # STOK YENİLEME SİHİRBAZI
    with st.expander("🪄 Stok Yenileme Sihirbazı", expanded=bool(kritik)):
        if kritik:
            st.warning(f"🚨 {len(kritik)} ürün kritik stok seviyesinde!")
            for u in kritik:
                st.write(f"📦 {u['urun_adi']} – Mevcut: {u['miktar']} {u['birim']} (Min: {u['min_miktar']} {u['birim']})")
            if st.button("⚡ Tüm Kritik Ürünleri Siparişe Ekle ve Tedarikçilere Bildir", type="primary"):
                eklenen = 0
                gonderilen = 0
                for u in kritik:
                    if not any(f["urun_adi"] == u["urun_adi"] and f["durum"] == "Bekliyor" for f in st.session_state.fire):
                        st.session_state.fire.append({
                            "urun_adi": u["urun_adi"],
                            "miktar": u["min_miktar"] - u["miktar"] + 5,
                            "birim": u["birim"],
                            "aciliyet": "🔥 Yüksek",
                            "tedarikci": u.get("tedarikci", ""),
                            "durum": "Bekliyor",
                            "eklenme_tarihi": datetime.now().strftime("%Y-%m-%d %H:%M")
                        })
                        eklenen += 1
                    tedarikci_eposta = ""
                    for t in st.session_state.tedarikciler:
                        if t["ad"] == u.get("tedarikci", ""):
                            tedarikci_eposta = t.get("eposta", "")
                            break
                    if tedarikci_eposta:
                        urun_dict = u.copy()
                        urun_dict["miktar"] = u["miktar"]
                        urun_dict["min_miktar"] = u.get("min_miktar", 10)
                        if tedarikciye_siparis_gonder(urun_dict, tedarikci_eposta):
                            gonderilen += 1
                veriyi_kaydet()
                st.session_state.son_islem_mesaji = f"✅ {eklenen} ürün siparişe eklendi, {gonderilen} tedarikçiye e‑posta gönderildi"
                st.rerun()
        else:
            st.success("✅ Tüm ürünler minimum stok seviyesinin üzerinde.")

    # KRİTİK STOK VE SKT UYARILARI
    if kritik:
        st.markdown('<div class="sticky-alert">⚠️ KRİTİK STOK UYARISI</div>', unsafe_allow_html=True)
    skt = []
    for u in st.session_state.stok:
        s = u.get("son_kullanma_tarihi", "")
        if s:
            try:
                k = (datetime.strptime(s, "%Y-%m-%d").date() - bugun).days
                if 0 <= k <= SKT_UYARI_GUN:
                    skt.append({**u, "kalan": k})
            except:
                pass
    if kritik:
        st.subheader("🚨 Kritik Stoklar")
        for u in kritik[:5]:
            st.error(f"{guvenli_html(u['urun_adi'])}: {u['miktar']:.2f} {u['birim']}")
        st.balloons()
    if skt:
        st.subheader("⏰ Yaklaşan SKT (Bilimsel İndirim)")
        for u in skt[:5]:
            oneri = bilimsel_indirim_hesapla(u, u['kalan'])
            st.warning(f"{guvenli_html(u['urun_adi'])}: {u['kalan']} gün → Önerilen İndirim: %{oneri}")

# ---------------------------- STOK SAYIMI (BARKOD HIZLI) -------------
def stok_sayfasi() -> None:
    st.markdown('<div class="main-header">📦 Stok Yönetimi</div>', unsafe_allow_html=True)
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["📋 Liste", "➕ Ekle", "✏️ Düzenle/Sil", "🔢 Stok Sayım", "📥 Toplu Güncelle"]
    )
    with tab1:
        df = pd.DataFrame(st.session_state.stok)
        if not df.empty:
            def style_row(row):
                return ['background-color:#ffcccc' if row.get('min_miktar', 0) > 0 and row['miktar'] <= row['min_miktar'] else '' for _ in row]
            st.dataframe(df.style.apply(style_row, axis=1).format(precision=2), width='stretch')
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
                    st.session_state.son_islem_mesaji = f"🎉 {ad.strip()} stoğa eklendi!"
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
                    except Exception:
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
                        st.session_state.son_islem_mesaji = f"✅ {yeni_ad.strip()} güncellendi"
                        st.rerun()
            with st.popover("🗑️ Sil"):
                st.warning("Geri alınamaz!")
                if st.button("⚠️ Onayla", key=f"pop_sil_{idx}"):
                    silinen = st.session_state.stok.pop(idx)
                    veriyi_kaydet()
                    hareket_ekle(st.session_state.current_user["kullanici_adi"], "Silme", silinen["urun_adi"],
                                 "Ürün stoğu silindi")
                    st.session_state.son_islem_mesaji = f"🗑️ {silinen['urun_adi']} silindi"
                    st.rerun()
        else:
            st.info("Ürün yok.")
    with tab4:
        st.subheader("🔢 Stok Sayım (Barkod ile Hızlı Eşleştirme)")
        st.info("📱 Barkod okutarak veya manuel barkod girerek anında ilgili ürünü bulup sayım yapabilirsiniz.")
        
        # Kamera butonu (mobil için)
        kamera_img = st.camera_input("📷 Barkodu kameraya gösterin", key="sayim_kamera")
        sayim_barkod = st.text_input("🔍 veya barkodu manuel yazın", key="sayim_barkod", placeholder="Barkodu okutun veya yazın...")
        
        # Kameradan barkod okunduysa otomatik doldur
        if kamera_img and not sayim_barkod:
            try:
                import cv2, numpy as np
                img = cv2.imdecode(np.asarray(bytearray(kamera_img.read()), dtype=np.uint8), cv2.IMREAD_COLOR)
                detector = cv2.QRCodeDetector()
                data, _, _ = detector.detectAndDecode(img)
                if data:
                    sayim_barkod = data
                    st.success(f"✅ Okunan barkod: {sayim_barkod}")
            except Exception as e:
                st.error(f"Kamera hatası: {e}")
        
        if sayim_barkod:
            bulunan = next((u for u in st.session_state.stok if u.get("barkod") == sayim_barkod), None)
            if bulunan:
                st.success(f"✅ {bulunan['urun_adi']} bulundu (Sistem: {bulunan['miktar']} {bulunan['birim']})")
                with st.form("hizli_sayim"):
                    yeni = st.number_input("Gerçek Miktar", value=float(bulunan['miktar']), format="%.2f")
                    if st.form_submit_button("💾 Sayımı Kaydet"):
                        fark = yeni - bulunan['miktar']
                        bulunan['miktar'] = yeni
                        veriyi_kaydet()
                        hareket_ekle(st.session_state.current_user["kullanici_adi"], "Sayım Düzeltme (Barkod)",
                                     bulunan['urun_adi'], f"Fark: {fark:+.2f}")
                        st.session_state.son_islem_mesaji = f"✅ {bulunan['urun_adi']} sayımı kaydedildi"
                        st.rerun()
            else:
                st.warning("❌ Barkod stokta bulunamadı.")
        
        st.markdown("---")
        st.write("📋 Manuel Sayım:")
        if st.session_state.stok:
            for i, u in enumerate(st.session_state.stok):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"{u['urun_adi']} – Sistem: {u['miktar']} {u['birim']}")
                with col2:
                    with st.popover("Sayım"):
                        sayim = st.number_input("Gerçek Miktar", value=float(u['miktar']), format="%.2f", key=f"man_{i}")
                        if st.button("Kaydet", key=f"kaydet_{i}"):
                            fark = sayim - u['miktar']
                            u['miktar'] = sayim
                            veriyi_kaydet()
                            hareket_ekle(st.session_state.current_user["kullanici_adi"], "Sayım Düzeltme",
                                         u['urun_adi'], f"Fark: {fark:+.2f}")
                            st.session_state.son_islem_mesaji = f"✅ Sayım kaydedildi"
                            st.rerun()
        else:
            st.info("Ürün yok.")
    with tab5:
        st.subheader("📥 Toplu Stok Güncelleme (CSV)")
        st.markdown("**Format:** `barkod,miktar` (başlık satırı olmadan)")
        csv_dosya = st.file_uploader("CSV yükle", type=["csv"], key="toplu_csv")
        if csv_dosya:
            try:
                df_csv = pd.read_csv(csv_dosya, header=None, names=["barkod", "miktar"])
                for _, row in df_csv.iterrows():
                    barkod = str(row["barkod"]).strip()
                    miktar = float(row["miktar"])
                    for u in st.session_state.stok:
                        if u.get("barkod") == barkod:
                            u["miktar"] += miktar
                            hareket_ekle(st.session_state.current_user["kullanici_adi"],
                                         "Toplu Güncelleme", u["urun_adi"],
                                         f"{miktar:+.2f} {u['birim']}")
                            break
                veriyi_kaydet()
                st.session_state.son_islem_mesaji = f"✅ {len(df_csv)} ürün güncellendi"
                st.rerun()
            except Exception as e:
                st.error(f"CSV işlenirken hata: {e}")

# ---------------------------- DİĞER SAYFALAR (ÖZET) -------------------
def barkod_sayfasi() -> None:
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
            st.info(f"📦 **{guvenli_html(urun_adi)}** ({bilgi.get('birim', '')}) – {guvenli_html(bilgi.get('uretici', ''))}")
        else:
            st.warning("❓ Yeni barkod.")
        with st.form("barkod_form"):
            c1, c2 = st.columns(2)
            ad = c1.text_input("Ürün Adı *", value=urun_adi)
            miktar = c1.number_input("Miktar", 0.01, format="%.2f", value=1.0)
            birim = c2.selectbox("Birim", BIRIMLER, index=BIRIMLER.index(bilgi.get("birim", "adet")) if bilgi.get("birim") in BIRIMLER else 0)
            kategori = c2.selectbox("Kategori", KATEGORILER, index=KATEGORILER.index(bilgi.get("kategori", "Diğer")) if bilgi.get("kategori") in KATEGORILER else 0)
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
                        st.session_state.barkod_db[aktif] = {"urun_adi": ad.strip(), "birim": birim, "kategori": kategori}
                        dosya_yaz(BARKOD_DB_DOSYASI, st.session_state.barkod_db)
                    gercek = miktar if islem == "📥 Giriş" else -miktar
                    skt_str = skt.strftime("%Y-%m-%d") if skt_var else ""
                    for u in st.session_state.stok:
                        if u.get("barkod") == aktif:
                            u["miktar"] += gercek
                            if skt_var:
                                u["son_kullanma_tarihi"] = skt_str
                            veriyi_kaydet()
                            st.session_state.son_islem_mesaji = f"✅ {ad.strip()} güncellendi"
                            st.rerun()
                    st.session_state.stok.append({
                        "urun_adi": ad.strip(), "miktar": max(0, gercek), "birim": birim,
                        "kategori": kategori, "son_kullanma_tarihi": skt_str,
                        "barkod": aktif, "min_miktar": 0, "alis_fiyat": 0, "satis_fiyat": 0
                    })
                    veriyi_kaydet()
                    st.session_state.son_islem_mesaji = f"✅ {ad.strip()} eklendi"
                    st.rerun()

def satis_sayfasi() -> None:
    st.markdown('<div class="main-header">💰 Satış (POS)</div>', unsafe_allow_html=True)
    satilabilir = [u for u in st.session_state.stok if u["miktar"] > 0]
    if not satilabilir:
        st.warning("Satılacak ürün yok")
        return
    populer = en_cok_satanlar(5, gun=7)
    if populer:
        st.subheader("⚡ Son 7 Günün En Çok Satanları")
        kisa_sutun = st.columns(len(populer))
        for i, urun_adi in enumerate(populer):
            urun = next((u for u in satilabilir if u["urun_adi"] == urun_adi), None)
            if urun:
                with kisa_sutun[i]:
                    if st.button(f"🛒 {urun['urun_adi']}\n1 {urun['birim']}", key=f"hizli_{urun_adi}"):
                        urun["miktar"] -= 1
                        satis_kaydet(urun["urun_adi"], urun["birim"], 1, urun.get("satis_fiyat", 0),
                                     urun.get("satis_fiyat", 0), st.session_state.current_user["kullanici_adi"])
                        veriyi_kaydet()
                        st.session_state.son_islem_mesaji = f"✅ Hızlı satış: {urun['urun_adi']}"
                        st.rerun()
    with st.expander("📷 QR ile Hızlı Satış (Mobil Kamera)", expanded=False):
        qr_img = st.camera_input("QR / Barkod okut", key="qr_satis")
        if qr_img:
            try:
                import cv2, numpy as np
                img = cv2.imdecode(np.asarray(bytearray(qr_img.read()), dtype=np.uint8), cv2.IMREAD_COLOR)
                detector = cv2.QRCodeDetector()
                data, _, _ = detector.detectAndDecode(img)
                if data:
                    for u in satilabilir:
                        if u.get("barkod") == data:
                            st.success(f"✅ {u['urun_adi']} bulundu, sepete eklendi.")
                            u["miktar"] -= 1
                            satis_kaydet(u["urun_adi"], u["birim"], 1, u.get("satis_fiyat", 0),
                                         u.get("satis_fiyat", 0), st.session_state.current_user["kullanici_adi"])
                            veriyi_kaydet()
                            st.session_state.son_islem_mesaji = f"✅ QR satış: {u['urun_adi']}"
                            st.rerun()
                    st.error("Barkod eşleşmedi.")
                else:
                    st.warning("QR kod çözülemedi.")
            except Exception as e:
                st.error(f"Kamera hatası: {e}")
    secili_str = st.selectbox("Ürün Seçin", [f"{guvenli_html(u['urun_adi'])} ({u['miktar']:.2f} {u['birim']} - {u.get('satis_fiyat', 0):.2f} ₺)" for u in satilabilir])
    idx = [f"{u['urun_adi']} ({u['miktar']:.2f} {u['birim']} - {u.get('satis_fiyat', 0):.2f} ₺)" for u in satilabilir].index(secili_str)
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
    with st.expander("📋 Son Satış Geçmişi"):
        son = [s for s in dosya_oku(SATIS_DOSYASI, []) if s["urun_adi"] == urun["urun_adi"]]
        son = sorted(son, key=lambda x: x["tarih"], reverse=True)[:3]
        if son:
            for s in son:
                st.caption(f"🕒 {s['tarih']} – {s['miktar']} {s['birim']} – {s['toplam_tutar']:.2f} ₺")
        else:
            st.caption("Henüz satış yok.")
    if st.button("💳 Satış Yap", type="primary", use_container_width=True):
        if miktar <= 0 or miktar > mevcut:
            st.error("Geçersiz miktar")
        else:
            for u in st.session_state.stok:
                if u["urun_adi"] == urun["urun_adi"] and u.get("barkod") == urun.get("barkod"):
                    u["miktar"] = round(u["miktar"] - miktar, 2)
                    if u["miktar"] <= u.get("min_miktar", 0):
                        if not any(f["urun_adi"] == u["urun_adi"] and f["durum"] == "Bekliyor" for f in st.session_state.fire):
                            st.session_state.fire.append({
                                "urun_adi": u["urun_adi"], "miktar": u["min_miktar"] - u["miktar"] + 2,
                                "birim": u["birim"], "aciliyet": "🔥 Yüksek",
                                "tedarikci": u.get("tedarikci", ""), "durum": "Bekliyor",
                                "eklenme_tarihi": datetime.now().strftime("%Y-%m-%d %H:%M")
                            })
                    break
            satis_kaydet(urun["urun_adi"], urun["birim"], miktar, fiyat, toplam,
                         st.session_state.current_user["kullanici_adi"] if st.session_state.current_user else "kasiyer")
            hareket_ekle(st.session_state.current_user["kullanici_adi"], "Satış", urun["urun_adi"],
                         f"{miktar} {urun['birim']} satıldı, tutar: {toplam:.2f} ₺")
            veriyi_kaydet()
            st.session_state.son_islem_mesaji = f"✅ Satış: {toplam:.2f} ₺"
            st.rerun()

def tedarikci_sayfasi() -> None:
    st.markdown('<div class="main-header">🏭 Tedarikçi Yönetimi</div>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["📋 Liste", "➕ Ekle"])
    with tab1:
        if st.session_state.tedarikciler:
            for t in st.session_state.tedarikciler:
                st.markdown(f"**{guvenli_html(t['ad'])}** – Güven: {t.get('guven_puani', 0):.1f}/10 – Tel: {t.get('tel', '')} – E‑posta: {t.get('eposta', '')}")
        else:
            st.info("Henüz tedarikçi eklenmemiş.")
    with tab2:
        with st.form("tedarikci_ekle"):
            ad = st.text_input("Firma Adı")
            guven = st.slider("Güven Puanı", 0.0, 10.0, 5.0)
            tel = st.text_input("Telefon")
            eposta = st.text_input("E‑posta")
            if st.form_submit_button("Ekle"):
                st.session_state.tedarikciler.append({"ad": ad, "guven_puani": guven, "tel": tel, "eposta": eposta})
                dosya_yaz(TEDARIKCI_DOSYASI, st.session_state.tedarikciler)
                st.session_state.son_islem_mesaji = "🏭 Tedarikçi eklendi"
                st.rerun()

def stok_analizi() -> None:
    st.markdown('<div class="main-header">📈 Stok Analizi</div>', unsafe_allow_html=True)
    if not st.session_state.stok:
        st.info("Henüz ürün yok.")
        return
    df = pd.DataFrame(st.session_state.stok)
    st.subheader("💵 Kâr Marjı Raporu")
    df["kar_marji"] = df.apply(lambda r: ((r['satis_fiyat'] - r['alis_fiyat']) / r['satis_fiyat'] * 100) if r['satis_fiyat'] > 0 else 0, axis=1)
    st.dataframe(df[["urun_adi", "satis_fiyat", "alis_fiyat", "kar_marji"]].style.format({"kar_marji": "{:.1f}%"}), width='stretch')
    st.subheader("🔄 Stok Devir Hızı")
    for u in st.session_state.stok:
        hiz = urun_gunluk_satis_hizi(u["urun_adi"], varsayilan=u.get("tahmini_gunluk_satis", 1.0))
        st.write(f"{u['urun_adi']}: {hiz:.2f} {u['birim']}/gün")

def siparis_sayfasi() -> None:
    st.markdown('<div class="main-header">🔥 Sipariş Panosu</div>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["📋 Liste", "➕ Ekle"])
    with tab1:
        df = pd.DataFrame(st.session_state.fire)
        if not df.empty:
            for i, row in df.iterrows():
                c1, c2, c3 = st.columns([3, 1, 1])
                with c1:
                    renk = "🟢" if "Düşük" in row['aciliyet'] else "🟡" if "Orta" in row['aciliyet'] else "🔴"
                    st.write(f"{renk} **{guvenli_html(row['urun_adi'])}** – {row['miktar']} {row['birim']} – {row['durum']}")
                with c2:
                    if st.button("🗑️ Sil", key=f"sil_fire_{i}"):
                        st.session_state.fire.pop(i); veriyi_kaydet(); st.session_state.son_islem_mesaji = "Sipariş silindi"; st.rerun()
                with c3:
                    if st.button("📧 Tedarikçiye Gönder", key=f"tedarik_fire_{i}"):
                        urun_adi = row['urun_adi']; tedarikci_adi = row.get("tedarikci", "")
                        tedarikci_eposta = next((t["eposta"] for t in st.session_state.tedarikciler if t["ad"] == tedarikci_adi), "")
                        if tedarikci_eposta:
                            urun_dict = row.to_dict()
                            for u in st.session_state.stok:
                                if u["urun_adi"] == urun_adi:
                                    urun_dict["miktar"] = u["miktar"]; urun_dict["min_miktar"] = u.get("min_miktar", 10)
                                    break
                            if tedarikciye_siparis_gonder(urun_dict, tedarikci_eposta):
                                st.session_state.son_islem_mesaji = f"📧 {urun_adi} siparişi gönderildi"; st.rerun()
                        else:
                            st.error("Tedarikçi e‑postası bulunamadı.")
        else:
            st.info("Sipariş yok.")
    with tab2:
        with st.form("fire_ekle"):
            ad = st.text_input("Ürün"); miktar = st.number_input("Miktar", 0.01, format="%.2f")
            if st.form_submit_button("Ekle"):
                st.session_state.fire.append({"urun_adi": ad, "miktar": miktar, "birim": "adet", "aciliyet": "⚡ Orta", "durum": "Bekliyor", "eklenme_tarihi": datetime.now().strftime("%Y-%m-%d %H:%M")})
                veriyi_kaydet(); st.session_state.son_islem_mesaji = "🔥 Sipariş eklendi"; st.rerun()

def fire_analizi() -> None:
    st.markdown('<div class="main-header">📉 Fire Analizi</div>', unsafe_allow_html=True)
    if st.session_state.fire:
        kat_fire = {}
        for f in st.session_state.fire:
            kat = next((u.get("kategori", "Diğer") for u in st.session_state.stok if u["urun_adi"] == f["urun_adi"]), "Diğer")
            kat_fire[kat] = kat_fire.get(kat, 0) + f["miktar"]
        fig = px.pie(names=list(kat_fire.keys()), values=list(kat_fire.values()), title="Kategori Bazlı Fire", hole=0.3)
        st.plotly_chart(fig, width='stretch')
    else:
        st.info("Fire kaydı yok.")

def satis_raporu() -> None:
    st.markdown('<div class="main-header">📊 Satış Raporu</div>', unsafe_allow_html=True)
    satislar = dosya_oku(SATIS_DOSYASI, [])
    if not satislar: st.info("Henüz satış yok."); return
    df = pd.DataFrame(satislar)
    df["tarih"] = pd.to_datetime(df["tarih"]); df["gun"] = df["tarih"].dt.date; df["ay"] = df["tarih"].dt.strftime("%Y-%m")
    c1, c2, _ = st.columns(3)
    with c1: aralik = st.date_input("Tarih Aralığı", value=(df["gun"].min(), df["gun"].max()), key="rapor_tarih")
    with c2: tip = st.radio("Kırılım", ["Günlük", "Aylık", "Ürün Bazlı", "Kâr Marjı"], horizontal=True)
    if len(aralik) == 2: df = df[(df["gun"] >= aralik[0]) & (df["gun"] <= aralik[1])]
    if tip == "Günlük":
        rpr = df.groupby("gun")["toplam_tutar"].sum().reset_index(); rpr.columns = ["Tarih", "Toplam Satış (₺)"]
        st.dataframe(rpr, width='stretch'); fig = px.bar(rpr, x="Tarih", y="Toplam Satış (₺)", title="Günlük Satışlar")
        st.plotly_chart(fig, width='stretch')
    elif tip == "Aylık":
        rpr = df.groupby("ay")["toplam_tutar"].sum().reset_index(); rpr.columns = ["Ay", "Toplam Satış (₺)"]
        st.dataframe(rpr, width='stretch'); fig = px.line(rpr, x="Ay", y="Toplam Satış (₺)", markers=True, title="Aylık Trend")
        st.plotly_chart(fig, width='stretch')
    elif tip == "Ürün Bazlı":
        rpr = df.groupby("urun_adi").agg(Adet=("miktar", "sum"), Ciro=("toplam_tutar", "sum")).reset_index()
        st.dataframe(rpr, width='stretch')
        colA, colB = st.columns(2)
        with colA: fig1 = px.pie(rpr, values="Ciro", names="urun_adi", title="Ciro", hole=0.3); st.plotly_chart(fig1, width='stretch')
        with colB: fig2 = px.bar(rpr, x="urun_adi", y="Adet", title="Satış Adedi"); st.plotly_chart(fig2, width='stretch')
    else:
        df_kar = pd.DataFrame(st.session_state.stok)
        df_kar["kar_marji"] = df_kar.apply(lambda r: ((r['satis_fiyat'] - r['alis_fiyat']) / r['satis_fiyat'] * 100) if r['satis_fiyat'] > 0 else 0, axis=1)
        st.dataframe(df_kar[["urun_adi", "satis_fiyat", "alis_fiyat", "kar_marji"]].style.format({"kar_marji": "{:.1f}%"}), width='stretch')

def aktivite_logu() -> None:
    st.markdown('<div class="main-header">📋 Aktivite Logu</div>', unsafe_allow_html=True)
    hareketler = dosya_oku(HAREKET_DOSYASI, [])
    if not hareketler: st.info("Henüz hareket kaydı yok."); return
    df = pd.DataFrame(hareketler); df["tarih"] = pd.to_datetime(df["tarih"])
    c1, c2 = st.columns(2)
    with c1: baslangic = st.date_input("Başlangıç", df["tarih"].min().date())
    with c2: bitis = st.date_input("Bitiş", df["tarih"].max().date())
    mask = (df["tarih"].dt.date >= baslangic) & (df["tarih"].dt.date <= bitis)
    st.dataframe(df[mask].sort_values("tarih", ascending=False), width='stretch')

def kasa_kapanisi() -> None:
    st.markdown('<div class="main-header">🧾 Günlük Kasa Kapanışı</div>', unsafe_allow_html=True)
    bugun = datetime.now().strftime("%Y-%m-%d")
    satislar = [s for s in dosya_oku(SATIS_DOSYASI, []) if s["tarih"].startswith(bugun)]
    if not satislar: st.info("Bugün henüz satış yapılmamış."); return
    toplam = sum(s["toplam_tutar"] for s in satislar)
    df = pd.DataFrame(satislar)
    st.subheader("📋 Satış Detayı")
    st.dataframe(df[["urun_adi", "miktar", "birim_fiyat", "toplam_tutar"]], width='stretch')
    st.metric("Toplam Satış", f"{toplam:.2f} ₺")
    if st.button("📄 PDF İndir"):
        pdf = FPDF(); pdf.add_page()
        pdf.add_font("DejaVu", "", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", uni=True); pdf.set_font("DejaVu", size=12)
        pdf.cell(200, 10, txt=f"Günlük Kasa Kapanışı - {bugun}", ln=True, align='C'); pdf.ln(10)
        for _, row in df.iterrows():
            pdf.cell(50, 10, txt=row["urun_adi"], border=1)
            pdf.cell(30, 10, txt=str(row["miktar"]), border=1)
            pdf.cell(30, 10, txt=f"{row['birim_fiyat']} ₺", border=1)
            pdf.cell(30, 10, txt=f"{row['toplam_tutar']} ₺", border=1)
            pdf.ln()
        pdf.ln(10); pdf.cell(200, 10, txt=f"Toplam: {toplam:.2f} ₺", ln=True)
        pdf.output("kasa_kapanis.pdf")
        with open("kasa_kapanis.pdf", "rb") as f: st.download_button("📥 PDF İndir", f.read(), "kasa_kapanis.pdf")
    if st.button("📧 Patrona Gönder"):
        alici = st.session_state.get("patron_email", "")
        if not alici: st.error("Ayarlar sayfasından patron e‑postasını tanımlayın.")
        else:
            pdf = FPDF(); pdf.add_page(); pdf.add_font("DejaVu", "", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", uni=True); pdf.set_font("DejaVu", size=12)
            pdf.cell(200, 10, txt=f"Günlük Kasa Kapanışı - {bugun}", ln=True, align='C'); pdf.ln(10)
            for _, row in df.iterrows():
                pdf.cell(50, 10, txt=row["urun_adi"], border=1)
                pdf.cell(30, 10, txt=str(row["miktar"]), border=1)
                pdf.cell(30, 10, txt=f"{row['birim_fiyat']} ₺", border=1)
                pdf.cell(30, 10, txt=f"{row['toplam_tutar']} ₺", border=1)
                pdf.ln()
            pdf.ln(10); pdf.cell(200, 10, txt=f"Toplam: {toplam:.2f} ₺", ln=True); pdf.output("kasa_kapanis.pdf")
            if email_gonder_pdf(alici, "Günlük Kasa Raporu", "Günlük kasa kapanış raporu ektedir.", open("kasa_kapanis.pdf", "rb").read(), "kasa_kapanis.pdf"):
                st.success("✅ Rapor e‑posta ile gönderildi.")
            else:
                st.error("E‑posta gönderilemedi.")

def kullanici_yonetimi() -> None:
    st.markdown('<div class="main-header">👥 Kullanıcı Yönetimi</div>', unsafe_allow_html=True)
    with st.form("kullanici_ekle"):
        yeni_kul = st.text_input("Kullanıcı Adı"); yeni_sifre = st.text_input("Şifre", type="password")
        rol = st.selectbox("Rol", list(ROLLER.keys())); ad = st.text_input("Ad Soyad")
        if st.form_submit_button("Ekle"):
            if not yeni_kul or not yeni_sifre: st.error("Kullanıcı adı ve şifre zorunlu")
            else:
                st.session_state.kullanicilar.append({"kullanici_adi": yeni_kul, "sifre": hashlib.sha256(yeni_sifre.encode()).hexdigest(), "rol": rol, "ad": ad})
                dosya_yaz(KULLANICI_DOSYASI, st.session_state.kullanicilar); st.session_state.son_islem_mesaji = f"✅ {yeni_kul} eklendi"; st.rerun()

def sifre_sifirla() -> None:
    st.markdown('<div class="main-header">🔑 Şifre Sıfırlama</div>', unsafe_allow_html=True)
    with st.form("sifre_sifirla"):
        eski_sifre = st.text_input("Eski Şifre", type="password"); yeni_sifre = st.text_input("Yeni Şifre", type="password"); yeni_sifre2 = st.text_input("Yeni Şifre (Tekrar)", type="password")
        if st.form_submit_button("Sıfırla"):
            admin_pass = config.get("sifre", "1234")
            try: admin_pass = st.secrets["admin"]["sifre"]
            except: pass
            if eski_sifre != admin_pass: st.error("Eski şifre yanlış.")
            elif yeni_sifre != yeni_sifre2: st.error("Yeni şifreler eşleşmiyor.")
            elif len(yeni_sifre) < 4: st.error("Şifre en az 4 karakter olmalı.")
            else:
                config["sifre"] = yeni_sifre; dosya_yaz(CONFIG_DOSYASI, config)
                st.session_state.son_islem_mesaji = "✅ Şifre güncellendi."; st.rerun()

def geri_bildirim() -> None:
    st.markdown('<div class="main-header">💬 Geri Bildirim</div>', unsafe_allow_html=True)
    with st.form("geribildirim"):
        konu = st.text_input("Konu"); mesaj = st.text_area("Görüş ve önerileriniz")
        if st.form_submit_button("Gönder"): logging.info(f"Geri Bildirim: {konu} - {mesaj}"); st.session_state.son_islem_mesaji = "✅ Teşekkürler!"; st.rerun()

def ayarlar_sayfasi() -> None:
    st.markdown('<div class="main-header">⚙️ Ayarlar</div>', unsafe_allow_html=True)
    with st.form("ayarlar_form"):
        eposta = st.text_input("Patron E‑posta", value=st.session_state.get("patron_email", ""))
        telefon = st.text_input("Patron Telefon (5XXXXXXXXX)", value=st.session_state.get("patron_telefon", ""))
        col1, col2, col3 = st.columns(3)
        with col1: kaydet = st.form_submit_button("💾 Kaydet")
        with col2: test_eposta = st.form_submit_button("📧 Test E‑postası")
        with col3: test_whatsapp = st.form_submit_button("📱 Test WhatsApp")
        if kaydet: st.session_state.patron_email = eposta; st.session_state.patron_telefon = telefon; st.session_state.son_islem_mesaji = "✅ Ayarlar güncellendi"; st.rerun()
        if test_eposta:
            if not eposta: st.error("Önce e‑posta girin")
            elif email_gonder(eposta, "Test Mesajı", "Market Yönetim Sistemi test e‑postasıdır."): st.session_state.son_islem_mesaji = "✅ Test e‑postası gönderildi"; st.rerun()
            else: st.error("E‑posta gönderilemedi.")
        if test_whatsapp:
            if not telefon: st.error("Önce telefon girin")
            elif whatsapp_gonder(f"+90{telefon}", "Market Yönetim Sistemi test mesajıdır."): st.session_state.son_islem_mesaji = "✅ Test WhatsApp gönderildi"; st.rerun()
            else: st.error("WhatsApp gönderilemedi.")

def yedekleme_sayfasi() -> None:
    st.markdown('<div class="main-header">💾 Yedekleme</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        yedek = {"stok": st.session_state.stok, "fire": st.session_state.fire, "barkod_db": st.session_state.barkod_db, "tedarikciler": st.session_state.tedarikciler}
        st.download_button("📥 JSON İndir", json.dumps(yedek, ensure_ascii=False, indent=2), "yedek.json", use_container_width=True)
    with c2:
        dosya = st.file_uploader("Yedek yükle", type="json")
        if dosya:
            icerik = json.load(dosya); st.session_state.stok = icerik.get("stok", []); st.session_state.fire = icerik.get("fire", []); st.session_state.barkod_db = icerik.get("barkod_db", {}); st.session_state.tedarikciler = icerik.get("tedarikciler", [])
            veriyi_kaydet(); st.session_state.son_islem_mesaji = "✅ Yedek yüklendi"; st.rerun()

def veriyi_kaydet() -> None:
    dosya_yaz(STOK_DOSYASI, st.session_state.stok); dosya_yaz(FIRE_DOSYASI, st.session_state.fire); dosya_yaz(TEDARIKCI_DOSYASI, st.session_state.tedarikciler)

SAYFALAR = {
    "🏠 Ana Panel": ana_sayfa, "📱 Barkod": barkod_sayfasi, "💵 Satış": satis_sayfasi,
    "📦 Stok": stok_sayfasi, "🔥 Sipariş": siparis_sayfasi, "🏭 Tedarikçi": tedarikci_sayfasi,
    "📈 Stok Analizi": stok_analizi, "📉 Fire Analizi": fire_analizi, "📊 Satış Raporu": satis_raporu,
    "📋 Aktivite Logu": aktivite_logu, "🧾 Kasa Kapanışı": kasa_kapanisi, "👥 Kullanıcı Yönetimi": kullanici_yonetimi,
    "🔑 Şifre Sıfırlama": sifre_sifirla, "💬 Geri Bildirim": geri_bildirim, "⚙️ Ayarlar": ayarlar_sayfasi,
    "💾 Yedekleme": yedekleme_sayfasi,
}

def main() -> None:
    st.set_page_config(page_title="Market Yönetim", page_icon="🏪", layout="wide", initial_sidebar_state="expanded")
    oturumu_baslat(); enerjik_css(st.session_state.get("tema", "Koyu")); pd.set_option('display.float_format', '{:.2f}'.format)
    oturum_kontrol()
    if not st.session_state.authenticated: giris_ekrani(); return
    if st.session_state.son_islem_mesaji: st.success(st.session_state.son_islem_mesaji); st.session_state.son_islem_mesaji = ""
    with st.sidebar:
        st.markdown('<h2 style="color:white;">🏪 Market</h2>', unsafe_allow_html=True)
        st.markdown('<p style="color:#F97316;">v3.0 Akıllı Asistan</p>', unsafe_allow_html=True)
        if st.session_state.current_user:
            st.markdown(f'<div style="background:rgba(249,115,22,0.2);border-radius:12px;padding:12px;"><p style="color:white;">👤 {st.session_state.current_user.get("ad", "Kullanıcı")}</p></div>', unsafe_allow_html=True)
        st.selectbox("Tema", ["Koyu", "Aydınlık"], index=0 if st.session_state.get("tema", "Koyu") == "Koyu" else 1, key="tema_secimi", on_change=tema_degistir)
        aktif_sayfalar = izinli_sayfalar(st.session_state.current_user)
        if not aktif_sayfalar: st.error("İzinli sayfa yok."); st.stop()
        sayfa = st.radio("Menü", list(aktif_sayfalar.keys()), label_visibility="collapsed")
        if st.button("🚪 Çıkış", use_container_width=True): cikis()
    aktif_sayfalar[sayfa]()

if __name__ == "__main__":
    main()
