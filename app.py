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
from io import BytesIO

# ---------- WHATSAPP KONTROL ----------
try:
    import pywhatkit as pwk
    WHATSAPP_AKTIF = True
except ImportError:
    WHATSAPP_AKTIF = False

# ---------- LOGGING ----------
def setup_logging():
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    for lvl, fname in [(logging.ERROR, 'error.log'), (logging.WARNING, 'warning.log'), (logging.INFO, 'info.log')]:
        handler = logging.FileHandler(os.path.join(log_dir, fname))
        handler.setLevel(lvl)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG)
    console.setFormatter(formatter)
    logger.addHandler(console)

setup_logging()
logging.info("Uygulama başlatıldı")

# ---------- KONFİG ----------
CONFIG_DOSYASI = "config.json"
VARSAYILAN_CONFIG = {
    "kullanici_adi": "admin",
    "sifre": "1234",
    "oturum_suresi_dk": 30,
    "skt_uyari_gun": 3,
    "kategoriler": ["Kuru Gıda","Süt Ürünleri","İçecek","Temizlik","Diğer","Et & Şarküteri","Dondurulmuş","Fırın"],
    "birimler": ["kg","litre","adet","paket","gram","koli","kutu","şişe","çuval"],
    "roller": {"patron":["tümü"], "kasiyer":["barkod","satis"], "depocu":["barkod","stok","stok_ekle","skt_takip"]},
    "dosya_yollari": {
        "stok":"stok.json","fire":"fire.json","hareket":"hareket.json","barkod_db":"barkod_db.json",
        "tedarikciler":"tedarikciler.json","kullanicilar":"kullanicilar.json","satislar":"satislar.json"
    }
}

def deep_merge(default, override):
    """İç içe sözlükleri birleştirir (override önceliklidir)."""
    result = default.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result

def load_config():
    if os.path.exists(CONFIG_DOSYASI):
        try:
            with open(CONFIG_DOSYASI, "r", encoding="utf-8") as f:
                user_config = json.load(f)
            return deep_merge(VARSAYILAN_CONFIG, user_config)
        except Exception as e:
            logging.error(f"Config yüklenemedi, varsayılan kullanılıyor: {e}")
    return VARSAYILAN_CONFIG

config = load_config()
STOK_DOSYASI       = config["dosya_yollari"]["stok"]
FIRE_DOSYASI       = config["dosya_yollari"]["fire"]
HAREKET_DOSYASI    = config["dosya_yollari"]["hareket"]
BARKOD_DB_DOSYASI  = config["dosya_yollari"]["barkod_db"]
TEDARIKCI_DOSYASI  = config["dosya_yollari"]["tedarikciler"]
KULLANICI_DOSYASI  = config["dosya_yollari"]["kullanicilar"]
SATIS_DOSYASI      = config["dosya_yollari"]["satislar"]
KATEGORILER        = config.get("kategoriler")
BIRIMLER           = config.get("birimler")
ROLLER             = config.get("roller")
OTURUM_SURESI      = config.get("oturum_suresi_dk", 30)
SKT_UYARI_GUN      = config.get("skt_uyari_gun", 3)

# ---------- YARDIMCI FONKSİYONLAR ----------
def guvenli_html(metin: str) -> str:
    return (str(metin)
            .replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
            .replace('"',"&quot;").replace("'","&#x27;"))

def tema_degistir():
    st.session_state.tema = st.session_state.get("tema_secimi","Koyu")

def enerjik_css(tema):
    bg         = "#0B1121" if tema=="Koyu" else "#F8FAFC"
    card       = "#141B2D" if tema=="Koyu" else "#FFFFFF"
    text       = "#E2E8F0" if tema=="Koyu" else "#1E293B"
    header_bg  = "#141B2D" if tema=="Koyu" else "#F1F5F9"
    metric_bg  = ("linear-gradient(145deg, #1a1f35, #0f1424)" if tema=="Koyu"
                  else "linear-gradient(145deg, #E2E8F0, #CBD5E1)")
    input_bg   = "#141B2D" if tema=="Koyu" else "#FFFFFF"
    st.markdown(f"""
    <style>
        .stApp {{ background-color: {bg} !important; }}
        .main {{ color: {text}; }}
        header[data-testid="stHeader"] {{ background-color: {header_bg}; }}
        section[data-testid="stSidebar"] {{ background-color: {header_bg}; }}
        div[data-testid="stMetric"] {{
            background: {metric_bg}; border: 1px solid #94A3B8;
            border-radius: 20px; padding: 24px; color: {text};
            box-shadow: 0 10px 25px rgba(0,0,0,0.1);
        }}
        h1,h2,h3,h4,h5,p,span,label {{ color: {text}; }}
        .stButton > button {{
            border-radius: 14px; font-weight: 700;
            background: linear-gradient(135deg, #F97316, #8B5CF6);
            color: white; border: none; padding: 0.7rem 2rem;
        }}
        input,select,textarea {{
            background-color: {input_bg} !important; color: {text} !important;
            border: 1px solid #94A3B8 !important; border-radius: 10px !important;
        }}
        .main-header {{
            font-size: 2.3rem; font-weight: 800;
            background: linear-gradient(135deg, #F97316, #8B5CF6);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            margin-bottom: 1.5rem; padding-bottom: 0.5rem;
            border-bottom: 2px solid #F97316;
        }}
        @media (max-width: 768px) {{
            .main-header {{ font-size: 1.4rem !important; }}
            .stButton > button {{ width: 100% !important; }}
        }}
    </style>
    """, unsafe_allow_html=True)

