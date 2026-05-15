import streamlit as st
import sqlite3
import hashlib
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import logging
import os
import uuid
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import io
import re
import base64
from PIL import Image
import numpy as np

# Barkod okuma için pyzbar
try:
    from pyzbar.pyzbar import decode as pyzbar_decode
    BARCODE_AVAILABLE = True
except ImportError:
    BARCODE_AVAILABLE = False
    logging.warning("pyzbar bulunamadı, barkod okuma devre dışı")

# PDF için fpdf2
from fpdf import FPDF

# WhatsApp opsiyonel
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
    logger.setLevel(logging.WARNING)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    for lvl, fname in [(logging.ERROR, 'error.log'), (logging.WARNING, 'warning.log')]:
        handler = logging.FileHandler(os.path.join(log_dir, fname))
        handler.setLevel(lvl)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    console = logging.StreamHandler()
    console.setLevel(logging.WARNING)
    console.setFormatter(formatter)
    logger.addHandler(console)

setup_logging()
logging.info("Uygulama başlatıldı")

# ---------- SABİTLER ----------
CONFIG_DOSYASI = "config.json"
VARSAYILAN_CONFIG = {
    "oturum_suresi_dk": 45,
    "skt_uyari_gun": 3,
    "kategoriler": ["Kuru Gıda","Süt Ürünleri","İçecek","Temizlik","Diğer","Et & Şarküteri","Dondurulmuş","Fırın"],
    "birimler": ["kg","litre","adet","paket","gram","koli","kutu","şişe","çuval"],
    "roller": {"patron":["tümü"], "kasiyer":["barkod","satis"], "depocu":["barkod","stok","stok_ekle","skt_takip"]}
}
KATEGORILER = VARSAYILAN_CONFIG["kategoriler"]
BIRIMLER    = VARSAYILAN_CONFIG["birimler"]
ROLLER      = VARSAYILAN_CONFIG["roller"]
OTURUM_SURESI = VARSAYILAN_CONFIG["oturum_suresi_dk"]
SKT_UYARI_GUN = VARSAYILAN_CONFIG["skt_uyari_gun"]

