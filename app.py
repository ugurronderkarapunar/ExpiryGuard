import streamlit as st
import json
import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import logging
from io import BytesIO
import time
import hashlib

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
        "kasiyer": ["barkod", "stok_goruntule"],
        "depocu": ["barkod", "stok_goruntule", "stok_ekle", "skt_takip"]
    },
    "dosya_yollari": {
        "stok": "stok.json",
        "fire": "fire.json",
        "hareket": "hareket.json",
        "barkod_db": "barkod_db.json",
        "tedarikciler": "tedarikciler.json",
        "kullanicilar": "kullanicilar.json"
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
STOK_DOSYASI = config["dosya_yollari"]["stok"]
FIRE_DOSYASI = config["dosya_yollari"]["fire"]
HAREKET_DOSYASI = config["dosya_yollari"]["hareket"]
BARKOD_DB_DOSYASI = config["dosya_yollari"]["barkod_db"]
TEDARIKCI_DOSYASI = config["dosya_yollari"]["tedarikciler"]
KULLANICI_DOSYASI = config["dosya_yollari"]["kullanicilar"]
KATEGORILER = config["kategoriler"]
BIRIMLER = config["birimler"]
ROLLER = config["roller"]
OTURUM_SURESI = config["oturum_suresi_dk"]
SKT_UYARI_GUN = config["skt_uyari_gun"]

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
        for anahtar, varsayilan in [("miktar", 0), ("birim", "adet"), ("tedarikci", ""), ("durum", "Bekliyor")]:
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
         "alis_fiyat": 18.50, "satis_fiyat": 25.90, "tedarikci": "ABC Un Fabrikası", "kdv_oran": 1},
        {"urun_adi": "Şeker", "miktar": 5, "birim": "kg", "kategori": "Kuru Gıda",
         "min_miktar": 10, "barkod": "8691234567891", "son_kullanma_tarihi": "2026-05-15",
         "alis_fiyat": 22.00, "satis_fiyat": 32.50, "tedarikci": "XYZ Şeker", "kdv_oran": 8},
        {"urun_adi": "Süt", "miktar": 40, "birim": "litre", "kategori": "Süt Ürünleri",
         "min_miktar": 15, "barkod": "8691234567892", "son_kullanma_tarihi": "2026-05-08",
         "alis_fiyat": 12.00, "satis_fiyat": 18.90, "tedarikci": "Sütaş", "kdv_oran": 1},
        {"urun_adi": "Yumurta", "miktar": 200, "birim": "adet", "kategori": "Diğer",
         "min_miktar": 30, "barkod": "8691234567893", "son_kullanma_tarihi": "2026-05-06",
         "alis_fiyat": 2.50, "satis_fiyat": 4.50, "tedarikci": "Köy Yumurtası", "kdv_oran": 1},
        {"urun_adi": "Tereyağı", "miktar": 25, "birim": "kg", "kategori": "Süt Ürünleri",
         "min_miktar": 5, "barkod": "8691234567894", "son_kullanma_tarihi": "2026-06-20",
         "alis_fiyat": 120.00, "satis_fiyat": 175.00, "tedarikci": "Sütaş", "kdv_oran": 8},
    ]

def mock_fire_olustur():
    return [
        {"urun_adi": "Un", "miktar": 10, "birim": "kg", "aciliyet": "🔥 Yüksek", "tedarikci": "ABC Un Fabrikası", "durum": "Bekliyor"},
        {"urun_adi": "Şeker", "miktar": 5, "birim": "kg", "aciliyet": "⚡ Orta", "tedarikci": "XYZ Şeker", "durum": "Sipariş Verildi"},
        {"urun_adi": "Yumurta", "miktar": 50, "birim": "adet", "aciliyet": "✅ Düşük", "tedarikci": "Köy Yumurtası", "durum": "Bekliyor"},
    ]

def mock_tedarikciler_olustur():
    return [
        {"ad": "ABC Un Fabrikası", "urunler": ["Un"], "guven_puani": 9.2, "ortalama_teslimat_gun": 2, "son_siparis": "2026-04-28"},
        {"ad": "Sütaş", "urunler": ["Süt", "Tereyağı"], "guven_puani": 8.7, "ortalama_teslimat_gun": 1, "son_siparis": "2026-05-01"},
        {"ad": "Köy Yumurtası", "urunler": ["Yumurta"], "guven_puani": 7.5, "ortalama_teslimat_gun": 3, "son_siparis": "2026-04-30"},
    ]

