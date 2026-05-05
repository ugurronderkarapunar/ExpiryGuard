import streamlit as st
import json
import os
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import logging

# ---------------------------- LOGLAMA --------------------------------
logging.basicConfig(
    filename='error.log',
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ---------------------------- CONFIG OKUMA ---------------------------
CONFIG_DOSYASI = "config.json"
VARSAYILAN_CONFIG = {
    "kullanici_adi": "admin",
    "sifre": "1234",
    "oturum_suresi_dk": 30,
    "varsayilan_min_stok": 10,
    "kategoriler": ["Kuru Gıda", "Süt Ürünleri", "İçecek", "Temizlik", "Diğer"],
    "dosya_yollari": {
        "stok": "stok.json",
        "fire": "fire.json",
        "hareket": "hareket.json"
    }
}

def load_config():
    if os.path.exists(CONFIG_DOSYASI):
        try:
            with open(CONFIG_DOSYASI, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Config okuma hatası: {e}")
            st.error("Config dosyası okunamadı, varsayılan ayarlar kullanılıyor.")
    return VARSAYILAN_CONFIG

config = load_config()

# ---------------------------- SABİTLER ----------------------------
STOK_DOSYASI = config["dosya_yollari"]["stok"]
FIRE_DOSYASI = config["dosya_yollari"]["fire"]
HAREKET_DOSYASI = config["dosya_yollari"]["hareket"]
KATEGORILER = config["kategoriler"]
OTURUM_SURESI = config["oturum_suresi_dk"]

# ---------------------------- DOSYA İŞLEMLERİ -----------------------
def dosya_oku(dosya_adi, varsayilan=None):
    if os.path.exists(dosya_adi):
        try:
            with open(dosya_adi, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"{dosya_adi} okuma hatası: {e}")
            st.error(f"{dosya_adi} okunurken hata oluştu.")
    return varsayilan if varsayilan is not None else []

def dosya_yaz(dosya_adi, veri):
    try:
        with open(dosya_adi, "w", encoding="utf-8") as f:
            json.dump(veri, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logging.error(f"{dosya_adi} yazma hatası: {e}")
        st.error(f"Dosyaya yazılamadı: {dosya_adi}")
        return False

# ---------------------------- MOCK VERİ -----------------------------
def mock_stok_olustur():
    return [
        {"urun_adi": "Un", "miktar": 150, "birim": "kg", "kategori": "Kuru Gıda", "min_miktar": 20},
        {"urun_adi": "Şeker", "miktar": 5, "birim": "kg", "kategori": "Kuru Gıda", "min_miktar": 10},
        {"urun_adi": "Süt", "miktar": 40, "birim": "litre", "kategori": "Süt Ürünleri", "min_miktar": 15},
        {"urun_adi": "Yumurta", "miktar": 200, "birim": "adet", "kategori": "Diğer", "min_miktar": 30},
        {"urun_adi": "Tereyağı", "miktar": 25, "birim": "kg", "kategori": "Süt Ürünleri", "min_miktar": 5},
    ]

def mock_fire_olustur():
    return [
        {"urun_adi": "Un", "adet": 10, "aciliyet": "🔥 Yüksek"},
        {"urun_adi": "Şeker", "adet": 5, "aciliyet": "⚡ Orta"},
        {"urun_adi": "Yumurta", "adet": 50, "aciliyet": "✅ Düşük"},
    ]

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
    dosya_yaz(HAREKET_DOSYASI, hareketler)

# ---------------------------- OTURUM YÖNETİMİ -----------------------
def oturumu_baslat():
    if "stok" not in st.session_state:
        st.session_state.stok = dosya_oku(STOK_DOSYASI, mock_stok_olustur())
    if "fire" not in st.session_state:
        st.session_state.fire = dosya_oku(FIRE_DOSYASI, mock_fire_olustur())
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "last_activity" not in st.session_state:
        st.session_state.last_activity = datetime.now()
    if "config" not in st.session_state:
        st.session_state.config = config

def oturum_kontrol():
    if st.session_state.authenticated:
        now = datetime.now()
        fark = now - st.session_state.last_activity
        if fark > timedelta(minutes=OTURUM_SURESI):
            st.session_state.authenticated = False
            st.warning("⏳ Oturum süresi doldu. Lütfen tekrar giriş yapın.")
            st.rerun()
        else:
            st.session_state.last_activity = now

# ---------------------------- GİRİŞ EKRANI --------------------------
def giris_ekrani():
    st.title("🔐 Stok Takip Sistemi - Giriş")
    with st.form("giris_formu"):
        kullanici = st.text_input("Kullanıcı Adı")
        sifre = st.text_input("Şifre", type="password")
        if st.form_submit_button("Giriş Yap"):
            if kullanici == st.session_state.config["kullanici_adi"] and sifre == st.session_state.config["sifre"]:
                st.session_state.authenticated = True
                st.session_state.last_activity = datetime.now()
                st.rerun()
            else:
                st.error("❌ Hatalı kullanıcı adı veya şifre!")

# ---------------------------- ÇIKIŞ -------------------------------
def cikis_yap():
    st.session_state.authenticated = False
    st.rerun()

# ---------------------------- ANA SAYFA (KPI) ---------------------
def ana_sayfa():
    st.header("📊 Yönetim Paneli")
    # Kritik stok eşiği kontrolü
    kritik_esik = 10  # varsayılan, istenirse config'ten alınabilir
    kritik_urunler = [u for u in st.session_state.stok if u.get("min_miktar", 0) > 0 and u["miktar"] <= u["min_miktar"]]
    toplam_urun = len(st.session_state.stok)
    acik_siparis = len(st.session_state.fire)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("📦 Toplam Ürün Çeşidi", toplam_urun)
    col2.metric("⚠️ Kritik Stok", len(kritik_urunler), delta_color="inverse")
    col3.metric("🔥 Açık Sipariş", acik_siparis)
    
    if kritik_urunler:
        st.subheader("🚨 Kritik Stok Uyarıları")
        for urun in kritik_urunler:
            st.error(f"{urun['urun_adi']}: {urun['miktar']} {urun['birim']} (Minimum: {urun['min_miktar']})")

# ---------------------------- STOK SAYFASI (GÜNCELLENMİŞ) ----------
def stok_sayfasi():
    st.header("📦 Stok Yönetimi")
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📋 Liste", "➕ Ekle", "✏️ Düzenle/Sil", "📊 Grafikler", "📥 Toplu Yükleme"])
    
    with tab1:
        st.subheader("Stok Listesi")
        # Arama ve filtre
        arama = st.text_input("Ürün Ara", key="stok_arama")
        kategori_sec = st.selectbox("Kategori Filtrele", ["Tümü"] + KATEGORILER, key="stok_kategori")
        
        df = pd.DataFrame(st.session_state.stok)
        if not df.empty:
            if kategori_sec != "Tümü":
                df = df[df["kategori"] == kategori_sec]
            if arama:
                df = df[df["urun_adi"].str.contains(arama, case=False)]
            # Renklendirilmiş tablo (kritik stok satırları kırmızı)
            def highlight_critical(row):
                min_m = row.get("min_miktar", 0)
                if min_m > 0 and row["miktar"] <= min_m:
                    return ['background-color: #ffcccc'] * len(row)
                return [''] * len(row)
            
            styled_df = df.style.apply(highlight_critical, axis=1)
            st.dataframe(styled_df, use_container_width=True)
        else:
            st.info("Gösterilecek ürün yok.")
        
        if st.button("🔄 Mock Veriye Sıfırla", key="sifirla_stok"):
            st.session_state.stok = mock_stok_olustur()
            veriyi_kaydet()
            st.toast("Stok mock verilerle sıfırlandı.", icon="🔄")
            st.rerun()
    
    with tab2:
        with st.form("urun_ekle_form"):
            urun_adi = st.text_input("Ürün Adı")
            miktar = st.number_input("Miktar", min_value=0.0, step=0.01)
            birim = st.selectbox("Birim", ["kg", "litre", "adet", "paket", "gram", "koli"])
            kategori = st.selectbox("Kategori", KATEGORILER)
            min_miktar = st.number_input("Minimum Stok (uyarı için)", min_value=0.0, step=0.01, value=0.0)
            if st.form_submit_button("Ekle"):
                if not urun_adi.strip():
                    st.error("Ürün adı boş olamaz!")
                else:
                    yeni_urun = {
                        "urun_adi": urun_adi.strip(),
                        "miktar": miktar,
                        "birim": birim,
                        "kategori": kategori,
                        "min_miktar": min_miktar
                    }
                    st.session_state.stok.append(yeni_urun)
                    veriyi_kaydet()
                    hareket_ekle(config["kullanici_adi"], "Ekleme", urun_adi, f"{miktar} {birim} eklendi")
                    st.toast(f"{urun_adi} stoğa eklendi.", icon="✅")
                    st.rerun()
    
    with tab3:
        st.subheader("Düzenle veya Sil")
        if st.session_state.stok:
            urun_listesi = [u["urun_adi"] for u in st.session_state.stok]
            secili = st.selectbox("Ürün Seç", urun_listesi, key="duzenle_sec")
            idx = urun_listesi.index(secili)
            urun = st.session_state.stok[idx]
            with st.form("duzenle_form"):
                yeni_ad = st.text_input("Ürün Adı", value=urun["urun_adi"])
                yeni_miktar = st.number_input("Miktar", value=float(urun["miktar"]), min_value=0.0)
                yeni_birim = st.selectbox("Birim", ["kg", "litre", "adet", "paket", "gram", "koli"],
                                          index=["kg", "litre", "adet", "paket", "gram", "koli"].index(urun["birim"]) if urun["birim"] in ["kg", "litre", "adet", "paket", "gram", "koli"] else 0)
                yeni_kategori = st.selectbox("Kategori", KATEGORILER,
                                            index=KATEGORILER.index(urun["kategori"]) if urun["kategori"] in KATEGORILER else 0)
                yeni_min = st.number_input("Min. Stok", value=float(urun.get("min_miktar", 0)), min_value=0.0)
                
                col1, col2, col3 = st.columns([2,1,1])
                with col1:
                    if st.form_submit_button("💾 Kaydet"):
                        if not yeni_ad.strip():
                            st.error("Ürün adı boş olamaz!")
                        else:
                            st.session_state.stok[idx] = {
                                "urun_adi": yeni_ad.strip(),
                                "miktar": yeni_miktar,
                                "birim": yeni_birim,
                                "kategori": yeni_kategori,
                                "min_miktar": yeni_min
                            }
                            veriyi_kaydet()
                            hareket_ekle(config["kullanici_adi"], "Güncelleme", yeni_ad, "Bilgiler güncellendi")
                            st.toast("Ürün güncellendi.", icon="✏️")
                            st.rerun()
                with col2:
                    # Silme onayı expander içinde
                    with st.expander("🗑️ Sil", expanded=False):
                        st.warning("Bu işlem geri alınamaz!")
                        onay = st.checkbox("Eminim, silmek istiyorum.", key=f"sil_onay_{idx}")
                        if onay:
                            if st.form_submit_button("⚠️ Silmeyi Onayla"):
                                silinen = st.session_state.stok.pop(idx)
                                veriyi_kaydet()
                                hareket_ekle(config["kullanici_adi"], "Silme", silinen["urun_adi"], "Ürün silindi")
                                st.toast(f"{silinen['urun_adi']} silindi.", icon="🗑️")
                                st.rerun()
        else:
            st.info("Düzenlenecek ürün yok.")
    
    with tab4:
        st.subheader("Stok Dağılımı")
        if st.session_state.stok:
            df_stok = pd.DataFrame(st.session_state.stok)
            fig = px.pie(df_stok, values='miktar', names='urun_adi', title='Ürünlere Göre Miktar Dağılımı')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Grafik için veri yok.")
    
    with tab5:
        st.subheader("CSV ile Toplu Ürün Yükleme")
        st.markdown("Şablon dosyasını indirip doldurarak toplu yükleme yapabilirsiniz.")
        sablon_df = pd.DataFrame(columns=["urun_adi", "miktar", "birim", "kategori", "min_miktar"])
        st.download_button("📥 CSV Şablon İndir", sablon_df.to_csv(index=False), "stok_sablon.csv", "text/csv")
        
        uploaded_file = st.file_uploader("CSV dosyası seçin", type="csv")
        if uploaded_file is not None:
            try:
                df_csv = pd.read_csv(uploaded_file)
                for _, row in df_csv.iterrows():
                    st.session_state.stok.append({
                        "urun_adi": row["urun_adi"],
                        "miktar": float(row["miktar"]),
                        "birim": row["birim"],
                        "kategori": row["kategori"] if row["kategori"] in KATEGORILER else "Diğer",
                        "min_miktar": float(row.get("min_miktar", 0))
                    })
                veriyi_kaydet()
                st.toast(f"{len(df_csv)} ürün başarıyla eklendi.", icon="📥")
                st.rerun()
            except Exception as e:
                st.error(f"CSV yüklenirken hata: {e}")
    
    # Excel dışa aktarma
    if st.session_state.stok:
        st.download_button(
            "📊 Stok Listesini Excel Olarak İndir",
            pd.DataFrame(st.session_state.stok).to_excel(index=False, engine='openpyxl'),
            "stok_listesi.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# ---------------------------- SİPARİŞ PANOSU (GÜNCELLENMİŞ) ---------
def siparis_sayfasi():
    st.header("🔥 Sipariş Panosu (Fire Takibi)")
    tab1, tab2, tab3 = st.tabs(["📋 Siparişler", "➕ Ekle", "✏️ Düzenle/Sil"])
    
    with tab1:
        arama = st.text_input("Sipariş Ara", key="siparis_arama")
        df = pd.DataFrame(st.session_state.fire)
        if not df.empty:
            if arama:
                df = df[df["urun_adi"].str.contains(arama, case=False)]
            # Aciliyet badge'lerini HTML ile göster
            def format_aciliyet(val):
                if "Yüksek" in val:
                    return '🔥 <span style="color:red; font-weight:bold">Yüksek</span>'
                elif "Orta" in val:
                    return '⚡ <span style="color:orange; font-weight:bold">Orta</span>'
                else:
                    return '✅ <span style="color:green; font-weight:bold">Düşük</span>'
            if "aciliyet" in df.columns:
                df["aciliyet_gorsel"] = df["aciliyet"].apply(format_aciliyet)
            st.write(df.to_html(escape=False, index=False), unsafe_allow_html=True)
        else:
            st.info("Henüz sipariş eklenmemiş.")
        if st.button("🔄 Mock Siparişlere Sıfırla", key="sifirla_fire"):
            st.session_state.fire = mock_fire_olustur()
            veriyi_kaydet()
            st.toast("Siparişler mock verilerle sıfırlandı.", icon="🔄")
            st.rerun()
        # Grafik
        st.subheader("Aciliyet Dağılımı")
        if not df.empty:
            fig = px.bar(df, x='aciliyet', title='Sipariş Aciliyet Durumları')
            st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        with st.form("siparis_ekle_form"):
            urun_adi = st.text_input("Ürün Adı")
            adet = st.number_input("Adet", min_value=1, step=1)
            aciliyet = st.selectbox("Aciliyet", ["🔥 Yüksek", "⚡ Orta", "✅ Düşük"])
            if st.form_submit_button("Ekle"):
                if not urun_adi.strip():
                    st.error("Ürün adı gerekli!")
                else:
                    st.session_state.fire.append({
                        "urun_adi": urun_adi.strip(),
                        "adet": int(adet),
                        "aciliyet": aciliyet,
                        "eklenme_tarihi": datetime.now().strftime("%Y-%m-%d %H:%M")
                    })
                    veriyi_kaydet()
                    hareket_ekle(config["kullanici_adi"], "Sipariş Ekleme", urun_adi, f"{adet} adet {aciliyet}")
                    st.toast("Sipariş eklendi.", icon="🔥")
                    st.rerun()
    
    with tab3:
        if st.session_state.fire:
            siparis_str = [f"{s['urun_adi']} ({s['adet']} adet - {s['aciliyet']})" for s in st.session_state.fire]
            secili_str = st.selectbox("Sipariş Seç", siparis_str, key="siparis_duzenle")
            idx = siparis_str.index(secili_str)
            siparis = st.session_state.fire[idx]
            with st.form("siparis_duzenle_form"):
                yeni_ad = st.text_input("Ürün Adı", value=siparis["urun_adi"])
                yeni_adet = st.number_input("Adet", value=int(siparis["adet"]), min_value=1)
                yeni_aciliyet = st.selectbox("Aciliyet", ["🔥 Yüksek", "⚡ Orta", "✅ Düşük"],
                                            index=["🔥 Yüksek", "⚡ Orta", "✅ Düşük"].index(siparis["aciliyet"]) if siparis["aciliyet"] in ["🔥 Yüksek", "⚡ Orta", "✅ Düşük"] else 0)
                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("💾 Kaydet"):
                        if not yeni_ad.strip():
                            st.error("Ürün adı gerekli!")
                        else:
                            st.session_state.fire[idx] = {
                                "urun_adi": yeni_ad.strip(),
                                "adet": yeni_adet,
                                "aciliyet": yeni_aciliyet,
                                "eklenme_tarihi": siparis.get("eklenme_tarihi", "")
                            }
                            veriyi_kaydet()
                            hareket_ekle(config["kullanici_adi"], "Sipariş Güncelleme", yeni_ad, "Bilgiler güncellendi")
                            st.toast("Sipariş güncellendi.", icon="✏️")
                            st.rerun()
                with col2:
                    with st.expander("🗑️ Sil", expanded=False):
                        st.warning("Bu işlem geri alınamaz!")
                        onay = st.checkbox("Eminim, silmek istiyorum.", key=f"sil_siparis_{idx}")
                        if onay:
                            if st.form_submit_button("⚠️ Silmeyi Onayla"):
                                silinen = st.session_state.fire.pop(idx)
                                veriyi_kaydet()
                                hareket_ekle(config["kullanici_adi"], "Sipariş Silme", silinen["urun_adi"], "Sipariş silindi")
                                st.toast("Sipariş silindi.", icon="🗑️")
                                st.rerun()
        else:
            st.info("Düzenlenecek sipariş yok.")

# ---------------------------- YEDEKLEME SAYFASI -----------------------
def yedekleme_sayfasi():
    st.header("💾 Yedekleme")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📤 Yedek Al")
        yedek = {
            "stok": st.session_state.stok,
            "fire": st.session_state.fire,
            "hareket": dosya_oku(HAREKET_DOSYASI, []),
            "tarih": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        st.download_button(
            "📥 JSON Yedek İndir",
            json.dumps(yedek, ensure_ascii=False, indent=2),
            f"stok_yedek_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "application/json"
        )
    with col2:
        st.subheader("📥 Yedek Yükle")
        dosya = st.file_uploader("JSON yedek seç", type="json")
        if dosya:
            try:
                icerik = json.loads(dosya.getvalue())
                if "stok" in icerik and "fire" in icerik:
                    st.session_state.stok = icerik["stok"]
                    st.session_state.fire = icerik["fire"]
                    if "hareket" in icerik:
                        dosya_yaz(HAREKET_DOSYASI, icerik["hareket"])
                    veriyi_kaydet()
                    st.toast("Yedek geri yüklendi.", icon="✅")
                    st.rerun()
                else:
                    st.error("Geçersiz dosya formatı.")
            except Exception as e:
                st.error(f"Hata: {e}")

# ---------------------------- VERİ KAYDET ----------------------------
def veriyi_kaydet():
    dosya_yaz(STOK_DOSYASI, st.session_state.stok)
    dosya_yaz(FIRE_DOSYASI, st.session_state.fire)

# ---------------------------- ANA UYGULAMA ---------------------------
def main():
    st.set_page_config(page_title="Stok Takip Pro", page_icon="📦", layout="wide")
    oturumu_baslat()
    oturum_kontrol()
    
    if not st.session_state.authenticated:
        giris_ekrani()
        return
    
    with st.sidebar:
        st.title("📌 Menü")
        sayfa = st.radio(
            "Sayfa Seç",
            ["🏠 Ana Panel", "📦 Stok Yönetimi", "🔥 Sipariş Panosu", "💾 Yedekleme"],
            key="current_page"
        )
        st.divider()
        st.caption(f"Oturum: {st.session_state.config['kullanici_adi']}")
        if st.button("🚪 Çıkış Yap"):
            cikis_yap()
    
    # Sayfa yönlendirme
    if sayfa == "🏠 Ana Panel":
        ana_sayfa()
    elif sayfa == "📦 Stok Yönetimi":
        stok_sayfasi()
    elif sayfa == "🔥 Sipariş Panosu":
        siparis_sayfasi()
    elif sayfa == "💾 Yedekleme":
        yedekleme_sayfasi()

if __name__ == "__main__":
    main()
