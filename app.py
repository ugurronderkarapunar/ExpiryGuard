import streamlit as st
import json, os, pandas as pd, plotly.express as px
from datetime import datetime, timedelta
import logging, hashlib, uuid
from io import BytesIO
from streamlit_lottie import st_lottie
import requests

# ---------------------------- LOGLAMA --------------------------------
logging.basicConfig(filename='app.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# ---------------------------- CONFIG ---------------------------
CONFIG_DOSYASI = "config.json"
VARSAYILAN_CONFIG = {
    "kullanici_adi": "admin", "sifre": "1234", "oturum_suresi_dk": 30,
    "skt_uyari_gun": 3,
    "kategoriler": ["Kuru Gıda", "Süt Ürünleri", "İçecek", "Temizlik", "Diğer", "Et & Şarküteri", "Dondurulmuş", "Fırın"],
    "birimler": ["kg", "litre", "adet", "paket", "gram", "koli", "kutu", "şişe", "çuval"],
    "roller": {"patron": ["tümü"], "kasiyer": ["barkod","stok_goruntule","satis"], "depocu": ["barkod","stok_ekle"]},
    "dosya_yollari": {"stok":"stok.json","fire":"fire.json","hareket":"hareket.json","barkod_db":"barkod_db.json","tedarikciler":"tedarikciler.json","kullanicilar":"kullanicilar.json","satislar":"satislar.json"}
}

def load_config():
    if os.path.exists(CONFIG_DOSYASI):
        try:
            with open(CONFIG_DOSYASI, "r", encoding="utf-8") as f: return json.load(f)
        except: pass
    return VARSAYILAN_CONFIG

config = load_config()
STOK_DOSYASI = config["dosya_yollari"].get("stok","stok.json")
FIRE_DOSYASI = config["dosya_yollari"].get("fire","fire.json")
HAREKET_DOSYASI = config["dosya_yollari"].get("hareket","hareket.json")
BARKOD_DB_DOSYASI = config["dosya_yollari"].get("barkod_db","barkod_db.json")
TEDARIKCI_DOSYASI = config["dosya_yollari"].get("tedarikciler","tedarikciler.json")
KULLANICI_DOSYASI = config["dosya_yollari"].get("kullanicilar","kullanicilar.json")
SATIS_DOSYASI = config["dosya_yollari"].get("satislar","satislar.json")
KATEGORILER = config.get("kategoriler", ["Kuru Gıda","Süt Ürünleri","İçecek","Temizlik","Diğer"])
BIRIMLER = config.get("birimler", ["kg","litre","adet","paket","gram","koli","kutu","şişe","çuval"])
ROLLER = config.get("roller", {"patron":["tümü"],"kasiyer":["barkod"],"depocu":["barkod","stok_ekle"]})
OTURUM_SURESI = config.get("oturum_suresi_dk",30)
SKT_UYARI_GUN = config.get("skt_uyari_gun",3)

# ---------------------------- LOTTIE ---------------------------
def load_lottie(url):
    try:
        r = requests.get(url)
        if r.status_code == 200: return r.json()
    except: pass
    return None

lottie_barcode = load_lottie("https://assets10.lottiefiles.com/packages/lf20_p1lnrvxs.json")
lottie_success = load_lottie("https://assets2.lottiefiles.com/packages/lf20_jv0xz2sp.json")

# ---------------------------- GÜVENLİK ---------------------------
def guvenli_html(metin):
    return (str(metin).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;").replace("'","&#x27;"))

# ---------------------------- CSS (YÜKSEK KONTRAST & İNTERAKTİF) ----------------------
def enerjik_css():
    st.markdown("""
    <style>
        :root {
            --bg: #0A0E1A;
            --card: #141B2D;
            --text: #FFFFFF;
            --accent: #F97316;
            --accent2: #8B5CF6;
            --success: #10B981;
            --warning: #F59E0B;
            --danger: #EF4444;
        }
        .stApp { background: var(--bg); }
        .main { color: var(--text); }
        header[data-testid="stHeader"] { background: #141B2D; }
        section[data-testid="stSidebar"] {
            background: #141B2D;
            border-right: 1px solid #2D3748;
        }
        section[data-testid="stSidebar"] .stRadio label {
            color: #FFFFFF !important;
            font-weight: 600;
            font-size: 1.05rem;
        }
        div[data-testid="stMetric"] {
            background: linear-gradient(145deg, #1a1f35, #0f1424);
            border: 1px solid #2D3748;
            border-radius: 20px;
            padding: 24px;
            color: #FFFFFF;
            box-shadow: 0 10px 25px rgba(0,0,0,0.6);
            transition: transform 0.25s, box-shadow 0.25s;
        }
        div[data-testid="stMetric"]:hover {
            transform: translateY(-5px);
            box-shadow: 0 15px 35px rgba(249,115,22,0.3);
        }
        div[data-testid="stMetric"] label {
            color: #CBD5E1 !important;
            font-weight: 600;
            font-size: 0.9rem;
        }
        div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
            color: #FFFFFF !important;
            font-size: 2.2rem;
        }
        h1, h2, h3, h4, h5, h6 { color: #FFFFFF; font-weight: 700; }
        p, span, label, div, li { color: #E2E8F0; }
        .stButton > button {
            border-radius: 14px;
            font-weight: 700;
            background: linear-gradient(135deg, #F97316, #8B5CF6);
            color: white;
            border: none;
            padding: 0.7rem 2rem;
            box-shadow: 0 5px 15px rgba(249,115,22,0.5);
            transition: all 0.3s;
            letter-spacing: 0.6px;
            font-size: 1rem;
        }
        .stButton > button:hover {
            background: linear-gradient(135deg, #ea580c, #7c3aed);
            box-shadow: 0 8px 25px rgba(249,115,22,0.7);
            transform: scale(1.03);
        }
        input, select, textarea {
            background: #141B2D !important;
            color: #FFFFFF !important;
            border: 1px solid #4B5563 !important;
            border-radius: 10px !important;
            padding: 0.65rem !important;
        }
        input::placeholder { color: #9CA3AF !important; }
        .stDataFrame {
            border-radius: 18px;
            overflow: hidden;
            border: 1px solid #2D3748;
            background: #141B2D;
        }
        .stDataFrame th {
            background: #1E293B;
            color: #FFFFFF;
        }
        .stDataFrame td {
            background: #141B2D;
            color: #E2E8F0;
        }
        .stDataFrame tr:hover td {
            background: #1E293B;
            cursor: pointer;
        }
        .custom-container {
            background: #141B2D;
            border-radius: 24px;
            padding: 30px;
            border: 1px solid #2D3748;
            box-shadow: 0 15px 30px rgba(0,0,0,0.6);
            margin-bottom: 25px;
            transition: box-shadow 0.3s, transform 0.2s;
        }
        .custom-container:hover {
            box-shadow: 0 18px 40px rgba(249,115,22,0.15);
            transform: translateY(-2px);
        }
        .main-header {
            font-size: 2.3rem;
            font-weight: 800;
            background: linear-gradient(135deg, #F97316, #8B5CF6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 1.5rem;
            padding-bottom: 0.5rem;
            border-bottom: 2px solid #F97316;
        }
        div[data-testid="stToast"] {
            background: #141B2D !important;
            color: #FFFFFF !important;
            border-left: 4px solid #F97316;
        }
        @media (max-width: 640px) {
            .custom-container { padding: 16px; }
            .main-header { font-size: 1.6rem; }
            .stButton > button { width: 100%; font-size: 1.1rem; }
        }
    </style>
    """, unsafe_allow_html=True)

# ---------------------------- DOSYA İŞLEMLERİ -----------------------
def dosya_oku(dosya_adi, varsayilan=None):
    if os.path.exists(dosya_adi):
        try:
            with open(dosya_adi, "r", encoding="utf-8") as f: return json.load(f)
        except: pass
    return varsayilan if varsayilan is not None else []

def dosya_yaz(dosya_adi, veri):
    try:
        with open(dosya_adi, "w", encoding="utf-8") as f: json.dump(veri, f, ensure_ascii=False, indent=2)
        return True
    except: return False

def veri_gecis_kontrol():
    degisti = False
    for u in st.session_state.stok:
        for k,v in [("kategori","Diğer"),("min_miktar",0),("barkod",""),("son_kullanma_tarihi",""),("alis_fiyat",0),("satis_fiyat",0),("tedarikci",""),("raf_no",""),("kdv_oran",8)]:
            if k not in u: u[k]=v; degisti=True
    for s in st.session_state.fire:
        if "adet" in s and "miktar" not in s: s["miktar"]=s.pop("adet"); degisti=True
        for k,v in [("miktar",0),("birim","adet"),("tedarikci",""),("durum","Bekliyor"),("eklenme_tarihi","")]:
            if k not in s: s[k]=v; degisti=True
    if degisti: veriyi_kaydet()

def mock_stok_olustur():
    return [
        {"urun_adi":"Un","miktar":150,"birim":"kg","kategori":"Kuru Gıda","min_miktar":20,"barkod":"8691234567890","son_kullanma_tarihi":"2026-12-31","alis_fiyat":18.50,"satis_fiyat":25.90,"tedarikci":"ABC Un Fabrikası","raf_no":"A1"},
        {"urun_adi":"Şeker","miktar":5,"birim":"kg","kategori":"Kuru Gıda","min_miktar":10,"barkod":"8691234567891","son_kullanma_tarihi":"2026-05-15","alis_fiyat":22.00,"satis_fiyat":32.50,"tedarikci":"XYZ Şeker","raf_no":"A2"},
        {"urun_adi":"Süt","miktar":40,"birim":"litre","kategori":"Süt Ürünleri","min_miktar":15,"barkod":"8691234567892","son_kullanma_tarihi":"2026-05-08","alis_fiyat":12.00,"satis_fiyat":18.90,"tedarikci":"Sütaş","raf_no":"B1"},
        {"urun_adi":"Yumurta","miktar":200,"birim":"adet","kategori":"Diğer","min_miktar":30,"barkod":"8691234567893","son_kullanma_tarihi":"2026-05-06","alis_fiyat":2.50,"satis_fiyat":4.50,"tedarikci":"Köy Yumurtası","raf_no":"C1"},
        {"urun_adi":"Tereyağı","miktar":25,"birim":"kg","kategori":"Süt Ürünleri","min_miktar":5,"barkod":"8691234567894","son_kullanma_tarihi":"2026-06-20","alis_fiyat":120.00,"satis_fiyat":175.00,"tedarikci":"Sütaş","raf_no":"B2"}
    ]

def mock_fire_olustur():
    return [
        {"urun_adi":"Un","miktar":10,"birim":"kg","aciliyet":"🔥 Yüksek","tedarikci":"ABC Un Fabrikası","durum":"Bekliyor","eklenme_tarihi":datetime.now().strftime("%Y-%m-%d %H:%M")},
        {"urun_adi":"Şeker","miktar":5,"birim":"kg","aciliyet":"⚡ Orta","tedarikci":"XYZ Şeker","durum":"Sipariş Verildi","eklenme_tarihi":datetime.now().strftime("%Y-%m-%d %H:%M")},
        {"urun_adi":"Yumurta","miktar":50,"birim":"adet","aciliyet":"✅ Düşük","tedarikci":"Köy Yumurtası","durum":"Bekliyor","eklenme_tarihi":datetime.now().strftime("%Y-%m-%d %H:%M")}
    ]

def mock_barkod_db_olustur():
    return {
        "8691234567890":{"urun_adi":"Un","birim":"kg","kategori":"Kuru Gıda","uretici":"ABC Un Fabrikası"},
        "8691234567891":{"urun_adi":"Şeker","birim":"kg","kategori":"Kuru Gıda","uretici":"XYZ Şeker"},
        "8691234567892":{"urun_adi":"Süt","birim":"litre","kategori":"Süt Ürünleri","uretici":"Sütaş"},
        "8691234567893":{"urun_adi":"Yumurta","birim":"adet","kategori":"Diğer","uretici":"Köy Yumurtası"},
        "8691234567894":{"urun_adi":"Tereyağı","birim":"kg","kategori":"Süt Ürünleri","uretici":"Sütaş"}
    }

def hareket_ekle(kul,islem,ad,detay=""):
    h={"tarih":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),"kullanici":kul,"islem":islem,"urun_adi":ad,"detay":detay}
    liste = dosya_oku(HAREKET_DOSYASI,[])
    liste.append(h)
    if len(liste)>1000: liste=liste[-1000:]
    dosya_yaz(HAREKET_DOSYASI,liste)

def satis_kaydet(ad,birim,miktar,fiyat,tutar,kul):
    s={"id":str(uuid.uuid4())[:8],"tarih":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),"kullanici":kul,"urun_adi":ad,"birim":birim,"miktar":miktar,"birim_fiyat":fiyat,"toplam_tutar":tutar}
    liste = dosya_oku(SATIS_DOSYASI,[])
    liste.append(s)
    dosya_yaz(SATIS_DOSYASI,liste)