def mock_kullanicilar_olustur():
    return [
        {"kullanici_adi": "admin", "sifre": hashlib.sha256("1234".encode()).hexdigest(), "rol": "patron", "ad": "Ahmet Yılmaz"},
        {"kullanici_adi": "kasiyer1", "sifre": hashlib.sha256("1234".encode()).hexdigest(), "rol": "kasiyer", "ad": "Ayşe Demir"},
        {"kullanici_adi": "depocu1", "sifre": hashlib.sha256("1234".encode()).hexdigest(), "rol": "depocu", "ad": "Mehmet Can"},
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
    # Son 1000 kayıt tut
    if len(hareketler) > 1000:
        hareketler = hareketler[-1000:]
    dosya_yaz(HAREKET_DOSYASI, hareketler)

# ---------------------------- OTURUM YÖNETİMİ -----------------------
def oturumu_baslat():
    if "stok" not in st.session_state:
        st.session_state.stok = dosya_oku(STOK_DOSYASI, mock_stok_olustur())
    if "fire" not in st.session_state:
        st.session_state.fire = dosya_oku(FIRE_DOSYASI, mock_fire_olustur())
    if "barkod_db" not in st.session_state:
        st.session_state.barkod_db = dosya_oku(BARKOD_DB_DOSYASI, mock_barkod_db_olustur())
    if "tedarikciler" not in st.session_state:
        st.session_state.tedarikciler = dosya_oku(TEDARIKCI_DOSYASI, mock_tedarikciler_olustur())
    if "kullanicilar" not in st.session_state:
        st.session_state.kullanicilar = dosya_oku(KULLANICI_DOSYASI, mock_kullanicilar_olustur())
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

def yetki_kontrol(gerekli_yetki):
    if not st.session_state.current_user:
        return False
    rol = st.session_state.current_user["rol"]
    if rol == "patron":
        return True
    return gerekli_yetki in ROLLER.get(rol, [])

# ---------------------------- GİRİŞ EKRANI --------------------------
def giris_ekrani():
    st.title("🏪 Market Yönetim Sistemi - Giriş")
    with st.form("giris_formu"):
        kullanici = st.text_input("👤 Kullanıcı Adı")
        sifre = st.text_input("🔒 Şifre", type="password")
        if st.form_submit_button("Giriş Yap", use_container_width=True):
            sifre_hash = hashlib.sha256(sifre.encode()).hexdigest()
            for k in st.session_state.kullanicilar:
                if k["kullanici_adi"] == kullanici:
                    if k["sifre"] == sifre_hash or (kullanici == "admin" and sifre == "1234"):  # demo için
                        st.session_state.authenticated = True
                        st.session_state.current_user = k
                        st.session_state.last_activity = datetime.now()
                        st.rerun()
                    else:
                        st.error("❌ Hatalı şifre!")
                        return
            st.error("❌ Kullanıcı bulunamadı!")

def cikis_yap():
    st.session_state.authenticated = False
    st.session_state.current_user = None
    st.rerun()

# ---------------------------- ANA SAYFA (GELİŞMİŞ KPI) ---------------
def ana_sayfa():
    st.header("📊 Yönetim Paneli")
    
    # KPI Kartları
    kritik_stok = [u for u in st.session_state.stok if u.get("min_miktar", 0) > 0 and u["miktar"] <= u.get("min_miktar", 0)]
    skt_yaklasan = []
    bugun = datetime.now().date()
    for u in st.session_state.stok:
        skt_str = u.get("son_kullanma_tarihi", "")
        if skt_str:
            try:
                skt = datetime.strptime(skt_str, "%Y-%m-%d").date()
                kalan = (skt - bugun).days
                if 0 <= kalan <= SKT_UYARI_GUN:
                    skt_yaklasan.append(u)
            except ValueError:
                pass
    
    toplam_urun = len(st.session_state.stok)
    acik_siparis = len([s for s in st.session_state.fire if s.get("durum") == "Bekliyor"])
    toplam_deger = sum(u["miktar"] * u.get("satis_fiyat", 0) for u in st.session_state.stok)
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📦 Toplam Ürün", toplam_urun)
    col2.metric("⚠️ Kritik Stok", len(kritik_stok), delta_color="inverse")
    col3.metric("⏰ SKT Yaklaşan", len(skt_yaklasan), delta_color="inverse")
    col4.metric("💰 Stok Değeri", f"{toplam_deger:,.2f} ₺")
    
    # İkinci satır
    col5, col6, col7, col8 = st.columns(4)
    col5.metric("🔥 Açık Sipariş", acik_siparis)
    col6.metric("🏭 Tedarikçi", len(st.session_state.tedarikciler))
    
    # Kâr tahmini
    toplam_maliyet = sum(u["miktar"] * u.get("alis_fiyat", 0) for u in st.session_state.stok)
    potansiyel_kar = toplam_deger - toplam_maliyet
    col7.metric("💸 Potansiyel Kâr", f"{potansiyel_kar:,.2f} ₺")
    
    kar_marji = (potansiyel_kar / toplam_deger * 100) if toplam_deger > 0 else 0
    col8.metric("📈 Kâr Marjı", f"%{kar_marji:.1f}")
    
    st.divider()
    
    # Uyarılar bölümü
    if kritik_stok or skt_yaklasan:
        col_uyari1, col_uyari2 = st.columns(2)
        
        with col_uyari1:
            if kritik_stok:
                st.subheader("🚨 Kritik Stok Uyarıları")
                for urun in kritik_stok[:5]:
                    st.error(f"📦 {urun['urun_adi']}: {urun['miktar']:.2f} {urun['birim']} (Min: {urun['min_miktar']:.2f})")
        
        with col_uyari2:
            if skt_yaklasan:
                st.subheader("⏰ SKT Yaklaşan Ürünler")
                for urun in skt_yaklasan[:5]:
                    skt = datetime.strptime(urun["son_kullanma_tarihi"], "%Y-%m-%d").date()
                    kalan = (skt - bugun).days
                    indirim = "%30" if kalan <= 1 else "%20" if kalan <= 3 else "%10"
                    st.warning(f"📛 {urun['urun_adi']}: {kalan} gün → {indirim} indirim öner")
    
    # Hızlı grafikler
    st.divider()
    col_grafik1, col_grafik2 = st.columns(2)
    
    with col_grafik1:
        st.subheader("📊 Kategori Bazlı Stok Dağılımı")
        if st.session_state.stok:
            df = pd.DataFrame(st.session_state.stok)
            df_kategori = df.groupby("kategori")["miktar"].sum().reset_index()
            fig = px.pie(df_kategori, values="miktar", names="kategori", hole=0.4)
            st.plotly_chart(fig, use_container_width=True)
    
    with col_grafik2:
        st.subheader("🔥 Acil Siparişler")
        acil_siparisler = [s for s in st.session_state.fire if s.get("aciliyet") == "🔥 Yüksek" and s.get("durum") == "Bekliyor"]
        if acil_siparisler:
            df_acil = pd.DataFrame(acil_siparisler)
            st.dataframe(df_acil[["urun_adi", "miktar", "birim", "tedarikci"]], use_container_width=True)
        else:
            st.success("✅ Acil sipariş bulunmamaktadır.")

# ---------------------------- STOK SAYFASI --------------------------
def stok_sayfasi():
    st.header("📦 Stok Yönetimi")
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📋 Liste", "➕ Ekle", "✏️ Düzenle/Sil", "📊 Analiz", "📥 Toplu Yükleme"])
    
    with tab1:
        st.subheader("Stok Listesi")
        col1, col2, col3 = st.columns(3)
        arama = col1.text_input("🔍 Ürün Ara", key="stok_arama")
        kategori_sec = col2.selectbox("📂 Kategori", ["Tümü"] + KATEGORILER, key="stok_kategori")
        siralama = col3.selectbox("📊 Sırala", ["Ürün Adı", "Miktar (Azalan)", "Miktar (Artan)", "SKT"])
        
        df = pd.DataFrame(st.session_state.stok)
        if not df.empty:
            if kategori_sec != "Tümü":
                df = df[df["kategori"] == kategori_sec]
            if arama:
                df = df[df["urun_adi"].str.contains(arama, case=False)]
            
            # Sıralama
            if siralama == "Miktar (Azalan)":
                df = df.sort_values("miktar", ascending=False)
            elif siralama == "Miktar (Artan)":
                df = df.sort_values("miktar", ascending=True)
            elif siralama == "SKT":
                df["skt_siralama"] = pd.to_datetime(df["son_kullanma_tarihi"].replace("", None))
                df = df.sort_values("skt_siralama")
            
            # Kâr bilgisi ekle
            df["kar_marji"] = df.apply(lambda r: f"%{((r['satis_fiyat'] - r['alis_fiyat']) / r['satis_fiyat'] * 100):.1f}" if r.get("satis_fiyat", 0) > 0 else "-", axis=1)
            
            def highlight_row(row):
                min_m = row.get("min_miktar", 0)
                if min_m > 0 and row["miktar"] <= min_m:
                    return ['background-color: #ffcccc'] * len(row)
                return [''] * len(row)
            
            gosterilecek = ["urun_adi", "miktar", "birim", "kategori", "alis_fiyat", "satis_fiyat", "kar_marji", "son_kullanma_tarihi", "tedarikci"]
            styled_df = df[gosterilecek].style.apply(highlight_row, axis=1).format(precision=2)
            st.dataframe(styled_df, use_container_width=True)
        else:
            st.info("Ürün bulunamadı.")
    
    with tab2:
        with st.form("urun_ekle_form"):
            col1, col2, col3 = st.columns(3)
            urun_adi = col1.text_input("Ürün Adı *")
            barkod = col2.text_input("Barkod")
            miktar = col1.number_input("Miktar", min_value=0.0, step=0.01, format="%.2f")
            birim = col2.selectbox("Birim", BIRIMLER)
            kategori = col3.selectbox("Kategori", KATEGORILER)
            alis_fiyat = col1.number_input("Alış Fiyatı (₺)", min_value=0.0, step=0.01, format="%.2f")
            satis_fiyat = col2.number_input("Satış Fiyatı (₺)", min_value=0.0, step=0.01, format="%.2f")
            min_miktar = col3.number_input("Min Stok", min_value=0.0, step=0.01, format="%.2f", value=5.0)
            tedarikci = col1.selectbox("Tedarikçi", ["Seçiniz"] + [t["ad"] for t in st.session_state.tedarikciler])
            skt = col2.date_input("SKT", min_value=datetime.now().date())
            raf_no = col3.text_input("Raf No", placeholder="A-12")
            
            if st.form_submit_button("✅ Ürün Ekle", use_container_width=True):
                if not urun_adi.strip():
                    st.error("Ürün adı zorunludur!")
                else:
                    st.session_state.stok.append({
                        "urun_adi": urun_adi.strip(),
                        "miktar": miktar,
                        "birim": birim,
                        "kategori": kategori,
                        "min_miktar": min_miktar,
                        "barkod": barkod.strip(),
                        "son_kullanma_tarihi": skt.strftime("%Y-%m-%d"),
                        "alis_fiyat": alis_fiyat,
                        "satis_fiyat": satis_fiyat,
                        "tedarikci": tedarikci if tedarikci != "Seçiniz" else "",
                        "raf_no": raf_no.strip(),
                        "kdv_oran": 8
                    })
                    veriyi_kaydet()
                    st.toast(f"✅ {urun_adi} stoğa eklendi", icon="✅")
                    st.rerun()
    
    with tab3:
        st.subheader("Düzenle veya Sil")
        if st.session_state.stok:
            urun_listesi = [f"{u['urun_adi']} ({u['miktar']:.2f} {u['birim']})" for u in st.session_state.stok]
            secili = st.selectbox("Ürün Seç", urun_listesi, key="duzenle_sec")
            idx = urun_listesi.index(secili)
            urun = st.session_state.stok[idx]
            
            with st.form("duzenle_form"):
                col1, col2, col3 = st.columns(3)
                yeni_ad = col1.text_input("Ürün Adı", value=urun["urun_adi"])
                yeni_miktar = col1.number_input("Miktar", value=float(urun["miktar"]), min_value=0.0, format="%.2f")
                try:
                    birim_index = BIRIMLER.index(urun.get("birim", "adet"))
                except ValueError:
                    birim_index = 0
                yeni_birim = col2.selectbox("Birim", BIRIMLER, index=birim_index)
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
                
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.form_submit_button("💾 Kaydet"):
                        st.session_state.stok[idx] = {
                            "urun_adi": yeni_ad.strip(), "miktar": yeni_miktar, "birim": yeni_birim,
                            "kategori": yeni_kategori, "min_miktar": yeni_min,
                            "barkod": urun.get("barkod", ""), "son_kullanma_tarihi": yeni_skt.strftime("%Y-%m-%d"),
                            "alis_fiyat": yeni_alis, "satis_fiyat": yeni_satis,
                            "tedarikci": urun.get("tedarikci", ""), "raf_no": yeni_raf.strip(),
                            "kdv_oran": urun.get("kdv_oran", 8)
                        }
                        veriyi_kaydet()
                        st.toast("✅ Güncellendi", icon="✏️")
                        st.rerun()
                with col_btn2:
                    with st.expander("🗑️ Sil", expanded=False):
                        if st.checkbox("Onaylıyorum", key=f"sil_{idx}"):
                            if st.form_submit_button("⚠️ Sil"):
                                st.session_state.stok.pop(idx)
                                veriyi_kaydet()
                                st.toast("🗑️ Silindi", icon="🗑️")
                                st.rerun()
        else:
            st.info("Düzenlenecek ürün yok.")
    
    with tab4:
        st.subheader("📊 Stok Analizi")
        if st.session_state.stok:
            df = pd.DataFrame(st.session_state.stok)
            # Kategori bazlı stok değeri
            df["stok_degeri"] = df["miktar"] * df["satis_fiyat"]
            kategori_deger = df.groupby("kategori")["stok_degeri"].sum().reset_index()
            fig = px.bar(kategori_deger, x="kategori", y="stok_degeri", title="Kategori Bazlı Stok Değeri (₺)")
            st.plotly_chart(fig, use_container_width=True)
    
    with tab5:
        st.subheader("📥 Toplu Yükleme")
        sablon = pd.DataFrame(columns=["urun_adi", "miktar", "birim", "kategori", "alis_fiyat", "satis_fiyat", "min_miktar", "barkod", "son_kullanma_tarihi", "tedarikci", "raf_no"])
        st.download_button("📥 CSV Şablon", sablon.to_csv(index=False), "stok_sablon.csv", "text/csv")
        uploaded = st.file_uploader("CSV yükle", type="csv")
        if uploaded:
            try:
                df_csv = pd.read_csv(uploaded)
                for _, row in df_csv.iterrows():
                    st.session_state.stok.append({
                        "urun_adi": row["urun_adi"], "miktar": float(row["miktar"]), "birim": row["birim"],
                        "kategori": row["kategori"] if row["kategori"] in KATEGORILER else "Diğer",
                        "min_miktar": float(row.get("min_miktar", 0)),
                        "barkod": str(row.get("barkod", "")), "son_kullanma_tarihi": str(row.get("son_kullanma_tarihi", "")),
                        "alis_fiyat": float(row.get("alis_fiyat", 0)), "satis_fiyat": float(row.get("satis_fiyat", 0)),
                        "tedarikci": str(row.get("tedarikci", "")), "raf_no": str(row.get("raf_no", ""))
                    })
                veriyi_kaydet()
                st.toast(f"✅ {len(df_csv)} ürün eklendi", icon="📥")
                st.rerun()
            except Exception as e:
                st.error(f"Hata: {e}")
        
        # Excel çıktı
        if st.session_state.stok:
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                pd.DataFrame(st.session_state.stok).to_excel(writer, index=False, sheet_name='Stok')
            st.download_button("📊 Excel İndir", data=output.getvalue(), file_name="stok.xlsx")

# ---------------------------- FİRE/SPARİŞ SAYFASI --------------------
def siparis_sayfasi():
    st.header("🔥 Sipariş & Fire Takibi")
    tab1, tab2, tab3, tab4 = st.tabs(["📋 Liste", "➕ Ekle", "📊 Analiz", "🏭 Tedarikçi"])
    
    with tab1:
        st.subheader("Aktif Siparişler")
        df = pd.DataFrame(st.session_state.fire)
        if not df.empty:
            # Filtre
            durum_sec = st.selectbox("Durum", ["Tümü", "Bekliyor", "Sipariş
