import streamlit as st
import json
import os
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import logging
from io import BytesIO

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

# ---------------------------- VERİ GEÇİŞ KONTROL --------------------
def veri_gecis_kontrol():
    """Eski formatı yeni alanlarla günceller."""
    degisti = False
    # Stok için
    for urun in st.session_state.stok:
        for anahtar, varsayilan in [("kategori", "Diğer"), ("min_miktar", 0),
                                    ("barkod", ""), ("son_kullanma_tarihi", "")]:
            if anahtar not in urun:
                urun[anahtar] = varsayilan
                degisti = True
    # Fire için
    for siparis in st.session_state.fire:
        if "adet" in siparis and "miktar" not in siparis:
            siparis["miktar"] = siparis.pop("adet")
            degisti = True
        if "miktar" not in siparis:
            siparis["miktar"] = 0
            degisti = True
        if "birim" not in siparis:
            siparis["birim"] = "adet"
            degisti = True
    if degisti:
        veriyi_kaydet()

# ---------------------------- MOCK VERİ -----------------------------
def mock_stok_olustur():
    return [
        {"urun_adi": "Un", "miktar": 150, "birim": "kg", "kategori": "Kuru Gıda",
         "min_miktar": 20, "barkod": "1000001", "son_kullanma_tarihi": "2026-12-31"},
        {"urun_adi": "Şeker", "miktar": 5, "birim": "kg", "kategori": "Kuru Gıda",
         "min_miktar": 10, "barkod": "1000002", "son_kullanma_tarihi": "2026-05-15"},
        {"urun_adi": "Süt", "miktar": 40, "birim": "litre", "kategori": "Süt Ürünleri",
         "min_miktar": 15, "barkod": "1000003", "son_kullanma_tarihi": "2026-05-08"},
        {"urun_adi": "Yumurta", "miktar": 200, "birim": "adet", "kategori": "Diğer",
         "min_miktar": 30, "barkod": "1000004", "son_kullanma_tarihi": "2026-05-06"},
        {"urun_adi": "Tereyağı", "miktar": 25, "birim": "kg", "kategori": "Süt Ürünleri",
         "min_miktar": 5, "barkod": "1000005", "son_kullanma_tarihi": "2026-06-20"},
    ]