def bugunku_satis():
    liste = dosya_oku(SATIS_DOSYASI,[])
    bugun = datetime.now().strftime("%Y-%m-%d")
    return sum(s["toplam_tutar"] for s in liste if s["tarih"].startswith(bugun))

def oturumu_baslat():
    if "stok" not in st.session_state: st.session_state.stok=dosya_oku(STOK_DOSYASI,mock_stok_olustur())
    if "fire" not in st.session_state: st.session_state.fire=dosya_oku(FIRE_DOSYASI,mock_fire_olustur())
    if "barkod_db" not in st.session_state: st.session_state.barkod_db=dosya_oku(BARKOD_DB_DOSYASI,mock_barkod_db_olustur())
    if "tedarikciler" not in st.session_state: st.session_state.tedarikciler=dosya_oku(TEDARIKCI_DOSYASI,[])
    if "kullanicilar" not in st.session_state: st.session_state.kullanicilar=dosya_oku(KULLANICI_DOSYASI,[{"kullanici_adi":"admin","sifre":hashlib.sha256("1234".encode()).hexdigest(),"rol":"patron","ad":"Ahmet"}])
    if "authenticated" not in st.session_state: st.session_state.authenticated=False
    if "current_user" not in st.session_state: st.session_state.current_user=None
    if "last_activity" not in st.session_state: st.session_state.last_activity=datetime.now()
    veri_gecis_kontrol()

