"""
affiliate_link.py — Açıklama Affiliate Link Otomasyonu (Faz 5).

YouTube açıklamasına konuyla ilgili affiliate link otomatik ekler. YPP
eşiğinden BAĞIMSIZ gelir — affiliate satışları AdSense'den önce başlar.

Stratejiler:
  1) Amazon Associates US (TR'den signup yapılabilir, Payoneer ile ödeme)
  2) AliExpress Affiliate (TR'den OK)
  3) ShareASale (geniş kategori)
  4) Hostinger / NordVPN / digital tool affiliate'leri

Aktif olması için env'de ilgili affiliate tag/code'lar olmalı:
    AMAZON_ASSOCIATES_TAG=trendcatcher-20
    ALIEXPRESS_AFF_KEY=xxx

NOT: Hiç tag yoksa açıklamaya hiçbir şey eklenmez — güvenli no-op.

Kullanım (modül olarak):
    from affiliate_link import aciklama_zenginleştir
    yeni_aciklama = aciklama_zenginleştir(eski_aciklama, baslik, anahtar_kelimeler)
"""
import os
from pathlib import Path


PANEL_KOK = Path(__file__).parent

# Niş — uzay/astronomi — anahtar kelime → product arama eşlemesi
NIS_PRODUCT_HARITASI = {
    "black hole": "black hole physics book",
    "neutron star": "neutron stars astrophysics book",
    "nebula": "nebula photography book",
    "galaxy": "galaxy photography coffee table book",
    "exoplanet": "exoplanet discovery book",
    "saturn": "saturn telescope amateur",
    "jupiter": "planetary science book",
    "mars": "mars exploration book",
    "moon": "moon photography book",
    "supernova": "astrophysics textbook",
    "jwst": "james webb space telescope book",
    "hubble": "hubble photography book",
    "telescope": "amateur telescope beginner",
    "cosmos": "cosmos carl sagan book",
    "universe": "universe documentary blu-ray",
    "astronomy": "astronomy beginners guide",
    "astrophysics": "astrophysics textbook beginner",
    "meteor": "meteorite collection",
    "comet": "stargazing guide book",
    "asteroid": "asteroid impact book",
    "dark matter": "dark matter physics book",
    "stargazing": "stargazing for beginners book",
    "space": "stargazing star chart",
    "cosmology": "cosmology textbook beginner",
    "milky way": "milky way photography book",
}


def _aff_tag(servis: str) -> str | None:
    """Env veya .env'den affiliate code oku."""
    key = {
        "amazon": "AMAZON_ASSOCIATES_TAG",
        "aliexpress": "ALIEXPRESS_AFF_KEY",
    }.get(servis)
    if not key: return None
    v = os.environ.get(key)
    if v: return v
    envf = PANEL_KOK / ".env"
    if envf.exists():
        for line in envf.read_text().splitlines():
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip()
    return None


def en_uygun_keyword(baslik: str, tags: list[str]) -> str | None:
    """Başlık + tag'lardan en uygun keyword bul."""
    metin = (baslik + " " + " ".join(tags or [])).lower()
    for keyword in NIS_PRODUCT_HARITASI:
        if keyword in metin:
            return keyword
    return None


def amazon_link(keyword: str, tag: str) -> str:
    """Amazon US arama URL'si + affiliate tag."""
    import urllib.parse
    q = urllib.parse.quote_plus(NIS_PRODUCT_HARITASI[keyword])
    return f"https://www.amazon.com/s?k={q}&tag={tag}"


def aciklama_zenginleştir(aciklama: str, baslik: str, tags: list[str] = None) -> str:
    """Açıklamaya konuyla ilgili affiliate link bloğu ekle. Aktif tag yoksa
    no-op (güvenli)."""
    tags = tags or []
    keyword = en_uygun_keyword(baslik, tags)
    if not keyword:
        return aciklama

    blok_satirlari = []

    amazon_tag = _aff_tag("amazon")
    if amazon_tag:
        blok_satirlari.append(f"📖 Related read: {amazon_link(keyword, amazon_tag)}")

    if not blok_satirlari:
        return aciklama

    blok = "\n\n--\n" + "\n".join(blok_satirlari) + "\n(As an Amazon Associate, we earn from qualifying purchases.)"
    return aciklama.rstrip() + blok


if __name__ == "__main__":
    # Self test
    test = aciklama_zenginleştir(
        "The Veil Nebula is expanding at 370,000 mph.",
        "Veil Nebula: A Cosmic Firework Expanding at 370,000 MPH",
        ["nebula", "supernova", "astronomy"],
    )
    print(test)
