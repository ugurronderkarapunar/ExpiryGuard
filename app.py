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
import io
import re

# ---------- WHATSAPP KONTROL ----------
try:
    import pywhatkit as pwk
    WHATSAPP_AKTIF = True
except ImportError:
    WHATSAPP_AKTIF = False

# ---------- LOGGING YAPILANDIRMASI ----------
def setup_logging():
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    error_handler = logging.FileHandler(os.path.join(log_dir, 'error.log'))
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    
    warning_handler = logging.FileHandler(os.path.join(log_dir, 'warning.log'))
    warning_handler.setLevel(logging.WARNING)
    warning_handler.setFormatter(formatter)
    
    info_handler = logging.FileHandler(os.path.join(log_dir, 'info.log'))
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(formatter)
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(error_handler)
    logger.addHandler(warning_handler)
    logger.addHandler(info_handler)
    logger.addHandler(console_handler)

setup_logging()
logging.info("Uygulama başlatıldı")

# ---------- KONFİGÜRASYON ----------
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
STOK_DOSYASI = config["dosya_yollari"]["stok"]
FIRE_DOSYASI = config["dosya_yollari"]["fire"]
HAREKET_DOSYASI = config["dosya_yollari"]["hareket"]
BARKOD_DB_DOSYASI = config["dosya_yollari"]["barkod_db"]
TEDARIKCI_DOSYASI = config["dosya_yollari"]["tedarikciler"]
KULLANICI_DOSYASI = config["dosya_yollari"]["kullanicilar"]
SATIS_DOSYASI = config["dosya_yollari"]["satislar"]
KATEGORILER = config.get("kategoriler", ["Kuru Gıda", "Süt Ürünleri", "İçecek", "Temizlik", "Diğer"])
BIRIMLER = config.get("birimler", ["kg", "litre", "adet", "paket", "gram", "koli", "kutu", "şişe", "çuval"])
ROLLER = config.get("roller", {"patron": ["tümü"], "kasiyer": ["barkod", "satis"], "depocu": ["barkod", "stok"]})
OTURUM_SURESI = config.get("oturum_suresi_dk", 30)
SKT_UYARI_GUN = config.get("skt_uyari_gun", 3)