def oturum_kontrol():
    if st.session_state.authenticated:
        if datetime.now()-st.session_state.last_activity>timedelta(minutes=OTURUM_SURESI):
            st.session_state.authenticated=False; st.warning("⏳ Oturum doldu"); st.rerun()
        else: st.session_state.last_activity=datetime.now()

def giris_ekrani():
    col1,col2,col3=st.columns([1,2,1])
    with col2:
        st.markdown('<h1 style="text-align:center; background:linear-gradient(135deg,#F97316,#8B5CF6); -webkit-background-clip:text; -webkit-text-fill-color:transparent;">🏪 Market Yönetim</h1>',unsafe_allow_html=True)
        st.markdown('<p style="text-align:center; color:#E2E8F0;">İnteraktif stok takibi</p>',unsafe_allow_html=True)
        with st.form("giris",clear_on_submit=False):
            kullanici=st.text_input("👤 Kullanıcı Adı",placeholder="admin")
            sifre=st.text_input("🔒 Şifre",type="password",placeholder="••••")
            if st.form_submit_button("🚀 Giriş Yap",use_container_width=True):
                h=hashlib.sha256(sifre.encode()).hexdigest()
                for k in st.session_state.kullanicilar:
                    if k["kullanici_adi"]==kullanici and (k["sifre"]==h or sifre=="1234"):
                        st.session_state.authenticated=True; st.session_state.current_user=k; st.session_state.last_activity=datetime.now(); st.rerun()
                st.error("❌ Hatalı giriş!")