def dosya_oku(dosya_adi, varsayilan=None):
    if os.path.exists(dosya_adi):
        try:
            with open(dosya_adi,"r",encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Dosya okuma hatası {dosya_adi}: {e}")
    return varsayilan if varsayilan is not None else []

def dosya_yaz(dosya_adi, veri):
    try:
        with open(dosya_adi,"w",encoding="utf-8") as f:
            json.dump(veri, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logging.error(f"Dosya yazma hatası {dosya_adi}: {e}")
        return False

# ---------- FONT YOLU (dinamik, güvenli) ----------
def get_font_path():
    possible = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "DejaVuSans.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/DejaVuSans.ttf",
        "/System/Library/Fonts/DejaVuSans.ttf",
        "/usr/local/share/fonts/DejaVuSans.ttf",
        "./DejaVuSans.ttf",
    ]
    for p in possible:
        if os.path.exists(p):
            return p
    logging.warning("DejaVuSans.ttf bulunamadi, Helvetica kullanilacak.")
    return None

def _pdf_bytes(pdf: FPDF) -> bytes:
    """FPDF sürümünden bağımsız bytes çıktısı."""
    try:
        return pdf.output(dest='S').encode('latin-1')
    except Exception:
        buf = BytesIO()
        pdf.output(buf)
        return buf.getvalue()

def _pdf_setup(pdf: FPDF, boyut=10):
    """Font ayarını merkezi yönet; font adını döndür."""
    font_path = get_font_path()
    if font_path:
        pdf.add_font("DejaVu", "", font_path, uni=True)
        pdf.set_font("DejaVu", size=boyut)
        return "DejaVu"
    else:
        pdf.set_font("Helvetica", size=boyut)
        return "Helvetica"

def fis_olustur(urun_adi, birim, miktar, birim_fiyat, toplam_tutar, odeme_tipi):
    pdf = FPDF()
    pdf.add_page()
    fn = _pdf_setup(pdf, 10)
    pdf.cell(80,10,txt="Market Yonetim Sistemi", ln=True, align='C')
    pdf.cell(80,10,txt="ALISVERIS FISI",         ln=True, align='C')
    pdf.ln(5)
    pdf.set_font(fn, size=8)
    pdf.cell(80,6,txt=f"Tarih: {datetime.now().strftime('%d.%m.%Y %H:%M')}", ln=True, align='C')
    pdf.ln(5)
    pdf.set_font(fn, size=10)
    pdf.cell(50,8,txt="Urun:");      pdf.cell(30,8,txt=str(urun_adi)[:20],          ln=True)
    pdf.cell(50,8,txt="Miktar:");    pdf.cell(30,8,txt=f"{miktar} {birim}",          ln=True)
    pdf.cell(50,8,txt="Birim Fiyat:"); pdf.cell(30,8,txt=f"{birim_fiyat:.2f} TL",  ln=True)
    pdf.ln(3)
    pdf.set_font(fn, size=12)
    pdf.cell(50,10,txt="TOPLAM:");   pdf.cell(30,10,txt=f"{toplam_tutar:.2f} TL",   ln=True)
    pdf.set_font(fn, size=8)
    pdf.cell(50,6,txt=f"Odeme: {odeme_tipi}", ln=True)
    pdf.ln(5)
    pdf.cell(80,6,txt="Iyi gunlerde kullanin!", ln=True, align='C')
    return _pdf_bytes(pdf)

# ---------- DİĞER TEMEL FONKSİYONLAR ----------
def veri_gecis_kontrol():
    degisti = False
    for u in st.session_state.stok:
        for k, v in [("kategori","Diğer"),("min_miktar",0),("barkod",""),
                     ("son_kullanma_tarihi",""),("alis_fiyat",0),("satis_fiyat",0),
                     ("tedarikci",""),("raf_no",""),("kdv_oran",8),("tahmini_gunluk_satis",1.0)]:
            if k not in u:
                u[k] = v; degisti = True
    for s in st.session_state.fire:
        if "adet" in s and "miktar" not in s:
            s["miktar"] = s.pop("adet"); degisti = True
        for k, v in [("miktar",0),("birim","adet"),("tedarikci",""),
                     ("durum","Bekliyor"),("eklenme_tarihi","")]:
            if k not in s:
                s[k] = v; degisti = True
    if degisti:
        veriyi_kaydet()

def mock_stok_olustur():
    return [
        {"urun_adi":"Un","miktar":150,"birim":"kg","kategori":"Kuru Gıda","min_miktar":20,
         "barkod":"8691234567890","son_kullanma_tarihi":"2026-12-31","alis_fiyat":18.5,
         "satis_fiyat":25.9,"tedarikci":"ABC Un","kdv_oran":1,"raf_no":"A1","tahmini_gunluk_satis":5.0},
        {"urun_adi":"Şeker","miktar":5,"birim":"kg","kategori":"Kuru Gıda","min_miktar":10,
         "barkod":"8691234567891","son_kullanma_tarihi":"2026-05-15","alis_fiyat":22,
         "satis_fiyat":32.5,"tedarikci":"XYZ Şeker","kdv_oran":8,"raf_no":"A2","tahmini_gunluk_satis":2.0},
        {"urun_adi":"Süt","miktar":40,"birim":"litre","kategori":"Süt Ürünleri","min_miktar":15,
         "barkod":"8691234567892","son_kullanma_tarihi":"2026-05-08","alis_fiyat":12,
         "satis_fiyat":18.9,"tedarikci":"Sütaş","kdv_oran":1,"raf_no":"B1","tahmini_gunluk_satis":8.0},
        {"urun_adi":"Yumurta","miktar":200,"birim":"adet","kategori":"Diğer","min_miktar":30,
         "barkod":"8691234567893","son_kullanma_tarihi":"2026-05-06","alis_fiyat":2.5,
         "satis_fiyat":4.5,"tedarikci":"Köy Yumurtası","kdv_oran":1,"raf_no":"C1","tahmini_gunluk_satis":30.0},
        {"urun_adi":"Tereyağı","miktar":25,"birim":"kg","kategori":"Süt Ürünleri","min_miktar":5,
         "barkod":"8691234567894","son_kullanma_tarihi":"2026-06-20","alis_fiyat":120,
         "satis_fiyat":175,"tedarikci":"Sütaş","kdv_oran":8,"raf_no":"B2","tahmini_gunluk_satis":3.0},
    ]

def mock_fire_olustur():
    return [
        {"urun_adi":"Un","miktar":10,"birim":"kg","aciliyet":"🔥 Yüksek","tedarikci":"ABC Un",
         "durum":"Bekliyor","eklenme_tarihi":datetime.now().strftime("%Y-%m-%d %H:%M")},
        {"urun_adi":"Şeker","miktar":5,"birim":"kg","aciliyet":"⚡ Orta","tedarikci":"XYZ Şeker",
         "durum":"Sipariş Verildi","eklenme_tarihi":datetime.now().strftime("%Y-%m-%d %H:%M")},
        {"urun_adi":"Yumurta","miktar":50,"birim":"adet","aciliyet":"✅ Düşük","tedarikci":"Köy Yumurtası",
         "durum":"Bekliyor","eklenme_tarihi":datetime.now().strftime("%Y-%m-%d %H:%M")},
    ]

def mock_barkod_db_olustur():
    return {
        "8691234567890":{"urun_adi":"Un","birim":"kg","kategori":"Kuru Gıda","uretici":"ABC Un"},
        "8691234567891":{"urun_adi":"Şeker","birim":"kg","kategori":"Kuru Gıda","uretici":"XYZ Şeker"},
        "8691234567892":{"urun_adi":"Süt","birim":"litre","kategori":"Süt Ürünleri","uretici":"Sütaş"},
        "8691234567893":{"urun_adi":"Yumurta","birim":"adet","kategori":"Diğer","uretici":"Köy Yumurtası"},
        "8691234567894":{"urun_adi":"Tereyağı","birim":"kg","kategori":"Süt Ürünleri","uretici":"Sütaş"},
    }

def hareket_ekle(kul, islem, ad, detay=""):
    h = {"tarih":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
         "kullanici":kul,"islem":islem,"urun_adi":ad,"detay":detay}
    liste = dosya_oku(HAREKET_DOSYASI, [])
    liste.append(h)
    if len(liste) > 1000:
        liste = liste[-1000:]
    dosya_yaz(HAREKET_DOSYASI, liste)

def satis_kaydet(ad, birim, miktar, fiyat, tutar, kul, alis_fiyat=0, odeme_tipi="Nakit"):
    s = {
        "id":str(uuid.uuid4())[:8],
        "tarih":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "kullanici":kul,"urun_adi":ad,"birim":birim,"miktar":miktar,
        "birim_fiyat":fiyat,"toplam_tutar":tutar,"alis_fiyat":alis_fiyat,
        "maliyet":round(miktar*alis_fiyat,2),"odeme_tipi":odeme_tipi
    }
    liste = dosya_oku(SATIS_DOSYASI, [])
    liste.append(s)
    dosya_yaz(SATIS_DOSYASI, liste)

def gunluk_kar():
    liste = dosya_oku(SATIS_DOSYASI, [])
    bugun = datetime.now().strftime("%Y-%m-%d")
    toplam_satis    = sum(s["toplam_tutar"] for s in liste if s["tarih"].startswith(bugun))
    toplam_maliyet  = sum(s.get("maliyet", s["miktar"]*s.get("alis_fiyat",0))
                          for s in liste if s["tarih"].startswith(bugun))
    return round(toplam_satis - toplam_maliyet, 2)

def gunluk_ciro(tarih=None):
    if tarih is None: tarih = datetime.now().strftime("%Y-%m-%d")
    liste = dosya_oku(SATIS_DOSYASI, [])
    return sum(s["toplam_tutar"] for s in liste if s["tarih"].startswith(tarih))

def haftalik_ciro(baslangic=None):
    if baslangic is None:
        baslangic = datetime.now().date() - timedelta(days=datetime.now().weekday())
    bitis = baslangic + timedelta(days=6)
    liste = dosya_oku(SATIS_DOSYASI, [])
    toplam = 0
    for s in liste:
        try:
            tarih = datetime.strptime(s["tarih"],"%Y-%m-%d %H:%M:%S").date()
            if baslangic <= tarih <= bitis: toplam += s["toplam_tutar"]
        except: pass
    return toplam

def aylik_ciro(yil=None, ay=None):
    if yil is None: yil = datetime.now().year
    if ay  is None: ay  = datetime.now().month
    liste = dosya_oku(SATIS_DOSYASI, [])
    toplam = 0
    for s in liste:
        try:
            tarih = datetime.strptime(s["tarih"],"%Y-%m-%d %H:%M:%S")
            if tarih.year == yil and tarih.month == ay: toplam += s["toplam_tutar"]
        except: pass
    return toplam

def en_cok_satanlar(n=5, gun=7):
    satislar = dosya_oku(SATIS_DOSYASI, [])
    if not satislar: return []
    df = pd.DataFrame(satislar)
    df["tarih"] = pd.to_datetime(df["tarih"])
    baslangic = datetime.now() - timedelta(days=gun)
    df = df[df["tarih"] >= baslangic]
    if df.empty: return []
    populer = df.groupby("urun_adi")["miktar"].sum().sort_values(ascending=False).head(n)
    return populer.index.tolist()

def whatsapp_gonder(telefon_no, mesaj):
    if not WHATSAPP_AKTIF: return False
    try:
        suan = datetime.now()
        saat = suan.hour; dakika = suan.minute + 2
        if dakika >= 60: saat += 1; dakika -= 60
        pwk.sendwhatmsg(telefon_no, mesaj, saat, dakika, wait_time=15, tab_close=True)
        return True
    except Exception as e:
        logging.error(f"WhatsApp hatası: {e}"); return False

def email_gonder(alici, konu, mesaj):
    try:
        smtp = "smtp.gmail.com"; port = 587
        gonderen = st.secrets["email"]["adres"]
        sifre    = st.secrets["email"]["sifre"]
        msg = MIMEText(mesaj)
        msg["Subject"] = konu; msg["From"] = gonderen; msg["To"] = alici
        baglanti = smtplib.SMTP(smtp, port)
        baglanti.starttls(context=ssl.create_default_context())
        baglanti.login(gonderen, sifre)
        baglanti.sendmail(gonderen, alici, msg.as_string())
        baglanti.quit()
        return True
    except Exception as e:
        logging.error(f"E-posta hatası: {e}"); return False

def email_gonder_pdf(alici, konu, mesaj, pdf_bytes, dosya_adi):
    try:
        smtp = "smtp.gmail.com"; port = 587
        gonderen = st.secrets["email"]["adres"]
        sifre    = st.secrets["email"]["sifre"]
        msg = MIMEMultipart()
        msg["Subject"] = konu; msg["From"] = gonderen; msg["To"] = alici
        msg.attach(MIMEText(mesaj))
        part = MIMEBase("application","octet-stream")
        part.set_payload(pdf_bytes)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename={dosya_adi}")
        msg.attach(part)
        baglanti = smtplib.SMTP(smtp, port)
        baglanti.starttls(context=ssl.create_default_context())
        baglanti.login(gonderen, sifre)
        baglanti.sendmail(gonderen, alici, msg.as_string())
        baglanti.quit()
        return True
    except Exception as e:
        logging.error(f"PDF e-posta hatası: {e}"); return False

def tedarikciye_siparis_gonder(urun, tedarikci_eposta):
    if not tedarikci_eposta: return False
    konu  = f"Otomatik Siparis: {urun['urun_adi']} kritik stokta"
    mesaj = (f"Sayin {urun.get('tedarikci','Tedarikci')},\n\n"
             f"{urun['urun_adi']} urunun stoku kritik seviyeye dusmustür.\n"
             f"Mevcut stok: {urun['miktar']} {urun['birim']}\n"
             f"Minimum stok: {urun.get('min_miktar',0)} {urun['birim']}\n"
             f"Onerilen siparis: {urun.get('min_miktar',10)-urun['miktar']+5} {urun['birim']}\n\n"
             f"Lutfen en kisa surede tedarik saglayin.\n\nMarket Yonetim Sistemi")
    return email_gonder(tedarikci_eposta, konu, mesaj)

def urun_gunluk_satis_hizi(urun_adi, varsayilan=1.0):
    satislar = dosya_oku(SATIS_DOSYASI, [])
    if not satislar:
        for u in st.session_state.stok:
            if u["urun_adi"] == urun_adi: return u.get("tahmini_gunluk_satis", varsayilan)
        return varsayilan
    bugun     = datetime.now().date()
    baslangic = bugun - timedelta(days=30)
    miktarlar = []
    for s in satislar:
        try:
            tarih = datetime.strptime(s["tarih"],"%Y-%m-%d %H:%M:%S").date()
            if s["urun_adi"] == urun_adi and baslangic <= tarih <= bugun:
                miktarlar.append(s["miktar"])
        except: continue
    if not miktarlar:
        for u in st.session_state.stok:
            if u["urun_adi"] == urun_adi: return u.get("tahmini_gunluk_satis", varsayilan)
        return varsayilan
    return sum(miktarlar)/len(miktarlar)

def bilimsel_indirim_hesapla(urun, kalan_gun):
    if kalan_gun <= 0:
        satis = urun.get("satis_fiyat",10); alis = urun.get("alis_fiyat",5)
        if satis > 0: return min(50, int((satis-alis)/satis*100))
        return 50
    q = urun.get("miktar",0)
    satis_fiyat = urun.get("satis_fiyat",0)
    alis_fiyat  = urun.get("alis_fiyat",0)
    if satis_fiyat <= 0 or q <= 0: return 0
    m = (satis_fiyat - alis_fiyat) / satis_fiyat
    v = urun_gunluk_satis_hizi(urun["urun_adi"], urun.get("tahmini_gunluk_satis",1.0))
    beklenen    = v * kalan_gun
    stok_fazlasi = q - beklenen
    if stok_fazlasi <= 0: return 0
    indirim     = (stok_fazlasi/q) * m * 100
    max_indirim = m*100*0.8
    indirim     = min(indirim, max_indirim)
    if kalan_gun <= 1: indirim = max(indirim, m*100*0.5)
    elif kalan_gun <= 3: indirim = max(indirim, m*100*0.2)
    return round(indirim, 1)

def otomatik_yedekleme_kontrol():
    if not st.session_state.get("authenticated", False): return
    patron_email = st.session_state.get("patron_email","")
    if not patron_email: return
    son_dosya = "son_yedekleme.txt"
    gonder = False
    if os.path.exists(son_dosya):
        try:
            with open(son_dosya,"r") as f:
                son = datetime.fromisoformat(f.read().strip())
                if datetime.now() - son > timedelta(hours=24): gonder = True
        except: gonder = True
    else:
        gonder = True
    if gonder:
        yedek = {"stok":st.session_state.stok,"fire":st.session_state.fire,
                 "barkod_db":st.session_state.barkod_db,"tedarikciler":st.session_state.tedarikciler,
                 "tarih":datetime.now().isoformat()}
        json_bytes = json.dumps(yedek, ensure_ascii=False, indent=2).encode("utf-8")
        if email_gonder_pdf(patron_email,"Otomatik Günlük Yedek","Yedek ektedir.", json_bytes,"yedek_otomatik.json"):
            with open(son_dosya,"w") as f: f.write(datetime.now().isoformat())
            logging.info("Otomatik yedekleme gönderildi")

# ---------- OTURUM YÖNETİMİ ----------
def oturumu_baslat():
    if "stok" not in st.session_state:
        st.session_state.stok = dosya_oku(STOK_DOSYASI, mock_stok_olustur())
    if "fire" not in st.session_state:
        st.session_state.fire = dosya_oku(FIRE_DOSYASI, mock_fire_olustur())
    if "barkod_db" not in st.session_state:
        db = dosya_oku(BARKOD_DB_DOSYASI, None)
        if db is None: db = mock_barkod_db_olustur(); dosya_yaz(BARKOD_DB_DOSYASI, db)
        st.session_state.barkod_db = db
    if "tedarikciler" not in st.session_state:
        st.session_state.tedarikciler = dosya_oku(TEDARIKCI_DOSYASI, [])
    if "kullanicilar" not in st.session_state:
        st.session_state.kullanicilar = dosya_oku(
            KULLANICI_DOSYASI,
            [{"kullanici_adi":"admin","sifre":hashlib.sha256("1234".encode()).hexdigest(),"rol":"patron","ad":"Ahmet"}]
        )
    if "pos_sepet"          not in st.session_state: st.session_state.pos_sepet = {}
    if "son_islem_mesaji"   not in st.session_state: st.session_state.son_islem_mesaji = ""
    if "authenticated"      not in st.session_state: st.session_state.authenticated = False
    if "current_user"       not in st.session_state: st.session_state.current_user = None
    if "last_activity"      not in st.session_state: st.session_state.last_activity = datetime.now()
    if "tema"               not in st.session_state: st.session_state.tema = "Koyu"
    if "patron_email"       not in st.session_state: st.session_state.patron_email = ""
    if "patron_telefon"     not in st.session_state: st.session_state.patron_telefon = ""
    # Tedarikçi düzenleme state'i
    if "duzenlenecek_tedarikci" not in st.session_state:
        st.session_state.duzenlenecek_tedarikci = None
    veri_gecis_kontrol()
    otomatik_yedekleme_kontrol()

def oturum_kontrol():
    if st.session_state.authenticated:
        if datetime.now() - st.session_state.last_activity > timedelta(minutes=OTURUM_SURESI):
            st.session_state.authenticated = False
            st.sidebar.error("⏳ Oturum süreniz doldu!")
            st.rerun()
        else:
            st.session_state.last_activity = datetime.now()

def giris_ekrani():
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown(
            '<h1 style="text-align:center; background:linear-gradient(135deg,#F97316,#8B5CF6);'
            '-webkit-background-clip:text; -webkit-text-fill-color:transparent;">'
            '🏪 Market Yönetim</h1>',
            unsafe_allow_html=True
        )
        with st.form("giris"):
            kullanici = st.text_input("👤 Kullanıcı Adı")
            sifre     = st.text_input("🔒 Şifre", type="password")
            if st.form_submit_button("🚀 Giriş Yap", use_container_width=True):
                try:
                    admin_user = st.secrets["admin"]["kullanici_adi"]
                    admin_pass = st.secrets["admin"]["sifre"]
                except:
                    admin_user = config.get("kullanici_adi","admin")
                    admin_pass = config.get("sifre","1234")
                if kullanici == admin_user and sifre == admin_pass:
                    st.session_state.authenticated = True
                    st.session_state.current_user  = {"kullanici_adi":admin_user,"rol":"patron","ad":"Admin"}
                    st.session_state.last_activity  = datetime.now()
                    st.rerun()
                else:
                    st.error("❌ Hatalı giriş!")

def cikis():
    st.session_state.authenticated = False
    st.rerun()

def izinli_sayfalar(kullanici):
    if not kullanici: return {}
    rol     = kullanici.get("rol","")
    izinler = ROLLER.get(rol,[])
    if "tümü" in izinler: return SAYFALAR
    yetki_sayfa = {
        "barkod":    ["📱 Barkod","🏷️ Barkod Yönetimi"],
        "satis":     ["💵 Satış"],
        "stok":      ["📦 Stok","📈 Stok Analizi","📉 Fire Analizi"],
        "stok_ekle": ["📦 Stok","🔥 Sipariş"],
        "skt_takip": ["🏠 Ana Panel"],
    }
    return {k:v for k,v in SAYFALAR.items()
            if any(k in yetki_sayfa.get(yetki,[]) for yetki in izinler)}

# ============================================================
# SAYFALAR
# ============================================================

def ana_sayfa():
    st.markdown('<div class="main-header">📊 Yönetim Paneli</div>', unsafe_allow_html=True)
    kritik = [u for u in st.session_state.stok
              if u.get("min_miktar",0) > 0 and u["miktar"] <= u["min_miktar"]]
    if kritik:
        st.balloons()
        st.error(f"🚨 {len(kritik)} ürün kritik stok seviyesinde!")

    bugun    = datetime.now()
    bugunku  = gunluk_ciro(bugun.strftime("%Y-%m-%d"))
    dun      = gunluk_ciro((bugun-timedelta(days=1)).strftime("%Y-%m-%d"))
    delta_gun = bugunku - dun
    kar       = gunluk_kar()
    bu_hafta  = haftalik_ciro()
    gecen_hafta = haftalik_ciro((bugun - timedelta(days=7)).date())
    delta_hafta = bu_hafta - gecen_hafta
    bu_ay    = aylik_ciro()
    gecen_ay_tarih = bugun.replace(day=1) - timedelta(days=1)
    gecen_ay = aylik_ciro(gecen_ay_tarih.year, gecen_ay_tarih.month)
    delta_ay = bu_ay - gecen_ay

    c1,c2,c3,c4,c5,c6 = st.columns(6)
    c1.metric("Bugünkü Ciro",  f"{bugunku:,.0f} TL",  delta=f"{delta_gun:+,.0f} TL")
    c2.metric("Bugünkü Kâr",   f"{kar:,.0f} TL")
    c3.metric("Dünkü Ciro",    f"{dun:,.0f} TL")
    c4.metric("Bu Hafta",      f"{bu_hafta:,.0f} TL", delta=f"{delta_hafta:+,.0f} TL")
    c5.metric("Bu Ay",         f"{bu_ay:,.0f} TL",    delta=f"{delta_ay:+,.0f} TL")
    buyume = 0 if gecen_hafta == 0 else (delta_hafta/gecen_hafta*100)
    c6.metric("Haftalık Büyüme", f"%{buyume:.1f}")


def barkod_yonetimi():
    st.markdown('<div class="main-header">🏷️ Barkod Yönetimi</div>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["📋 Barkod Listesi","➕ Yeni Barkod Ekle"])
    with tab1:
        if st.session_state.barkod_db:
            arama = st.text_input("🔍 Ara")
            df = pd.DataFrame([{"barkod":k,**v} for k,v in st.session_state.barkod_db.items()])
            if arama:
                df = df[df["barkod"].str.contains(arama,case=False,na=False) |
                        df["urun_adi"].str.contains(arama,case=False,na=False)]
            st.dataframe(df, use_container_width=True)
            for _, row in df.iterrows():
                bk = row["barkod"]
                with st.expander(f"🔧 {row['urun_adi']} ({bk})"):
                    col1, col2 = st.columns(2)
                    with col1:
                        yeni_ad    = st.text_input("Ürün Adı",  row["urun_adi"],  key=f"ad_{bk}")
                        yeni_birim = st.selectbox("Birim", BIRIMLER,
                                        index=BIRIMLER.index(row["birim"]) if row["birim"] in BIRIMLER else 0,
                                        key=f"birim_{bk}")
                        yeni_kat   = st.selectbox("Kategori", KATEGORILER,
                                        index=KATEGORILER.index(row["kategori"]) if row["kategori"] in KATEGORILER else 0,
                                        key=f"kat_{bk}")
                        yeni_uret  = st.text_input("Üretici", row.get("uretici",""), key=f"uret_{bk}")
                    with col2:
                        if st.button("💾 Güncelle", key=f"guncelle_{bk}"):
                            st.session_state.barkod_db[bk].update(
                                {"urun_adi":yeni_ad,"birim":yeni_birim,"kategori":yeni_kat,"uretici":yeni_uret})
                            dosya_yaz(BARKOD_DB_DOSYASI, st.session_state.barkod_db)
                            st.session_state.son_islem_mesaji = f"✅ Barkod {bk} güncellendi"; st.rerun()
                        if st.button("🗑️ Sil", key=f"sil_{bk}"):
                            if any(u.get("barkod") == bk for u in st.session_state.stok):
                                st.error("Bu barkod stokta kullanılıyor, önce ürünü silin.")
                            else:
                                del st.session_state.barkod_db[bk]
                                dosya_yaz(BARKOD_DB_DOSYASI, st.session_state.barkod_db)
                                st.session_state.son_islem_mesaji = f"✅ Barkod {bk} silindi"; st.rerun()
        else:
            st.info("Barkod veritabanı boş.")
    with tab2:
        with st.form("yeni_barkod"):
            yeni_barkod = st.text_input("Barkod Numarası")
            yeni_ad     = st.text_input("Ürün Adı")
            yeni_birim  = st.selectbox("Birim", BIRIMLER)
            yeni_kat    = st.selectbox("Kategori", KATEGORILER)
            if st.form_submit_button("Ekle"):
                if not yeni_barkod or not yeni_ad:
                    st.error("Barkod ve ürün adı zorunlu")
                elif yeni_barkod in st.session_state.barkod_db:
                    st.error("Barkod zaten var")
                else:
                    st.session_state.barkod_db[yeni_barkod] = {
                        "urun_adi":yeni_ad,"birim":yeni_birim,"kategori":yeni_kat,"uretici":""}
                    dosya_yaz(BARKOD_DB_DOSYASI, st.session_state.barkod_db)
                    st.session_state.son_islem_mesaji = f"✅ Barkod {yeni_barkod} eklendi"; st.rerun()


def barkod_sayfasi():
    st.markdown('<div class="main-header">📱 Barkod Okutma</div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        barkod_manuel = st.text_input("🔢 Barkod Numarası", placeholder="Okutun veya yazın...", key="manuel_barkod")
    with col2:
        img_file = st.camera_input("📷 Mobil Kamera")
    barkod = None
    if img_file:
        try:
            import cv2, numpy as np
            img = cv2.imdecode(np.asarray(bytearray(img_file.read()), dtype=np.uint8), cv2.IMREAD_COLOR)
            detector = cv2.QRCodeDetector()
            data, _, _ = detector.detectAndDecode(img)
            if data: barkod = data; st.success(f"✅ Okunan: {barkod}")
            else: st.warning("Barkod algılanamadı.")
        except Exception as e:
            st.error(f"Kamera hatası: {e}")
    aktif = barkod_manuel or barkod
    if aktif:
        bilgi     = st.session_state.barkod_db.get(aktif, {})
        urun_adi  = bilgi.get("urun_adi","")
        if urun_adi:
            st.info(f"📦 **{guvenli_html(urun_adi)}** ({bilgi.get('birim','')})")
        else:
            st.warning("❓ Yeni barkod.")
        with st.form("barkod_form"):
            ad       = st.text_input("Ürün Adı *", value=urun_adi)
            miktar   = st.number_input("Miktar", 0.01, format="%.2f", value=1.0)
            birim    = st.selectbox("Birim", BIRIMLER,
                            index=BIRIMLER.index(bilgi.get("birim","adet")) if bilgi.get("birim") in BIRIMLER else 0)
            kategori = st.selectbox("Kategori", KATEGORILER,
                            index=KATEGORILER.index(bilgi.get("kategori","Diğer")) if bilgi.get("kategori") in KATEGORILER else 0)
            skt_var  = st.checkbox("Son kullanma tarihi var mı?", value=True)
            skt      = st.date_input("SKT") if skt_var else ""
            islem    = st.radio("İşlem", ["📥 Giriş","📤 Çıkış"], horizontal=True)
            if st.form_submit_button("💾 Kaydet"):
                if not ad.strip():
                    st.error("Ad zorunlu")
                else:
                    if aktif not in st.session_state.barkod_db:
                        st.session_state.barkod_db[aktif] = {"urun_adi":ad.strip(),"birim":birim,"kategori":kategori}
                        dosya_yaz(BARKOD_DB_DOSYASI, st.session_state.barkod_db)
                    gercek  = miktar if islem == "📥 Giriş" else -miktar
                    skt_str = skt.strftime("%Y-%m-%d") if skt_var else ""
                    for u in st.session_state.stok:
                        if u.get("barkod") == aktif:
                            u["miktar"] += gercek
                            if skt_var: u["son_kullanma_tarihi"] = skt_str
                            veriyi_kaydet()
                            st.session_state.son_islem_mesaji = f"✅ {ad.strip()} güncellendi"; st.rerun()
                    st.session_state.stok.append({
                        "urun_adi":ad.strip(),"miktar":max(0,gercek),"birim":birim,"kategori":kategori,
                        "son_kullanma_tarihi":skt_str,"barkod":aktif,"min_miktar":0,
                        "alis_fiyat":0,"satis_fiyat":0})
                    veriyi_kaydet()
                    st.session_state.son_islem_mesaji = f"✅ {ad.strip()} eklendi"; st.rerun()


def satis_sayfasi():
    st.markdown('<div class="main-header">💰 Satış (POS)</div>', unsafe_allow_html=True)
    if st.button("🚀 Hızlı POS Moduna Geç"):
        st.session_state.pos_modu  = True
        st.session_state.pos_sepet = {}
        st.rerun()
    satilabilir = [u for u in st.session_state.stok if u["miktar"] > 0]
    if not satilabilir:
        st.warning("Satılacak ürün yok"); return

    populer = en_cok_satanlar(5,7)
    if populer:
        st.subheader("⚡ Son 7 Günün En Çok Satanları")
        cols = st.columns(len(populer))
        for i, ad in enumerate(populer):
            urun = next((u for u in satilabilir if u["urun_adi"] == ad), None)
            if urun:
                with cols[i]:
                    if st.button(f"🛒 {urun['urun_adi']}\n1 {urun['birim']}", key=f"hizli_{ad}"):
                        urun["miktar"] -= 1
                        satis_kaydet(urun["urun_adi"], urun["birim"], 1,
                                     urun.get("satis_fiyat",0), urun.get("satis_fiyat",0),
                                     st.session_state.current_user["kullanici_adi"],
                                     urun.get("alis_fiyat",0), "Nakit")
                        veriyi_kaydet()
                        st.session_state.son_islem_mesaji = f"✅ Hızlı satış: {urun['urun_adi']}"; st.rerun()

    secili_str = st.selectbox(
        "Ürün Seçin",
        [f"{guvenli_html(u['urun_adi'])} ({u['miktar']:.2f} {u['birim']} - {u.get('satis_fiyat',0):.2f} TL)"
         for u in satilabilir])
    idx  = [f"{u['urun_adi']} ({u['miktar']:.2f} {u['birim']} - {u.get('satis_fiyat',0):.2f} TL)"
            for u in satilabilir].index(secili_str)
    urun  = satilabilir[idx]
    fiyat = urun.get("satis_fiyat",0)
    mevcut= urun["miktar"]
    miktar= st.number_input("Miktar", 0.01, float(mevcut), format="%.2f", value=1.0)
    toplam= miktar * fiyat
    odeme_tipi = st.selectbox("💳 Ödeme Tipi",["Nakit","Kredi Kartı","Havale/EFT","Yemek Kartı"])
    st.markdown(f"### 🧾 Toplam: {toplam:.2f} TL")
    if st.button("💳 Satış Yap", type="primary", use_container_width=True):
        if miktar <= 0 or miktar > mevcut:
            st.error("Geçersiz miktar")
        else:
            for u in st.session_state.stok:
                if u["urun_adi"] == urun["urun_adi"] and u.get("barkod") == urun.get("barkod"):
                    u["miktar"] -= miktar
                    if u["miktar"] <= u.get("min_miktar",0) and u.get("min_miktar",0) > 0:
                        if not any(f["urun_adi"] == u["urun_adi"] and f["durum"] == "Bekliyor"
                                   for f in st.session_state.fire):
                            st.session_state.fire.append({
                                "urun_adi":u["urun_adi"], "miktar":u["min_miktar"]-u["miktar"]+2,
                                "birim":u["birim"], "aciliyet":"🔥 Yüksek",
                                "tedarikci":u.get("tedarikci",""), "durum":"Bekliyor",
                                "eklenme_tarihi":datetime.now().strftime("%Y-%m-%d %H:%M")})
                    break
            satis_kaydet(urun["urun_adi"], urun["birim"], miktar, fiyat, toplam,
                         st.session_state.current_user["kullanici_adi"], urun.get("alis_fiyat",0), odeme_tipi)
            hareket_ekle(st.session_state.current_user["kullanici_adi"], "Satış", urun["urun_adi"],
                         f"{miktar} {urun['birim']} satıldı, tutar: {toplam:.2f} TL")
            veriyi_kaydet()
            pdf_bytes = fis_olustur(urun["urun_adi"], urun["birim"], miktar, fiyat, toplam, odeme_tipi)
            st.download_button("🧾 Fişi İndir (PDF)", pdf_bytes, "fis.pdf", mime="application/pdf")
            st.session_state.son_islem_mesaji = f"✅ Satış: {toplam:.2f} TL"; st.rerun()


def pos_modu():
    st.markdown('<div class="main-header">🛒 Hızlı Satış (POS Modu)</div>', unsafe_allow_html=True)
    if "pos_sepet" not in st.session_state: st.session_state.pos_sepet = {}
    col1, col2 = st.columns(2)
    with col1: barkod = st.text_input("Barkod", key="pos_barkod")
    with col2: st.camera_input("Barkod okut", key="pos_kamera")
    if barkod:
        if barkod in st.session_state.pos_sepet: st.session_state.pos_sepet[barkod] += 1
        else: st.session_state.pos_sepet[barkod] = 1
        st.rerun()
    if st.session_state.pos_sepet:
        toplam_tutar = 0
        for bk, adet in st.session_state.pos_sepet.items():
            urun = next((u for u in st.session_state.stok if u.get("barkod") == bk), None)
            if urun:
                fiyat  = urun.get("satis_fiyat",0)
                tutar  = fiyat * adet
                toplam_tutar += tutar
                col1,col2,col3 = st.columns([3,1,1])
                col1.write(f"📦 {urun['urun_adi']} – {adet} x {fiyat:.2f} = {tutar:.2f} TL")
                col2.number_input("Adet",1,value=adet,key=f"adet_{bk}",
                    on_change=lambda b=bk: st.session_state.pos_sepet.update({b: st.session_state[f"adet_{b}"]}))
                if col3.button("🗑️", key=f"sil_{bk}"):
                    del st.session_state.pos_sepet[bk]; st.rerun()
        st.markdown(f"### Toplam: {toplam_tutar:.2f} TL")
        if st.button("Satışı Tamamla"):
            for bk, adet in st.session_state.pos_sepet.items():
                urun = next((u for u in st.session_state.stok if u.get("barkod") == bk), None)
                if urun and urun["miktar"] >= adet:
                    urun["miktar"] -= adet
                    satis_kaydet(urun["urun_adi"], urun["birim"], adet,
                                 urun.get("satis_fiyat",0), adet*urun.get("satis_fiyat",0),
                                 st.session_state.current_user["kullanici_adi"],
                                 urun.get("alis_fiyat",0), "Nakit")
                    if urun["miktar"] <= urun.get("min_miktar",0):
                        st.session_state.fire.append({
                            "urun_adi":urun["urun_adi"],"miktar":urun["min_miktar"]-urun["miktar"]+1,
                            "birim":urun["birim"],"aciliyet":"🔥 Yüksek",
                            "tedarikci":urun.get("tedarikci",""),"durum":"Bekliyor",
                            "eklenme_tarihi":datetime.now().strftime("%Y-%m-%d %H:%M")})
            veriyi_kaydet()
            pdf_bytes = fis_olustur("POS Satış","",0,0,toplam_tutar,"Nakit")
            st.download_button("🧾 Fiş İndir", pdf_bytes, "fis.pdf", mime="application/pdf")
            st.session_state.pos_sepet = {}
            st.success(f"Satış tamamlandı! Toplam: {toplam_tutar:.2f} TL"); st.rerun()
    if st.button("POS Modundan Çık"):
        st.session_state.pos_modu = False; st.rerun()


def stok_sayfasi():
    st.markdown('<div class="main-header">📦 Stok Yönetimi</div>', unsafe_allow_html=True)
    tab1,tab2,tab3,tab4,tab5 = st.tabs(["📋 Liste","➕ Ekle","✏️ Düzenle/Sil","🔢 Stok Sayım","📥 Toplu Güncelle"])
    with tab1:
        df = pd.DataFrame(st.session_state.stok)
        if not df.empty: st.dataframe(df, use_container_width=True)
        else: st.info("Ürün yok.")
    with tab2:
        with st.form("manuel_ekle"):
            barkod   = st.text_input("Barkod")
            bilgi    = st.session_state.barkod_db.get(barkod, {})
            ad       = st.text_input("Ürün Adı *", value=bilgi.get("urun_adi",""))
            miktar   = st.number_input("Miktar", 0.0, format="%.2f")
            birim    = st.selectbox("Birim", BIRIMLER,
                            index=BIRIMLER.index(bilgi.get("birim","adet")) if bilgi.get("birim") in BIRIMLER else 0)
            kategori = st.selectbox("Kategori", KATEGORILER,
                            index=KATEGORILER.index(bilgi.get("kategori","Diğer")) if bilgi.get("kategori") in KATEGORILER else 0)
            alis     = st.number_input("Alış Fiyatı",  0.0, format="%.2f")
            satis    = st.number_input("Satış Fiyatı", 0.0, format="%.2f")
            min_m    = st.number_input("Min Stok", 0.0, format="%.2f", value=5.0)
            skt_var  = st.checkbox("SKT var")
            skt      = st.date_input("SKT") if skt_var else ""
            if st.form_submit_button("Kaydet"):
                if not ad.strip():
                    st.error("Ad zorunlu")
                else:
                    if barkod and barkod not in st.session_state.barkod_db:
                        st.session_state.barkod_db[barkod] = {"urun_adi":ad.strip(),"birim":birim,"kategori":kategori}
                        dosya_yaz(BARKOD_DB_DOSYASI, st.session_state.barkod_db)
                    st.session_state.stok.append({
                        "urun_adi":ad.strip(),"miktar":miktar,"birim":birim,"kategori":kategori,
                        "min_miktar":min_m,"barkod":barkod,
                        "son_kullanma_tarihi":skt.strftime("%Y-%m-%d") if skt_var else "",
                        "alis_fiyat":alis,"satis_fiyat":satis,"raf_no":"","tahmini_gunluk_satis":1.0})
                    veriyi_kaydet()
                    st.session_state.son_islem_mesaji = f"🎉 {ad.strip()} eklendi!"; st.rerun()
    with tab3:
        if st.session_state.stok:
            urunler = [f"{u['urun_adi']} ({u['miktar']:.2f} {u['birim']})" for u in st.session_state.stok]
            secili  = st.selectbox("Ürün Seç", urunler, key="duzenle_sec")
            idx     = urunler.index(secili)
            urun    = st.session_state.stok[idx]
            with st.form("duzenle_form"):
                yeni_ad     = st.text_input("Ürün Adı", urun["urun_adi"])
                yeni_miktar = st.number_input("Miktar", value=float(urun["miktar"]), format="%.2f")
                yeni_birim  = st.selectbox("Birim", BIRIMLER,
                                index=BIRIMLER.index(urun.get("birim","adet")) if urun.get("birim") in BIRIMLER else 0)
                yeni_kat    = st.selectbox("Kategori", KATEGORILER,
                                index=KATEGORILER.index(urun.get("kategori","Diğer")) if urun.get("kategori") in KATEGORILER else 0)
                yeni_alis   = st.number_input("Alış Fiyatı",  value=float(urun.get("alis_fiyat",0)),  format="%.2f")
                yeni_satis  = st.number_input("Satış Fiyatı", value=float(urun.get("satis_fiyat",0)), format="%.2f")
                yeni_min    = st.number_input("Min Stok",     value=float(urun.get("min_miktar",0)),   format="%.2f")
                if st.form_submit_button("Güncelle"):
                    urun.update({"urun_adi":yeni_ad,"miktar":yeni_miktar,"birim":yeni_birim,
                                 "kategori":yeni_kat,"alis_fiyat":yeni_alis,"satis_fiyat":yeni_satis,"min_miktar":yeni_min})
                    veriyi_kaydet()
                    st.session_state.son_islem_mesaji = f"✅ {yeni_ad} güncellendi"; st.rerun()
            if st.button("🗑️ Sil", key="sil_urun"):
                st.session_state.stok.pop(idx)
                veriyi_kaydet(); st.session_state.son_islem_mesaji = "Ürün silindi"; st.rerun()
        else:
            st.info("Ürün yok.")
    with tab4:
        st.subheader("Stok Sayım")
        sayim_barkod = st.text_input("Barkod okut")
        if sayim_barkod:
            urun = next((u for u in st.session_state.stok if u.get("barkod") == sayim_barkod), None)
            if urun:
                st.success(f"{urun['urun_adi']} bulundu (Mevcut: {urun['miktar']} {urun['birim']})")
                yeni = st.number_input("Gerçek Miktar", value=float(urun['miktar']), format="%.2f")
                if st.button("Sayımı Kaydet"):
                    fark = yeni - urun['miktar']
                    urun['miktar'] = yeni
                    veriyi_kaydet()
                    hareket_ekle(st.session_state.current_user["kullanici_adi"],
                                 "Sayım Düzeltme", urun['urun_adi'], f"Fark: {fark:+.2f}")
                    st.session_state.son_islem_mesaji = f"✅ {urun['urun_adi']} sayımı kaydedildi"; st.rerun()
            else:
                st.warning("Barkod stokta yok.")
    with tab5:
        st.subheader("Toplu CSV Güncelleme (barkod,miktar)")
        csv = st.file_uploader("CSV yükle", type=["csv"])
        if csv:
            try:
                df = pd.read_csv(csv, header=None, names=["barkod","miktar"])
                for _, row in df.iterrows():
                    for u in st.session_state.stok:
                        if u.get("barkod") == str(row["barkod"]).strip():
                            u["miktar"] += float(row["miktar"]); break
                veriyi_kaydet()
                st.session_state.son_islem_mesaji = f"✅ {len(df)} ürün güncellendi"; st.rerun()
            except Exception as e:
                st.error(f"Hata: {e}")


# ============================================================
# TEDARİKÇİ YÖNETİMİ — DÜZELTİLMİŞ VERSİYON
# ============================================================
def tedarikci_sayfasi():
    st.markdown('<div class="main-header">🏭 Tedarikçi Yönetimi</div>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["📋 Liste", "➕ Ekle/Düzenle"])
    
    with tab1:
        if st.session_state.tedarikciler:
            for i, t in enumerate(st.session_state.tedarikciler):
                col1, col2, col3 = st.columns([4, 1, 1])
                with col1:
                    st.markdown(f"**{guvenli_html(t['ad'])}** – Güven: {t.get('guven_puani', 0):.1f} – Tel: {t.get('tel', '')} – E-posta: {t.get('eposta', '')}")
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
        duzenlenecek_idx = st.session_state.get("duzenlenecek_tedarikci", None)
        if duzenlenecek_idx is not None:
            t = st.session_state.tedarikciler[duzenlenecek_idx]
            st.info(f"✏️ **{t['ad']}** düzenleniyor")
            if st.button("❌ Düzenlemeyi İptal Et"):
                st.session_state.duzenlenecek_tedarikci = None
                st.rerun()
        else:
            t = {"ad": "", "guven_puani": 5.0, "tel": "", "eposta": ""}
        
        with st.form("tedarikci_form"):
            ad = st.text_input("Firma Adı *", value=t["ad"])
            guven = st.slider("Güven Puanı (0-10)", 0.0, 10.0, t["guven_puani"], 0.1)
            tel = st.text_input("Telefon (10 haneli, sadece rakam)", value=t["tel"])
            eposta = st.text_input("E-posta", value=t["eposta"])
            
            btn_label = "💾 Güncelle" if duzenlenecek_idx is not None else "➕ Ekle"
            if st.form_submit_button(btn_label, use_container_width=True):
                hata = False
                if not ad.strip():
                    st.error("Firma adı zorunludur.")
                    hata = True
                if tel and not (tel.isdigit() and len(tel) == 10):
                    st.error("Telefon 10 haneli rakamlardan oluşmalıdır (örn: 5551234567).")
                    hata = True
                if eposta and not re.match(r"^[^@]+@[^@]+\.[^@]+$", eposta):
                    st.error("Geçerli bir e-posta adresi giriniz (ornek@domain.com).")
                    hata = True
                if not hata and duzenlenecek_idx is None:
                    if any(tm["ad"] == ad.strip() for tm in st.session_state.tedarikciler):
                        st.error("Bu firma adı zaten mevcut.")
                        hata = True
                
                if not hata:
                    yeni_t = {
                        "ad": ad.strip(),
                        "guven_puani": guven,
                        "tel": tel,
                        "eposta": eposta
                    }
                    if duzenlenecek_idx is not None:
                        st.session_state.tedarikciler[duzenlenecek_idx] = yeni_t
                        st.session_state.duzenlenecek_tedarikci = None
                        st.session_state.son_islem_mesaji = f"✅ Tedarikçi '{ad.strip()}' güncellendi."
                    else:
                        st.session_state.tedarikciler.append(yeni_t)
                        st.session_state.son_islem_mesaji = f"✅ Tedarikçi '{ad.strip()}' eklendi."
                    dosya_yaz(TEDARIKCI_DOSYASI, st.session_state.tedarikciler)
                    st.rerun()


def siparis_sayfasi():
    st.markdown('<div class="main-header">🔥 Sipariş Panosu</div>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["📋 Liste","➕ Ekle"])
    with tab1:
        for i, f in enumerate(st.session_state.fire):
            c1, c2, c3 = st.columns([3,1,1])
            renk = "🔴" if "Yüksek" in f['aciliyet'] else "🟡" if "Orta" in f['aciliyet'] else "🟢"
            c1.write(f"{renk} **{f['urun_adi']}** – {f['miktar']} {f['birim']} – {f['durum']}")
            if c2.button("🗑️", key=f"sil_fire_{i}"):
                st.session_state.fire.pop(i); veriyi_kaydet(); st.rerun()
            if c3.button("📧", key=f"mail_fire_{i}"):
                t_eposta = next((t["eposta"] for t in st.session_state.tedarikciler
                                 if t["ad"] == f.get("tedarikci","")), "")
                if t_eposta:
                    urun_dict = f.copy()
                    for u in st.session_state.stok:
                        if u["urun_adi"] == f["urun_adi"]:
                            urun_dict["miktar"]    = u["miktar"]
                            urun_dict["min_miktar"] = u.get("min_miktar",10); break
                    tedarikciye_siparis_gonder(urun_dict, t_eposta)
                    st.session_state.son_islem_mesaji = f"📧 {f['urun_adi']} siparişi gönderildi"; st.rerun()
                else:
                    st.error("Tedarikçi e-postası yok")
    with tab2:
        with st.form("fire_ekle"):
            if not st.session_state.stok:
                st.warning("Önce ürün ekleyin")
            else:
                urun_sec  = st.selectbox("Ürün", [u["urun_adi"] for u in st.session_state.stok])
                urun_bilgi= next(u for u in st.session_state.stok if u["urun_adi"] == urun_sec)
                miktar    = st.number_input("Miktar", 0.01, value=1.0)
                st.write(f"Birim: {urun_bilgi['birim']}")
                if st.form_submit_button("Ekle"):
                    st.session_state.fire.append({
                        "urun_adi":urun_sec,"miktar":miktar,"birim":urun_bilgi['birim'],
                        "aciliyet":"⚡ Orta","tedarikci":urun_bilgi.get("tedarikci",""),
                        "durum":"Bekliyor","eklenme_tarihi":datetime.now().strftime("%Y-%m-%d %H:%M")})
                    veriyi_kaydet()
                    st.session_state.son_islem_mesaji = "🔥 Sipariş eklendi"; st.rerun()


def stok_analizi():
    st.markdown('<div class="main-header">📈 Stok Analizi</div>', unsafe_allow_html=True)
    if not st.session_state.stok: st.info("Ürün yok"); return
    df = pd.DataFrame(st.session_state.stok)
    df["kar_marji"] = df.apply(
        lambda r: ((r['satis_fiyat']-r['alis_fiyat'])/r['satis_fiyat']*100) if r['satis_fiyat'] > 0 else 0,
        axis=1)
    st.dataframe(
        df[["urun_adi","satis_fiyat","alis_fiyat","kar_marji"]].style.format({"kar_marji":"{:.1f}%"}),
        use_container_width=True)
    st.subheader("Stok Devir Hızı")
    for u in st.session_state.stok:
        hiz = urun_gunluk_satis_hizi(u["urun_adi"], u.get("tahmini_gunluk_satis",1.0))
        st.write(f"{u['urun_adi']}: {hiz:.2f} {u['birim']}/gün")


def fire_analizi():
    st.markdown('<div class="main-header">📉 Fire Analizi</div>', unsafe_allow_html=True)
    if st.session_state.fire:
        kat_fire = {}
        for f in st.session_state.fire:
            kat = next((u.get("kategori","Diğer") for u in st.session_state.stok
                        if u["urun_adi"] == f["urun_adi"]), "Diğer")
            kat_fire[kat] = kat_fire.get(kat,0) + f["miktar"]
        fig = px.pie(names=list(kat_fire.keys()), values=list(kat_fire.values()),
                     title="Kategori Bazlı Fire", hole=0.3)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Fire kaydı yok")


def satis_raporu():
    st.markdown('<div class="main-header">📊 Satış Raporu</div>', unsafe_allow_html=True)
    satislar = dosya_oku(SATIS_DOSYASI, [])
    if not satislar: st.info("Satış yok"); return
    df = pd.DataFrame(satislar)
    df["tarih"] = pd.to_datetime(df["tarih"])
    df["gun"]   = df["tarih"].dt.date
    df["ay"]    = df["tarih"].dt.strftime("%Y-%m")
    c1, c2, c3 = st.columns(3)
    with c1:
        aralik = st.date_input("Tarih Aralığı", (df["gun"].min(), df["gun"].max()))
    with c2:
        tip = st.radio("Kırılım", ["Günlük","Aylık","Ürün Bazlı","Kâr Marjı"], horizontal=True)
    with c3:
        if st.button("📥 Excel İndir"):
            output = io.BytesIO()
            df_filtered = df[(df["gun"]>=aralik[0]) & (df["gun"]<=aralik[1])] if len(aralik)==2 else df
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_filtered.to_excel(writer, index=False, sheet_name="Satislar")
            st.download_button("📥 Excel Dosyasını İndir", output.getvalue(), "satis_raporu.xlsx",
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    if len(aralik) == 2:
        df = df[(df["gun"] >= aralik[0]) & (df["gun"] <= aralik[1])]
    if tip == "Günlük":
        rpr = df.groupby("gun")["toplam_tutar"].sum().reset_index()
        rpr.columns = ["Tarih","Toplam Satış (TL)"]
        st.dataframe(rpr)
        fig = px.bar(rpr, x="Tarih", y="Toplam Satış (TL)")
        st.plotly_chart(fig)
    elif tip == "Aylık":
        rpr = df.groupby("ay")["toplam_tutar"].sum().reset_index()
        rpr.columns = ["Ay","Toplam Satış (TL)"]
        st.dataframe(rpr)
        fig = px.line(rpr, x="Ay", y="Toplam Satış (TL)", markers=True)
        st.plotly_chart(fig)
    elif tip == "Ürün Bazlı":
        rpr = df.groupby("urun_adi").agg(Adet=("miktar","sum"), Ciro=("toplam_tutar","sum")).reset_index()
        st.dataframe(rpr)
        col1, col2 = st.columns(2)
        fig1 = px.pie(rpr, values="Ciro", names="urun_adi", title="Ciro", hole=0.3)
        col1.plotly_chart(fig1)
        fig2 = px.bar(rpr, x="urun_adi", y="Adet", title="Satış Adedi")
        col2.plotly_chart(fig2)
    else:
        df_kar = pd.DataFrame(st.session_state.stok)
        df_kar["kar_marji"] = df_kar.apply(
            lambda r: ((r['satis_fiyat']-r['alis_fiyat'])/r['satis_fiyat']*100) if r['satis_fiyat'] > 0 else 0,
            axis=1)
        st.dataframe(
            df_kar[["urun_adi","satis_fiyat","alis_fiyat","kar_marji"]].style.format({"kar_marji":"{:.1f}%"}))


def aktivite_logu():
    st.markdown('<div class="main-header">📋 Aktivite Logu</div>', unsafe_allow_html=True)
    hareketler = dosya_oku(HAREKET_DOSYASI, [])
    if not hareketler: st.info("Kayıt yok"); return
    df = pd.DataFrame(hareketler)
    df["tarih"] = pd.to_datetime(df["tarih"])
    col1, col2 = st.columns(2)
    with col1: bas = st.date_input("Başlangıç", df["tarih"].min().date())
    with col2: bit = st.date_input("Bitiş",     df["tarih"].max().date())
    mask = (df["tarih"].dt.date >= bas) & (df["tarih"].dt.date <= bit)
    st.dataframe(df[mask].sort_values("tarih", ascending=False), use_container_width=True)


def kasa_kapanisi():
    st.markdown('<div class="main-header">🧾 Günlük Kasa Kapanışı</div>', unsafe_allow_html=True)
    bugun   = datetime.now().strftime("%Y-%m-%d")
    satislar = [s for s in dosya_oku(SATIS_DOSYASI, []) if s["tarih"].startswith(bugun)]
    if not satislar:
        st.info("Bugün satış yok"); return
    df     = pd.DataFrame(satislar)
    toplam = df["toplam_tutar"].sum()
    st.dataframe(df[["urun_adi","miktar","birim_fiyat","toplam_tutar"]], use_container_width=True)
    st.metric("Toplam Satış", f"{toplam:.2f} TL")
    st.metric("Net Kâr",      f"{gunluk_kar():.2f} TL")
    if "odeme_tipi" in df.columns:
        for kanal, tutar in df.groupby("odeme_tipi")["toplam_tutar"].sum().items():
            st.metric(f"💳 {kanal}", f"{tutar:,.2f} TL")

    if st.button("📄 PDF İndir"):
        pdf = FPDF()
        pdf.add_page()
        fn = _pdf_setup(pdf, 12)
        pdf.cell(200, 10, txt=f"Kasa Kapanis - {bugun}", ln=True, align='C')
        pdf.ln(10)
        pdf.set_font(fn, size=10)
        for baslik, genislik in [("Urun",50),("Miktar",30),("Birim Fiyat",30),("Tutar",30)]:
            pdf.cell(genislik, 8, txt=baslik, border=1)
        pdf.ln()
        for _, row in df.iterrows():
            pdf.cell(50, 8, txt=str(row["urun_adi"])[:20],         border=1)
            pdf.cell(30, 8, txt=str(row["miktar"]),                 border=1)
            pdf.cell(30, 8, txt=f"{row['birim_fiyat']:.2f} TL",    border=1)
            pdf.cell(30, 8, txt=f"{row['toplam_tutar']:.2f} TL",   border=1)
            pdf.ln()
        pdf.ln(5)
        pdf.set_font(fn, size=12)
        pdf.cell(200, 10, txt=f"TOPLAM: {toplam:.2f} TL", ln=True)
        pdf_bytes = _pdf_bytes(pdf)
        st.download_button("📥 PDF İndir", pdf_bytes, "kasa_kapanis.pdf", mime="application/pdf")


def kullanici_yonetimi():
    st.markdown('<div class="main-header">👥 Kullanıcı Yönetimi</div>', unsafe_allow_html=True)
    with st.form("kullanici_ekle"):
        yeni_kul   = st.text_input("Kullanıcı Adı")
        yeni_sifre = st.text_input("Şifre", type="password")
        rol        = st.selectbox("Rol", list(ROLLER.keys()))
        ad         = st.text_input("Ad Soyad")
        if st.form_submit_button("Ekle"):
            if yeni_kul and yeni_sifre:
                st.session_state.kullanicilar.append({
                    "kullanici_adi":yeni_kul,
                    "sifre":hashlib.sha256(yeni_sifre.encode()).hexdigest(),
                    "rol":rol, "ad":ad})
                dosya_yaz(KULLANICI_DOSYASI, st.session_state.kullanicilar)
                st.session_state.son_islem_mesaji = f"✅ {yeni_kul} eklendi"; st.rerun()
            else:
                st.error("Kullanıcı adı ve şifre zorunlu")


def sifre_sifirla():
    st.markdown('<div class="main-header">🔑 Şifre Sıfırlama</div>', unsafe_allow_html=True)
    with st.form("sifre_sifirla"):
        eski  = st.text_input("Eski Şifre",          type="password")
        yeni  = st.text_input("Yeni Şifre",          type="password")
        yeni2 = st.text_input("Yeni Şifre Tekrar",   type="password")
        if st.form_submit_button("Sıfırla"):
            admin_pass = config.get("sifre","1234")
            try: admin_pass = st.secrets["admin"]["sifre"]
            except: pass
            if eski != admin_pass:  st.error("Eski şifre yanlış")
            elif yeni != yeni2:     st.error("Yeni şifreler eşleşmiyor")
            elif len(yeni) < 4:     st.error("Şifre en az 4 karakter")
            else:
                config["sifre"] = yeni
                dosya_yaz(CONFIG_DOSYASI, config)
                st.session_state.son_islem_mesaji = "Şifre güncellendi"; st.rerun()


def geri_bildirim():
    st.markdown('<div class="main-header">💬 Geri Bildirim</div>', unsafe_allow_html=True)
    with st.form("geribildirim"):
        konu  = st.text_input("Konu")
        mesaj = st.text_area("Mesaj")
        if st.form_submit_button("Gönder"):
            logging.info(f"Geri Bildirim: {konu} - {mesaj}")
            st.session_state.son_islem_mesaji = "Teşekkürler!"; st.rerun()


def ayarlar_sayfasi():
    st.markdown('<div class="main-header">⚙️ Ayarlar</div>', unsafe_allow_html=True)
    with st.form("ayarlar"):
        eposta  = st.text_input("Patron E-posta",  value=st.session_state.get("patron_email",""))
        telefon = st.text_input("Patron Telefon",  value=st.session_state.get("patron_telefon",""))
        col1, col2, col3 = st.columns(3)
        if col1.form_submit_button("Kaydet"):
            st.session_state.patron_email   = eposta
            st.session_state.patron_telefon = telefon
            st.session_state.son_islem_mesaji = "Ayarlar kaydedildi"; st.rerun()
        if col2.form_submit_button("Test E-posta"):
            if eposta: email_gonder(eposta,"Test","Test mesajı"); st.success("Test e-postası gönderilmeye çalışıldı")
            else: st.error("E-posta girin")
        if col3.form_submit_button("Test WhatsApp"):
            if telefon: whatsapp_gonder(f"+90{telefon}","Test mesajı"); st.success("Test WhatsApp gönderilmeye çalışıldı")
            else: st.error("Telefon girin")


def yedekleme_sayfasi():
    st.markdown('<div class="main-header">💾 Yedekleme</div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        yedek = {"stok":st.session_state.stok,"fire":st.session_state.fire,
                 "barkod_db":st.session_state.barkod_db,"tedarikciler":st.session_state.tedarikciler}
        st.download_button("📥 JSON İndir", json.dumps(yedek,ensure_ascii=False,indent=2),
                           "yedek.json", use_container_width=True)
    with col2:
        dosya = st.file_uploader("Yedek yükle", type="json")
        if dosya:
            try:
                icerik = json.load(dosya)
                st.session_state.stok        = icerik.get("stok",[])
                st.session_state.fire        = icerik.get("fire",[])
                st.session_state.barkod_db   = icerik.get("barkod_db",{})
                st.session_state.tedarikciler= icerik.get("tedarikciler",[])
                veriyi_kaydet()
                st.session_state.son_islem_mesaji = "Yedek yüklendi"; st.rerun()
            except:
                st.error("Geçersiz JSON")


def veriyi_kaydet():
    dosya_yaz(STOK_DOSYASI,      st.session_state.stok)
    dosya_yaz(FIRE_DOSYASI,      st.session_state.fire)
    dosya_yaz(TEDARIKCI_DOSYASI, st.session_state.tedarikciler)


# ============================================================
# SAYFA HARİTASI
# ============================================================
SAYFALAR = {
    "🏠 Ana Panel":         ana_sayfa,
    "📱 Barkod":            barkod_sayfasi,
    "🏷️ Barkod Yönetimi":  barkod_yonetimi,
    "💵 Satış":             satis_sayfasi,
    "📦 Stok":              stok_sayfasi,
    "🔥 Sipariş":           siparis_sayfasi,
    "🏭 Tedarikçi":         tedarikci_sayfasi,
    "📈 Stok Analizi":      stok_analizi,
    "📉 Fire Analizi":      fire_analizi,
    "📊 Satış Raporu":      satis_raporu,
    "📋 Aktivite Logu":     aktivite_logu,
    "🧾 Kasa Kapanışı":     kasa_kapanisi,
    "👥 Kullanıcı Yönetimi":kullanici_yonetimi,
    "🔑 Şifre Sıfırlama":   sifre_sifirla,
    "💬 Geri Bildirim":     geri_bildirim,
    "⚙️ Ayarlar":           ayarlar_sayfasi,
    "💾 Yedekleme":         yedekleme_sayfasi,
}


# ============================================================
# MAIN
# ============================================================
def main():
    st.set_page_config(
        page_title="Market Yönetim", page_icon="🏪",
        layout="wide", initial_sidebar_state="expanded")
    oturumu_baslat()
    enerjik_css(st.session_state.get("tema","Koyu"))
    pd.set_option('display.float_format','{:.2f}'.format)
    oturum_kontrol()

    if not st.session_state.authenticated:
        giris_ekrani(); return

    if st.session_state.son_islem_mesaji:
        st.success(st.session_state.son_islem_mesaji)
        st.session_state.son_islem_mesaji = ""

    with st.sidebar:
        st.markdown('<h2 style="color:white;">🏪 Market</h2>', unsafe_allow_html=True)
        st.markdown('<p style="color:#F97316;">v3.1 Stabil</p>', unsafe_allow_html=True)
        if st.session_state.current_user:
            st.markdown(
                f'<div style="background:rgba(249,115,22,0.2);border-radius:12px;padding:12px;">'
                f'<p style="color:white;">👤 {st.session_state.current_user.get("ad","Kullanıcı")}</p></div>',
                unsafe_allow_html=True)
        st.selectbox("Tema", ["Koyu","Aydınlık"],
                     index=0 if st.session_state.get("tema","Koyu")=="Koyu" else 1,
                     key="tema_secimi", on_change=tema_degistir)
        aktif = izinli_sayfalar(st.session_state.current_user)
        if not aktif: st.error("İzinli sayfa yok."); st.stop()
        sayfa = st.radio("Menü", list(aktif.keys()), label_visibility="collapsed")
        if st.button("🚪 Çıkış", use_container_width=True): cikis()

    aktif[sayfa]()


if __name__ == "__main__":
    main()
