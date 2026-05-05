# 🏪 Market Yönetim Sistemi (MVP)

> **Akıllı stok takibi, barkod okutma ve bilimsel indirim önerileri ile marketinizi modernleştirin.**

[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=Streamlit&logoColor=white)](https://streamlit.io)
[![Python](https://img.shields.io/badge/Python-3.8+-blue?style=for-the-badge&logo=python)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

<p align="center">
  <img src="demo.gif" alt="Demo" width="600"/>
</p>

## 🚀 Özellikler

- 📱 **Mobil Barkod Okutma:** Telefon kamerası ile anında stok girişi/çıkışı.
- 📅 **Son Kullanma Tarihi Takibi:** Yaklaşan SKT'leri otomatik uyarı ve bilimsel indirim önerisi.
- 🧠 **Veri Bilimi Temelli İndirim:** Satış hızı, stok fazlası ve kar marjına göre dinamik indirim.
- 💰 **POS Satış Ekranı:** Stoktan düş, kasayı gör.
- 📊 **Satış Raporu:** Günlük/aylık/ürün bazlı ciro analizi.
- 🔥 **Sipariş Panosu:** Kritik stokta otomatik sipariş fişi oluşturma.
- 📉 **Fire Analizi:** Kategori bazlı kayıp raporu.
- 🔐 **Kullanıcı Rolleri:** Patron, kasiyer, depocu yetkileri.
- 💾 **Yedekleme:** Tek tıkla JSON yedek al/geri yükle.

## 🛠️ Kurulum

```bash
# Depoyu klonla
git clone https://github.com/kullaniciadi/market-yonetim.git
cd market-yonetim

# Bağımlılıkları yükle
pip install -r requirements.txt

# Uygulamayı başlat
streamlit run app.py