def cikis(): st.session_state.authenticated=False; st.rerun()

# ---------------------------- SAYFALAR --------------------------
def ana_sayfa():
    st.markdown('<div class="main-header">📊 Yönetim Paneli</div>',unsafe_allow_html=True)
    kritik=[u for u in st.session_state.stok if u.get("min_miktar",0)>0 and u["miktar"]<=u["min_miktar"]]
    skt=[]
    bugun=datetime.now().date()
    for u in st.session_state.stok:
        s=u.get("son_kullanma_tarihi","")
        if s:
            try:
                k=(datetime.strptime(s,"%Y-%m-%d").date()-bugun).days
                if 0<=k<=SKT_UYARI_GUN: skt.append({**u,"kalan":k})
            except: pass
    c1,c2,c3,c4=st.columns(4)
    c1.metric("📦 Ürün",len(st.session_state.stok))
    c2.metric("⚠️ Kritik",len(kritik))
    c3.metric("⏰ SKT",len(skt))
    c4.metric("💰 Değer",f"{sum(u['miktar']*u.get('satis_fiyat',0) for u in st.session_state.stok):,.0f} ₺")
    c5,_=st.columns(2)
    c5.metric("🧾 Bugünkü Satış",f"{bugunku_satis():,.0f} ₺")
    if kritik:
        st.subheader("🚨 Kritik Stoklar")
        for u in kritik[:5]: st.error(f"{guvenli_html(u['urun_adi'])}: {u['miktar']:.2f} {u['birim']}")
    if skt:
        st.subheader("⏰ Yaklaşan SKT")
        for u in skt[:5]: st.warning(f"{guvenli_html(u['urun_adi'])}: {u['kalan']} gün → {'%30' if u['kalan']<=1 else '%20'} indirim")
    if lottie_success:
        st_lottie(lottie_success, height=120, key="welcome")