def mock_fire_olustur():
    return [
        {"urun_adi": "Un", "miktar": 10, "birim": "kg", "aciliyet": "🔥 Yüksek"},
        {"urun_adi": "Şeker", "miktar": 5, "birim": "kg", "aciliyet": "⚡ Orta"},
        {"urun_adi": "Yumurta", "miktar": 50, "birim": "adet", "aciliyet": "✅ Düşük"},
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
    veri_gecis_kontrol()

def oturum_kontrol():
    if st.session_state.authenticated:
        now = datetime.now()
        if now - st.session_state.last_activity > timedelta(minutes=OTURUM_SURESI):
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

def cikis_yap():
    st.session_state.authenticated = False
    st.rerun()

# ---------------------------- ANA SAYFA (KPI + SKT) ------------------
def ana_sayfa():
    st.header("📊 Yönetim Paneli")
    kritik_urunler = [u for u in st.session_state.stok if u.get("min_miktar", 0) > 0 and u["miktar"] <= u.get("min_miktar", 0)]
    toplam_urun = len(st.session_state.stok)
    acik_siparis = len(st.session_state.fire)

    col1, col2, col3 = st.columns(3)
    col1.metric("📦 Toplam Ürün Çeşidi", toplam_urun)
    col2.metric("⚠️ Kritik Stok", len(kritik_urunler), delta_color="inverse")
    col3.metric("🔥 Açık Sipariş", acik_siparis)

    if kritik_urunler:
        st.subheader("🚨 Kritik Stok Uyarıları")
        for urun in kritik_urunler:
            st.error(f"{urun['urun_adi']}: {urun['miktar']:.2f} {urun['birim']} (Minimum: {urun['min_miktar']:.2f})")

    # ---- SKT Tehlike Bölgesi ----
    bugun = datetime.now().date()
    tehlike_urunleri = []
    for urun in st.session_state.stok:
        skt_str = urun.get("son_kullanma_tarihi", "")
        if skt_str:
            try:
                skt = datetime.strptime(skt_str, "%Y-%m-%d").date()
                kalan = (skt - bugun).days
                if 0 <= kalan <= 3:
                    urun["kalan_gun"] = kalan
                    tehlike_urunleri.append(urun)
            except ValueError:
                pass  # hatalı tarih

    if tehlike_urunleri:
        st.subheader("⚠️ Son Kullanma Tarihi Yaklaşan Ürünler (İndirim Önerisi)")
        for u in tehlike_urunleri:
            indirim = "%30" if u["kalan_gun"] <= 1 else "%20"
            st.warning(
                f"📛 {u['urun_adi']} – SKT: {u['son_kullanma_tarihi']} "
                f"({u['kalan_gun']} gün kaldı) → Önerilen İndirim: {indirim}"
            )

# ---------------------------- STOK SAYFASI --------------------------
def stok_sayfasi():
    st.header("📦 Stok Yönetimi")
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📋 Liste", "➕ Ekle", "✏️ Düzenle/Sil", "📊 Grafikler", "📥 Toplu Yükleme"])

    with tab1:
        st.subheader("Stok Listesi")
        arama = st.text_input("Ürün Ara", key="stok_arama")
        kategori_sec = st.selectbox("Kategori Filtrele", ["Tümü"] + KATEGORILER, key="stok_kategori")
        df = pd.DataFrame(st.session_state.stok)
        if not df.empty:
            if kategori_sec != "Tümü":
                df = df[df["kategori"] == kategori_sec]
            if arama:
                df = df[df["urun_adi"].str.contains(arama, case=False)]
            def highlight_critical(row):
                min_m = row.get("min_miktar", 0)
                if min_m > 0 and row["miktar"] <= min_m:
                    return ['background-color: #ffcccc'] * len(row)
                return [''] * len(row)
            styled_df = df.style.apply(highlight_critical, axis=1)
            styled_df = styled_df.format(precision=2)  # 2 ondalık basamak
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
            col1, col2 = st.columns(2)
            urun_adi = col1.text_input("Ürün Adı")
            barkod = col2.text_input("Barkod (Opsiyonel)")
            miktar = col1.number_input("Miktar", min_value=0.0, step=0.01, format="%.2f")
            birim = col2.selectbox("Birim", ["kg", "litre", "adet", "paket", "gram", "koli"])
            kategori = col1.selectbox("Kategori", KATEGORILER)
            min_miktar = col2.number_input("Minimum Stok", min_value=0.0, step=0.01, format="%.2f")
            skt = col1.text_input("Son Kullanma Tarihi (YYYY-AA-GG)", placeholder="2026-12-31")
            if st.form_submit_button("Ekle"):
                if not urun_adi.strip():
                    st.error("Ürün adı boş olamaz!")
                else:
                    st.session_state.stok.append({
                        "urun_adi": urun_adi.strip(),
                        "miktar": miktar,
                        "birim": birim,
                        "kategori": kategori,
                        "min_miktar": min_miktar,
                        "barkod": barkod.strip(),
                        "son_kullanma_tarihi": skt.strip()
                    })
                    veriyi_kaydet()
                    hareket_ekle(config["kullanici_adi"], "Ekleme", urun_adi, f"{miktar:.2f} {birim}")
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
                col1, col2 = st.columns(2)
                yeni_ad = col1.text_input("Ürün Adı", value=urun["urun_adi"])
                yeni_barkod = col2.text_input("Barkod", value=urun.get("barkod", ""))
                yeni_miktar = col1.number_input("Miktar", value=float(urun["miktar"]), min_value=0.0, format="%.2f")
                birimler = ["kg", "litre", "adet", "paket", "gram", "koli"]
                try:
                    birim_index = birimler.index(urun.get("birim", "kg"))
                except ValueError:
                    birim_index = 0
                yeni_birim = col2.selectbox("Birim", birimler, index=birim_index)
                try:
                    kat_index = KATEGORILER.index(urun.get("kategori", "Diğer"))
                except ValueError:
                    kat_index = 0
                yeni_kategori = col1.selectbox("Kategori", KATEGORILER, index=kat_index)
                yeni_min = col2.number_input("Min. Stok", value=float(urun.get("min_miktar", 0)), min_value=0.0, format="%.2f")
                yeni_skt = col1.text_input("Son Kullanma Tarihi", value=urun.get("son_kullanma_tarihi", ""))
                
                colA, colB = st.columns([2,1])
                with colA:
                    if st.form_submit_button("💾 Kaydet"):
                        if not yeni_ad.strip():
                            st.error("Ürün adı boş olamaz!")
                        else:
                            st.session_state.stok[idx] = {
                                "urun_adi": yeni_ad.strip(),
                                "miktar": yeni_miktar,
                                "birim": yeni_birim,
                                "kategori": yeni_kategori,
                                "min_miktar": yeni_min,
                                "barkod": yeni_barkod.strip(),
                                "son_kullanma_tarihi": yeni_skt.strip()
                            }
                            veriyi_kaydet()
                            hareket_ekle(config["kullanici_adi"], "Güncelleme", yeni_ad, "Bilgiler güncellendi")
                            st.toast("Ürün güncellendi.", icon="✏️")
                            st.rerun()
                with colB:
                    with st.expander("🗑️ Sil", expanded=False):
                        st.warning("Bu işlem geri alınamaz!")
                        if st.checkbox("Eminim, silmek istiyorum.", key=f"sil_onay_{idx}"):
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

    with tab5:
        st.subheader("CSV ile Toplu Ürün Yükleme")
        sablon_df = pd.DataFrame(columns=["urun_adi", "miktar", "birim", "kategori", "min_miktar", "barkod", "son_kullanma_tarihi"])
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
                        "min_miktar": float(row.get("min_miktar", 0)),
                        "barkod": str(row.get("barkod", "")),
                        "son_kullanma_tarihi": str(row.get("son_kullanma_tarihi", ""))
                    })
                veriyi_kaydet()
                st.toast(f"{len(df_csv)} ürün başarıyla eklendi.", icon="📥")
                st.rerun()
            except Exception as e:
                st.error(f"CSV yüklenirken hata: {e}")

    # Excel çıkışı
    if st.session_state.stok:
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            pd.DataFrame(st.session_state.stok).to_excel(writer, index=False, sheet_name='Stok', float_format="%.2f")
        excel_data = output.getvalue()
        st.download_button(
            label="📊 Stok Listesini Excel Olarak İndir",
            data=excel_data,
            file_name="stok_listesi.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# ---------------------------- SİPARİŞ PANOSU -------------------------
def siparis_sayfasi():
    st.header("🔥 Sipariş Panosu (Fire Takibi)")
    tab1, tab2, tab3 = st.tabs(["📋 Siparişler", "➕ Ekle", "✏️ Düzenle/Sil"])

    with tab1:
        arama = st.text_input("Sipariş Ara", key="siparis_arama")
        df = pd.DataFrame(st.session_state.fire)
        if not df.empty:
            if arama:
                df = df[df["urun_adi"].str.contains(arama, case=False)]
            def guvenli_miktar(row):
                return row.get("miktar", row.get("adet", 0))
            def guvenli_birim(row):
                return row.get("birim", "adet")
            df["gorunum"] = df.apply(lambda r: f"{guvenli_miktar(r):.2f} {guvenli_birim(r)} {r['urun_adi']}", axis=1)
            def format_aciliyet(val):
                if "Yüksek" in str(val):
                    return '🔥 <span style="color:red; font-weight:bold">Yüksek</span>'
                elif "Orta" in str(val):
                    return '⚡ <span style="color:orange; font-weight:bold">Orta</span>'
                else:
                    return '✅ <span style="color:green; font-weight:bold">Düşük</span>'
            df["aciliyet_gorsel"] = df["aciliyet"].apply(format_aciliyet)
            st.write(df[["gorunum", "aciliyet_gorsel", "eklenme_tarihi"]].to_html(escape=False, index=False), unsafe_allow_html=True)
        else:
            st.info("Henüz sipariş eklenmemiş.")
        if st.button("🔄 Mock Siparişlere Sıfırla", key="sifirla_fire"):
            st.session_state.fire = mock_fire_olustur()
            veriyi_kaydet()
            st.toast("Siparişler mock verilerle sıfırlandı.", icon="🔄")
            st.rerun()
        st.subheader("Aciliyet Dağılımı")
        if not df.empty:
            fig = px.bar(df, x='aciliyet', title='Sipariş Aciliyet Durumları')
            st.plotly_chart(fig, use_container_width=True)

    with tab2:
        with st.form("siparis_ekle_form"):
            urun_adi = st.text_input("Ürün Adı")
            miktar = st.number_input("Miktar", min_value=0.01, step=0.01, format="%.2f")
            birim = st.selectbox("Birim", ["kg", "litre", "adet", "paket", "koli"])
            aciliyet = st.selectbox("Aciliyet", ["🔥 Yüksek", "⚡ Orta", "✅ Düşük"])
            if st.form_submit_button("Ekle"):
                if not urun_adi.strip():
                    st.error("Ürün adı gerekli!")
                else:
                    st.session_state.fire.append({
                        "urun_adi": urun_adi.strip(),
                        "miktar": miktar,
                        "birim": birim,
                        "aciliyet": aciliyet,
                        "eklenme_tarihi": datetime.now().strftime("%Y-%m-%d %H:%M")
                    })
                    veriyi_kaydet()
                    hareket_ekle(config["kullanici_adi"], "Sipariş Ekleme", urun_adi, f"{miktar:.2f} {birim} {aciliyet}")
                    st.toast("Sipariş eklendi.", icon="🔥")
                    st.rerun()

    with tab3:
        if st.session_state.fire:
            def siparis_gorunum(s):
                m = s.get("miktar", s.get("adet", 0))
                b = s.get("birim", "adet")
                return f"{m:.2f} {b} {s['urun_adi']} ({s.get('aciliyet', '')})"
            siparis_str = [siparis_gorunum(s) for s in st.session_state.fire]
            secili_str = st.selectbox("Sipariş Seç", siparis_str, key="siparis_duzenle")
            idx = siparis_str.index(secili_str)
            siparis = st.session_state.fire[idx]
            with st.form("siparis_duzenle_form"):
                yeni_ad = st.text_input("Ürün Adı", value=siparis["urun_adi"])
                mevcut_miktar = float(siparis.get("miktar", siparis.get("adet", 0)))
                yeni_miktar = st.number_input("Miktar", value=mevcut_miktar, min_value=0.01, format="%.2f")
                birimler = ["kg", "litre", "adet", "paket", "koli"]
                try:
                    bir_index = birimler.index(siparis.get("birim", "adet"))
                except ValueError:
                    bir_index = 2
                yeni_birim = st.selectbox("Birim", birimler, index=bir_index)
                aciliyetler = ["🔥 Yüksek", "⚡ Orta", "✅ Düşük"]
                try:
                    aci_index = aciliyetler.index(siparis.get("aciliyet", "✅ Düşük"))
                except ValueError:
                    aci_index = 2
                yeni_aciliyet = st.selectbox("Aciliyet", aciliyetler, index=aci_index)
                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("💾 Kaydet"):
                        if not yeni_ad.strip():
                            st.error("Ürün adı gerekli!")
                        else:
                            st.session_state.fire[idx] = {
                                "urun_adi": yeni_ad.strip(),
                                "miktar": yeni_miktar,
                                "birim": yeni_birim,
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
                        if st.checkbox("Eminim, silmek istiyorum.", key=f"sil_siparis_{idx}"):
                            if st.form_submit_button("⚠️ Silmeyi Onayla"):
                                silinen = st.session_state.fire.pop(idx)
                                veriyi_kaydet()
                                hareket_ekle(config["kullanici_adi"], "Sipariş Silme", silinen["urun_adi"], "Sipariş silindi")
                                st.toast("Sipariş silindi.", icon="🗑️")
                                st.rerun()
        else:
            st.info("Düzenlenecek sipariş yok.")

# ---------------------------- FİRE ANALİZİ --------------------------
def fire_analizi():
    st.header("📉 Geçmiş Fire Analizi (Kategori Bazlı)")
    if not st.session_state.fire:
        st.info("Henüz fire kaydı yok.")
        return
    stok_kat = {u["urun_adi"]: u.get("kategori", "Diğer") for u in st.session_state.stok}
    kategori_fire = {}
    for f in st.session_state.fire:
        ad = f["urun_adi"]
        kat = stok_kat.get(ad, "Diğer")
        miktar = float(f.get("miktar", f.get("adet", 0)))
        kategori_fire[kat] = kategori_fire.get(kat, 0) + miktar

    df_fire = pd.DataFrame(list(kategori_fire.items()), columns=["Kategori", "Toplam Fire"])
    df_fire["Toplam Fire"] = df_fire["Toplam Fire"].apply(lambda x: f"{x:.2f}")
    st.dataframe(df_fire, use_container_width=True)
    fig = px.pie(df_fire, values="Toplam Fire", names="Kategori", title="Kategorilere Göre Fire Dağılımı")
    st.plotly_chart(fig, use_container_width=True)

# ---------------------------- YEDEKLEME SAYFASI ---------------------
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
                    veri_gecis_kontrol()
                    st.toast("Yedek geri yüklendi.", icon="✅")
                    st.rerun()
                else:
                    st.error("Geçersiz dosya formatı.")
            except Exception as e:
                st.error(f"Hata: {e}")

# ---------------------------- VERİ KAYDET --------------------------
def veriyi_kaydet():
    dosya_yaz(STOK_DOSYASI, st.session_state.stok)
    dosya_yaz(FIRE_DOSYASI, st.session_state.fire)

# ---------------------------- ANA UYGULAMA -------------------------
def main():
    st.set_page_config(page_title="Stok Takip Pro", page_icon="📦", layout="wide")
    pd.set_option('display.float_format', '{:.2f}'.format)  # genel float formatı
    oturumu_baslat()
    oturum_kontrol()
    
    if not st.session_state.authenticated:
        giris_ekrani()
        return
    
    with st.sidebar:
        st.title("📌 Menü")
        sayfa = st.radio(
            "Sayfa Seç",
            ["🏠 Ana Panel", "📦 Stok Yönetimi", "🔥 Sipariş Panosu", "📉 Fire Analizi", "💾 Yedekleme"],
            key="current_page"
        )
        st.divider()
        st.caption(f"Oturum: {st.session_state.config['kullanici_adi']}")
        if st.button("🚪 Çıkış Yap"):
            cikis_yap()
    
    if sayfa == "🏠 Ana Panel":
        ana_sayfa()
    elif sayfa == "📦 Stok Yönetimi":
        stok_sayfasi()
    elif sayfa == "🔥 Sipariş Panosu":
        siparis_sayfasi()
    elif sayfa == "📉 Fire Analizi":
        fire_analizi()
    elif sayfa == "💾 Yedekleme":
        yedekleme_sayfasi()

if __name__ == "__main__":
    main()
