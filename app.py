import streamlit as st
import json
import os
import pandas as pd
from datetime import datetime

# ---------------------------- SABİTLER ----------------------------
STOK_DOSYASI = "stok.json"
FIRE_DOSYASI = "fire.json"

# ---------------------------- DOSYA İŞLEMLERİ -----------------------
def dosya_oku(dosya_adi, varsayilan=None):
    """JSON dosyasını okur, hata durumunda varsayılan değeri döndürür."""
    if os.path.exists(dosya_adi):
        try:
            with open(dosya_adi, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            st.error(f"{dosya_adi} okunurken hata oluştu: {e}")
    return varsayilan if varsayilan is not None else []

def dosya_yaz(dosya_adi, veri):
    """Veriyi anında JSON dosyasına yazar."""
    try:
        with open(dosya_adi, "w", encoding="utf-8") as f:
            json.dump(veri, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        st.error(f"Dosyaya yazma hatası ({dosya_adi}): {e}")
        return False

# ---------------------------- MOCK VERİ -----------------------------
def mock_stok_olustur():
    """Örnek stok verisi oluşturur."""
    return [
        {"urun_adi": "Un", "miktar": 150, "birim": "kg"},
        {"urun_adi": "Şeker", "miktar": 80, "birim": "kg"},
        {"urun_adi": "Süt", "miktar": 40, "birim": "litre"},
        {"urun_adi": "Yumurta", "miktar": 200, "birim": "adet"},
        {"urun_adi": "Tereyağı", "miktar": 25, "birim": "kg"},
    ]

def mock_fire_olustur():
    """Örnek sipariş panosu (fire) verisi oluşturur."""
    return [
        {"urun_adi": "Un", "adet": 10, "aciliyet": "🔥 Yüksek"},
        {"urun_adi": "Şeker", "adet": 5, "aciliyet": "⚡ Orta"},
        {"urun_adi": "Yumurta", "adet": 50, "aciliyet": "✅ Düşük"},
    ]

# ---------------------------- OTURUM YÖNETİMİ -----------------------
def oturumu_baslat():
    """Session state anahtarlarını ilk yüklemede dosyadan okur."""
    if "stok" not in st.session_state:
        st.session_state.stok = dosya_oku(STOK_DOSYASI, mock_stok_olustur())
    if "fire" not in st.session_state:
        st.session_state.fire = dosya_oku(FIRE_DOSYASI, mock_fire_olustur())
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

def veriyi_kaydet():
    """Session state'teki veriyi kalıcı dosyalara yazar."""
    dosya_yaz(STOK_DOSYASI, st.session_state.stok)
    dosya_yaz(FIRE_DOSYASI, st.session_state.fire)

# ---------------------------- GİRİŞ EKRANI --------------------------
def giris_ekrani():
    st.title("🔐 Stok Takip Sistemi - Giriş")
    with st.form("giris_formu"):
        kullanici = st.text_input("Kullanıcı Adı")
        sifre = st.text_input("Şifre", type="password")
        giris_btn = st.form_submit_button("Giriş Yap")
        if giris_btn:
            if kullanici == "admin" and sifre == "1234":
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ Hatalı kullanıcı adı veya şifre!")

# ---------------------------- STOK SAYFASI --------------------------
def stok_sayfasi():
    st.header("📦 Stok Yönetimi")
    
    tablo, ekle, duzenle = st.tabs(["📋 Stok Listesi", "➕ Ürün Ekle", "✏️ Düzenle/Sil"])
    
    with tablo:
        if st.session_state.stok:
            df = pd.DataFrame(st.session_state.stok)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("Stokta hiç ürün bulunmamaktadır.")
        if st.button("🔄 Sıfırla (Mock Veri Yükle)", key="sifirla_stok"):
            st.session_state.stok = mock_stok_olustur()
            veriyi_kaydet()
            st.rerun()
    
    with ekle:
        with st.form("urun_ekle_form"):
            urun_adi = st.text_input("Ürün Adı")
            miktar = st.number_input("Miktar", min_value=0.0, step=0.01)
            birim = st.selectbox("Birim", ["kg", "litre", "adet", "paket", "gram", "koli"])
            ekle_btn = st.form_submit_button("Ekle")
            if ekle_btn:
                if not urun_adi.strip():
                    st.error("Ürün adı boş olamaz!")
                else:
                    st.session_state.stok.append({
                        "urun_adi": urun_adi.strip(),
                        "miktar": miktar,
                        "birim": birim
                    })
                    veriyi_kaydet()
                    st.success(f"{urun_adi} stoğa eklendi.")
                    st.rerun()
    
    with duzenle:
        if st.session_state.stok:
            urun_listesi = [u["urun_adi"] for u in st.session_state.stok]
            secili = st.selectbox("Düzenlenecek ürünü seç", urun_listesi, key="duzenle_sec")
            urun_index = urun_listesi.index(secili)
            urun = st.session_state.stok[urun_index]
            with st.form("duzenle_form"):
                yeni_ad = st.text_input("Yeni Ad", value=urun["urun_adi"])
                yeni_miktar = st.number_input("Yeni Miktar", value=float(urun["miktar"]), min_value=0.0)
                yeni_birim = st.selectbox("Birim", ["kg", "litre", "adet", "paket", "gram", "koli"],
                                          index=["kg", "litre", "adet", "paket", "gram", "koli"].index(urun["birim"]) if urun["birim"] in ["kg", "litre", "adet", "paket", "gram", "koli"] else 0)
                col1, col2 = st.columns(2)
                with col1:
                    kaydet_btn = st.form_submit_button("💾 Kaydet")
                with col2:
                    sil_btn = st.form_submit_button("🗑️ Sil")
                
                if kaydet_btn:
                    if not yeni_ad.strip():
                        st.error("Ürün adı boş olamaz!")
                    else:
                        st.session_state.stok[urun_index] = {
                            "urun_adi": yeni_ad.strip(),
                            "miktar": yeni_miktar,
                            "birim": yeni_birim
                        }
                        veriyi_kaydet()
                        st.success("Güncelleme başarılı!")
                        st.rerun()
                if sil_btn:
                    st.session_state.stok.pop(urun_index)
                    veriyi_kaydet()
                    st.success("Ürün silindi.")
                    st.rerun()
        else:
            st.info("Düzenlenecek ürün bulunamadı.")

# ---------------------------- SİPARİŞ PANOSU ------------------------
def siparis_sayfasi():
    st.header("🔥 Sipariş Panosu (Fire Takibi)")
    
    tablo, ekle, duzenle = st.tabs(["📋 Siparişler", "➕ Sipariş Ekle", "✏️ Düzenle/Sil"])
    
    with tablo:
        if st.session_state.fire:
            df = pd.DataFrame(st.session_state.fire)
            # Renklendirmek için stil uygulayabiliriz (opsiyonel)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("Henüz sipariş eklenmemiş.")
        if st.button("🔄 Sıfırla (Mock Sipariş Yükle)", key="sifirla_fire"):
            st.session_state.fire = mock_fire_olustur()
            veriyi_kaydet()
            st.rerun()
    
    with ekle:
        with st.form("siparis_ekle_form"):
            urun_adi = st.text_input("Ürün Adı")
            adet = st.number_input("Adet", min_value=1, step=1)
            aciliyet = st.selectbox("Aciliyet", ["🔥 Yüksek", "⚡ Orta", "✅ Düşük"])
            ekle_btn = st.form_submit_button("Ekle")
            if ekle_btn:
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
                    st.success("Sipariş eklendi.")
                    st.rerun()
    
    with duzenle:
        if st.session_state.fire:
            siparisler = [f"{s['urun_adi']} ({s['adet']} adet - {s['aciliyet']})" for s in st.session_state.fire]
            secili_str = st.selectbox("Düzenlenecek sipariş", siparisler, key="siparis_duzenle_sec")
            secili_index = siparisler.index(secili_str)
            siparis = st.session_state.fire[secili_index]
            with st.form("siparis_duzenle_form"):
                yeni_ad = st.text_input("Ürün Adı", value=siparis["urun_adi"])
                yeni_adet = st.number_input("Adet", value=int(siparis["adet"]), min_value=1)
                yeni_aciliyet = st.selectbox("Aciliyet", ["🔥 Yüksek", "⚡ Orta", "✅ Düşük"],
                                            index=["🔥 Yüksek", "⚡ Orta", "✅ Düşük"].index(siparis["aciliyet"]) if siparis["aciliyet"] in ["🔥 Yüksek", "⚡ Orta", "✅ Düşük"] else 0)
                col1, col2 = st.columns(2)
                with col1:
                    kaydet_btn = st.form_submit_button("💾 Kaydet")
                with col2:
                    sil_btn = st.form_submit_button("🗑️ Sil")
                
                if kaydet_btn:
                    if not yeni_ad.strip():
                        st.error("Ürün adı gerekli!")
                    else:
                        st.session_state.fire[secili_index] = {
                            "urun_adi": yeni_ad.strip(),
                            "adet": yeni_adet,
                            "aciliyet": yeni_aciliyet,
                            "eklenme_tarihi": siparis.get("eklenme_tarihi", datetime.now().strftime("%Y-%m-%d %H:%M"))
                        }
                        veriyi_kaydet()
                        st.success("Sipariş güncellendi.")
                        st.rerun()
                if sil_btn:
                    st.session_state.fire.pop(secili_index)
                    veriyi_kaydet()
                    st.success("Sipariş silindi.")
                    st.rerun()
        else:
            st.info("Düzenlenecek sipariş yok.")

# ---------------------------- YEDEKLEME SAYFASI ---------------------
def yedekleme_sayfasi():
    st.header("💾 Yedekleme")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📤 Yedek Al (Dışa Aktar)")
        yedek_verisi = {
            "stok": st.session_state.stok,
            "fire": st.session_state.fire,
            "yedekleme_tarihi": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        yedek_json = json.dumps(yedek_verisi, ensure_ascii=False, indent=2)
        st.download_button(
            label="📥 JSON Yedeği İndir",
            data=yedek_json,
            file_name=f"stok_yedek_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )
    
    with col2:
        st.subheader("📥 Yedekten Geri Yükle")
        yuklenen_dosya = st.file_uploader("JSON yedek dosyasını seçin", type=["json"])
        if yuklenen_dosya is not None:
            try:
                icerik = json.loads(yuklenen_dosya.getvalue().decode("utf-8"))
                if "stok" in icerik and "fire" in icerik:
                    st.session_state.stok = icerik["stok"]
                    st.session_state.fire = icerik["fire"]
                    veriyi_kaydet()
                    st.success("✅ Yedek başarıyla geri yüklendi! Sayfa yeniden yükleniyor...")
                    st.rerun()
                else:
                    st.error("⚠️ Geçersiz yedek dosyası! 'stok' ve 'fire' anahtarları bulunamadı.")
            except Exception as e:
                st.error(f"❌ Dosya okunamadı: {e}")

# ---------------------------- ANA UYGULAMA --------------------------
def main():
    st.set_page_config(page_title="Stok Takip Demo", page_icon="📦", layout="wide")
    oturumu_baslat()
    
    if not st.session_state.authenticated:
        giris_ekrani()
        return
    
    # Başarılı giriş sonrası kenar menüsü
    with st.sidebar:
        st.title("📌 Menü")
        sayfa = st.radio(
            "Sayfa Seçin",
            ["📦 Stok Yönetimi", "🔥 Sipariş Panosu", "💾 Yedekleme"],
            key="current_page"
        )
        st.divider()
        if st.button("🚪 Çıkış Yap"):
            st.session_state.authenticated = False
            st.rerun()
    
    # Sayfa yönlendirme
    if sayfa == "📦 Stok Yönetimi":
        stok_sayfasi()
    elif sayfa == "🔥 Sipariş Panosu":
        siparis_sayfasi()
    elif sayfa == "💾 Yedekleme":
        yedekleme_sayfasi()

if __name__ == "__main__":
    main()