# ---------- YARDIMCI FONKSİYONLAR ----------
def guvenli_html(metin: str) -> str:
    return (str(metin).replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#x27;"))

def tema_degistir() -> None:
    st.session_state.tema = st.session_state.get("tema_secimi", "Koyu")

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

def dosya_oku(dosya_adi: str, varsayilan=None):
    if os.path.exists(dosya_adi):
        try:
            with open(dosya_adi, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Dosya okuma hatası {dosya_adi}: {e}")
    return varsayilan if varsayilan is not None else []

def dosya_yaz(dosya_adi: str, veri) -> bool:
    try:
        with open(dosya_adi, "w", encoding="utf-8") as f:
            json.dump(veri, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logging.error(f"Dosya yazma hatası {dosya_adi}: {e}")
        return False

# ---------- PDF FONT HATASI ÇÖZÜMÜ ----------
def get_font_path():
    """Sistemde DejaVuSans.ttf fontunu bulur, yoksa None döndürür."""
    possible_paths = [
        os.path.join(os.path.dirname(__file__), "fonts", "DejaVuSans.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/DejaVuSans.ttf",
        "/System/Library/Fonts/DejaVuSans.ttf",
        "/usr/local/share/fonts/DejaVuSans.ttf",
        "./DejaVuSans.ttf"
    ]
    for p in possible_paths:
        if os.path.exists(p):
            return p
    logging.warning("DejaVuSans.ttf fontu bulunamadı, Helvetica kullanılacak (Türkçe karakter sorunu olabilir).")
    return None

def fis_olustur(urun_adi: str, birim: str, miktar: float, birim_fiyat: float,
                toplam_tutar: float, odeme_tipi: str) -> FPDF:
    pdf = FPDF()
    pdf.add_page()
    font_path = get_font_path()
    if font_path:
        pdf.add_font("DejaVu", "", font_path, uni=True)
        pdf.set_font("DejaVu", size=10)
    else:
        pdf.set_font("Helvetica", size=10)
    pdf.cell(80, 10, txt="🏪 Market Yönetim Sistemi", ln=True, align='C')
    pdf.cell(80, 10, txt="ALIŞVERİŞ FİŞİ", ln=True, align='C')
    pdf.ln(5)
    pdf.set_font("DejaVu" if font_path else "Helvetica", size=8)
    pdf.cell(80, 6, txt=f"Tarih: {datetime.now().strftime('%d.%m.%Y %H:%M')}", ln=True, align='C')
    pdf.ln(5)
    pdf.set_font("DejaVu" if font_path else "Helvetica", size=10)
    pdf.cell(50, 8, txt="Ürün:", border=0)
    pdf.cell(30, 8, txt=urun_adi[:20], border=0, ln=True)
    pdf.cell(50, 8, txt="Miktar:", border=0)
    pdf.cell(30, 8, txt=f"{miktar} {birim}", border=0, ln=True)
    pdf.cell(50, 8, txt="Birim Fiyat:", border=0)
    pdf.cell(30, 8, txt=f"{birim_fiyat:.2f} ₺", border=0, ln=True)
    pdf.ln(3)
    pdf.set_font("DejaVu" if font_path else "Helvetica", size=12)
    pdf.cell(50, 10, txt="TOPLAM:", border=0)
    pdf.cell(30, 10, txt=f"{toplam_tutar:.2f} ₺", border=0, ln=True)
    pdf.set_font("DejaVu" if font_path else "Helvetica", size=8)
    pdf.cell(50, 6, txt=f"Ödeme: {odeme_tipi}", border=0, ln=True)
    pdf.ln(5)
    pdf.cell(80, 6, txt="İyi günlerde kullanın!", ln=True, align='C')
    return pdf

# ---------- OTOMATİK YEDEKLEME ----------
def otomatik_yedekleme_kontrol():
    """Son yedekleme 24 saatten fazla olduysa ve patron e-postası varsa yedek gönder."""
    if not st.session_state.get("authenticated", False):
        return
    patron_email = st.session_state.get("patron_email", "")
    if not patron_email:
        return
    yedek_dosyasi = "yedek_otomatik.json"
    son_yedekleme_dosyasi = "son_yedekleme.txt"
    gonder = False
    if os.path.exists(son_yedekleme_dosyasi):
        with open(son_yedekleme_dosyasi, "r") as f:
            try:
                son_zaman = datetime.fromisoformat(f.read().strip())
                if datetime.now() - son_zaman > timedelta(hours=24):
                    gonder = True
            except:
                gonder = True
    else:
        gonder = True
    
    if gonder:
        yedek = {
            "stok": st.session_state.stok,
            "fire": st.session_state.fire,
            "barkod_db": st.session_state.barkod_db,
            "tedarikciler": st.session_state.tedarikciler,
            "kullanicilar": st.session_state.kullanicilar,
            "tarih": datetime.now().isoformat()
        }
        with open(yedek_dosyasi, "w", encoding="utf-8") as f:
            json.dump(yedek, f, ensure_ascii=False, indent=2)
        with open(yedek_dosyasi, "rb") as f:
            json_bytes = f.read()
        konu = "Otomatik Günlük Yedek"
        mesaj = f"Market yönetim sisteminin {datetime.now().strftime('%d.%m.%Y')} tarihli otomatik yedeği ektedir."
        if email_gonder_pdf(patron_email, konu, mesaj, json_bytes, "yedek_otomatik.json"):
            with open(son_yedekleme_dosyasi, "w") as f:
                f.write(datetime.now().isoformat())
            logging.info("Otomatik yedekleme e-postası gönderildi")
        else:
            logging.error("Otomatik yedekleme e-postası gönderilemedi")

# ---------- DİĞER TEMEL FONKSİYONLAR ----------
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

def hareket_ekle(kul: str, islem: str, ad: str, detay: str = "") -> None:
    h = {"tarih": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "kullanici": kul, "islem": islem,
         "urun_adi": ad, "detay": detay}
    liste = dosya_oku(HAREKET_DOSYASI, [])
    liste.append(h)
    if len(liste) > 1000:
        liste = liste[-1000:]
    dosya_yaz(HAREKET_DOSYASI, liste)

def satis_kaydet(ad: str, birim: str, miktar: float, fiyat: float, tutar: float, kul: str,
                 alis_fiyat: float = 0, odeme_tipi: str = "Nakit") -> None:
    s = {"id": str(uuid.uuid4())[:8], "tarih": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
         "kullanici": kul, "urun_adi": ad, "birim": birim, "miktar": miktar,
         "birim_fiyat": fiyat, "toplam_tutar": tutar,
         "alis_fiyat": alis_fiyat, "maliyet": round(miktar * alis_fiyat, 2),
         "odeme_tipi": odeme_tipi}
    liste = dosya_oku(SATIS_DOSYASI, [])
    liste.append(s)
    dosya_yaz(SATIS_DOSYASI, liste)

def gunluk_kar() -> float:
    liste = dosya_oku(SATIS_DOSYASI, [])
    bugun = datetime.now().strftime("%Y-%m-%d")
    toplam_satis = 0
    toplam_maliyet = 0
    for s in liste:
        if s["tarih"].startswith(bugun):
            toplam_satis += s["toplam_tutar"]
            maliyet = s.get("maliyet", s.get("miktar", 0) * s.get("alis_fiyat", 0))
            toplam_maliyet += maliyet
    return round(toplam_satis - toplam_maliyet, 2)

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

# ---------- OTURUM YÖNETİMİ ----------
def oturumu_baslat() -> None:
    if "stok" not in st.session_state:
        st.session_state.stok = dosya_oku(STOK_DOSYASI, mock_stok_olustur())
    if "fire" not in st.session_state:
        st.session_state.fire = dosya_oku(FIRE_DOSYASI, mock_fire_olustur())
    if "barkod_db" not in st.session_state:
        db = dosya_oku(BARKOD_DB_DOSYASI, None)
        if db is None:
            db = mock_barkod_db_olustur()
            dosya_yaz(BARKOD_DB_DOSYASI, db)
        st.session_state.barkod_db = db
    if "tedarikciler" not in st.session_state:
        st.session_state.tedarikciler = dosya_oku(TEDARIKCI_DOSYASI, [])
    if "kullanicilar" not in st.session_state:
        st.session_state.kullanicilar = dosya_oku(KULLANICI_DOSYASI, [
            {"kullanici_adi": "admin", "sifre": hashlib.sha256("1234".encode()).hexdigest(), "rol": "patron",
             "ad": "Ahmet"}
        ])
    if "pos_sepet" not in st.session_state:
        st.session_state.pos_sepet = {}
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
    otomatik_yedekleme_kontrol()

def oturum_kontrol() -> None:
    if st.session_state.authenticated:
        if datetime.now() - st.session_state.last_activity > timedelta(minutes=OTURUM_SURESI):
            st.session_state.authenticated = False
            st.sidebar.error("⏳ Oturum süreniz doldu! Lütfen tekrar giriş yapın.")
            st.session_state.son_islem_mesaji = "Oturum süresi doldu"
            st.rerun()
        else:
            st.session_state.last_activity = datetime.now()

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

def izinli_sayfalar(kullanici: dict) -> dict:
    if not kullanici:
        return {}
    rol = kullanici.get("rol", "")
    izinler = ROLLER.get(rol, [])
    if "tümü" in izinler:
        return SAYFALAR
    yetki_sayfa = {
        "barkod": ["📱 Barkod", "🏷️ Barkod Yönetimi"],
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

# ---------- BARKOD YÖNETİM SAYFASI ----------
def barkod_yonetimi():
    st.markdown('<div class="main-header">🏷️ Barkod Yönetimi</div>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["📋 Barkod Listesi", "➕ Yeni Barkod Ekle"])
    
    with tab1:
        if st.session_state.barkod_db:
            arama = st.text_input("🔍 Barkod veya ürün adı ile ara", placeholder="869... veya Un")
            df_barkod = pd.DataFrame([{"barkod": k, **v} for k, v in st.session_state.barkod_db.items()])
            if arama:
                df_barkod = df_barkod[df_barkod["barkod"].str.contains(arama, case=False, na=False) |
                                      df_barkod["urun_adi"].str.contains(arama, case=False, na=False)]
            st.dataframe(df_barkod, use_container_width=True)
            
            for idx, row in df_barkod.iterrows():
                barkod_kodu = row["barkod"]
                with st.expander(f"🔧 {row['urun_adi']} ({barkod_kodu})"):
                    col1, col2 = st.columns(2)
                    with col1:
                        yeni_ad = st.text_input("Ürün Adı", value=row["urun_adi"], key=f"ad_{barkod_kodu}")
                        yeni_birim = st.selectbox("Birim", BIRIMLER, index=BIRIMLER.index(row["birim"]) if row["birim"] in BIRIMLER else 0, key=f"birim_{barkod_kodu}")
                        yeni_kategori = st.selectbox("Kategori", KATEGORILER, index=KATEGORILER.index(row["kategori"]) if row["kategori"] in KATEGORILER else 0, key=f"kat_{barkod_kodu}")
                        yeni_uretici = st.text_input("Üretici", value=row.get("uretici", ""), key=f"uret_{barkod_kodu}")
                    with col2:
                        if st.button("💾 Güncelle", key=f"guncelle_{barkod_kodu}"):
                            st.session_state.barkod_db[barkod_kodu].update({
                                "urun_adi": yeni_ad,
                                "birim": yeni_birim,
                                "kategori": yeni_kategori,
                                "uretici": yeni_uretici
                            })
                            dosya_yaz(BARKOD_DB_DOSYASI, st.session_state.barkod_db)
                            st.session_state.son_islem_mesaji = f"✅ Barkod {barkod_kodu} güncellendi"
                            st.rerun()
                        if st.button("🗑️ Sil", key=f"sil_{barkod_kodu}"):
                            kullaniliyor = any(u.get("barkod") == barkod_kodu for u in st.session_state.stok)
                            if kullaniliyor:
                                st.error("Bu barkod stokta bir ürüne ait, önce ürünü silin veya barkodunu değiştirin.")
                            else:
                                del st.session_state.barkod_db[barkod_kodu]
                                dosya_yaz(BARKOD_DB_DOSYASI, st.session_state.barkod_db)
                                st.session_state.son_islem_mesaji = f"✅ Barkod {barkod_kodu} silindi"
                                st.rerun()
        else:
            st.info("Henüz barkod veritabanı boş.")
    
    with tab2:
        with st.form("yeni_barkod_form"):
            yeni_barkod = st.text_input("Barkod Numarası")
            yeni_ad = st.text_input("Ürün Adı")
            yeni_birim = st.selectbox("Birim", BIRIMLER)
            yeni_kategori = st.selectbox("Kategori", KATEGORILER)
            yeni_uretici = st.text_input("Üretici (isteğe bağlı)")
            if st.form_submit_button("➕ Ekle"):
                if not yeni_barkod or not yeni_ad:
                    st.error("Barkod ve ürün adı zorunlu")
                elif yeni_barkod in st.session_state.barkod_db:
                    st.error("Bu barkod zaten mevcut")
                else:
                    st.session_state.barkod_db[yeni_barkod] = {
                        "urun_adi": yeni_ad,
                        "birim": yeni_birim,
                        "kategori": yeni_kategori,
                        "uretici": yeni_uretici
                    }
                    dosya_yaz(BARKOD_DB_DOSYASI, st.session_state.barkod_db)
                    st.session_state.son_islem_mesaji = f"✅ Barkod {yeni_barkod} eklendi"
                    st.rerun()

# ---------- RAPOR DIŞA AKTARMA ----------
def excel_rapor_indir(df, dosya_adi="rapor.xlsx"):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="Rapor")
    output.seek(0)
    return output.getvalue()

# ---------- TEDARİKÇİ SAYFASI (iyileştirilmiş) ----------
def tedarikci_sayfasi() -> None:
    st.markdown('<div class="main-header">🏭 Tedarikçi Yönetimi</div>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["📋 Liste", "➕ Ekle/Düzenle"])
    
    with tab1:
        if st.session_state.tedarikciler:
            for i, t in enumerate(st.session_state.tedarikciler):
                col1, col2, col3 = st.columns([4,1,1])
                with col1:
                    st.markdown(f"**{guvenli_html(t['ad'])}** – Güven: {t.get('guven_puani', 0):.1f}/10 – Tel: {t.get('tel', '')} – E‑posta: {t.get('eposta', '')}")
                with col2:
                    if st.button("✏️ Düzenle", key=f"duzenle_{i}"):
                        st.session_state.duzenlenecek_tedarikci = i
                        st.rerun()
                with col3:
                    if st.button("🗑️ Sil", key=f"sil_{i}"):
                        st.session_state.tedarikciler.pop(i)
                        dosya_yaz(TEDARIKCI_DOSYASI, st.session_state.tedarikciler)
                        st.session_state.son_islem_mesaji = "Tedarikçi silindi"
                        st.rerun()
        else:
            st.info("Henüz tedarikçi eklenmemiş.")
    
    with tab2:
        duzenle_index = st.session_state.get("duzenlenecek_tedarikci", None)
        if duzenle_index is not None:
            t = st.session_state.tedarikciler[duzenle_index]
            baslik = "Tedarikçi Düzenle"
        else:
            t = {"ad": "", "guven_puani": 5.0, "tel": "", "eposta": ""}
            baslik = "Yeni Tedarikçi Ekle"
        
        st.subheader(baslik)
        with st.form("tedarikci_form"):
            ad = st.text_input("Firma Adı", value=t["ad"])
            guven = st.slider("Güven Puanı", 0.0, 10.0, t["guven_puani"])
            tel = st.text_input("Telefon (5XX XXX XX XX)", value=t["tel"])
            eposta = st.text_input("E‑posta", value=t["eposta"])
            
            if st.form_submit_button("Kaydet"):
                hata = False
                if not ad.strip():
                    st.error("Firma adı zorunlu")
                    hata = True
                if tel and not (tel.isdigit() and len(tel) == 10):
                    st.error("Telefon 10 haneli rakamlardan oluşmalı (örnek: 5551234567)")
                    hata = True
                if eposta and not re.match(r"^[^@]+@[^@]+\.[^@]+$", eposta):
                    st.error("Geçerli bir e-posta adresi girin (ornek@domain.com)")
                    hata = True
                if not hata:
                    yeni_t = {"ad": ad.strip(), "guven_puani": guven, "tel": tel, "eposta": eposta}
                    if duzenle_index is not None:
                        st.session_state.tedarikciler[duzenle_index] = yeni_t
                        del st.session_state.duzenlenecek_tedarikci
                    else:
                        if any(tm["ad"] == ad.strip() for tm in st.session_state.tedarikciler):
                            st.error("Bu firma adı zaten mevcut")
                        else:
                            st.session_state.tedarikciler.append(yeni_t)
                    dosya_yaz(TEDARIKCI_DOSYASI, st.session_state.tedarikciler)
                    st.session_state.son_islem_mesaji = f"✅ Tedarikçi {'güncellendi' if duzenle_index is not None else 'eklendi'}"
                    st.rerun()

# ---------- FİRE (SİPARİŞ) SAYFASI (dropdown ile) ----------
def siparis_sayfasi() -> None:
    st.markdown('<div class="main-header">🔥 Sipariş Panosu</div>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["📋 Liste", "➕ Ekle"])
    with tab1:
        if st.session_state.fire:
            for i, row in enumerate(st.session_state.fire):
                c1, c2, c3 = st.columns([3, 1, 1])
                with c1:
                    renk = "🟢" if "Düşük" in row['aciliyet'] else "🟡" if "Orta" in row['aciliyet'] else "🔴"
                    st.write(f"{renk} **{guvenli_html(row['urun_adi'])}** – {row['miktar']} {row['birim']} – {row['durum']}")
                with c2:
                    if st.button("🗑️ Sil", key=f"sil_fire_{i}"):
                        st.session_state.fire.pop(i)
                        veriyi_kaydet()
                        st.session_state.son_islem_mesaji = "Sipariş silindi"
                        st.rerun()
                with c3:
                    if st.button("📧 Tedarikçiye Gönder", key=f"tedarik_fire_{i}"):
                        urun_adi = row['urun_adi']
                        tedarikci_adi = row.get("tedarikci", "")
                        tedarikci_eposta = next((t["eposta"] for t in st.session_state.tedarikciler if t["ad"] == tedarikci_adi), "")
                        if tedarikci_eposta:
                            urun_dict = row.copy()
                            for u in st.session_state.stok:
                                if u["urun_adi"] == urun_adi:
                                    urun_dict["miktar"] = u["miktar"]
                                    urun_dict["min_miktar"] = u.get("min_miktar", 10)
                                    break
                            if tedarikciye_siparis_gonder(urun_dict, tedarikci_eposta):
                                st.session_state.son_islem_mesaji = f"📧 {urun_adi} siparişi gönderildi"
                                st.rerun()
                        else:
                            st.error("Tedarikçi e‑postası bulunamadı.")
        else:
            st.info("Sipariş yok.")
    with tab2:
        with st.form("fire_ekle"):
            if not st.session_state.stok:
                st.warning("Önce stokta ürün olmalı")
            else:
                urun_secenekleri = {u["urun_adi"]: u for u in st.session_state.stok}
                secili_urun = st.selectbox("Ürün", list(urun_secenekleri.keys()))
                urun_bilgi = urun_secenekleri[secili_urun]
                miktar = st.number_input("Miktar", min_value=0.01, value=1.0, format="%.2f")
                st.write(f"Birim: {urun_bilgi['birim']}")
                if st.form_submit_button("Ekle"):
                    st.session_state.fire.append({
                        "urun_adi": secili_urun,
                        "miktar": miktar,
                        "birim": urun_bilgi["birim"],
                        "aciliyet": "⚡ Orta",
                        "tedarikci": urun_bilgi.get("tedarikci", ""),
                        "durum": "Bekliyor",
                        "eklenme_tarihi": datetime.now().strftime("%Y-%m-%d %H:%M")
                    })
                    veriyi_kaydet()
                    st.session_state.son_islem_mesaji = "🔥 Sipariş eklendi"
                    st.rerun()

# ---------- ANA SAYFA (kritik stok balonu düzeltildi) ----------
def ana_sayfa() -> None:
    st.markdown('<div class="main-header">📊 Yönetim Paneli</div>', unsafe_allow_html=True)
    kritik = [u for u in st.session_state.stok if u.get("min_miktar", 0) > 0 and u["miktar"] <= u["min_miktar"]]
    if kritik:
        st.balloons()
        st.error(f"🚨 {len(kritik)} ürün kritik stok seviyesinde!")
    
    bugun = datetime.now()
    bugun_str = bugun.strftime("%Y-%m-%d")
    bugunku = gunluk_ciro(bugun_str)
    dun = gunluk_ciro((bugun - timedelta(days=1)).strftime("%Y-%m-%d"))
    delta_gun = bugunku - dun
    bugunku_kar = gunluk_kar()
    
    st.subheader("📈 Hızlı İstatistikler")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Bugünkü Ciro", f"{bugunku:,.0f} ₺", delta=f"{delta_gun:+,.0f} ₺")
    c2.metric("Bugünkü Kâr", f"{bugunku_kar:,.0f} ₺")
    c3.metric("Dünkü Ciro", f"{dun:,.0f} ₺")
    
    bu_hafta = haftalik_ciro()
    gecen_hafta = haftalik_ciro((bugun - timedelta(days=7)).date())
    delta_hafta = bu_hafta - gecen_hafta
    c4.metric("Bu Hafta", f"{bu_hafta:,.0f} ₺", delta=f"{delta_hafta:+,.0f} ₺")
    
    bu_ay = aylik_ciro()
    gecen_ay_tarih = bugun.replace(day=1) - timedelta(days=1)
    gecen_ay = aylik_ciro(gecen_ay_tarih.year, gecen_ay_tarih.month)
    delta_ay = bu_ay - gecen_ay
    c5.metric("Bu Ay", f"{bu_ay:,.0f} ₺", delta=f"{delta_ay:+,.0f} ₺")
    
    haftalik_buyume = 0 if gecen_hafta == 0 else (delta_hafta / gecen_hafta * 100)
    c6.metric("Haftalık Büyüme", f"%{haftalik_buyume:.1f}")

# ---------- DİĞER SAYFALAR (kısaltılmış, mevcut mantık) ----------
# Not: Burada stok_sayfasi, barkod_sayfasi, satis_sayfasi, stok_analizi,
# fire_analizi, satis_raporu, aktivite_logu, kasa_kapanisi, kullanici_yonetimi,
# sifre_sifirla, geri_bildirim, ayarlar_sayfasi, yedekleme_sayfasi gibi
# sayfaların da tanımlı olması gerekir. Ancak uzunluk nedeniyle burada
# sadece kritik düzeltmeler gösterilmiştir. Gerçekte tüm sayfalar mevcut olmalıdır.
# Aşağıda placeholder olarak bırakılmıştır. Çalışan tam uygulama için
# bu fonksiyonların da doldurulması gerekir (önceki kodunuzda zaten vardır).

def barkod_sayfasi():
    st.markdown('<div class="main-header">📱 Barkod Okutma</div>', unsafe_allow_html=True)
    st.info("Bu sayfa mevcut kodunuzda tanımlıdır. Detaylar için önceki sürümünüzü kullanın.")
    # ... (mevcut kodunuz)

def satis_sayfasi():
    st.markdown('<div class="main-header">💰 Satış (POS)</div>', unsafe_allow_html=True)
    st.info("Bu sayfa mevcut kodunuzda tanımlıdır. Detaylar için önceki sürümünüzü kullanın.")

def stok_sayfasi():
    st.markdown('<div class="main-header">📦 Stok Yönetimi</div>', unsafe_allow_html=True)
    st.info("Bu sayfa mevcut kodunuzda tanımlıdır. Detaylar için önceki sürümünüzü kullanın.")

def stok_analizi():
    st.markdown('<div class="main-header">📈 Stok Analizi</div>', unsafe_allow_html=True)
    st.info("Bu sayfa mevcut kodunuzda tanımlıdır.")

def fire_analizi():
    st.markdown('<div class="main-header">📉 Fire Analizi</div>', unsafe_allow_html=True)
    st.info("Bu sayfa mevcut kodunuzda tanımlıdır.")

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
    with c3:
        if st.button("📥 Excel İndir"):
            excel_data = excel_rapor_indir(df, "satis_raporu.xlsx")
            st.download_button("Excel Dosyasını İndir", excel_data, "satis_raporu.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    
    if len(aralik) == 2:
        df = df[(df["gun"] >= aralik[0]) & (df["gun"] <= aralik[1])]
    
    if tip == "Günlük":
        rpr = df.groupby("gun")["toplam_tutar"].sum().reset_index()
        rpr.columns = ["Tarih", "Toplam Satış (₺)"]
        st.dataframe(rpr, use_container_width=True)
        fig = px.bar(rpr, x="Tarih", y="Toplam Satış (₺)", title="Günlük Satışlar")
        st.plotly_chart(fig, use_container_width=True)
    elif tip == "Aylık":
        rpr = df.groupby("ay")["toplam_tutar"].sum().reset_index()
        rpr.columns = ["Ay", "Toplam Satış (₺)"]
        st.dataframe(rpr, use_container_width=True)
        fig = px.line(rpr, x="Ay", y="Toplam Satış (₺)", markers=True, title="Aylık Trend")
        st.plotly_chart(fig, use_container_width=True)
    elif tip == "Ürün Bazlı":
        rpr = df.groupby("urun_adi").agg(Adet=("miktar", "sum"), Ciro=("toplam_tutar", "sum")).reset_index()
        st.dataframe(rpr, use_container_width=True)
        colA, colB = st.columns(2)
        with colA:
            fig1 = px.pie(rpr, values="Ciro", names="urun_adi", title="Ciro", hole=0.3)
            st.plotly_chart(fig1, use_container_width=True)
        with colB:
            fig2 = px.bar(rpr, x="urun_adi", y="Adet", title="Satış Adedi")
            st.plotly_chart(fig2, use_container_width=True)
    else:
        df_kar = pd.DataFrame(st.session_state.stok)
        df_kar["kar_marji"] = df_kar.apply(lambda r: ((r['satis_fiyat'] - r['alis_fiyat']) / r['satis_fiyat'] * 100) if r['satis_fiyat'] > 0 else 0, axis=1)
        st.dataframe(df_kar[["urun_adi", "satis_fiyat", "alis_fiyat", "kar_marji"]].style.format({"kar_marji": "{:.1f}%"}), use_container_width=True)

def aktivite_logu():
    st.markdown('<div class="main-header">📋 Aktivite Logu</div>', unsafe_allow_html=True)
    hareketler = dosya_oku(HAREKET_DOSYASI, [])
    if not hareketler:
        st.info("Henüz hareket kaydı yok.")
        return
    df = pd.DataFrame(hareketler)
    df["tarih"] = pd.to_datetime(df["tarih"])
    c1, c2 = st.columns(2)
    with c1:
        baslangic = st.date_input("Başlangıç", df["tarih"].min().date())
    with c2:
        bitis = st.date_input("Bitiş", df["tarih"].max().date())
    mask = (df["tarih"].dt.date >= baslangic) & (df["tarih"].dt.date <= bitis)
    st.dataframe(df[mask].sort_values("tarih", ascending=False), use_container_width=True)

def kasa_kapanisi():
    st.markdown('<div class="main-header">🧾 Günlük Kasa Kapanışı</div>', unsafe_allow_html=True)
    bugun = datetime.now().strftime("%Y-%m-%d")
    satislar = [s for s in dosya_oku(SATIS_DOSYASI, []) if s["tarih"].startswith(bugun)]
    if not satislar:
        st.info("Bugün henüz satış yapılmamış.")
        return
    toplam = sum(s["toplam_tutar"] for s in satislar)
    df = pd.DataFrame(satislar)
    st.subheader("📋 Satış Detayı")
    st.dataframe(df[["urun_adi", "miktar", "birim_fiyat", "toplam_tutar"]], use_container_width=True)
    st.metric("Toplam Satış", f"{toplam:.2f} ₺")
    st.metric("💎 Net Kâr", f"{gunluk_kar():.2f} ₺")
    
    st.subheader("💳 Ödeme Kanallarına Göre Dağılım")
    if "odeme_tipi" in df.columns:
        odeme_ozet = df.groupby("odeme_tipi")["toplam_tutar"].sum()
        for kanal, tutar in odeme_ozet.items():
            st.metric(f"💳 {kanal}", f"{tutar:,.2f} ₺")
    else:
        st.info("Ödeme kanalı bilgisi bulunamadı.")
    
    if st.button("📄 PDF İndir"):
        pdf = fis_olustur("Kasa Kapanışı", "", 0, 0, toplam, "")
        pdf.output("kasa_kapanis.pdf")
        with open("kasa_kapanis.pdf", "rb") as f:
            st.download_button("📥 PDF İndir", f.read(), "kasa_kapanis.pdf")

def kullanici_yonetimi():
    st.markdown('<div class="main-header">👥 Kullanıcı Yönetimi</div>', unsafe_allow_html=True)
    with st.form("kullanici_ekle"):
        yeni_kul = st.text_input("Kullanıcı Adı")
        yeni_sifre = st.text_input("Şifre", type="password")
        rol = st.selectbox("Rol", list(ROLLER.keys()))
        ad = st.text_input("Ad Soyad")
        if st.form_submit_button("Ekle"):
            if not yeni_kul or not yeni_sifre:
                st.error("Kullanıcı adı ve şifre zorunlu")
            else:
                st.session_state.kullanicilar.append({
                    "kullanici_adi": yeni_kul,
                    "sifre": hashlib.sha256(yeni_sifre.encode()).hexdigest(),
                    "rol": rol,
                    "ad": ad
                })
                dosya_yaz(KULLANICI_DOSYASI, st.session_state.kullanicilar)
                st.session_state.son_islem_mesaji = f"✅ {yeni_kul} eklendi"
                st.rerun()

def sifre_sifirla():
    st.markdown('<div class="main-header">🔑 Şifre Sıfırlama</div>', unsafe_allow_html=True)
    with st.form("sifre_sifirla"):
        eski_sifre = st.text_input("Eski Şifre", type="password")
        yeni_sifre = st.text_input("Yeni Şifre", type="password")
        yeni_sifre2 = st.text_input("Yeni Şifre (Tekrar)", type="password")
        if st.form_submit_button("Sıfırla"):
            admin_pass = config.get("sifre", "1234")
            try:
                admin_pass = st.secrets["admin"]["sifre"]
            except:
                pass
            if eski_sifre != admin_pass:
                st.error("Eski şifre yanlış.")
            elif yeni_sifre != yeni_sifre2:
                st.error("Yeni şifreler eşleşmiyor.")
            elif len(yeni_sifre) < 4:
                st.error("Şifre en az 4 karakter olmalı.")
            else:
                config["sifre"] = yeni_sifre
                dosya_yaz(CONFIG_DOSYASI, config)
                st.session_state.son_islem_mesaji = "✅ Şifre güncellendi."
                st.rerun()

def geri_bildirim():
    st.markdown('<div class="main-header">💬 Geri Bildirim</div>', unsafe_allow_html=True)
    with st.form("geribildirim"):
        konu = st.text_input("Konu")
        mesaj = st.text_area("Görüş ve önerileriniz")
        if st.form_submit_button("Gönder"):
            logging.info(f"Geri Bildirim: {konu} - {mesaj}")
            st.session_state.son_islem_mesaji = "✅ Teşekkürler!"
            st.rerun()

def ayarlar_sayfasi():
    st.markdown('<div class="main-header">⚙️ Ayarlar</div>', unsafe_allow_html=True)
    with st.form("ayarlar_form"):
        eposta = st.text_input("Patron E‑posta", value=st.session_state.get("patron_email", ""))
        telefon = st.text_input("Patron Telefon (5XXXXXXXXX)", value=st.session_state.get("patron_telefon", ""))
        col1, col2, col3 = st.columns(3)
        with col1:
            kaydet = st.form_submit_button("💾 Kaydet")
        with col2:
            test_eposta = st.form_submit_button("📧 Test E‑postası")
        with col3:
            test_whatsapp = st.form_submit_button("📱 Test WhatsApp")
        if kaydet:
            st.session_state.patron_email = eposta
            st.session_state.patron_telefon = telefon
            st.session_state.son_islem_mesaji = "✅ Ayarlar güncellendi"
            st.rerun()
        if test_eposta:
            if not eposta:
                st.error("Önce e‑posta girin")
            elif email_gonder(eposta, "Test Mesajı", "Market Yönetim Sistemi test e‑postasıdır."):
                st.session_state.son_islem_mesaji = "✅ Test e‑postası gönderildi"
                st.rerun()
            else:
                st.error("E‑posta gönderilemedi.")
        if test_whatsapp:
            if not telefon:
                st.error("Önce telefon girin")
            elif whatsapp_gonder(f"+90{telefon}", "Market Yönetim Sistemi test mesajıdır."):
                st.session_state.son_islem_mesaji = "✅ Test WhatsApp gönderildi"
                st.rerun()
            else:
                st.error("WhatsApp gönderilemedi.")

def yedekleme_sayfasi():
    st.markdown('<div class="main-header">💾 Yedekleme</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        yedek = {
            "stok": st.session_state.stok,
            "fire": st.session_state.fire,
            "barkod_db": st.session_state.barkod_db,
            "tedarikciler": st.session_state.tedarikciler
        }
        st.download_button("📥 JSON İndir", json.dumps(yedek, ensure_ascii=False, indent=2), "yedek.json", use_container_width=True)
    with c2:
        dosya = st.file_uploader("Yedek yükle", type="json")
        if dosya:
            icerik = json.load(dosya)
            st.session_state.stok = icerik.get("stok", [])
            st.session_state.fire = icerik.get("fire", [])
            st.session_state.barkod_db = icerik.get("barkod_db", {})
            st.session_state.tedarikciler = icerik.get("tedarikciler", [])
            veriyi_kaydet()
            st.session_state.son_islem_mesaji = "✅ Yedek yüklendi"
            st.rerun()

def veriyi_kaydet() -> None:
    dosya_yaz(STOK_DOSYASI, st.session_state.stok)
    dosya_yaz(FIRE_DOSYASI, st.session_state.fire)
    dosya_yaz(TEDARIKCI_DOSYASI, st.session_state.tedarikciler)

# ---------- SAYFALAR SÖZLÜĞÜ ----------
SAYFALAR = {
    "🏠 Ana Panel": ana_sayfa,
    "📱 Barkod": barkod_sayfasi,
    "🏷️ Barkod Yönetimi": barkod_yonetimi,
    "💵 Satış": satis_sayfasi,
    "📦 Stok": stok_sayfasi,
    "🔥 Sipariş": siparis_sayfasi,
    "🏭 Tedarikçi": tedarikci_sayfasi,
    "📈 Stok Analizi": stok_analizi,
    "📉 Fire Analizi": fire_analizi,
    "📊 Satış Raporu": satis_raporu,
    "📋 Aktivite Logu": aktivite_logu,
    "🧾 Kasa Kapanışı": kasa_kapanisi,
    "👥 Kullanıcı Yönetimi": kullanici_yonetimi,
    "🔑 Şifre Sıfırlama": sifre_sifirla,
    "💬 Geri Bildirim": geri_bildirim,
    "⚙️ Ayarlar": ayarlar_sayfasi,
    "💾 Yedekleme": yedekleme_sayfasi,
}

# ---------- MAIN ----------
def main() -> None:
    st.set_page_config(page_title="Market Yönetim", page_icon="🏪", layout="wide", initial_sidebar_state="expanded")
    oturumu_baslat()
    enerjik_css(st.session_state.get("tema", "Koyu"))
    pd.set_option('display.float_format', '{:.2f}'.format)
    oturum_kontrol()
    if not st.session_state.authenticated:
        giris_ekrani()
        return
    if st.session_state.son_islem_mesaji:
        st.success(st.session_state.son_islem_mesaji)
        st.session_state.son_islem_mesaji = ""
    with st.sidebar:
        st.markdown('<h2 style="color:white;">🏪 Market</h2>', unsafe_allow_html=True)
        st.markdown('<p style="color:#F97316;">v3.0 Akıllı Asistan</p>', unsafe_allow_html=True)
        if st.session_state.current_user:
            st.markdown(f'<div style="background:rgba(249,115,22,0.2);border-radius:12px;padding:12px;"><p style="color:white;">👤 {st.session_state.current_user.get("ad", "Kullanıcı")}</p></div>', unsafe_allow_html=True)
        st.selectbox("Tema", ["Koyu", "Aydınlık"], index=0 if st.session_state.get("tema", "Koyu") == "Koyu" else 1, key="tema_secimi", on_change=tema_degistir)
        aktif_sayfalar = izinli_sayfalar(st.session_state.current_user)
        if not aktif_sayfalar:
            st.error("İzinli sayfa yok.")
            st.stop()
        sayfa = st.radio("Menü", list(aktif_sayfalar.keys()), label_visibility="collapsed")
        if st.button("🚪 Çıkış", use_container_width=True):
            cikis()
    aktif_sayfalar[sayfa]()

if __name__ == "__main__":
    main()