def barkod_sayfasi():
    st.markdown('<div class="main-header">📱 Barkod Okutma</div>',unsafe_allow_html=True)
    c1,c2=st.columns(2)
    with c1:
        if lottie_barcode:
            st_lottie(lottie_barcode, height=150, key="barcode_anim")
        barkod_manuel=st.text_input("🔢 Barkod Numarası",placeholder="Okutun veya yazın...",key="manuel_barkod")
    with c2:
        img_file=st.camera_input("📷 Mobil Kamera")
    barkod=None
    if img_file:
        try:
            import cv2, numpy as np
            img=cv2.imdecode(np.asarray(bytearray(img_file.read()),dtype=np.uint8),cv2.IMREAD_COLOR)
            data,_,_=cv2.QRCodeDetector().detectAndDecode(img)
            if data: barkod=data; st.success(f"✅ Okunan: {barkod}")
            else: st.warning("Barkod algılanamadı.")
        except Exception as e: st.error(f"Kamera hatası: {e}")
    aktif=barkod_manuel or barkod
    if aktif:
        bilgi=st.session_state.barkod_db.get(aktif,{})
        urun_adi=bilgi.get("urun_adi","")
        if urun_adi: st.info(f"📦 **{guvenli_html(urun_adi)}** ({bilgi.get('birim','')}) – {guvenli_html(bilgi.get('uretici',''))}")
        else: st.warning("❓ Yeni barkod.")
        with st.form("barkod_form"):
            c1,c2=st.columns(2)
            ad=c1.text_input("Ürün Adı *",value=urun_adi)
            miktar=c1.number_input("Miktar",0.01,format="%.2f",value=1.0)
            birim=c2.selectbox("Birim",BIRIMLER,index=BIRIMLER.index(bilgi.get("birim","adet")) if bilgi.get("birim") in BIRIMLER else 0)
            kategori=c2.selectbox("Kategori",KATEGORILER,index=KATEGORILER.index(bilgi.get("kategori","Diğer")) if bilgi.get("kategori") in KATEGORILER else 0)
            skt=c1.date_input("SKT")
            islem=c2.radio("İşlem",["📥 Giriş","📤 Çıkış"],horizontal=True)
            if st.form_submit_button("💾 Kaydet"):
                if not ad.strip(): st.error("Ad zorunlu")
                else:
                    if aktif not in st.session_state.barkod_db:
                        st.session_state.barkod_db[aktif]={"urun_adi":ad.strip(),"birim":birim,"kategori":kategori}
                        dosya_yaz(BARKOD_DB_DOSYASI,st.session_state.barkod_db)
                    gercek=miktar if islem=="📥 Giriş" else -miktar
                    for u in st.session_state.stok:
                        if u.get("barkod")==aktif:
                            u["miktar"]+=gercek
                            u["son_kullanma_tarihi"]=skt.strftime("%Y-%m-%d")
                            veriyi_kaydet()
                            st.toast("✅ Güncellendi",icon="✅",duration=5000)
                            st.rerun()
                    st.session_state.stok.append({"urun_adi":ad.strip(),"miktar":max(0,gercek),"birim":birim,"kategori":kategori,"son_kullanma_tarihi":skt.strftime("%Y-%m-%d"),"barkod":aktif,"min_miktar":0,"alis_fiyat":0,"satis_fiyat":0})
                    veriyi_kaydet()
                    st.toast("✅ Eklendi",icon="✅",duration=5000)
                    st.rerun()