# ---------- VERİTABANI BAĞLANTISI ----------
def get_db():
    if 'db' not in st.session_state:
        conn = sqlite3.connect('market.db', check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        st.session_state.db = conn
    return st.session_state.db

def init_db():
    db = get_db()
    cursor = db.cursor()
    # Stok tablosu
    cursor.execute('''CREATE TABLE IF NOT EXISTS stok (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        urun_adi TEXT NOT NULL,
        miktar REAL DEFAULT 0,
        birim TEXT DEFAULT 'adet',
        kategori TEXT DEFAULT 'Diğer',
        min_miktar REAL DEFAULT 0,
        barkod TEXT UNIQUE,
        son_kullanma_tarihi TEXT DEFAULT '',
        alis_fiyat REAL DEFAULT 0,
        satis_fiyat REAL DEFAULT 0,
        tedarikci TEXT DEFAULT '',
        raf_no TEXT DEFAULT '',
        kdv_oran INTEGER DEFAULT 8,
        tahmini_gunluk_satis REAL DEFAULT 1.0
    )''')

    # Fire/Sipariş tablosu
    cursor.execute('''CREATE TABLE IF NOT EXISTS fire (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        urun_adi TEXT NOT NULL,
        miktar REAL DEFAULT 0,
        birim TEXT DEFAULT 'adet',
        aciliyet TEXT DEFAULT 'Orta',
        tedarikci TEXT DEFAULT '',
        durum TEXT DEFAULT 'Bekliyor',
        eklenme_tarihi TEXT DEFAULT ''
    )''')

    # Satış tablosu
    cursor.execute('''CREATE TABLE IF NOT EXISTS satislar (
        id TEXT PRIMARY KEY,
        tarih TEXT NOT NULL,
        kullanici TEXT,
        urun_adi TEXT,
        birim TEXT,
        miktar REAL,
        birim_fiyat REAL,
        toplam_tutar REAL,
        alis_fiyat REAL,
        maliyet REAL,
        odeme_tipi TEXT DEFAULT 'Nakit'
    )''')

    # Hareket log tablosu
    cursor.execute('''CREATE TABLE IF NOT EXISTS hareketler (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tarih TEXT NOT NULL,
        kullanici TEXT,
        islem TEXT,
        urun_adi TEXT,
        detay TEXT
    )''')

    # Barkod veritabanı
    cursor.execute('''CREATE TABLE IF NOT EXISTS barkod_db (
        barkod TEXT PRIMARY KEY,
        urun_adi TEXT,
        birim TEXT,
        kategori TEXT,
        uretici TEXT DEFAULT ''
    )''')

    # Tedarikçiler
    cursor.execute('''CREATE TABLE IF NOT EXISTS tedarikciler (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ad TEXT UNIQUE,
        guven_puani REAL DEFAULT 5.0,
        tel TEXT DEFAULT '',
        eposta TEXT DEFAULT ''
    )''')

    # Kullanıcılar
    cursor.execute('''CREATE TABLE IF NOT EXISTS kullanicilar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kullanici_adi TEXT UNIQUE,
        sifre_hash TEXT,
        rol TEXT,
        ad TEXT
    )''')

    db.commit()

# ---------- VERİTABANI YARDIMCILARI ----------
def db_execute(query, params=()):
    db = get_db()
    db.execute(query, params)
    db.commit()

def db_fetchall(query, params=()):
    db = get_db()
    cur = db.execute(query, params)
    return [dict(row) for row in cur.fetchall()]

def db_fetchone(query, params=()):
    db = get_db()
    cur = db.execute(query, params)
    row = cur.fetchone()
    return dict(row) if row else None

# İlk çalıştırmada varsayılan kullanıcı ve mock veri ekleme (isteğe bağlı)
def ilk_kurulum():
    init_db()
    # Eğer hiç kullanıcı yoksa admin ekle
    if not db_fetchall("SELECT * FROM kullanicilar"):
        # Admin şifresi hash'li: 1234
        admin_hash = hashlib.sha256("1234".encode()).hexdigest()
        db_execute("INSERT INTO kullanicilar (kullanici_adi, sifre_hash, rol, ad) VALUES (?,?,?,?)",
                   ("admin", admin_hash, "patron", "Admin"))
    # Eğer barkod_db boşsa birkaç örnek ekle
    if not db_fetchall("SELECT * FROM barkod_db"):
        ornek_barkodlar = [
            ("8691234567890", "Un", "kg", "Kuru Gıda", "ABC Un"),
            ("8691234567891", "Şeker", "kg", "Kuru Gıda", "XYZ Şeker"),
            ("8691234567892", "Süt", "litre", "Süt Ürünleri", "Sütaş"),
            ("8691234567893", "Yumurta", "adet", "Diğer", "Köy Yumurtası"),
            ("8691234567894", "Tereyağı", "kg", "Süt Ürünleri", "Sütaş")
        ]
        for b in ornek_barkodlar:
            db_execute("INSERT INTO barkod_db (barkod, urun_adi, birim, kategori, uretici) VALUES (?,?,?,?,?)", b)

# ---------- OTURUM & AUTH ----------
def hash_sifre(sifre):
    return hashlib.sha256(sifre.encode()).hexdigest()

def giris_kontrol(kullanici, sifre):
    user = db_fetchone("SELECT * FROM kullanicilar WHERE kullanici_adi = ?", (kullanici,))
    if user and user['sifre_hash'] == hash_sifre(sifre):
        return user
    return None

def oturumu_baslat():
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.current_user = None
        st.session_state.last_activity = datetime.now()
        st.session_state.tema = "Koyu"
        st.session_state.pos_sepet = {}
        st.session_state.son_islem_mesajlari = []
        st.session_state.patron_email = ""
        st.session_state.patron_telefon = ""
        st.session_state.duzenlenecek_tedarikci = None
    # Veritabanı ilk kurulum
    ilk_kurulum()

def oturum_kontrol():
    if st.session_state.authenticated:
        if datetime.now() - st.session_state.last_activity > timedelta(minutes=OTURUM_SURESI):
            st.session_state.authenticated = False
            st.session_state.current_user = None
            st.sidebar.error("⏳ Oturum süreniz doldu!")
            st.rerun()
        else:
            st.session_state.last_activity = datetime.now()

# ---------- YARDIMCI FONKSİYONLAR ----------
def mesaj_ekle(m):
    st.session_state.son_islem_mesajlari.append(m)
    if len(st.session_state.son_islem_mesajlari) > 3:
        st.session_state.son_islem_mesajlari.pop(0)

def tema_degistir():
    st.session_state.tema = st.session_state.get("tema_secimi","Koyu")

def guvenli_html(metin: str) -> str:
    return (str(metin)
            .replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
            .replace('"',"&quot;").replace("'","&#x27;"))

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

# ---------- PDF (Fiş) ----------
FONT_PATH = None
def get_font_path():
    global FONT_PATH
    if FONT_PATH: return FONT_PATH
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
            FONT_PATH = p
            return p
    return None

def _pdf_bytes(pdf: FPDF) -> bytes:
    try:
        return pdf.output(dest='S').encode('latin-1')
    except Exception:
        buf = io.BytesIO()
        pdf.output(buf)
        return buf.getvalue()

def _pdf_setup(pdf: FPDF, boyut=10):
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

# ---------- BARKOD OKUMA ----------
def barkod_oku(image_bytes):
    if not BARCODE_AVAILABLE:
        st.error("pyzbar yüklü değil.")
        return None
    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        # Görüntüyü PIL'e çevir
        pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        decoded = pyzbar_decode(pil_img)
        if decoded:
            return decoded[0].data.decode("utf-8")
        return None
    except Exception as e:
        logging.error(f"Barkod okuma hatası: {e}")
        return None

# ---------- İLETİŞİM ----------
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

def whatsapp_gonder(telefon_no, mesaj):
    if not WHATSAPP_AKTIF: return False
    try:
        suan = datetime.now()
        saat, dakika = suan.hour, suan.minute + 2
        if dakika >= 60: saat += 1; dakika -= 60
        pwk.sendwhatmsg(telefon_no, mesaj, saat, dakika, wait_time=15, tab_close=True)
        return True
    except Exception as e:
        logging.error(f"WhatsApp hatası: {e}"); return False

# ---------- AKTİVİTE LOG ----------
def hareket_ekle(kul, islem, ad, detay=""):
    tarih = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db_execute("INSERT INTO hareketler (tarih, kullanici, islem, urun_adi, detay) VALUES (?,?,?,?,?)",
               (tarih, kul, islem, ad, detay))

# ---------- SATIŞ İŞLEMLERİ ----------
def satis_kaydet(urun_adi, birim, miktar, fiyat, toplam, kullanici, alis_fiyat, odeme_tipi):
    sid = str(uuid.uuid4())[:8]
    tarih = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    maliyet = round(miktar * alis_fiyat, 2)
    db_execute("INSERT INTO satislar (id, tarih, kullanici, urun_adi, birim, miktar, birim_fiyat, toplam_tutar, alis_fiyat, maliyet, odeme_tipi) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
               (sid, tarih, kullanici, urun_adi, birim, miktar, fiyat, toplam, alis_fiyat, maliyet, odeme_tipi))

@st.cache_data(ttl=60)
def gunluk_ciro(tarih_str):
    satislar = db_fetchall("SELECT toplam_tutar FROM satislar WHERE tarih LIKE ?", (tarih_str+'%',))
    return sum(s['toplam_tutar'] for s in satislar)

@st.cache_data(ttl=60)
def gunluk_kar(tarih_str=None):
    if tarih_str is None: tarih_str = datetime.now().strftime("%Y-%m-%d")
    satislar = db_fetchall("SELECT toplam_tutar, maliyet FROM satislar WHERE tarih LIKE ?", (tarih_str+'%',))
    return sum(s['toplam_tutar'] - s.get('maliyet',0) for s in satislar)

# ---------- BİLİMSEL İNDİRİM ----------
def urun_gunluk_satis_hizi(urun_adi):
    # Son 30 günlük ortalama satış
    bitis = datetime.now()
    baslangic = bitis - timedelta(days=30)
    rows = db_fetchall("SELECT miktar FROM satislar WHERE urun_adi = ? AND tarih >= ? AND tarih <= ?",
                       (urun_adi, baslangic.strftime("%Y-%m-%d"), bitis.strftime("%Y-%m-%d %H:%M:%S")))
    if not rows:
        # Veritabanındaki stok tahmini günlük satışı kullan
        stok = db_fetchone("SELECT tahmini_gunluk_satis FROM stok WHERE urun_adi = ?", (urun_adi,))
        return stok['tahmini_gunluk_satis'] if stok else 1.0
    return sum(r['miktar'] for r in rows) / len(rows)

def bilimsel_indirim_hesapla(urun, kalan_gun):
    if kalan_gun <= 0:
        satis = urun.get('satis_fiyat',10)
        alis = urun.get('alis_fiyat',5)
        if satis > 0:
            return min(50, int((satis-alis)/satis*100))
        return 50
    q = urun.get('miktar',0)
    satis_fiyat = urun.get('satis_fiyat',0)
    alis_fiyat  = urun.get('alis_fiyat',0)
    if satis_fiyat <= 0 or q <= 0: return 0
    m = (satis_fiyat - alis_fiyat) / satis_fiyat
    v = urun_gunluk_satis_hizi(urun['urun_adi'])
    beklenen = v * kalan_gun
    stok_fazlasi = q - beklenen
    if stok_fazlasi <= 0: return 0
    indirim = (stok_fazlasi/q) * m * 100
    max_indirim = m*100*0.8
    indirim = min(indirim, max_indirim)
    if kalan_gun <= 1: indirim = max(indirim, m*100*0.5)
    elif kalan_gun <= 3: indirim = max(indirim, m*100*0.2)
    return round(indirim,1)

# ---------- SAYFALAR ----------
def ana_sayfa():
    st.markdown('<div class="main-header">📊 Yönetim Paneli</div>', unsafe_allow_html=True)
    # SKT yaklaşan ürünler
    stoklar = db_fetchall("SELECT * FROM stok WHERE son_kullanma_tarihi != ''")
    yaklasan = []
    for u in stoklar:
        try:
            skt = datetime.strptime(u['son_kullanma_tarihi'], "%Y-%m-%d")
            kalan = (skt - datetime.now()).days
            if 0 <= kalan <= SKT_UYARI_GUN:
                ind = bilimsel_indirim_hesapla(u, kalan)
                yaklasan.append((u['urun_adi'], kalan, ind))
        except: pass
    if yaklasan:
        st.error("⏳ Son kullanma tarihi yaklaşan ürünler:")
        for ad, gun, ind in yaklasan:
            st.write(f"• **{ad}** – {gun} gün kaldı – Önerilen indirim: %{ind}")

    # Kritik stok uyarısı
    kritik = [u for u in stoklar if u['min_miktar'] > 0 and u['miktar'] <= u['min_miktar']]
    if kritik:
        st.warning("🚨 Kritik stok seviyesindeki ürünler:")
        for u in kritik:
            st.write(f"   • **{u['urun_adi']}** – Mevcut: {u['miktar']:.2f} {u['birim']} / Min: {u['min_miktar']} {u['birim']}")

    bugun = datetime.now().strftime("%Y-%m-%d")
    dun = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    bugunku_ciro = gunluk_ciro(bugun)
    dunku_ciro   = gunluk_ciro(dun)
    kar = gunluk_kar(bugun)
    delta_gun = bugunku_ciro - dunku_ciro

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Bugünkü Ciro", f"{bugunku_ciro:,.0f} TL", delta=f"{delta_gun:+,.0f} TL")
    col2.metric("Bugünkü Kâr",  f"{kar:,.0f} TL")
    col3.metric("Dünkü Ciro",   f"{dunku_ciro:,.0f} TL")
    # Haftalık ciro (cache yok ama basit)
    hafta_bas = datetime.now().date() - timedelta(days=datetime.now().weekday())
    haftalik = sum(s['toplam_tutar'] for s in db_fetchall("SELECT toplam_tutar FROM satislar WHERE tarih >= ? AND tarih <= ?",
                                                         (hafta_bas.strftime("%Y-%m-%d"), (hafta_bas+timedelta(days=6)).strftime("%Y-%m-%d 23:59:59"))))
    col4.metric("Bu Hafta", f"{haftalik:,.0f} TL")

def barkod_yonetimi():
    st.markdown('<div class="main-header">🏷️ Barkod Yönetimi</div>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["📋 Liste","➕ Yeni Barkod"])
    with tab1:
        barkodlar = db_fetchall("SELECT * FROM barkod_db")
        if barkodlar:
            arama = st.text_input("🔍 Ara")
            df = pd.DataFrame(barkodlar)
            if arama:
                df = df[df['barkod'].str.contains(arama, case=False) | df['urun_adi'].str.contains(arama, case=False)]
            st.dataframe(df, use_container_width=True)
            for _, row in df.iterrows():
                with st.expander(f"🔧 {row['urun_adi']} ({row['barkod']})"):
                    col1, col2 = st.columns(2)
                    with col1:
                        yeni_ad = st.text_input("Ürün Adı", row['urun_adi'], key=f"b_ad_{row['barkod']}")
                        yeni_birim = st.selectbox("Birim", BIRIMLER, index=BIRIMLER.index(row['birim']) if row['birim'] in BIRIMLER else 0, key=f"b_birim_{row['barkod']}")
                        yeni_kat = st.selectbox("Kategori", KATEGORILER, index=KATEGORILER.index(row['kategori']) if row['kategori'] in KATEGORILER else 0, key=f"b_kat_{row['barkod']}")
                    with col2:
                        if st.button("💾 Güncelle", key=f"b_guncel_{row['barkod']}"):
                            db_execute("UPDATE barkod_db SET urun_adi=?, birim=?, kategori=? WHERE barkod=?",
                                       (yeni_ad, yeni_birim, yeni_kat, row['barkod']))
                            mesaj_ekle(f"Barkod {row['barkod']} güncellendi")
                            st.rerun()
                        if st.button("🗑️ Sil", key=f"b_sil_{row['barkod']}"):
                            db_execute("DELETE FROM barkod_db WHERE barkod=?", (row['barkod'],))
                            mesaj_ekle(f"Barkod {row['barkod']} silindi")
                            st.rerun()
        else:
            st.info("Barkod veritabanı boş.")
    with tab2:
        with st.form("yeni_barkod"):
            yeni_barkod = st.text_input("Barkod Numarası")
            yeni_ad     = st.text_input("Ürün Adı")
            yeni_birim  = st.selectbox("Birim", BIRIMLER)
            yeni_kat    = st.selectbox("Kategori", KATEGORILER)
            submitted   = st.form_submit_button("Ekle")
            if submitted:
                if not yeni_barkod or not yeni_ad:
                    st.error("Barkod ve ürün adı zorunlu")
                else:
                    db_execute("INSERT OR IGNORE INTO barkod_db (barkod, urun_adi, birim, kategori) VALUES (?,?,?,?)",
                               (yeni_barkod, yeni_ad, yeni_birim, yeni_kat))
                    mesaj_ekle(f"Barkod {yeni_barkod} eklendi")
                    st.rerun()

def barkod_sayfasi():
    st.markdown('<div class="main-header">📱 Barkod Okutma</div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        barkod_manuel = st.text_input("🔢 Barkod Numarası", placeholder="Okutun veya yazın...")
    with col2:
        img_file = st.camera_input("📷 Mobil Kamera")
    barkod = None
    if img_file:
        barkod = barkod_oku(img_file.getvalue())
        if barkod:
            st.success(f"✅ Okunan: {barkod}")
        else:
            st.warning("Barkod algılanamadı.")
    aktif = barkod_manuel or barkod
    if aktif:
        bilgi = db_fetchone("SELECT * FROM barkod_db WHERE barkod=?", (aktif,))
        if bilgi:
            urun_adi = bilgi['urun_adi']
            st.info(f"📦 **{guvenli_html(urun_adi)}** ({bilgi['birim']})")
        else:
            urun_adi = ""
            st.warning("❓ Yeni barkod.")
        with st.form("barkod_form"):
            ad       = st.text_input("Ürün Adı *", value=urun_adi)
            miktar   = st.number_input("Miktar", 0.01, format="%.2f", value=1.0)
            birim    = st.selectbox("Birim", BIRIMLER, index=BIRIMLER.index(bilgi['birim']) if bilgi and bilgi['birim'] in BIRIMLER else 0)
            kategori = st.selectbox("Kategori", KATEGORILER, index=KATEGORILER.index(bilgi['kategori']) if bilgi and bilgi['kategori'] in KATEGORILER else 0)
            islem    = st.radio("İşlem", ["📥 Giriş","📤 Çıkış"], horizontal=True)
            submitted = st.form_submit_button("💾 Kaydet")
            if submitted:
                if not ad.strip():
                    st.error("Ad zorunlu")
                else:
                    # Barkod DB güncelle
                    if aktif not in [b['barkod'] for b in db_fetchall("SELECT barkod FROM barkod_db")]:
                        db_execute("INSERT INTO barkod_db (barkod, urun_adi, birim, kategori) VALUES (?,?,?,?)",
                                   (aktif, ad.strip(), birim, kategori))
                    gercek = miktar if islem == "📥 Giriş" else -miktar
                    # Stok güncelle
                    mevcut = db_fetchone("SELECT * FROM stok WHERE barkod=?", (aktif,))
                    if mevcut:
                        yeni_miktar = mevcut['miktar'] + gercek
                        db_execute("UPDATE stok SET miktar=? WHERE barkod=?", (max(0, yeni_miktar), aktif))
                    else:
                        if gercek > 0:
                            db_execute("INSERT INTO stok (urun_adi, miktar, birim, kategori, barkod) VALUES (?,?,?,?,?)",
                                       (ad.strip(), gercek, birim, kategori, aktif))
                    hareket_ekle(st.session_state.current_user['kullanici_adi'], islem, ad.strip(), f"{miktar} {birim}")
                    mesaj_ekle(f"{ad.strip()} güncellendi")
                    st.rerun()

def satis_sayfasi():
    st.markdown('<div class="main-header">💰 Satış (POS)</div>', unsafe_allow_html=True)
    if st.button("🚀 Hızlı POS Moduna Geç"):
        st.session_state.pos_modu = True
        st.session_state.pos_sepet = {}
        st.rerun()
    satilabilir = [u for u in db_fetchall("SELECT * FROM stok WHERE miktar > 0")]
    if not satilabilir:
        st.warning("Satılacak ürün yok"); return
    secili_str = st.selectbox("Ürün Seç", [f"{u['urun_adi']} ({u['miktar']:.2f} {u['birim']} - {u['satis_fiyat']:.2f} TL)" for u in satilabilir])
    idx = [f"{u['urun_adi']} ({u['miktar']:.2f} {u['birim']} - {u['satis_fiyat']:.2f} TL)" for u in satilabilir].index(secili_str)
    urun = satilabilir[idx]
    fiyat = urun['satis_fiyat']
    mevcut = urun['miktar']
    miktar = st.number_input("Miktar", 0.01, float(mevcut), format="%.2f", value=1.0)
    toplam = miktar * fiyat
    odeme_tipi = st.selectbox("💳 Ödeme Tipi", ["Nakit","Kredi Kartı","Havale/EFT","Yemek Kartı"])
    st.markdown(f"### 🧾 Toplam: {toplam:.2f} TL")
    if st.button("💳 Satış Yap", type="primary", use_container_width=True):
        if miktar <= 0:
            st.error("Geçersiz miktar")
        else:
            db_execute("UPDATE stok SET miktar = miktar - ? WHERE id=?", (miktar, urun['id']))
            satis_kaydet(urun['urun_adi'], urun['birim'], miktar, fiyat, toplam,
                         st.session_state.current_user['kullanici_adi'],
                         urun['alis_fiyat'], odeme_tipi)
            hareket_ekle(st.session_state.current_user['kullanici_adi'], "Satış", urun['urun_adi'], f"{miktar} {urun['birim']}")
            mesaj_ekle(f"✅ Satış: {toplam:.2f} TL")
            st.rerun()

def pos_modu():
    st.markdown('<div class="main-header">🛒 Hızlı Satış (POS Modu)</div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1: barkod = st.text_input("Barkod", key="pos_barkod")
    with col2: img = st.camera_input("Barkod okut", key="pos_kamera")
    if img:
        okunan = barkod_oku(img.getvalue())
        if okunan: barkod = okunan
    if barkod:
        if barkod in st.session_state.pos_sepet:
            st.session_state.pos_sepet[barkod] += 1
        else:
            st.session_state.pos_sepet[barkod] = 1
        st.rerun()
    if st.session_state.pos_sepet:
        toplam_tutar = 0
        for bk, adet in st.session_state.pos_sepet.items():
            urun = db_fetchone("SELECT * FROM stok WHERE barkod=?", (bk,))
            if urun:
                fiyat = urun['satis_fiyat']
                tutar = fiyat * adet
                toplam_tutar += tutar
                col1, col2, col3 = st.columns([3,1,1])
                col1.write(f"📦 {urun['urun_adi']} – {adet} x {fiyat:.2f} = {tutar:.2f} TL")
                yeni_adet = col2.number_input("Adet", min_value=1, value=adet, key=f"pos_adet_{bk}")
                if yeni_adet != adet:
                    st.session_state.pos_sepet[bk] = yeni_adet
                    st.rerun()
                if col3.button("🗑️", key=f"pos_sil_{bk}"):
                    del st.session_state.pos_sepet[bk]; st.rerun()
        st.markdown(f"### Toplam: {toplam_tutar:.2f} TL")
        if st.button("Satışı Tamamla"):
            for bk, adet in st.session_state.pos_sepet.items():
                urun = db_fetchone("SELECT * FROM stok WHERE barkod=?", (bk,))
                if urun and urun['miktar'] >= adet:
                    db_execute("UPDATE stok SET miktar = miktar - ? WHERE barkod=?", (adet, bk))
                    satis_kaydet(urun['urun_adi'], urun['birim'], adet,
                                 urun['satis_fiyat'], adet*urun['satis_fiyat'],
                                 st.session_state.current_user['kullanici_adi'],
                                 urun['alis_fiyat'], "Nakit")
            st.session_state.pos_sepet = {}
            mesaj_ekle(f"Satış tamamlandı: {toplam_tutar:.2f} TL")
            st.rerun()
    if st.button("POS Modundan Çık"):
        st.session_state.pos_modu = False; st.rerun()

def stok_sayfasi():
    st.markdown('<div class="main-header">📦 Stok Yönetimi</div>', unsafe_allow_html=True)
    tab1, tab2, tab3, tab4 = st.tabs(["📋 Liste","➕ Ekle","✏️ Düzenle/Sil","🔢 Sayım"])
    with tab1:
        arama = st.text_input("🔍 Ürün ara", key="stok_arama")
        stoklar = db_fetchall("SELECT * FROM stok")
        df = pd.DataFrame(stoklar)
        if arama:
            df = df[df['urun_adi'].str.contains(arama, case=False) | df['barkod'].astype(str).str.contains(arama)]
        st.dataframe(df, use_container_width=True)
    with tab2:
        with st.form("stok_ekle_form", clear_on_submit=True):
            barkod = st.text_input("Barkod (isteğe bağlı)")
            bilgi = db_fetchone("SELECT * FROM barkod_db WHERE barkod=?", (barkod,)) if barkod else None
            ad = st.text_input("Ürün Adı *", value=bilgi['urun_adi'] if bilgi else "")
            miktar = st.number_input("Miktar", 0.0, format="%.2f", value=1.0)
            birim = st.selectbox("Birim", BIRIMLER, index=BIRIMLER.index(bilgi['birim']) if bilgi and bilgi['birim'] in BIRIMLER else 0)
            kategori = st.selectbox("Kategori", KATEGORILER, index=KATEGORILER.index(bilgi['kategori']) if bilgi and bilgi['kategori'] in KATEGORILER else 0)
            alis = st.number_input("Alış Fiyatı", 0.0, format="%.2f", value=0.0)
            satis = st.number_input("Satış Fiyatı", 0.0, format="%.2f", value=0.0)
            min_m = st.number_input("Min Stok", 0.0, format="%.2f", value=5.0)
            raf_no = st.text_input("Raf No")
            tedarikci_sec = st.selectbox("Tedarikçi", ["Yok"] + [t['ad'] for t in db_fetchall("SELECT ad FROM tedarikciler")])
            tedarikci = tedarikci_sec if tedarikci_sec != "Yok" else ""
            kdv = st.selectbox("KDV Oranı (%)", [1,8,10,18,20], index=1)
            skt_var = st.checkbox("SKT var")
            skt = st.date_input("SKT") if skt_var else None
            submitted = st.form_submit_button("Ekle")
            if submitted:
                if not ad.strip():
                    st.error("Ürün adı zorunlu")
                else:
                    skt_str = skt.strftime("%Y-%m-%d") if skt_var else ""
                    db_execute("INSERT INTO stok (urun_adi, miktar, birim, kategori, min_miktar, barkod, son_kullanma_tarihi, alis_fiyat, satis_fiyat, tedarikci, raf_no, kdv_oran) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                               (ad.strip(), miktar, birim, kategori, min_m, barkod, skt_str, alis, satis, tedarikci, raf_no, kdv))
                    hareket_ekle(st.session_state.current_user['kullanici_adi'], "Stok Ekle", ad.strip(), f"{miktar} {birim}")
                    mesaj_ekle(f"✅ {ad.strip()} eklendi")
                    st.rerun()
    with tab3:
        stoklar = db_fetchall("SELECT * FROM stok")
        if stoklar:
            sec = st.selectbox("Ürün Seç", [f"{u['urun_adi']} ({u['miktar']} {u['birim']})" for u in stoklar])
            idx = [f"{u['urun_adi']} ({u['miktar']} {u['birim']})" for u in stoklar].index(sec)
            urun = stoklar[idx]
            with st.form("duzenle_form"):
                ad = st.text_input("Ürün Adı", urun['urun_adi'])
                miktar = st.number_input("Miktar", value=float(urun['miktar']), format="%.2f")
                birim = st.selectbox("Birim", BIRIMLER, index=BIRIMLER.index(urun['birim']) if urun['birim'] in BIRIMLER else 0)
                kat = st.selectbox("Kategori", KATEGORILER, index=KATEGORILER.index(urun['kategori']) if urun['kategori'] in KATEGORILER else 0)
                alis = st.number_input("Alış Fiyatı", value=float(urun['alis_fiyat']), format="%.2f")
                satis = st.number_input("Satış Fiyatı", value=float(urun['satis_fiyat']), format="%.2f")
                submitted = st.form_submit_button("Güncelle")
                if submitted:
                    db_execute("UPDATE stok SET urun_adi=?, miktar=?, birim=?, kategori=?, alis_fiyat=?, satis_fiyat=? WHERE id=?",
                               (ad, miktar, birim, kat, alis, satis, urun['id']))
                    mesaj_ekle(f"✅ {ad} güncellendi")
                    st.rerun()
            if st.button("🗑️ Sil", key=f"sil_{urun['id']}"):
                db_execute("DELETE FROM stok WHERE id=?", (urun['id'],))
                mesaj_ekle("Ürün silindi")
                st.rerun()
        else:
            st.info("Ürün yok.")
    with tab4:
        st.subheader("Stok Sayım")
        sayim_barkod = st.text_input("Barkod okut")
        if sayim_barkod:
            urun = db_fetchone("SELECT * FROM stok WHERE barkod=?", (sayim_barkod,))
            if urun:
                st.success(f"{urun['urun_adi']} – Mevcut: {urun['miktar']} {urun['birim']}")
                yeni = st.number_input("Gerçek Miktar", value=float(urun['miktar']), format="%.2f")
                if st.button("Sayımı Kaydet"):
                    fark = yeni - urun['miktar']
                    db_execute("UPDATE stok SET miktar=? WHERE id=?", (yeni, urun['id']))
                    hareket_ekle(st.session_state.current_user['kullanici_adi'], "Sayım", urun['urun_adi'], f"Fark: {fark:+.2f}")
                    mesaj_ekle("Sayım kaydedildi")
                    st.rerun()
            else:
                st.warning("Barkod stokta yok.")

def tedarikci_sayfasi():
    st.markdown('<div class="main-header">🏭 Tedarikçi Yönetimi</div>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["📋 Liste","➕ Ekle/Düzenle"])
    with tab1:
        tedarikciler = db_fetchall("SELECT * FROM tedarikciler")
        if tedarikciler:
            for t in tedarikciler:
                col1, col2 = st.columns([4,1])
                col1.write(f"**{t['ad']}** – Güven: {t['guven_puani']:.1f} – Tel: {t['tel']} – E-posta: {t['eposta']}")
                if col2.button("Sil", key=f"t_sil_{t['id']}"):
                    db_execute("DELETE FROM tedarikciler WHERE id=?", (t['id'],))
                    mesaj_ekle("Tedarikçi silindi")
                    st.rerun()
        else:
            st.info("Tedarikçi yok.")
    with tab2:
        duzenle_idx = st.session_state.get("duzenlenecek_tedarikci")
        if duzenle_idx is not None:
            t = db_fetchone("SELECT * FROM tedarikciler WHERE id=?", (duzenle_idx,))
            st.info(f"✏️ **{t['ad']}** düzenleniyor")
        else:
            t = {"ad":"", "guven_puani":5.0, "tel":"", "eposta":""}
        with st.form("tedarikci_form"):
            ad = st.text_input("Firma Adı *", value=t['ad'])
            guven = st.slider("Güven (0-10)", 0.0, 10.0, float(t['guven_puani']))
            tel = st.text_input("Telefon (10 hane)")
            eposta = st.text_input("E-posta")
            btn = "💾 Güncelle" if duzenle_idx else "➕ Ekle"
            submitted = st.form_submit_button(btn)
            if submitted:
                if not ad.strip():
                    st.error("Ad zorunlu")
                else:
                    if duzenle_idx:
                        db_execute("UPDATE tedarikciler SET ad=?, guven_puani=?, tel=?, eposta=? WHERE id=?",
                                   (ad.strip(), guven, tel, eposta, duzenle_idx))
                        st.session_state.duzenlenecek_tedarikci = None
                    else:
                        db_execute("INSERT INTO tedarikciler (ad, guven_puani, tel, eposta) VALUES (?,?,?,?)",
                                   (ad.strip(), guven, tel, eposta))
                    mesaj_ekle(f"Tedarikçi '{ad.strip()}' kaydedildi")
                    st.rerun()

def siparis_sayfasi():
    st.markdown('<div class="main-header">🔥 Sipariş Panosu</div>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["📋 Liste","➕ Ekle"])
    with tab1:
        fireler = db_fetchall("SELECT * FROM fire")
        if fireler:
            for f in fireler:
                c1, c2, c3 = st.columns([3,1,1])
                renk = "🔴" if "Yüksek" in f['aciliyet'] else "🟡" if "Orta" in f['aciliyet'] else "🟢"
                c1.write(f"{renk} **{f['urun_adi']}** – {f['miktar']} {f['birim']} – {f['durum']}")
                if c2.button("🗑️", key=f"fire_sil_{f['id']}"):
                    db_execute("DELETE FROM fire WHERE id=?", (f['id'],))
                    st.rerun()
                if c3.button("📧", key=f"fire_mail_{f['id']}"):
                    tedarikci = db_fetchone("SELECT eposta FROM tedarikciler WHERE ad=?", (f['tedarikci'],))
                    if tedarikci and tedarikci['eposta']:
                        st.info(f"Sipariş e-postası gönderilecek: {tedarikci['eposta']}")
                        # gerçek gönderim burada
        else:
            st.info("Sipariş yok.")
    with tab2:
        with st.form("fire_ekle"):
            stok_urunler = db_fetchall("SELECT urun_adi, birim, tedarikci FROM stok")
            if stok_urunler:
                sec = st.selectbox("Ürün", [u['urun_adi'] for u in stok_urunler])
                urun_bilgi = next(u for u in stok_urunler if u['urun_adi'] == sec)
                miktar = st.number_input(f"Miktar ({urun_bilgi['birim']})", 0.01, format="%.2f")
                submitted = st.form_submit_button("Ekle")
                if submitted:
                    db_execute("INSERT INTO fire (urun_adi, miktar, birim, tedarikci, durum, eklenme_tarihi) VALUES (?,?,?,?,?,?)",
                               (sec, miktar, urun_bilgi['birim'], urun_bilgi['tedarikci'], "Bekliyor", datetime.now().strftime("%Y-%m-%d %H:%M")))
                    mesaj_ekle("Sipariş eklendi")
                    st.rerun()
            else:
                st.warning("Önce stok ekleyin.")

def stok_analizi():
    st.markdown('<div class="main-header">📈 Stok Analizi</div>', unsafe_allow_html=True)
    stoklar = db_fetchall("SELECT * FROM stok")
    if not stoklar: st.info("Ürün yok"); return
    df = pd.DataFrame(stoklar)
    df['kar_marji'] = df.apply(lambda r: ((r['satis_fiyat']-r['alis_fiyat'])/r['satis_fiyat']*100) if r['satis_fiyat']>0 else 0, axis=1)
    st.dataframe(df[['urun_adi','satis_fiyat','alis_fiyat','kar_marji']].style.format({'kar_marji':'{:.1f}%'}), use_container_width=True)
    st.subheader("Günlük Satış Hızları")
    for u in stoklar:
        hiz = urun_gunluk_satis_hizi(u['urun_adi'])
        st.write(f"{u['urun_adi']}: {hiz:.2f} {u['birim']}/gün")

def fire_analizi():
    st.markdown('<div class="main-header">📉 Fire Analizi</div>', unsafe_allow_html=True)
    fireler = db_fetchall("SELECT * FROM fire")
    if fireler:
        kat_fire = {}
        for f in fireler:
            stok = db_fetchone("SELECT kategori FROM stok WHERE urun_adi=?", (f['urun_adi'],))
            kat = stok['kategori'] if stok else "Diğer"
            kat_fire[kat] = kat_fire.get(kat,0) + f['miktar']
        fig = px.pie(names=list(kat_fire.keys()), values=list(kat_fire.values()), title="Kategori Bazlı Fire", hole=0.3)
        st.plotly_chart(fig)
    else:
        st.info("Fire kaydı yok.")

def satis_raporu():
    st.markdown('<div class="main-header">📊 Satış Raporu</div>', unsafe_allow_html=True)
    satislar = db_fetchall("SELECT * FROM satislar")
    if not satislar: st.info("Satış yok"); return
    df = pd.DataFrame(satislar)
    df['tarih'] = pd.to_datetime(df['tarih'])
    df['gun'] = df['tarih'].dt.date
    c1, c2 = st.columns(2)
    with c1: bas = st.date_input("Başlangıç", df['gun'].min())
    with c2: bit = st.date_input("Bitiş", df['gun'].max())
    df = df[(df['gun'] >= bas) & (df['gun'] <= bit)]
    tip = st.radio("Kırılım", ["Günlük","Ürün Bazlı"], horizontal=True)
    if tip == "Günlük":
        rpr = df.groupby('gun')['toplam_tutar'].sum().reset_index()
        fig = px.bar(rpr, x='gun', y='toplam_tutar')
        st.plotly_chart(fig)
    else:
        rpr = df.groupby('urun_adi').agg(Adet=('miktar','sum'), Ciro=('toplam_tutar','sum')).reset_index()
        st.dataframe(rpr)

def aktivite_logu():
    st.markdown('<div class="main-header">📋 Aktivite Logu</div>', unsafe_allow_html=True)
    hareketler = db_fetchall("SELECT * FROM hareketler ORDER BY tarih DESC LIMIT 200")
    if hareketler:
        df = pd.DataFrame(hareketler)
        st.dataframe(df)
    else:
        st.info("Log boş.")

def kasa_kapanisi():
    st.markdown('<div class="main-header">🧾 Günlük Kasa Kapanışı</div>', unsafe_allow_html=True)
    bugun = datetime.now().strftime("%Y-%m-%d")
    satislar = db_fetchall("SELECT * FROM satislar WHERE tarih LIKE ?", (bugun+'%',))
    if not satislar: st.info("Bugün satış yok"); return
    df = pd.DataFrame(satislar)
    toplam = df['toplam_tutar'].sum()
    st.dataframe(df[['urun_adi','miktar','birim_fiyat','toplam_tutar']])
    st.metric("Toplam Satış", f"{toplam:.2f} TL")
    st.metric("Net Kâr", f"{gunluk_kar(bugun):.2f} TL")
    if 'odeme_tipi' in df.columns:
        for kanal, tutar in df.groupby('odeme_tipi')['toplam_tutar'].sum().items():
            st.metric(f"💳 {kanal}", f"{tutar:,.2f} TL")

def kullanici_yonetimi():
    st.markdown('<div class="main-header">👥 Kullanıcı Yönetimi</div>', unsafe_allow_html=True)
    with st.form("kullanici_ekle"):
        kul = st.text_input("Kullanıcı Adı")
        sifre = st.text_input("Şifre", type="password")
        rol = st.selectbox("Rol", list(ROLLER.keys()))
        ad = st.text_input("Ad Soyad")
        submitted = st.form_submit_button("Ekle")
        if submitted:
            if kul and sifre:
                db_execute("INSERT INTO kullanicilar (kullanici_adi, sifre_hash, rol, ad) VALUES (?,?,?,?)",
                           (kul, hash_sifre(sifre), rol, ad))
                mesaj_ekle(f"{kul} eklendi")
                st.rerun()
            else:
                st.error("Boş bırakılamaz")
    # Listeleme
    kullanicilar = db_fetchall("SELECT * FROM kullanicilar")
    if kullanicilar:
        st.dataframe(pd.DataFrame(kullanicilar))

def sifre_sifirla():
    st.markdown('<div class="main-header">🔑 Şifre Sıfırla</div>', unsafe_allow_html=True)
    with st.form("sifre_sifirla"):
        eski = st.text_input("Eski Şifre", type="password")
        yeni = st.text_input("Yeni Şifre", type="password")
        yeni2 = st.text_input("Yeni Şifre Tekrar", type="password")
        submitted = st.form_submit_button("Sıfırla")
        if submitted:
            user = st.session_state.current_user
            if hash_sifre(eski) != user['sifre_hash']:
                st.error("Eski şifre yanlış")
            elif yeni != yeni2:
                st.error("Şifreler eşleşmiyor")
            else:
                db_execute("UPDATE kullanicilar SET sifre_hash=? WHERE kullanici_adi=?",
                           (hash_sifre(yeni), user['kullanici_adi']))
                mesaj_ekle("Şifre değiştirildi, tekrar giriş yapın")
                st.session_state.authenticated = False
                st.rerun()

def geri_bildirim():
    st.markdown('<div class="main-header">💬 Geri Bildirim</div>', unsafe_allow_html=True)
    with st.form("geribildirim"):
        konu = st.text_input("Konu")
        mesaj = st.text_area("Mesaj")
        if st.form_submit_button("Gönder"):
            logging.info(f"Geri Bildirim: {konu} - {mesaj}")
            mesaj_ekle("Teşekkürler!")

def ayarlar_sayfasi():
    st.markdown('<div class="main-header">⚙️ Ayarlar</div>', unsafe_allow_html=True)
    eposta = st.text_input("Patron E-posta", value=st.session_state.get("patron_email",""))
    telefon = st.text_input("Patron Telefon", value=st.session_state.get("patron_telefon",""))
    if st.button("Kaydet"):
        st.session_state.patron_email = eposta
        st.session_state.patron_telefon = telefon
        mesaj_ekle("Ayarlar kaydedildi")

def yedekleme_sayfasi():
    st.markdown('<div class="main-header">💾 Yedekleme</div>', unsafe_allow_html=True)
    # SQLite dosyasını indir
    with open("market.db", "rb") as f:
        st.download_button("📥 Veritabanını İndir", f, "market.db")
    # JSON yedek (isteğe bağlı)
    yedek = {
        "stok": db_fetchall("SELECT * FROM stok"),
        "fire": db_fetchall("SELECT * FROM fire"),
        "barkod": db_fetchall("SELECT * FROM barkod_db"),
        "tedarikciler": db_fetchall("SELECT * FROM tedarikciler")
    }
    st.download_button("📥 JSON İndir", json.dumps(yedek, ensure_ascii=False, indent=2), "yedek.json")

# Sayfa haritası
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

# Yetki kontrolü
def izinli_sayfalar(kullanici):
    if not kullanici: return {}
    rol = kullanici.get("rol","")
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

def main():
    st.set_page_config(page_title="Market Yönetim", page_icon="🏪", layout="wide", initial_sidebar_state="expanded")
    oturumu_baslat()
    enerjik_css(st.session_state.tema)
    oturum_kontrol()

    if not st.session_state.authenticated:
        # Giriş ekranı
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            st.markdown('<h1 style="text-align:center; background:linear-gradient(135deg,#F97316,#8B5CF6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;">🏪 Market Yönetim</h1>', unsafe_allow_html=True)
            with st.form("giris_form"):
                kullanici = st.text_input("👤 Kullanıcı Adı")
                sifre = st.text_input("🔒 Şifre", type="password")
                if st.form_submit_button("🚀 Giriş Yap", use_container_width=True):
                    user = giris_kontrol(kullanici, sifre)
                    if user:
                        st.session_state.authenticated = True
                        st.session_state.current_user = user
                        st.session_state.last_activity = datetime.now()
                        st.rerun()
                    else:
                        st.error("Hatalı kullanıcı adı veya şifre")
        return

    # Başarı mesajları
    for m in st.session_state.son_islem_mesajlari:
        st.success(m)
    st.session_state.son_islem_mesajlari = []

    with st.sidebar:
        st.markdown('<h2 style="color:white;">🏪 Market</h2>', unsafe_allow_html=True)
        st.selectbox("Tema", ["Koyu","Aydınlık"], index=0 if st.session_state.tema=="Koyu" else 1, key="tema_secimi", on_change=tema_degistir)
        aktif = izinli_sayfalar(st.session_state.current_user)
        sayfa = st.radio("Menü", list(aktif.keys()), label_visibility="collapsed")
        if st.button("🚪 Çıkış", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.current_user = None
            st.rerun()

    # POS modu kontrolü
    if st.session_state.get("pos_modu") and sayfa == "💵 Satış":
        pos_modu()
    else:
        aktif[sayfa]()

if __name__ == "__main__":
    main()
