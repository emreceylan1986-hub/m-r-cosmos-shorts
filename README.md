# 🌌 CosmoBytes — Otonom YouTube Shorts Pipeline

**Niş:** Uzay & Astronomi · **Dil:** İngilizce · **Yayın:** 3 video/gün

TrendCatcher motorunun astronomi'ye adapte edilmiş versiyonu.

## 🛰️ Cron tablosu

| Cron | İş |
|---|---|
| `0 13,17,20 * * *` UTC | Ana pipeline (TR 16/20/23) |
| `*/10 * * * *` | Yorum yanıt bot |
| `0 4 * * *` UTC | Auto-private cleanup |

## 🎯 Niş Adaptasyonu (TrendCatcher'dan farklar)

- **Subreddit:** r/space + r/astronomy + r/spaceporn + r/astrophotography + r/cosmology
- **Daily theme:** Pzt=planets · Sal=blackholes · Çar=galaxies · Per=exoplanets · Cum=stars · Cmt=nebulae · Paz=solarsystem
- **YouTube kategori:** tech (28 — science)
- **Affiliate:** beginner telescope, stargazing books, planetarium, NASA history

## 🚀 İlk Kurulum

### 1. Luna kanalını CosmoBytes'a şekillendir (sen yapacaksın)

- YouTube Studio → kanal adı: **CosmoBytes**
- Handle: `@cosmobytes`
- Açıklama: `branding/README.md` Açıklama bloğu
- Banner: `branding/banner.png`
- Profil: `branding/profile.png`
- Settings → Audience → "No, not made for kids"
- Eski tek videoyu PRIVATE yap

### 2. OAuth flow

```bash
cd ~/Desktop/ÜRÜNYA/M-R/cosmos_paneli
cp ../denetleme_paneli/client_secret.json .

# Chrome'da emreceylan55555@gmail.com (CosmoBytes hesabı) ile login
python3 oauth_kurulum.py
```

### 3. GitHub Secrets

```bash
gh secret set TOKEN_JSON < token.json -R emreceylan1986-hub/m-r-cosmos-shorts
gh secret set CLIENT_SECRET_JSON < client_secret.json -R emreceylan1986-hub/m-r-cosmos-shorts
```

Diğer secret'lar TrendCatcher repo'sundan elle kopyalanmalı (Gemini, Pexels,
Pixabay, Jamendo, Reddit, Pinterest, Amazon).

## ⚠️ Quota

Aynı GCP project'te TrendCatcher + CosmoBytes:
- TrendCatcher: 3 video × 1,600 = 4,800
- CosmoBytes: 3 video × 1,600 = 4,800
- Toplam: 9,600 / 10,000 — sıkı ama OK (cron'lar 1 saat kaymalı)

## 📁 Brand Files

- `branding/banner.png` — 2048×1152
- `branding/profile.png` — 800×800
- `branding/README.md` — açıklama + SEO + niş kategorileri