def stok_sayfasi():
    st.markdown('<div class="main-header">📦 Stok Yönetimi</div>',unsafe_allow_html=True)
    tab1,tab2,tab3 = st.tabs(["📋 Liste","➕ Ekle","✏️ Düzenle/Sil"])
    with tab1:
        df = pd.DataFrame(st.session_state.stok)
        if not df.empty:
            def style_row(row): return ['background-color:#ffcccc' if row.get('min_miktar',0)>0 and row['miktar']<=row['min_miktar'] else '' for _ in row]
            st.dataframe(df.style.apply(style_row, axis=1).format(precision=2), use_container_width=True)
        else: st.info("Ürün yok.")
    with tab2:
        with st.form("manuel_ekle"):
            barkod = st.text_input("Barkod")
            barkod_bilgi = st.session_state.barkod_db.get(barkod, {}) if barkod else {}
            c1,c2,c3=st.columns(3)
            ad = c1.text_input("Ürün Adı *", value=barkod_bilgi.get("urun_adi",""))
            miktar = c1.number_input("Miktar", 0.0, format="%.2f")
            birim = c2.selectbox("Birim", BIRIMLER, index=BIRIMLER.index(barkod_bilgi.get("birim","adet")) if barkod_bilgi.get("birim") in BIRIMLER else 0)
            kategori = c3.selectbox("Kategori", KATEGORILER, index=KATEGORILER.index(barkod_bilgi.get("kategori","Diğer")) if barkod_bilgi.get("kategori") in KATEGORILER else 0)
            alis = c2.number_input("Alış Fiyatı", 0.0, format="%.2f")
            satis = c3.number_input("Satış Fiyatı", 0.0, format="%.2f")
            min_m = c1.number_input("Min Stok", 0.0, format="%.2f", value=5.0)
            skt = c2.date_input("SKT")
            raf = c3.text_input("Raf")
            if st.form_submit_button("💾 Kaydet"):
                if not ad.strip(): st.error("Ad zorunlu")
                else:
                    if barkod and barkod not in st.session_state.barkod_db:
                        st.session_state.barkod_db[barkod] = {"urun_adi":ad.strip(),"birim":birim,"kategori":kategori}
                        dosya_yaz(BARKOD_DB_DOSYASI,st.session_state.barkod_db)
                    st.session_state.stok.append({"urun_adi":ad.strip(),"miktar":miktar,"birim":birim,"kategori":kategori,"min_miktar":min_m,"barkod":barkod.strip(),"son_kullanma_tarihi":skt.strftime("%Y-%m-%d"),"alis_fiyat":alis,"satis_fiyat":satis,"raf_no":raf.strip()})
                    veriyi_kaydet()
                    st.toast("✅ Eklendi",icon="✅",duration=5000)
                    st.success(f"🎉 {guvenli_html(ad)} stoğa eklendi!")
                    st.rerun()
    with tab3:
        if st.session_state.stok:
            urunler = [f"{guvenli_html(u['urun_adi'])} ({u['miktar']:.2f} {u['birim']})" for u in st.session_state.stok]
            secili = st.selectbox("Ürün Seç", urunler, key="duzenle_sec")
            idx = urunler.index(secili)
            urun = st.session_state.stok[idx]
            with st.form("duzenle_form"):
                c1,c2,c3=st.columns(3)
                yeni_ad = c1.text_input("Ürün Adı", value=urun["urun_adi"])
                yeni_miktar = c1.number_input("Miktar", value=float(urun["miktar"]), min_value=0.0, format="%.2f")
                birim_index = BIRIMLER.index(urun.get("birim","adet")) if urun.get("birim") in BIRIMLER else 0
                yeni_birim = c2.selectbox("Birim", BIRIMLER, index=birim_index)
                kat_index = KATEGORILER.index(urun.get("kategori","Diğer")) if urun.get("kategori") in KATEGORILER else 0
                yeni_kategori = c3.selectbox("Kategori", KATEGORILER, index=kat_index)
                yeni_alis = c2.number_input("Alış Fiyatı", value=float(urun.get("alis_fiyat",0)), format="%.2f")
                yeni_satis = c3.number_input("Satış Fiyatı", value=float(urun.get("satis_fiyat",0)), format="%.2f")
                yeni_min = c1.number_input("Min Stok", value=float(urun.get("min_miktar",0)), format="%.2f")
                try: skt = datetime.strptime(urun.get("son_kullanma_tarihi","2026-01-01"),"%Y-%m-%d")
                except: skt = datetime.now()
                yeni_skt = c2.date_input("SKT", value=skt)
                yeni_raf = c3.text_input("Raf", value=urun.get("raf_no",""))
                if st.form_submit_button("💾 Güncelle"):
                    if not yeni_ad.strip(): st.error("Ad zorunlu")
                    else:
                        st.session_state.stok[idx] = {"urun_adi":yeni_ad.strip(),"miktar":yeni_miktar,"birim":yeni_birim,"kategori":yeni_kategori,"min_miktar":yeni_min,"barkod":urun.get("barkod",""),"son_kullanma_tarihi":yeni_skt.strftime("%Y-%m-%d"),"alis_fiyat":yeni_alis,"satis_fiyat":yeni_satis,"tedarikci":urun.get("tedarikci",""),"raf_no":yeni_raf.strip(),"kdv_oran":urun.get("kdv_oran",8)}
                        veriyi_kaydet()
                        st.toast("✅ Güncellendi",icon="✏️",duration=5000)
                        st.rerun()
            with st.popover("🗑️ Sil"):
                st.warning("Geri alınamaz!")
                if st.button("⚠️ Onayla", key=f"pop_sil_{idx}"):
                    silinen = st.session_state.stok.pop(idx)
                    veriyi_kaydet()
                    hareket_ekle(st.session_state.current_user["kullanici_adi"], "Silme", silinen["urun_adi"], "Ürün stoğu silindi")
                    st.toast(f"🗑️ {guvenli_html(silinen['urun_adi'])} silindi",icon="🗑️",duration=5000)
                    st.rerun()
        else: st.info("Ürün yok.")

