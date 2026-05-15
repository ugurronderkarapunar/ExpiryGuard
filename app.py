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
import io
import re
import json
from PIL import Image
import numpy as np
import cv2

# Barkod okuma için pyzbar
try:
    from pyzbar.pyzbar import decode as pyzbar_decode
    BARCODE_OK = True
except ImportError:
    BARCODE_OK = False
    st.error("pyzbar yüklü değil. Lütfen `pip install pyzbar` yapın.")

# PDF için fpdf2
from fpdf import FPDF

# WhatsApp (opsiyonel)
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

# ---------- VERİTABANI ----------
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
    cur = db.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS stok (
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
        tahmini_gunluk_satis REAL DEFAULT 1.0,
        birim_orani REAL DEFAULT 1.0
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS fire (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        urun_adi TEXT NOT NULL,
        miktar REAL DEFAULT 0,
        birim TEXT DEFAULT 'adet',
        aciliyet TEXT DEFAULT 'Orta',
        tedarikci TEXT DEFAULT '',
        durum TEXT DEFAULT 'Bekliyor',
        eklenme_tarihi TEXT DEFAULT ''
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS satislar (
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
    cur.execute('''CREATE TABLE IF NOT EXISTS hareketler (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tarih TEXT NOT NULL,
        kullanici TEXT,
        islem TEXT,
        urun_adi TEXT,
        detay TEXT
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS barkod_db (
        barkod TEXT PRIMARY KEY,
        urun_adi TEXT,
        birim TEXT,
        kategori TEXT,
        uretici TEXT DEFAULT ''
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS tedarikciler (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ad TEXT UNIQUE,
        guven_puani REAL DEFAULT 5.0,
        tel TEXT DEFAULT '',
        eposta TEXT DEFAULT ''
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS kullanicilar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kullanici_adi TEXT UNIQUE,
        sifre_hash TEXT,
        rol TEXT,
        ad TEXT
    )''')
    try:
        cur.execute("ALTER TABLE stok ADD COLUMN birim_orani REAL DEFAULT 1.0")
    except: pass
    db.commit()

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

def ilk_kurulum():
    init_db()
    if not db_fetchall("SELECT * FROM kullanicilar"):
        admin_hash = hashlib.sha256("1234".encode()).hexdigest()
        db_execute("INSERT INTO kullanicilar (kullanici_adi, sifre_hash, rol, ad) VALUES (?,?,?,?)",
                   ("admin", admin_hash, "patron", "Admin"))
    if not db_fetchall("SELECT * FROM barkod_db"):
        ornek = [
            ("8691234567890", "Un", "kg", "Kuru Gıda", "ABC Un"),
            ("8691234567891", "Şeker", "kg", "Kuru Gıda", "XYZ Şeker"),
            ("8691234567892", "Süt", "litre", "Süt Ürünleri", "Sütaş"),
            ("8691234567893", "Yumurta", "adet", "Diğer", "Köy Yumurtası"),
            ("8691234567894", "Tereyağı", "kg", "Süt Ürünleri", "Sütaş")
        ]
        for b in ornek:
            db_execute("INSERT INTO barkod_db (barkod, urun_adi, birim, kategori, uretici) VALUES (?,?,?,?,?)", b)

# ---------- AUTH ----------
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

# ---------- YARDIMCILAR ----------
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
        .indirim-box {{
            background: #1a1f35; border: 2px solid #F97316;
            border-radius: 15px; padding: 15px; margin: 10px 0;
        }}
        @media (max-width: 768px) {{
            .main-header {{ font-size: 1.4rem !important; }}
            .stButton > button {{ width: 100% !important; }}
        }}
    </style>
    """, unsafe_allow_html=True)

# PDF
FONT_PATH = None
def get_font_path():
    global FONT_PATH
    if FONT_PATH: return FONT_PATH
    paths = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "DejaVuSans.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/DejaVuSans.ttf",
        "/System/Library/Fonts/DejaVuSans.ttf",
        "/usr/local/share/fonts/DejaVuSans.ttf",
        "./DejaVuSans.ttf",
    ]
    for p in paths:
        if os.path.exists(p):
            FONT_PATH = p
            return p
    return None

def _pdf_bytes(pdf: FPDF) -> bytes:
    try:
        return pdf.output(dest='S').encode('latin-1')
    except:
        buf = io.BytesIO()
        pdf.output(buf)
        return buf.getvalue()

def _pdf_setup(pdf, boyut=10):
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
    pdf.cell(80,10,txt="ALISVERIS FISI", ln=True, align='C')
    pdf.ln(5)
    pdf.set_font(fn, size=8)
    pdf.cell(80,6,txt=f"Tarih: {datetime.now().strftime('%d.%m.%Y %H:%M')}", ln=True, align='C')
    pdf.ln(5)
    pdf.set_font(fn, size=10)
    pdf.cell(50,8,txt="Urun:"); pdf.cell(30,8,txt=str(urun_adi)[:20], ln=True)
    pdf.cell(50,8,txt="Miktar:"); pdf.cell(30,8,txt=f"{miktar} {birim}", ln=True)
    pdf.cell(50,8,txt="Birim Fiyat:"); pdf.cell(30,8,txt=f"{birim_fiyat:.2f} TL", ln=True)
    pdf.ln(3)
    pdf.set_font(fn, size=12)
    pdf.cell(50,10,txt="TOPLAM:"); pdf.cell(30,10,txt=f"{toplam_tutar:.2f} TL", ln=True)
    pdf.set_font(fn, size=8)
    pdf.cell(50,6,txt=f"Odeme: {odeme_tipi}", ln=True)
    pdf.ln(5)
    pdf.cell(80,6,txt="Iyi gunlerde kullanin!", ln=True, align='C')
    return _pdf_bytes(pdf)

# ---------- BARKOD OKUMA ----------
def barkod_oku(image_bytes):
    if not BARCODE_OK:
        st.error("pyzbar kütüphanesi yüklü değil.")
        return None
    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
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
        bag = smtplib.SMTP(smtp, port)
        bag.starttls(context=ssl.create_default_context())
        bag.login(gonderen, sifre)
        bag.sendmail(gonderen, alici, msg.as_string())
        bag.quit()
        return True
    except: return False

def whatsapp_gonder(no, mesaj):
    if not WHATSAPP_AKTIF: return False
    try:
        now = datetime.now()
        h, m = now.hour, now.minute+2
        if m>=60: h+=1; m-=60
        pwk.sendwhatmsg(no, mesaj, h, m, wait_time=15, tab_close=True)
        return True
    except: return False

# ---------- AKTİVİTE LOG ----------
def hareket_ekle(kul, islem, ad, detay=""):
    tarih = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db_execute("INSERT INTO hareketler (tarih, kullanici, islem, urun_adi, detay) VALUES (?,?,?,?,?)",
               (tarih, kul, islem, ad, detay))

# ---------- SATIŞ ----------
def satis_kaydet(urun_adi, birim, miktar, fiyat, toplam, kullanici, alis_fiyat, odeme):
    sid = str(uuid.uuid4())[:8]
    tarih = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    maliyet = round(miktar * alis_fiyat, 2)
    db_execute("INSERT INTO satislar (id, tarih, kullanici, urun_adi, birim, miktar, birim_fiyat, toplam_tutar, alis_fiyat, maliyet, odeme_tipi) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
               (sid, tarih, kullanici, urun_adi, birim, miktar, fiyat, toplam, alis_fiyat, maliyet, odeme))

@st.cache_data(ttl=60)
def gunluk_ciro(tarih_str):
    satislar = db_fetchall("SELECT toplam_tutar FROM satislar WHERE tarih LIKE ?", (tarih_str+'%',))
    return sum(s['toplam_tutar'] for s in satislar)

@st.cache_data(ttl=60)
def gunluk_kar(tarih_str=None):
    if tarih_str is None: tarih_str = datetime.now().strftime("%Y-%m-%d")
    satislar = db_fetchall("SELECT toplam_tutar, maliyet FROM satislar WHERE tarih LIKE ?", (tarih_str+'%',))
    return sum(s['toplam_tutar'] - s.get('maliyet',0) for s in satislar)

# ---------- SATIŞ HIZI VE İNDİRİM ----------
def urun_gunluk_satis_hizi(urun_adi):
    bitis = datetime.now()
    baslangic = bitis - timedelta(days=30)
    rows = db_fetchall(
        "SELECT miktar FROM satislar WHERE urun_adi = ? AND tarih >= ? AND tarih <= ?",
        (urun_adi, baslangic.strftime("%Y-%m-%d"), bitis.strftime("%Y-%m-%d %H:%M:%S"))
    )
    if not rows:
        stok = db_fetchone("SELECT tahmini_gunluk_satis FROM stok WHERE urun_adi = ?", (urun_adi,))
        return stok['tahmini_gunluk_satis'] if stok else 1.0
    return sum(r['miktar'] for r in rows) / len(rows)

def bilimsel_indirim_hesapla(urun):
    try:
        skt_str = urun.get('son_kullanma_tarihi','')
        if not skt_str:
            return 0, urun['satis_fiyat']
        skt = datetime.strptime(skt_str, "%Y-%m-%d")
        kalan_gun = (skt - datetime.now()).days
    except:
        return 0, urun['satis_fiyat']

    q = urun['miktar']
    satis_fiyat = urun['satis_fiyat']
    alis_fiyat  = urun['alis_fiyat']
    birim_orani = urun.get('birim_orani', 1.0) or 1.0

    if satis_fiyat <= 0 or q <= 0:
        return 0, satis_fiyat

    toplam_adet = q * birim_orani
    marj = (satis_fiyat - alis_fiyat) / satis_fiyat if satis_fiyat > 0 else 0
    v = urun_gunluk_satis_hizi(urun['urun_adi'])
    beklenen_satis = v * max(kalan_gun, 0)
    stok_fazlasi = toplam_adet - beklenen_satis
    if stok_fazlasi <= 0:
        return 0, satis_fiyat

    indirim = (stok_fazlasi / toplam_adet) * marj * 100
    max_indirim = marj * 100 * 0.8
    indirim = min(indirim, max_indirim)

    if kalan_gun <= 1:
        indirim = max(indirim, marj * 100 * 0.5)
    elif kalan_gun <= 3:
        indirim = max(indirim, marj * 100 * 0.2)

    indirim = min(indirim, 50)
    indirim = max(indirim, 0)

    indirimli_fiyat = satis_fiyat * (1 - indirim/100)
    return round(indirim,1), round(indirimli_fiyat, 2)

# ---------- SAYFALAR ----------
def ana_sayfa():
    st.markdown('<div class="main-header">📊 Yönetim Paneli</div>', unsafe_allow_html=True)
    stoklar = db_fetchall("SELECT * FROM stok WHERE son_kullanma_tarihi != ''")
    yaklasan = []
    for u in stoklar:
        try:
            skt = datetime.strptime(u['son_kullanma_tarihi'], "%Y-%m-%d")
            kalan = (skt - datetime.now()).days
            if 0 <= kalan <= SKT_UYARI_GUN:
                indirim, ind_fiyat = bilimsel_indirim_hesapla(u)
                yaklasan.append((u, kalan, indirim, ind_fiyat))
        except: pass

    if yaklasan:
        st.error("⏳ Son kullanma tarihi yaklaşan ürünler (önerilen indirim):")
        for urun, gun, ind, fiyat in yaklasan:
            col1, col2, col3 = st.columns([3,2,1])
            col1.write(f"• **{urun['urun_adi']}** – {gun} gün kaldı")
            col2.write(f"🔥 Önerilen: %{ind} → {fiyat} TL/adet")
            if col3.button("İndirimi Uygula", key=f"ana_ind_{urun['id']}"):
                db_execute("UPDATE stok SET satis_fiyat=? WHERE id=?", (fiyat, urun['id']))
                mesaj_ekle(f"{urun['urun_adi']} fiyatı {fiyat} TL olarak güncellendi")
                st.rerun()

    kritik = [u for u in stoklar if u['min_miktar'] > 0 and u['miktar'] <= u['min_miktar']]
    if kritik:
        st.warning("🚨 Kritik stok:")
        for u in kritik:
            st.write(f"• {u['urun_adi']} – {u['miktar']} {u['birim']} / Min: {u['min_miktar']}")

    bugun = datetime.now().strftime("%Y-%m-%d")
    dun = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    bg_ciro = gunluk_ciro(bugun)
    dn_ciro = gunluk_ciro(dun)
    kar = gunluk_kar(bugun)
    delta = bg_ciro - dn_ciro
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Bugünkü Ciro", f"{bg_ciro:,.0f} TL", delta=f"{delta:+,.0f} TL")
    col2.metric("Bugünkü Kâr",  f"{kar:,.0f} TL")
    col3.metric("Dünkü Ciro",   f"{dn_ciro:,.0f} TL")
    hafta_bas = datetime.now().date() - timedelta(days=datetime.now().weekday())
    haftalik = sum(s['toplam_tutar'] for s in db_fetchall(
        "SELECT toplam_tutar FROM satislar WHERE tarih >= ? AND tarih <= ?",
        (hafta_bas.strftime("%Y-%m-%d"), (hafta_bas+timedelta(days=6)).strftime("%Y-%m-%d 23:59:59"))))
    col4.metric("Bu Hafta", f"{haftalik:,.0f} TL")

def barkod_yonetimi():
    st.markdown('<div class="main-header">🏷️ Barkod Yönetimi</div>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["📋 Liste","➕ Yeni"])
    with tab1:
        barkodlar = db_fetchall("SELECT * FROM barkod_db")
        if barkodlar:
            arama = st.text_input("🔍 Ara")
            df = pd.DataFrame(barkodlar)
            if arama:
                df = df[df['barkod'].str.contains(arama, case=False) | df['urun_adi'].str.contains(arama, case=False)]
            st.dataframe(df, use_container_width=True)
        else:
            st.info("Veritabanı boş.")
    with tab2:
        with st.form("yeni_barkod"):
            bk = st.text_input("Barkod")
            ad = st.text_input("Ürün Adı")
            br = st.selectbox("Birim", BIRIMLER)
            kt = st.selectbox("Kategori", KATEGORILER)
            if st.form_submit_button("Ekle"):
                if bk and ad:
                    db_execute("INSERT OR IGNORE INTO barkod_db (barkod, urun_adi, birim, kategori) VALUES (?,?,?,?)",
                               (bk, ad, br, kt))
                    mesaj_ekle(f"{ad} eklendi"); st.rerun()
                else: st.error("Barkod ve ad zorunlu")

def barkod_sayfasi():
    st.markdown('<div class="main-header">📱 Barkod Okuma ve SKT İndirim</div>', unsafe_allow_html=True)

    img_file = st.camera_input("📷 Barkodu gösterip fotoğraf çekin", key="barkod_kamera")

    barkod = None
    if img_file:
        with st.spinner("Barkod okunuyor..."):
            barkod = barkod_oku(img_file.getvalue())
        if not barkod:
            st.error("Fotoğrafta barkod bulunamadı, lütfen daha net çekin.")

    if not barkod:
        st.info("📷 Kamera açık, barkodu gösterip alttaki butona tıklayarak fotoğraf çekin.")
        return

    st.success(f"✅ Okunan: {barkod}")
    bilgi = db_fetchone("SELECT * FROM barkod_db WHERE barkod=?", (barkod,))
    urun_adi = bilgi['urun_adi'] if bilgi else ""
    birim = bilgi['birim'] if bilgi else "adet"
    kategori = bilgi['kategori'] if bilgi else "Diğer"

    stok_urun = db_fetchone("SELECT * FROM stok WHERE barkod=?", (barkod,))
    skt_mevcut = stok_urun['son_kullanma_tarihi'] if stok_urun and stok_urun['son_kullanma_tarihi'] else ""
    if skt_mevcut:
        try:
            skt_date = datetime.strptime(skt_mevcut, "%Y-%m-%d")
            kalan = (skt_date - datetime.now()).days
            if kalan < 0:
                st.error(f"⚠️ Bu ürünün SKT'si geçmiş! ({skt_mevcut})")
            elif kalan <= SKT_UYARI_GUN:
                st.warning(f"⏳ SKT yaklaşıyor: {kalan} gün kaldı ({skt_mevcut})")
                if stok_urun:
                    indirim, ind_fiyat = bilimsel_indirim_hesapla(stok_urun)
                    if indirim > 0:
                        st.markdown(f"""
                        <div class="indirim-box">
                            <h3 style="color:#F97316;">🔥 İndirim Önerisi</h3>
                            <p>Mevcut Satış Fiyatı: <b>{stok_urun['satis_fiyat']:.2f} TL</b></p>
                            <p>Önerilen İndirim: <b>%{indirim}</b></p>
                            <p>İndirimli Fiyat: <b>{ind_fiyat:.2f} TL</b></p>
                        </div>
                        """, unsafe_allow_html=True)
                        if st.button(f"📌 İndirimi Uygula (%{indirim} → {ind_fiyat} TL)", key=f"ind_{barkod}"):
                            db_execute("UPDATE stok SET satis_fiyat=? WHERE barkod=?", (ind_fiyat, barkod))
                            mesaj_ekle(f"{stok_urun['urun_adi']} için satış fiyatı {ind_fiyat} TL olarak güncellendi")
                            st.rerun()
            else:
                st.info(f"📅 SKT: {skt_mevcut} ( {kalan} gün var)")
        except: pass

    if urun_adi:
        st.info(f"📦 **{guvenli_html(urun_adi)}** ({birim}) – Kategori: {kategori}")
    else:
        st.warning("Yeni barkod. Ürün bilgilerini girin.")

    skt_guncelle = st.checkbox("SKT güncelle", value=False)

    with st.form("barkod_islem_form", clear_on_submit=True):
        ad = st.text_input("Ürün Adı *", value=urun_adi)
        miktar = st.number_input(f"Miktar ({birim})", 0.01, format="%.2f", value=1.0)
        bir = st.selectbox("Birim", BIRIMLER, index=BIRIMLER.index(birim) if birim in BIRIMLER else 0)
        kat = st.selectbox("Kategori", KATEGORILER, index=KATEGORILER.index(kategori) if kategori in KATEGORILER else 0)
        islem = st.radio("İşlem", ["📥 Giriş","📤 Çıkış"], horizontal=True)

        varsayilan_tarih = datetime.strptime(skt_mevcut, "%Y-%m-%d") if skt_mevcut else datetime.now()
        if skt_guncelle:
            yeni_skt = st.date_input("Son Kullanma Tarihi", value=varsayilan_tarih)
        else:
            if skt_mevcut:
                st.caption(f"Mevcut SKT: {skt_mevcut}")
            yeni_skt = None

        submitted = st.form_submit_button("💾 Kaydet")
        if submitted:
            if not ad.strip():
                st.error("Ürün adı zorunlu")
                return
            if not db_fetchone("SELECT barkod FROM barkod_db WHERE barkod=?", (barkod,)):
                db_execute("INSERT INTO barkod_db (barkod, urun_adi, birim, kategori) VALUES (?,?,?,?)",
                           (barkod, ad.strip(), bir, kat))
            gercek = miktar if islem == "📥 Giriş" else -miktar
            if stok_urun:
                yeni_miktar = max(0, stok_urun['miktar'] + gercek)
                skt_sql = yeni_skt.strftime("%Y-%m-%d") if skt_guncelle and yeni_skt else stok_urun['son_kullanma_tarihi']
                db_execute("UPDATE stok SET miktar=?, son_kullanma_tarihi=?, urun_adi=?, birim=?, kategori=? WHERE barkod=?",
                           (yeni_miktar, skt_sql, ad.strip(), bir, kat, barkod))
            else:
                if gercek > 0:
                    skt_sql = yeni_skt.strftime("%Y-%m-%d") if skt_guncelle and yeni_skt else ""
                    db_execute("INSERT INTO stok (urun_adi, miktar, birim, kategori, barkod, son_kullanma_tarihi) VALUES (?,?,?,?,?,?)",
                               (ad.strip(), gercek, bir, kat, barkod, skt_sql))
            hareket_ekle(st.session_state.current_user['kullanici_adi'], islem, ad.strip(), f"{miktar} {bir}")
            mesaj_ekle(f"{ad.strip()} güncellendi")
            st.rerun()

def satis_sayfasi():
    st.markdown('<div class="main-header">💰 Satış</div>', unsafe_allow_html=True)
    urunler = db_fetchall("SELECT * FROM stok WHERE miktar > 0")
    if not urunler:
        st.warning("Satılacak ürün yok")
        return

    secenekler = [f"{u['urun_adi']} (Stok: {u['miktar']} {u['birim']}, Birim Fiyat: {u['satis_fiyat']:.2f} TL/adet)" for u in urunler]
    sec = st.selectbox("Ürün Seç", secenekler)
    urun = urunler[secenekler.index(sec)]

    stok_birimi = urun['birim']
    birim_orani = urun.get('birim_orani', 1.0) or 1.0

    st.info(f"**{urun['urun_adi']}** | Stok: {urun['miktar']} {stok_birimi} | 1 {stok_birimi} = {birim_orani} adet | Adet Fiyatı: {urun['satis_fiyat']:.2f} TL")

    # SKT kontrolü ve indirim önerisi
    skt_mevcut = urun.get('son_kullanma_tarihi','')
    if skt_mevcut:
        try:
            skt_date = datetime.strptime(skt_mevcut, "%Y-%m-%d")
            kalan = (skt_date - datetime.now()).days
            if 0 <= kalan <= SKT_UYARI_GUN:
                indirim, ind_fiyat = bilimsel_indirim_hesapla(urun)
                if indirim > 0:
                    st.warning(f"⏳ Bu ürünün SKT'sine {kalan} gün kaldı!")
                    st.markdown(f"""
                    <div class="indirim-box">
                        <h3 style="color:#F97316;">🔥 İndirim Önerisi</h3>
                        <p>Önerilen İndirim: <b>%{indirim}</b></p>
                        <p>İndirimli Fiyat: <b>{ind_fiyat:.2f} TL/adet</b></p>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button(f"📌 İndirimi Uygula (%{indirim} → {ind_fiyat} TL)", key=f"satis_ind_{urun['id']}"):
                        db_execute("UPDATE stok SET satis_fiyat=? WHERE id=?", (ind_fiyat, urun['id']))
                        mesaj_ekle(f"{urun['urun_adi']} fiyatı {ind_fiyat} TL olarak güncellendi")
                        st.rerun()
        except: pass

    birim_secenekleri = [stok_birimi, "adet"]
    satis_birimi = st.radio("Satış Birimi", birim_secenekleri, horizontal=True)

    if satis_birimi == stok_birimi:
        max_miktar = urun['miktar']
        miktar = st.number_input(f"Miktar ({stok_birimi})", 0.01, float(max_miktar), format="%.2f", value=1.0)
        stok_dusecek = miktar
        birim_fiyat = urun['satis_fiyat'] * birim_orani
    else:
        toplam_adet = urun['miktar'] * birim_orani
        miktar = st.number_input("Miktar (adet)", 0.01, float(toplam_adet), format="%.2f", value=1.0)
        stok_dusecek = miktar / birim_orani
        birim_fiyat = urun['satis_fiyat']

    toplam_tutar = miktar * birim_fiyat
    odeme = st.selectbox("Ödeme", ["Nakit","Kredi Kartı","Havale/EFT"])
    st.markdown(f"### Toplam: {toplam_tutar:.2f} TL")

    if st.button("Satış Yap", use_container_width=True):
        if miktar <= 0:
            st.error("Geçersiz miktar")
        else:
            yeni_miktar = urun['miktar'] - stok_dusecek
            db_execute("UPDATE stok SET miktar=? WHERE id=?", (max(0, yeni_miktar), urun['id']))
            satis_kaydet(urun['urun_adi'], satis_birimi, miktar, birim_fiyat, toplam_tutar,
                         st.session_state.current_user['kullanici_adi'], urun['alis_fiyat'], odeme)
            hareket_ekle(st.session_state.current_user['kullanici_adi'], "Satış", urun['urun_adi'],
                         f"{miktar} {satis_birimi}")
            mesaj_ekle(f"Satış: {toplam_tutar:.2f} TL")
            st.rerun()

def pos_modu():
    st.markdown('<div class="main-header">🛒 Hızlı POS</div>', unsafe_allow_html=True)
    if "pos_sepet" not in st.session_state:
        st.session_state.pos_sepet = {}

    img_file = st.camera_input("📷 Barkodu tarat", key="pos_kamera")
    if img_file:
        barkod = barkod_oku(img_file.getvalue())
        if barkod:
            urun = db_fetchone("SELECT * FROM stok WHERE barkod=? AND miktar>0", (barkod,))
            if urun:
                st.session_state.pos_sepet[barkod] = st.session_state.pos_sepet.get(barkod, 0) + 1
                mesaj_ekle(f"{urun['urun_adi']} sepete eklendi")
            else:
                st.error("Ürün bulunamadı veya stok yok")
        else:
            st.error("Barkod okunamadı")
        st.rerun()

    if st.session_state.pos_sepet:
        toplam = 0
        for bk, adet in list(st.session_state.pos_sepet.items()):
            urun = db_fetchone("SELECT * FROM stok WHERE barkod=?", (bk,))
            if urun:
                birim_orani = urun.get('birim_orani', 1.0) or 1.0
                fiyat = urun['satis_fiyat']
                tutar = fiyat * adet
                toplam += tutar
                c1,c2,c3 = st.columns([3,1,1])
                c1.write(f"📦 {urun['urun_adi']} – {adet} adet x {fiyat:.2f} TL = {tutar:.2f} TL")
                yeni = c2.number_input("Adet", 1, value=adet, key=f"pos_{bk}")
                if yeni != adet:
                    st.session_state.pos_sepet[bk] = yeni; st.rerun()
                if c3.button("🗑️", key=f"sil_{bk}"):
                    del st.session_state.pos_sepet[bk]; st.rerun()
        st.markdown(f"### Toplam: {toplam:.2f} TL")
        if st.button("Satışı Tamamla", type="primary"):
            for bk, adet in st.session_state.pos_sepet.items():
                urun = db_fetchone("SELECT * FROM stok WHERE barkod=?", (bk,))
                if urun and urun['miktar'] * urun.get('birim_orani', 1.0) >= adet:
                    stok_dusecek = adet / urun.get('birim_orani', 1.0)
                    db_execute("UPDATE stok SET miktar = miktar - ? WHERE barkod=?", (stok_dusecek, bk))
                    satis_kaydet(urun['urun_adi'], "adet", adet, urun['satis_fiyat'],
                                 adet*urun['satis_fiyat'], st.session_state.current_user['kullanici_adi'],
                                 urun['alis_fiyat'], "Nakit")
            st.session_state.pos_sepet = {}
            mesaj_ekle(f"Satış tamamlandı: {toplam:.2f} TL")
            st.rerun()
    if st.button("POS Modundan Çık"):
        st.session_state.pos_modu = False; st.rerun()

def stok_sayfasi():
    st.markdown('<div class="main-header">📦 Stok Yönetimi</div>', unsafe_allow_html=True)
    tab1, tab2, tab3, tab4 = st.tabs(["📋 Liste","➕ Ekle","✏️ Düzenle/Sil","🔢 Sayım"])
    with tab1:
        arama = st.text_input("🔍 Ara")
        stok = db_fetchall("SELECT * FROM stok")
        df = pd.DataFrame(stok)
        if arama:
            df = df[df['urun_adi'].str.contains(arama, case=False) | df['barkod'].astype(str).str.contains(arama)]
        if not df.empty:
            df['önerilen_indirim'] = df.apply(lambda r: f"%{bilimsel_indirim_hesapla(r)[0]}" if r.get('son_kullanma_tarihi') else "-", axis=1)
        st.dataframe(df, use_container_width=True)
    with tab2:
        skt_var = st.checkbox("SKT var")
        with st.form("stok_ekle", clear_on_submit=True):
            barkod = st.text_input("Barkod")
            bilgi = db_fetchone("SELECT * FROM barkod_db WHERE barkod=?", (barkod,)) if barkod else None
            ad = st.text_input("Ürün Adı *", value=bilgi['urun_adi'] if bilgi else "")
            miktar = st.number_input("Miktar", 0.0, format="%.2f", value=1.0)
            birim = st.selectbox("Birim", BIRIMLER, index=BIRIMLER.index(bilgi['birim']) if bilgi and bilgi['birim'] in BIRIMLER else 0)
            kategori = st.selectbox("Kategori", KATEGORILER, index=KATEGORILER.index(bilgi['kategori']) if bilgi and bilgi['kategori'] in KATEGORILER else 0)
            alis = st.number_input("Alış Fiyatı (adet başına)", 0.0, format="%.2f")
            satis = st.number_input("Satış Fiyatı (adet başına)", 0.0, format="%.2f")
            birim_orani = st.number_input(f"1 {birim} kaç adet?", min_value=1.0, value=1.0, step=1.0)
            min_m = st.number_input("Min Stok", 0.0, value=5.0)
            raf = st.text_input("Raf No")
            tedarik = st.selectbox("Tedarikçi", ["Yok"]+[t['ad'] for t in db_fetchall("SELECT ad FROM tedarikciler")])
            kdv = st.selectbox("KDV (%)", [1,8,10,18,20], index=1)

            skt_str = ""
            if skt_var:
                skt = st.date_input("SKT", value=datetime.now())
                skt_str = skt.strftime("%Y-%m-%d")

            if st.form_submit_button("Ekle"):
                if not ad.strip():
                    st.error("Ürün adı zorunlu")
                else:
                    db_execute("INSERT INTO stok (urun_adi, miktar, birim, kategori, min_miktar, barkod, son_kullanma_tarihi, alis_fiyat, satis_fiyat, tedarikci, raf_no, kdv_oran, birim_orani) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                               (ad.strip(), miktar, birim, kategori, min_m, barkod, skt_str, alis, satis,
                                tedarik if tedarik!="Yok" else "", raf, kdv, birim_orani))
                    mesaj_ekle(f"{ad.strip()} eklendi"); st.rerun()
    with tab3:
        stok = db_fetchall("SELECT * FROM stok")
        if stok:
            sec = st.selectbox("Ürün", [f"{u['urun_adi']} ({u['miktar']} {u['birim']})" for u in stok])
            idx = [f"{u['urun_adi']} ({u['miktar']} {u['birim']})" for u in stok].index(sec)
            urun = stok[idx]
            with st.form("duzenle"):
                ad = st.text_input("Ad", urun['urun_adi'])
                miktar = st.number_input("Miktar", value=float(urun['miktar']))
                birim = st.selectbox("Birim", BIRIMLER, index=BIRIMLER.index(urun['birim']) if urun['birim'] in BIRIMLER else 0)
                kat = st.selectbox("Kategori", KATEGORILER, index=KATEGORILER.index(urun['kategori']) if urun['kategori'] in KATEGORILER else 0)
                birim_orani = st.number_input(f"1 {birim} kaç adet?", value=float(urun.get('birim_orani', 1.0)), step=1.0)
                if st.form_submit_button("Güncelle"):
                    db_execute("UPDATE stok SET urun_adi=?, miktar=?, birim=?, kategori=?, birim_orani=? WHERE id=?",
                               (ad, miktar, birim, kat, birim_orani, urun['id']))
                    mesaj_ekle("Güncellendi"); st.rerun()
            if st.button("Sil", key=f"sil_{urun['id']}"):
                db_execute("DELETE FROM stok WHERE id=?", (urun['id'],))
                mesaj_ekle("Silindi"); st.rerun()
    with tab4:
        st.subheader("Sayım")
        b = st.text_input("Barkod")
        if b:
            urun = db_fetchone("SELECT * FROM stok WHERE barkod=?", (b,))
            if urun:
                st.write(f"{urun['urun_adi']} – {urun['miktar']} {urun['birim']}")
                yeni = st.number_input("Gerçek Miktar", value=float(urun['miktar']))
                if st.button("Kaydet"):
                    db_execute("UPDATE stok SET miktar=? WHERE id=?", (yeni, urun['id']))
                    hareket_ekle(st.session_state.current_user['kullanici_adi'], "Sayım", urun['urun_adi'],
                                 f"Fark: {yeni - urun['miktar']:+.2f}")
                    mesaj_ekle("Sayım kaydedildi"); st.rerun()
            else:
                st.warning("Bulunamadı")

def tedarikci_sayfasi():
    st.markdown('<div class="main-header">🏭 Tedarikçiler</div>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["📋 Liste","➕ Ekle/Düzenle"])
    with tab1:
        ted = db_fetchall("SELECT * FROM tedarikciler")
        if ted:
            for t in ted:
                c1,c2 = st.columns([4,1])
                c1.write(f"**{t['ad']}** – Güven: {t['guven_puani']:.1f} – Tel: {t['tel']} – E-posta: {t['eposta']}")
                if c2.button("Sil", key=f"t_sil_{t['id']}"):
                    db_execute("DELETE FROM tedarikciler WHERE id=?", (t['id'],))
                    mesaj_ekle("Silindi"); st.rerun()
        else:
            st.info("Tedarikçi yok")
    with tab2:
        duz = st.session_state.get("duzenlenecek_tedarikci")
        t = db_fetchone("SELECT * FROM tedarikciler WHERE id=?", (duz,)) if duz else {"ad":"","guven_puani":5.0,"tel":"","eposta":""}
        if duz: st.info(f"✏️ {t['ad']} düzenleniyor")
        with st.form("tedarikci_form"):
            ad = st.text_input("Firma Adı *", value=t['ad'])
            guven = st.slider("Güven", 0.0,10.0, float(t['guven_puani']))
            tel = st.text_input("Telefon")
            eposta = st.text_input("E-posta")
            btn = "Güncelle" if duz else "Ekle"
            if st.form_submit_button(btn):
                if not ad.strip():
                    st.error("Ad zorunlu")
                else:
                    if duz:
                        db_execute("UPDATE tedarikciler SET ad=?, guven_puani=?, tel=?, eposta=? WHERE id=?",
                                   (ad.strip(), guven, tel, eposta, duz))
                        st.session_state.duzenlenecek_tedarikci = None
                    else:
                        db_execute("INSERT INTO tedarikciler (ad, guven_puani, tel, eposta) VALUES (?,?,?,?)",
                                   (ad.strip(), guven, tel, eposta))
                    mesaj_ekle("Kaydedildi"); st.rerun()

def siparis_sayfasi():
    st.markdown('<div class="main-header">🔥 Sipariş Panosu</div>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["📋 Liste","➕ Ekle"])
    with tab1:
        fireler = db_fetchall("SELECT * FROM fire")
        if fireler:
            for f in fireler:
                c1,c2 = st.columns([4,1])
                c1.write(f"{f['aciliyet']} {f['urun_adi']} – {f['miktar']} {f['birim']} ({f['durum']})")
                if c2.button("🗑️", key=f"fire_{f['id']}"):
                    db_execute("DELETE FROM fire WHERE id=?", (f['id'],)); st.rerun()
        else:
            st.info("Sipariş yok")
    with tab2:
        urunler = db_fetchall("SELECT urun_adi, birim, tedarikci FROM stok")
        if urunler:
            with st.form("fire_ekle"):
                sec = st.selectbox("Ürün", [u['urun_adi'] for u in urunler])
                bilgi = next(u for u in urunler if u['urun_adi'] == sec)
                miktar = st.number_input("Miktar", 0.01, format="%.2f")
                if st.form_submit_button("Ekle"):
                    db_execute("INSERT INTO fire (urun_adi, miktar, birim, tedarikci, durum, eklenme_tarihi) VALUES (?,?,?,?,?,?)",
                               (sec, miktar, bilgi['birim'], bilgi['tedarikci'], "Bekliyor", datetime.now().strftime("%Y-%m-%d %H:%M")))
                    mesaj_ekle("Sipariş eklendi"); st.rerun()
        else:
            st.warning("Önce stok ekleyin")

def satis_raporu():
    st.markdown('<div class="main-header">📊 Satış Raporu</div>', unsafe_allow_html=True)
    satislar = db_fetchall("SELECT * FROM satislar")
    if not satislar:
        st.info("Satış yok"); return
    df = pd.DataFrame(satislar)
    df['tarih'] = pd.to_datetime(df['tarih'])
    df['gun'] = df['tarih'].dt.date
    bas = st.date_input("Başlangıç", df['gun'].min())
    bit = st.date_input("Bitiş", df['gun'].max())
    df = df[(df['gun'] >= bas) & (df['gun'] <= bit)]
    tip = st.radio("Kırılım", ["Günlük","Ürün Bazlı"], horizontal=True)
    if tip == "Günlük":
        rpr = df.groupby('gun')['toplam_tutar'].sum().reset_index()
        st.dataframe(rpr)
        fig = px.bar(rpr, x='gun', y='toplam_tutar')
        st.plotly_chart(fig)
    else:
        rpr = df.groupby('urun_adi').agg(Adet=('miktar','sum'), Ciro=('toplam_tutar','sum')).reset_index()
        st.dataframe(rpr)

def aktivite_logu():
    st.markdown('<div class="main-header">📋 Aktivite Logu</div>', unsafe_allow_html=True)
    h = db_fetchall("SELECT * FROM hareketler ORDER BY tarih DESC LIMIT 200")
    if h:
        st.dataframe(pd.DataFrame(h))
    else:
        st.info("Log boş")

def kasa_kapanisi():
    st.markdown('<div class="main-header">🧾 Kasa Kapanışı</div>', unsafe_allow_html=True)
    bugun = datetime.now().strftime("%Y-%m-%d")
    satislar = db_fetchall("SELECT * FROM satislar WHERE tarih LIKE ?", (bugun+'%',))
    if not satislar:
        st.info("Bugün satış yok"); return
    df = pd.DataFrame(satislar)
    toplam = df['toplam_tutar'].sum()
    st.dataframe(df[['urun_adi','miktar','birim_fiyat','toplam_tutar']])
    st.metric("Toplam Satış", f"{toplam:.2f} TL")
    st.metric("Net Kâr", f"{gunluk_kar(bugun):.2f} TL")

def kullanici_yonetimi():
    st.markdown('<div class="main-header">👥 Kullanıcı Yönetimi</div>', unsafe_allow_html=True)
    with st.form("kullanici_ekle"):
        kul = st.text_input("Kullanıcı Adı")
        sifre = st.text_input("Şifre", type="password")
        rol = st.selectbox("Rol", list(ROLLER.keys()))
        ad = st.text_input("Ad Soyad")
        if st.form_submit_button("Ekle"):
            if kul and sifre:
                db_execute("INSERT INTO kullanicilar (kullanici_adi, sifre_hash, rol, ad) VALUES (?,?,?,?)",
                           (kul, hash_sifre(sifre), rol, ad))
                mesaj_ekle(f"{kul} eklendi"); st.rerun()
            else: st.error("Boş olamaz")
    kullanicilar = db_fetchall("SELECT * FROM kullanicilar")
    if kullanicilar:
        st.dataframe(pd.DataFrame(kullanicilar))

def sifre_sifirla():
    st.markdown('<div class="main-header">🔑 Şifre Sıfırla</div>', unsafe_allow_html=True)
    with st.form("sifre_sifirla"):
        eski = st.text_input("Eski Şifre", type="password")
        yeni = st.text_input("Yeni Şifre", type="password")
        yeni2 = st.text_input("Yeni Şifre Tekrar", type="password")
        if st.form_submit_button("Sıfırla"):
            user = st.session_state.current_user
            if hash_sifre(eski) != user['sifre_hash']:
                st.error("Eski şifre yanlış")
            elif yeni != yeni2:
                st.error("Eşleşmiyor")
            else:
                db_execute("UPDATE kullanicilar SET sifre_hash=? WHERE id=?", (hash_sifre(yeni), user['id']))
                mesaj_ekle("Şifre değişti, tekrar giriş yapın")
                st.session_state.authenticated = False; st.rerun()

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
    tel = st.text_input("Patron Telefon", value=st.session_state.get("patron_telefon",""))
    if st.button("Kaydet"):
        st.session_state.patron_email = eposta
        st.session_state.patron_telefon = tel
        mesaj_ekle("Ayarlar kaydedildi")

def yedekleme_sayfasi():
    st.markdown('<div class="main-header">💾 Yedekleme</div>', unsafe_allow_html=True)
    if st.button("Veritabanını İndir"):
        with open("market.db", "rb") as f:
            st.download_button("İndir", f, "market.db")

SAYFALAR = {
    "🏠 Ana Panel": ana_sayfa,
    "📱 Barkod": barkod_sayfasi,
    "🏷️ Barkod Yönetimi": barkod_yonetimi,
    "💵 Satış": satis_sayfasi,
    "📦 Stok": stok_sayfasi,
    "🔥 Sipariş": siparis_sayfasi,
    "🏭 Tedarikçi": tedarikci_sayfasi,
    "📊 Satış Raporu": satis_raporu,
    "📋 Aktivite Logu": aktivite_logu,
    "🧾 Kasa Kapanışı": kasa_kapanisi,
    "👥 Kullanıcı Yönetimi": kullanici_yonetimi,
    "🔑 Şifre Sıfırlama": sifre_sifirla,
    "💬 Geri Bildirim": geri_bildirim,
    "⚙️ Ayarlar": ayarlar_sayfasi,
    "💾 Yedekleme": yedekleme_sayfasi,
}

def izinli_sayfalar(kul):
    if not kul: return {}
    rol = kul.get("rol","")
    izinler = ROLLER.get(rol,[])
    if "tümü" in izinler: return SAYFALAR
    yetki_sayfa = {
        "barkod": ["📱 Barkod","🏷️ Barkod Yönetimi"],
        "satis": ["💵 Satış"],
        "stok": ["📦 Stok","📊 Satış Raporu"],
        "stok_ekle": ["📦 Stok","🔥 Sipariş"],
        "skt_takip": ["🏠 Ana Panel"],
    }
    return {k:v for k,v in SAYFALAR.items() if any(k in yetki_sayfa.get(y,[]) for y in izinler)}

def main():
    st.set_page_config(page_title="Market Yönetim", page_icon="🏪", layout="wide", initial_sidebar_state="expanded")
    oturumu_baslat()
    enerjik_css(st.session_state.tema)
    oturum_kontrol()

    if not st.session_state.authenticated:
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            st.markdown('<h1 style="text-align:center; background:linear-gradient(135deg,#F97316,#8B5CF6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;">🏪 Market Yönetim</h1>', unsafe_allow_html=True)
            with st.form("giris"):
                kullanici = st.text_input("Kullanıcı Adı")
                sifre = st.text_input("Şifre", type="password")
                if st.form_submit_button("Giriş"):
                    user = giris_kontrol(kullanici, sifre)
                    if user:
                        st.session_state.authenticated = True
                        st.session_state.current_user = user
                        st.session_state.last_activity = datetime.now()
                        st.rerun()
                    else:
                        st.error("Hatalı giriş!")
        return

    for m in st.session_state.son_islem_mesajlari:
        st.success(m)
    st.session_state.son_islem_mesajlari = []

    with st.sidebar:
        st.markdown('<h2 style="color:white;">🏪 Market</h2>', unsafe_allow_html=True)
        st.selectbox("Tema", ["Koyu","Aydınlık"], index=0 if st.session_state.tema=="Koyu" else 1,
                     key="tema_secimi", on_change=tema_degistir)
        aktif = izinli_sayfalar(st.session_state.current_user)
        sayfa = st.radio("Menü", list(aktif.keys()), label_visibility="collapsed")
        if st.button("🚪 Çıkış"):
            st.session_state.authenticated = False; st.rerun()

    if st.session_state.get("pos_modu") and sayfa == "💵 Satış":
        pos_modu()
    else:
        aktif[sayfa]()

if __name__ == "__main__":
    main()