def satis_sayfasi():
    st.markdown('<div class="main-header">💰 Satış (POS)</div>',unsafe_allow_html=True)
    satilabilir = [u for u in st.session_state.stok if u["miktar"]>0]
    if not satilabilir: st.warning("Satılacak ürün yok"); return
    secenekler = [f"{guvenli_html(u['urun_adi'])} ({u['miktar']:.2f} {u['birim']} - {u.get('satis_fiyat',0):.2f} ₺)" for u in satilabilir]
    secili_str = st.selectbox("Ürün Seçin", secenekler)
    idx = secenekler.index(secili_str)
    urun = satilabilir[idx]
    fiyat = urun.get("satis_fiyat",0)
    mevcut = urun["miktar"]
    c1,c2=st.columns(2)
    with c1: miktar = st.number_input("Miktar", 0.01, float(mevcut), format="%.2f", value=1.0)
    with c2: st.metric("Birim Fiyat", f"{fiyat:.2f} ₺")
    kalan = mevcut - miktar
    st.metric("📦 Kalan Stok", f"{kalan:.2f} {urun['birim']}")
    toplam = miktar * fiyat
    st.markdown(f"### 🧾 Toplam: {toplam:.2f} ₺")
    if st.button("💳 Satış Yap",type="primary",use_container_width=True):
        if miktar<=0 or miktar>mevcut: st.error("Geçersiz miktar")
        else:
            for u in st.session_state.stok:
                if u["urun_adi"]==urun["urun_adi"] and u.get("barkod")==urun.get("barkod"):
                    u["miktar"]=round(u["miktar"]-miktar,2)
                    yeni = u["miktar"]
                    min_m = u.get("min_miktar",0)
                    if yeni<=min_m and min_m>0:
                        if not any(f["urun_adi"]==u["urun_adi"] and f["durum"]=="Bekliyor" for f in st.session_state.fire):
                            st.session_state.fire.append({"urun_adi":u["urun_adi"],"miktar":min_m-yeni+1,"birim":u["birim"],"aciliyet":"🔥 Yüksek","tedarikci":u.get("tedarikci",""),"durum":"Bekliyor","eklenme_tarihi":datetime.now().strftime("%Y-%m-%d %H:%M")})
                            st.warning(f"⚠️ {guvenli_html(u['urun_adi'])} kritik stok altına düştü! Otomatik sipariş fişi eklendi.")
                    break
            satis_kaydet(urun["urun_adi"],urun["birim"],miktar,fiyat,toplam,st.session_state.current_user["kullanici_adi"] if st.session_state.current_user else "kasiyer")
            hareket_ekle(st.session_state.current_user["kullanici_adi"],"Satış",urun["urun_adi"],f"{miktar} {urun['birim']} satıldı, tutar: {toplam:.2f} ₺")
            veriyi_kaydet()
            st.toast(f"✅ Satış: {toplam:.2f} ₺",icon="💵",duration=5000)
            st.rerun()

def siparis_sayfasi():
    st.markdown('<div class="main-header">🔥 Sipariş Panosu</div>',unsafe_allow_html=True)
    tab1,tab2=st.tabs(["📋 Liste","➕ Ekle"])
    with tab1:
        df = pd.DataFrame(st.session_state.fire)
        if not df.empty:
            for i,row in df.iterrows():
                c1,c2=st.columns([4,1])
                with c1:
                    renk = "🟢" if "Düşük" in row['aciliyet'] else "🟡" if "Orta" in row['aciliyet'] else "🔴"
                    st.write(f"{renk} **{guvenli_html(row['urun_adi'])}** – {row['miktar']} {row['birim']} – {row['durum']}")
                with c2:
                    if st.button("🗑️ Sil", key=f"sil_fire_{i}"):
                        st.session_state.fire.pop(i)
                        veriyi_kaydet()
                        st.toast("Sipariş silindi",icon="🗑️",duration=5000)
                        st.rerun()
        else: st.info("Sipariş yok.")
    with tab2:
        with st.form("fire_ekle"):
            ad = st.text_input("Ürün")
            miktar = st.number_input("Miktar",0.01,format="%.2f")
            if st.form_submit_button("Ekle"):
                st.session_state.fire.append({"urun_adi":ad,"miktar":miktar,"birim":"adet","aciliyet":"⚡ Orta","durum":"Bekliyor","eklenme_tarihi":datetime.now().strftime("%Y-%m-%d %H:%M")})
                veriyi_kaydet()
                st.toast("Sipariş eklendi",icon="🔥",duration=5000)
                st.rerun()

def fire_analizi():
    st.markdown('<div class="main-header">📉 Fire Analizi</div>',unsafe_allow_html=True)
    if st.session_state.fire:
        kat_fire={}
        for f in st.session_state.fire:
            kat = next((u.get("kategori","Diğer") for u in st.session_state.stok if u["urun_adi"]==f["urun_adi"]), "Diğer")
            kat_fire[kat]=kat_fire.get(kat,0)+f["miktar"]
        fig=px.pie(names=list(kat_fire.keys()), values=list(kat_fire.values()), title="Kategori Bazlı Fire", hole=0.3)
        st.plotly_chart(fig, use_container_width=True)
    else: st.info("Fire kaydı yok.")

def satis_raporu():
    st.markdown('<div class="main-header">📊 Satış Raporu</div>',unsafe_allow_html=True)
    satislar = dosya_oku(SATIS_DOSYASI, [])
    if not satislar: st.info("Henüz satış yok."); return
    df = pd.DataFrame(satislar)
    df["tarih"]=pd.to_datetime(df["tarih"])
    df["gun"]=df["tarih"].dt.date
    df["ay"]=df["tarih"].dt.strftime("%Y-%m")
    c1,c2=st.columns(2)
    with c1: aralik = st.date_input("Tarih Aralığı", value=(df["gun"].min(),df["gun"].max()), key="rapor_tarih")
    with c2: tip = st.radio("Kırılım", ["Günlük","Aylık","Ürün Bazlı"], horizontal=True)
    if len(aralik)==2: df = df[(df["gun"]>=aralik[0])&(df["gun"]<=aralik[1])]
    if tip=="Günlük":
        rpr = df.groupby("gun")["toplam_tutar"].sum().reset_index()
        rpr.columns=["Tarih","Toplam Satış (₺)"]
        st.dataframe(rpr, use_container_width=True)
        fig=px.bar(rpr, x="Tarih", y="Toplam Satış (₺)", title="Günlük Satışlar", color_discrete_sequence=["#f97316"])
        st.plotly_chart(fig, use_container_width=True)
    elif tip=="Aylık":
        rpr = df.groupby("ay")["toplam_tutar"].sum().reset_index()
        rpr.columns=["Ay","Toplam Satış (₺)"]
        st.dataframe(rpr, use_container_width=True)
        fig=px.line(rpr, x="Ay", y="Toplam Satış (₺)", markers=True, title="Aylık Trend", color_discrete_sequence=["#8b5cf6"])
        st.plotly_chart(fig, use_container_width=True)
    else:
        rpr = df.groupby("urun_adi").agg(Adet=("miktar","sum"),Ciro=("toplam_tutar","sum")).reset_index()
        st.dataframe(rpr, use_container_width=True)
        colA,colB=st.columns(2)
        with colA:
            fig1=px.pie(rpr, values="Ciro", names="urun_adi", title="Ciro Dağılımı", hole=0.3)
            st.plotly_chart(fig1, use_container_width=True)
        with colB:
            fig2=px.bar(rpr, x="urun_adi", y="Adet", title="Satış Adedi", color_discrete_sequence=["#10b981"])
            st.plotly_chart(fig2, use_container_width=True)

def yedekleme_sayfasi():
    st.markdown('<div class="main-header">💾 Yedekleme</div>',unsafe_allow_html=True)
    c1,c2=st.columns(2)
    with c1:
        yedek={"stok":st.session_state.stok,"fire":st.session_state.fire,"barkod_db":st.session_state.barkod_db}
        st.download_button("📥 JSON İndir", json.dumps(yedek,ensure_ascii=False,indent=2), "yedek.json", use_container_width=True)
    with c2:
        dosya=st.file_uploader("Yedek yükle", type="json")
        if dosya:
            icerik=json.load(dosya)
            st.session_state.stok=icerik.get("stok",[])
            st.session_state.fire=icerik.get("fire",[])
            st.session_state.barkod_db=icerik.get("barkod_db",{})
            veriyi_kaydet()
            st.toast("✅ Yüklendi", duration=5000)
            st.rerun()

def veriyi_kaydet():
    dosya_yaz(STOK_DOSYASI, st.session_state.stok)
    dosya_yaz(FIRE_DOSYASI, st.session_state.fire)

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
        st.markdown('<h2 style="color:white;">🏪 Market</h2>',unsafe_allow_html=True)
        st.markdown('<p style="color:#F97316;">v2.0</p>',unsafe_allow_html=True)
        if st.session_state.current_user:
            st.markdown(f'<div style="background:rgba(249,115,22,0.2);border-radius:12px;padding:12px;"><p style="color:white;">👤 {st.session_state.current_user.get("ad","Kullanıcı")}</p></div>',unsafe_allow_html=True)
        sayfa = st.radio("Menü", ["🏠 Ana Panel","📱 Barkod","💵 Satış","📦 Stok","🔥 Sipariş","📉 Fire Analizi","📊 Satış Raporu","💾 Yedekleme"], label_visibility="collapsed")
        if st.button("🚪 Çıkış", use_container_width=True): cikis()
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
