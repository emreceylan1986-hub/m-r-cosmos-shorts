"""
haberci.py — YouTube Shorts için Teknoloji Haberi Çekici

Son 24 saatin en popüler 3 teknoloji haberini getirir.

Kaynaklar (hepsi RESMİ API, scraping yok, ban riski sıfır):
    1) HackerNews Firebase API  → gerçek "score" metriği ile popülerlik
    2) Reddit r/technology .json → "ups" metriği ile popülerlik

Çıktı: JSON dosyası ve konsol özeti
    {
      "uretim_zamani": "...",
      "haberler": [
        {"baslik": "...", "url": "...", "kaynak": "HN", "skor": 1234, "yas_saat": 8.2},
        ...
      ]
    }
"""

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import requests


# NIS: UZAY + ASTRONOMI + KOZMOS (viral bilim/keşif formatı)
# Kaynaklar: tek bir konuya değil çoğunlukla görsel/duygusal/şaşırtıcı içeriğe
# odaklı, telif riski sıfır subreddit'ler.
REDDIT_URLS = [
    "https://www.reddit.com/r/space/top.json?t=day&limit=25",
    "https://www.reddit.com/r/astronomy/top.json?t=day&limit=25",
    "https://www.reddit.com/r/spaceporn/top.json?t=day&limit=25",
    "https://www.reddit.com/r/astrophotography/top.json?t=day&limit=25",
    "https://www.reddit.com/r/cosmology/top.json?t=day&limit=25",
]
KULLANICI_AJANI = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15"

# Eski HN/r/technology sabitleri (geçici — referans/import kırılmasın diye)
HN_TOP_URL = ""
HN_ITEM_URL = ""
HN_TARANACAK_ADET = 0
REDDIT_URL = REDDIT_URLS[0]

ZAMAN_PENCERESI_SAAT = 48  # niş içerikte gün gün taze değil, "viral son 2 gün"
ISTEK_ZAMAN_ASIMI = 10
ISTEKLER_ARASI_GECIKME = 0.05

CIKTI_DOSYASI = Path(__file__).parent / "haberler.json"
GECMIS_DOSYASI = Path(__file__).parent / "haber_gecmisi.json"
GECMIS_AZAMI_KAYIT = 1000  # eski kayıtlar bu sayının üzerine çıkınca budanır


def _simdi_utc() -> datetime:
    return datetime.now(timezone.utc)


def _yas_saat(unix_zaman: int) -> float:
    fark = _simdi_utc() - datetime.fromtimestamp(unix_zaman, tz=timezone.utc)
    return fark.total_seconds() / 3600


def hackernews_haberleri() -> list[dict]:
    """KAPATILDI — nişten çıkarıldı. Geri uyumluluk için boş döner."""
    return []


def _praw_clienti():
    """Reddit OAuth client (PRAW). Eğer credentials yoksa None döner ve
    anonim JSON fallback'e geçer."""
    import os
    cid = os.environ.get("REDDIT_CLIENT_ID")
    csec = os.environ.get("REDDIT_CLIENT_SECRET")
    if not (cid and csec):
        return None
    try:
        import praw
    except ImportError:
        print("[haberci] praw yok — anonim fallback")
        return None
    try:
        r = praw.Reddit(
            client_id=cid,
            client_secret=csec,
            user_agent="TrendCatcher/1.0 by /u/trendcatcher_bot",
            read_only=True,
        )
        # Test
        _ = r.subreddit("test").display_name
        return r
    except Exception as h:
        print(f"[haberci] PRAW client başarısız: {h}")
        return None


def _reddit_praw_fetch(reddit, sub_name: str) -> list[dict]:
    """PRAW ile bir subreddit'in günlük top postlarını çek."""
    out = []
    try:
        for post in reddit.subreddit(sub_name).top(time_filter="day", limit=25):
            if post.stickied or post.over_18: continue
            url = post.url or ""
            if not (url and post.title and post.created_utc): continue
            yas = _yas_saat(int(post.created_utc))
            if yas > ZAMAN_PENCERESI_SAAT: continue
            out.append({
                "baslik": post.title,
                "url": url,
                "kaynak": f"r/{sub_name}",
                "skor": int(post.ups or 0),
                "yas_saat": round(yas, 1),
                "yorum_sayisi": int(post.num_comments or 0),
            })
    except Exception as h:
        print(f"[haberci] PRAW r/{sub_name}: {h}")
    return out


def reddit_haberleri() -> list[dict]:
    """4 viral subreddit'ten son 48 saatin top postları (uzay/astronomi/bilim).

    Önce PRAW (OAuth) dener — GitHub Actions IP'lerinden 403 alma riskini
    sıfırlar. Credentials yoksa anonim JSON fallback'e döner."""
    reddit = _praw_clienti()
    if reddit is not None:
        print("[haberci] Reddit PRAW (OAuth) modunda")
        haberler = []
        for url in REDDIT_URLS:
            sub = url.split("/r/")[1].split("/")[0]
            haberler.extend(_reddit_praw_fetch(reddit, sub))
            time.sleep(0.5)
        return haberler

    # Anonim JSON fallback
    haberler: list[dict] = []
    for url in REDDIT_URLS:
        sub = url.split("/r/")[1].split("/")[0]
        try:
            yanit = requests.get(
                url,
                timeout=ISTEK_ZAMAN_ASIMI,
                headers={"User-Agent": KULLANICI_AJANI},
            )
            yanit.raise_for_status()
            gonderiler = yanit.json().get("data", {}).get("children", [])
        except requests.RequestException as hata:
            print(f"[haberci] r/{sub} alınamadı: {hata}")
            continue

        for g in gonderiler:
            veri = g.get("data", {})
            if veri.get("stickied") or veri.get("over_18"):
                continue
            url_h = veri.get("url_overridden_by_dest") or veri.get("url")
            baslik = veri.get("title")
            olusturma = veri.get("created_utc")
            if not (url_h and baslik and olusturma):
                continue
            yas = _yas_saat(int(olusturma))
            if yas > ZAMAN_PENCERESI_SAAT:
                continue
            haberler.append(
                {
                    "baslik": baslik,
                    "url": url_h,
                    "kaynak": f"r/{sub}",
                    "skor": int(veri.get("ups", 0)),
                    "yas_saat": round(yas, 1),
                    "yorum_sayisi": int(veri.get("num_comments", 0)),
                }
            )
        time.sleep(ISTEKLER_ARASI_GECIKME * 5)  # subreddit'ler arası nezaket

    return haberler


def _tekrarlari_ele(haberler: Iterable[dict]) -> list[dict]:
    gorulen: dict[str, dict] = {}
    for h in haberler:
        anahtar = h["url"].split("?")[0].rstrip("/")
        if anahtar not in gorulen or h["skor"] > gorulen[anahtar]["skor"]:
            gorulen[anahtar] = h
    return list(gorulen.values())


def _normalize_url(url: str) -> str:
    return url.split("?")[0].rstrip("/").lower()


def gunun_trend_seedleri() -> list[str]:
    """
    Google Trends (pytrends) — günün US trending searches'inden seed çek.
    Gemini fallback'e "şu konular şu an viral" ipucu olarak verilir.
    Fail-safe: pytrends hata verirse boş döner, ana akış bozulmaz.
    """
    try:
        from pytrends.request import TrendReq
        pt = TrendReq(hl="en-US", tz=0, timeout=(5, 10))
        df = pt.trending_searches(pn="united_states")
        seedler = [str(s) for s in df[0].head(10).tolist()]
        return seedler
    except Exception as hata:
        print(f"[haberci] pytrends trend seed alınamadı: {hata}")
        return []


GEMINI_KONU_SISTEM = """You produce viral YouTube Shorts TOPICS for a
SPACE / ASTRONOMY / COSMOS channel called CosmoBytes. Output ONLY a JSON array of EXACTLY
3 topic objects.

Each topic = a well-established, factual, surprising fact about a cosmic
phenomenon, planet, galaxy, star, or space wonder that:
- Has clear visual potential (NASA/JWST/Hubble images, Pexels stock exists)
- Is broadly known and TRUE (no debunked theories, no speculation as fact)
- Stops the scroll: emotionally surprising or beautiful

═══ PROVEN VIRAL PATTERNS (CosmoBytes top performers — 25 Haz 2026 güncel) ═══
These videos got 5-10× the channel average. ADAPT these patterns:

  🚀 2091 izl: "The Milky Way's Secret: Sagittarius A*"
     PATTERN: ICONIC ASTRONOMICAL NAME + "SECRET/HIDDEN" → MUST USE
  ✅ 1100 izl: "Rogue Planets Drift Alone in Interstellar Space Without a Sun"
     PATTERN: Yalnızlık + dramatik tablo (alone, drift, without)
  ✅ 1100 izl: "Europa's Ocean: More Water Than Earth's"
     PATTERN: Hayat ihtimali + somut karşılaştırma (more X than Y)
  ✅  717 izl: "Sun's Extreme Temps: Core vs. Surface!"
     PATTERN: Iconic obje + iç çelişki (core vs surface, day vs night)
  ✅  455 izl: "VY Canis Majoris: A Star So Big It Swallows Saturn's Orbit"
     PATTERN: ICONIC OBJE ADI + scale shock (so big it...)

═══ FAZ 1 ZORUNLU KURAL — "Sagittarius A* Formülü" (Emre kararı 25 Haz) ═══
Her gün ÜRETİLEN konularda EN AZ 1 tane şu kalıbı taşımak ZORUNLU:
  → "ICONIC ASTRONOMICAL NAME (Sagittarius A*, Betelgeuse, Hubble Deep Field,
     Pillars of Creation, Stephenson 2-18, Bootes Void, Boomerang Nebula vb.)"
  + ":" veya "—" + "HIDDEN/SECRET/UNSEEN/IMPOSSIBLE" tipi mystery hook
Örnek başlıklar:
  • "Bootes Void: The Hole in the Universe Nobody Talks About"
  • "Boomerang Nebula's Secret: The Coldest Place in the Cosmos"
  • "Stephenson 2-18: A Star So Big You Can't Even Picture It"
Bu kalıp viral patlamanın TEK kanıtlı yolu. Çiğneme.

═══ FORBIDDEN PATTERNS (low performers) ═══
  ❌ "Black Hole Event Horizon..." (12 izl) — too technical jargon
  ❌ "Milky Way & Andromeda Collision" (5 izl) — overused cliché

WRITE TITLES IN THE VIRAL PATTERN STYLE:
- Lead with isolation/wonder/hidden danger
- Use vivid metaphors (firework, web, hat, pillars, hellscape)
- Avoid pure jargon (event horizon, singularity); use plain words instead

═══ VIRAL TITLE FORMULA: "X Vs Y" (Outlawgaming 235M view kanıtı) ═══
MANDATORY ROTATION: Every 4th topic title MUST use "Vs" battle/comparison format.
Count blocked titles — if (len(blocked)+1) % 4 == 0, the next title is FORCED to be Vs style.
Otherwise, you may still use Vs for variety but it's optional.

Vs format examples:
  • "Black Hole Vs Light Speed: Who Wins?"
  • "Neutron Star Vs Sun: A Density Battle"
  • "Saturn's Rings Vs A Bathtub"
  • "JWST Vs Hubble: Image Battle"
  • "Quasar Vs Pulsar: Brightness War"
The "Vs" word is an algorithm trigger — comparison content gets 3-5x click-through.

Each object MUST have:
- "baslik": punchy English headline (e.g. "Rogue Planets Drift Alone in Interstellar Space")
- "url": Wikipedia URL of the main subject. MUST be a real Wikipedia page.

CRITICAL — ANTI-DUPLICATE RULES:
1) Avoid any topic whose Wikipedia URL appears in the BLOCKED URLs list.
2) Avoid topics SEMANTICALLY SIMILAR to BLOCKED TITLES.
3) Prefer subjects that do NOT share the main noun with any blocked title.


═══ TITLE GATE v2 (11 Aug 2026 — re-measured on 193 PUBLIC, 3-day-mature Shorts;
    views normalised by publish-hour band. ALL checks mandatory) ═══
Reject and regenerate any topic that fails one.

G1. HUMAN-SCALE ANCHOR: name something the viewer's body knows — Earth, the Sun,
    the Moon, Mars, a city, a coin, a teaspoon, a human.
    NOTE: "super-Earth" / "Earth-sized" / "Earth-like" DO NOT count. They are
    classification labels, not comparisons.

G2. STAKES OR PAYOFF: promise a consequence or wonder, never a bare description
    ("...characteristics and supernova potential", "is losing gas").

G3. FAMILIAR FIRST when possible (Europa, Betelgeuse, Jupiter, the Sun). Obscure
    catalog IDs are NOT penalised by channel data — Stephenson 2-18 earned 806,
    Gliese 667 Cc 772, HD 106906 b 1001 — but they MUST carry a G6 comparison,
    because the name alone gives the viewer nothing.

G4. SUBJECT COOLDOWN: 7 days, not 21. Channel data shows NO sequel decay
    (28 first-appearances median 408 vs 22 repeats median 430). Betelgeuse,
    Europa and Ganymede are proven repeat winners. Do not starve them.

G5. WATER/LIFE PRIORITY: at least 1 daily topic involves water, oceans,
    habitability or alien-life potential.

G6. ★ QUANTIFIED COMPARISON — STRONGEST MEASURED VARIABLE (p=0.0005) ★
    The title MUST contain an explicit comparison against a known object:
    "than", "times", "twice", "half", "beyond", "as much as", "could fit inside",
    "wider/brighter/deeper/larger/hotter than".
    Channel data: n=24 scored 1.74x normalised vs 0.93x without.
    A bare number is worthless — the number only works when it lands ON a
    comparison target. KEEP THE MULTIPLIER GRASPABLE (prefer under ~50,000x):
    "170 times brighter than the sun" earned 854; "five million times brighter"
    earned 130. Re-anchor astronomical figures into something imaginable
    ("brighter than forty thousand suns", "swelling beyond the orbit of Mars").

G7. VAGUE MAGNITUDE — BANNED (weaker signal, p=0.08, but costs nothing):
    never let an adjective carry the scale: extreme, extremely, swings,
    at a massive scale, over time, dramatic, significant, intense, powerful,
    incredible, amazing. Replace with the number and a comparison target.
    "Extreme temperature swings" -> "swings 400 degrees between day and night".

FEW-SHOT — PASS (real winners, view counts verified):
  ✅ 1140: "Europa's Ocean: More Water Than Earth's!"
  ✅ 1001: "HD 106906 b orbits seven hundred times further than Earth"
  ✅  854: "Arcturus orange giant star is 170 times brighter than the sun"
  ✅  839: "Coin sized black hole would destroy the Earth in minutes"
  ✅  830: "Over one million Earths could fit inside the Sun's immense volume"
  ✅  750: "Ganymede's hidden ocean contains more water than all Earth's oceans"
  ✅  742: "Betelgeuse is swelling beyond the orbit of Mars"
  ✅  665: "Rigel star shines brighter than forty thousand suns"

FEW-SHOT — FAIL (all PUBLIC and mature — never write these):
  ❌   3: "Comet Galaxy is losing its stars and gas at extreme speed"    (G6+G7)
  ❌  45: "Gliese 832 c super-Earth has extreme temperature swings"      (G1 fake anchor, G6, G7)
  ❌  67: "Betelgeuse star is shrinking and swelling at a massive scale" (G6, G7)
  ❌  98: "Wolf 1061c orbit changes cause extreme climate swings"        (G6, G7)
  ❌ 245: "Polaris is a triple star system brightening over time"        (G2, G6, G7)

THE DECISIVE PAIR — same star, same publish-hour band, 7 days apart:
  ✅ 742  "Betelgeuse is swelling BEYOND THE ORBIT OF MARS"   <- measured comparison
  ❌  67  "Betelgeuse ... swelling AT A MASSIVE SCALE"        <- vague adjective
  11x difference. The subject was not the problem. The measurement was.

⚠️ NOTE ON THE OLD FAIL EXAMPLES (removed 11 Aug): three of them were PRIVATE
   videos with 0 views — a publishing fault, not a title fault. One of them
   ("WOH G64 ... two thousand times wider than the Sun") is in fact the proven
   winning shape. The gate was banning its own best weapon.
"""


def _basit_baslik_kelimeleri(b: str) -> set[str]:
    """Başlığın anlamlı kelimelerini set olarak döner (stopword'leri at)."""
    import re as _re
    ATIL = {
        "a","an","the","is","are","was","were","of","in","on","at","to","for",
        "and","or","but","with","as","by","be","has","have","had","do","does",
        "did","this","that","these","those","it","its","i","you","we","they",
        "their","what","why","how","when","known","called","group","fact",
    }
    kelimeler = _re.findall(r"[a-z]{3,}", b.lower())
    return {k for k in kelimeler if k not in ATIL}


# 14 Ağu — regex GENİŞLETİLDİ. Dar sürüm gerçek kıyasları kaçırıyordu:
#   "Ten Thousand Galaxies Could HOLD"     → kıyas VAR ama yakalanmadı
#   "Thick ENOUGH TO walk through"          → kıyas VAR ama yakalanmadı
# Bu yüzden 2. turda üretilen iyi başlıklar da reddediliyordu.
_KIYAS = re.compile(
    r"\b(than|times|twice|triple|half|beyond|"
    r"as (much|many|big|wide|heavy|bright|hot|cold|long|far|dense)( \w+){0,2} as|"
    # ↑ araya kelime girebilir: "as much WATER as", "as wide AS THE MOON"
    r"could (fit|hold|swallow|contain|cover)|fits? inside|"
    r"enough to|size of|mass of|width of|weight of|"
    r"compared to|equivalent (to|of)|"
    r"wider|brighter|deeper|larger|hotter|colder|heavier|faster|denser|bigger)\b", re.I)
_MUGLAK = re.compile(r"\b(extreme(ly)?|swings?|massive scale|over time|dramatic|"
                     r"significant|intense|powerful|incredible|amazing)\b", re.I)


def _baslik_kapisi(b: str) -> str | None:
    """11 Ağu — G6/G7 SERT KAPI. None = geçti.

    Neden prompt yetmiyor: TITLE GATE 31 Tem'den beri promptta ama gate sonrası
    29 başlığın sadece 5'inde (%17) kıyas vardı. Model kuralı yok sayıyor.
    Ölçüm (193 public+olgun video, saat-bandına normalize, permütasyon):
      kıyas VAR  n=24 norm 1.74
      kıyas YOK  n=169 norm 0.93   → p=0.0005
    Doğal deney: aynı yıldız, aynı saat bandı, 7 gün arayla
      "Betelgeuse swelling BEYOND THE ORBIT OF MARS" = 742
      "Betelgeuse swelling AT A MASSIVE SCALE"       =  67  → 11 kat
    """
    if _MUGLAK.search(b):
        return "G7 muğlak büyüklük"
    if not _KIYAS.search(b):
        return "G6 ölçülmüş kıyas yok"
    return None


def _baslik_benzer_mi(yeni: str, eski_setleri: list[set[str]], esik: float = 0.4) -> bool:
    """Yeni başlık eski setlerden biriyle %esik üstü kelime overlap'ı varsa True."""
    y = _basit_baslik_kelimeleri(yeni)
    if not y:
        return False
    for s in eski_setleri:
        if not s:
            continue
        kesisim = len(y & s)
        oran = kesisim / max(len(y), 1)
        if oran >= esik:
            return True
    return False


def gemini_konu_uret(blokli_url: set[str], adet: int = 3) -> list[dict]:
    """Reddit fail olursa fallback — Gemini'den niş konu üretir.
    URL + konu/başlık benzerliği ile çift katmanlı dedup. pytrends seed eklenir."""
    import bridge
    blokli_liste = sorted(list(blokli_url))[-100:]  # son 100 URL
    bloklar = "\n".join(f"- {u}" for u in blokli_liste) or "(yok)"
    # YUKLEMELER son 50 başlık — semantik benzerlik için Gemini'ye + Python filter'a
    son_basliklar: list[str] = []
    try:
        yuklemeler_yolu = Path(__file__).parent / "yuklemeler.json"
        if yuklemeler_yolu.exists():
            kayitlar = json.loads(yuklemeler_yolu.read_text(encoding="utf-8"))
            son_basliklar = [k.get("title", "") for k in kayitlar[-50:] if k.get("title")]
    except (OSError, json.JSONDecodeError):
        pass
    baslik_bloklari = "\n".join(f"- {b}" for b in son_basliklar) or "(yok)"
    eski_set_listesi = [_basit_baslik_kelimeleri(b) for b in son_basliklar]

    trend_seedleri = gunun_trend_seedleri()
    trend_blok = (
        f"\nTODAY'S GOOGLE TRENDS (top US search trends — gentle inspiration, "
        f"NOT mandatory; pick a related space/astronomy angle ONLY if a clean "
        f"connection exists; otherwise ignore):\n"
        + "\n".join(f"  · {s}" for s in trend_seedleri)
        if trend_seedleri else ""
    )

    # FAZ 4: Daily Theme — kanal kimliği için günün haftasının teması
    import datetime
    DAILY_THEMES = {
        0: "planets and moons (Jupiter, Saturn rings, Europa, Titan)",
        1: "ocean worlds and icy moons (Europa, Enceladus, Titan) — water/life angle",
        2: "galaxies, dark matter, cosmic structures",
        3: "exoplanets, habitable zones, alien life potential",
        4: "stars, supernovae, stellar evolution",
        5: "habitable exoplanets and Earth-like worlds — water/life angle",
        6: "solar system mysteries (Sun, asteroids, comets)",
    }
    bugun_tema = DAILY_THEMES.get(datetime.datetime.now().weekday(), "any space/astronomy")
    tema_blok = (
        f"\nDAILY THEME (today's editorial focus — STRONGLY prefer topics from this theme):\n"
        f"  → {bugun_tema}\n"
    )

    # FAZ 4: Sequel injection — son haftanın top viral'lerinin DEVAMI
    sequel_blok = ""
    try:
        vp = Path(__file__).parent / "viral_patterns.json"
        if vp.exists():
            vp_data = json.loads(vp.read_text())
            ornek = vp_data.get("viral", {}).get("ornek_basliklar", [])[:3]
            if ornek:
                sequel_blok = (
                    f"\nSEQUEL OPPORTUNITY (own channel's recent viral hits — "
                    f"consider a 'next chapter' or related-but-different topic):\n"
                    + "\n".join(f"  · {t}" for t in ornek)
                    + "\n  → If you make a sequel, pick an ADJACENT topic (same category, different example).\n"
                    + "  → HARD RULE: NEVER the same star system/object within 21 days — "
                    + "sequel decay is proven on this channel (TRAPPIST: 1315→190→175→0).\n"
                )
    except Exception:
        pass

    # FAZ 8: Real-Time Trending Detector — competitor'lardan VIRAL (10K+ izl) konular
    trending_blok = ""
    try:
        cs = Path(__file__).parent / "competitor_signals.json"
        if cs.exists():
            cs_data = json.loads(cs.read_text())
            # 10K+ izlenmiş "GERÇEK viral" başlıklar
            top = cs_data.get("rakip_top_30_izlenme", [])
            gercek_viral = [t for t in top if t.get("views", 0) >= 10000][:8]
            if gercek_viral:
                lines = [f"  · [{t['views']:,} views] {t['title'][:80]}" for t in gercek_viral]
                trending_blok = (
                    f"\nREAL-TIME TRENDING (10K+ view SPACE shorts from top channels, last 7d) "
                    f"— THESE ANGLES ARE PROVEN VIRAL RIGHT NOW:\n"
                    + "\n".join(lines)
                    + "\n  → STRONGLY prefer adapting one of these angles to a different subject "
                    + "(same hook structure, different object/region). Trend riding = algorithm boost.\n"
                )
    except Exception:
        pass
    try:
        # 2 turlu üretim: ilk turda red varsa Python filter'la ele, 2. turda
        # daha güçlü uyarıyla yeniden iste.
        sonuc: list[dict] = []
        for tur in range(2):
            ek_uyari = (
                ""
                if tur == 0
                else (
                    "\n\nYOUR PREVIOUS BATCH CONTAINED TOPICS TOO SIMILAR TO BLOCKED "
                    "TITLES. Choose entirely different space objects/phenomena. "
                    "Forbidden subjects this round: "
                    + ", ".join(sorted({list(s)[0] for s in eski_set_listesi if s})[:30])
                    # 14 Ağu — KRİTİK: 2. tur kapısı "uyar-geç" modunda (starvation
                    # koruması). Yani 1. turda G6 reddi yiyen konular 2. turda AYNEN
                    # geçiyordu → uyum 3 gün sonra hâlâ %17. Çözüm: 2. tur PROMPT'una
                    # G6/G7'yi tekrar bas ki üretilen başlıklar zaten kıyaslı gelsin.
                    + "\n\n🔴 ABSOLUTE REQUIREMENT FOR THIS ROUND (previous batch was "
                      "rejected for missing it): EVERY title MUST contain an explicit "
                      "quantified comparison — 'than', 'times', 'twice', 'beyond', "
                      "'as much as', 'could fit inside', 'wider/brighter/larger than'. "
                      "Channel data: titles with a comparison earn 1.74x vs 0.93x "
                      "(p=0.0005). A bare number is NOT enough — the number must land "
                      "on a comparison target.\n"
                      "AND: never use vague magnitude words (extreme, extremely, swings, "
                      "massive scale, over time, dramatic, intense, powerful). "
                      "Replace them with the number + what it is being compared to.\n"
                      "Example rewrite: 'K2-9b is an extreme exoplanet where it rains "
                      "liquid iron' → 'K2-9b rains liquid iron at 2000 degrees hotter "
                      "than lava'."
                )
            )
            yanit = bridge.gemini_metin_uret(
                prompt=(
                    f"BLOCKED Wikipedia URLs (do not reuse):\n{bloklar}\n\n"
                    f"BLOCKED TITLES (do not produce semantically similar topics):\n{baslik_bloklari}"
                    f"{trend_blok}{tema_blok}{sequel_blok}{trending_blok}{ek_uyari}\n\n"
                    f"Produce exactly {adet} fresh viral space/astronomy topics now."
                ),
                sistem_promptu=GEMINI_KONU_SISTEM,
                sicaklik=0.95,
                max_token=2048,
            )
            m = re.search(r"\[.*\]", yanit, re.DOTALL)
            if not m:
                continue
            kayitlar = json.loads(m.group(0))
            for i, k in enumerate(kayitlar[:adet]):
                if not (k.get("baslik") and k.get("url")):
                    continue
                # Konu/başlık benzerliği kontrolü
                if _baslik_benzer_mi(k["baslik"], eski_set_listesi):
                    print(f"[haberci] Gemini başlığı '{k['baslik'][:40]}…' eski bir konuya çok benzer → atlandı")
                    continue
                # 11 Ağu: G6/G7 sert kapı. 1. turda ZORLA, 2. turda uyar-geç
                # (starvation koruması — konu hiç üretilemezse pipeline durur).
                _red = _baslik_kapisi(k["baslik"])
                if _red:
                    if tur == 0:
                        print(f"[haberci] TITLE GATE red ({_red}): {k['baslik'][:55]}…")
                        continue
                    print(f"[haberci] ⚠️ TITLE GATE uyarı ({_red}) — 2. tur, kabul: {k['baslik'][:55]}…")
                # URL geçmişte var mı
                if _normalize_url(k["url"]) in blokli_url:
                    print(f"[haberci] Gemini URL'si geçmişte → atlandı: {k['url']}")
                    continue
                sonuc.append({
                    "baslik": k["baslik"],
                    "url": k["url"],
                    "kaynak": "gemini-fallback",
                    "skor": 1000 - i,
                    "yas_saat": 0,
                    "yorum_sayisi": 0,
                })
            if len(sonuc) >= 1:
                break
        return sonuc[:adet]
    except Exception as hata:
        print(f"[haberci] Gemini fallback hatası: {hata}")
        return []


def _gecmisi_oku() -> set[str]:
    if not GECMIS_DOSYASI.exists():
        return set()
    try:
        veri = json.loads(GECMIS_DOSYASI.read_text(encoding="utf-8"))
        return {_normalize_url(u) for u in veri.get("islenen_url", [])}
    except (json.JSONDecodeError, OSError):
        return set()


def _gecmise_ekle(yeni_urller: list[str]) -> None:
    mevcut: list[str] = []
    if GECMIS_DOSYASI.exists():
        try:
            mevcut = json.loads(GECMIS_DOSYASI.read_text(encoding="utf-8")).get("islenen_url", [])
        except (json.JSONDecodeError, OSError):
            mevcut = []
    birlesim = mevcut + [u for u in yeni_urller if u not in mevcut]
    if len(birlesim) > GECMIS_AZAMI_KAYIT:
        birlesim = birlesim[-GECMIS_AZAMI_KAYIT:]
    GECMIS_DOSYASI.write_text(
        json.dumps({"islenen_url": birlesim}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def en_populer_3() -> list[dict]:
    """17 Haz 2026: Reddit GitHub IP'lerini blokladı (403). Ana kaynak Gemini.
    Reddit kodu kaldırılmadı (geriye uyumluluk için tutuldu) ama
    PRIMARY kaynak artık Gemini + viral_radar (YouTube trending besli).
    """
    gecmis = _gecmisi_oku()

    # 1. ÖNCELİK: Gemini direkt konu üretsin (viral_radar bloğu beslenir)
    print("[haberci] Ana kaynak: Gemini + viral_radar (Reddit kaldırıldı 17 Haz)", flush=True)
    secilen = gemini_konu_uret(gecmis, adet=15)
    print(f"[haberci] Gemini'den {len(secilen)} konu önerisi geldi", flush=True)
    if len(secilen) == 0:
        print("[haberci] 1. tur boş → 2. tur Gemini (geçmiş bypass)", flush=True)
        secilen = gemini_konu_uret(set(), adet=15)
        print(f"[haberci] 2. tur Gemini'den {len(secilen)} konu geldi", flush=True)

    # 2. Yedek: Reddit dene (eğer GitHub IP blok kalkmışsa bonus aday)
    if len(secilen) < 3:
        print("[haberci] Gemini yetersiz → Reddit deneniyor (yedek)...", flush=True)
        try:
            havuz = hackernews_haberleri() + reddit_haberleri()
            benzersiz = _tekrarlari_ele(havuz)
            ekstra = [
                h for h in benzersiz if _normalize_url(h["url"]) not in gecmis
            ]
            ekstra.sort(key=lambda h: h["skor"], reverse=True)
            mevcut_urller = {_normalize_url(h["url"]) for h in secilen}
            for k in ekstra:
                if _normalize_url(k["url"]) not in mevcut_urller:
                    secilen.append(k)
                    mevcut_urller.add(_normalize_url(k["url"]))
            print(f"[haberci] Reddit yedeği sonrası toplam: {len(secilen)}", flush=True)
        except Exception as h:
            print(f"[haberci] Reddit yedek başarısız: {str(h)[:120]}", flush=True)

    return secilen[:3]


# 11 Tem 2026 — EVERGREEN YEDEK: Gemini kotası biter + Reddit 403 olursa haberci
# ASLA boş dönmesin (pipeline exit-1 çökme kökü). Footage-bol, niş-özel, kanıtlı konular.
EVERGREEN_KONULAR = [
    {"baslik": "A black hole's gravity is so strong not even light escapes", "url": 'https://en.wikipedia.org/wiki/Black_hole', "ozet": 'Event horizon: the point of no return', "kaynak": "evergreen", "skor": 900, "yas_saat": 0, "yorum_sayisi": 0},
    {"baslik": "Saturn's rings are made of billions of ice chunks", "url": 'https://en.wikipedia.org/wiki/Rings_of_Saturn', "ozet": 'From dust grains to house-sized boulders', "kaynak": "evergreen", "skor": 900, "yas_saat": 0, "yorum_sayisi": 0},
    {"baslik": 'A neutron star teaspoon would weigh a billion tons', "url": 'https://en.wikipedia.org/wiki/Neutron_star', "ozet": 'The densest matter in the universe', "kaynak": "evergreen", "skor": 900, "yas_saat": 0, "yorum_sayisi": 0},
    {"baslik": "Jupiter's Great Red Spot is a storm bigger than Earth", "url": 'https://en.wikipedia.org/wiki/Great_Red_Spot', "ozet": 'Raging for over 350 years', "kaynak": "evergreen", "skor": 900, "yas_saat": 0, "yorum_sayisi": 0},
    {"baslik": "The Sun makes up 99.8% of the Solar System's mass", "url": 'https://en.wikipedia.org/wiki/Sun', "ozet": 'Everything else is a rounding error', "kaynak": "evergreen", "skor": 900, "yas_saat": 0, "yorum_sayisi": 0},
    {"baslik": 'A day on Venus is longer than its year', "url": 'https://en.wikipedia.org/wiki/Venus', "ozet": 'It spins backwards, too', "kaynak": "evergreen", "skor": 900, "yas_saat": 0, "yorum_sayisi": 0},
    {"baslik": 'The Milky Way and Andromeda will collide in 4 billion years', "url": 'https://en.wikipedia.org/wiki/Andromeda%E2%80%93Milky_Way_collision', "ozet": 'A galactic merger already begun', "kaynak": "evergreen", "skor": 900, "yas_saat": 0, "yorum_sayisi": 0},
    {"baslik": 'Neutron stars can spin 700 times per second', "url": 'https://en.wikipedia.org/wiki/Pulsar', "ozet": 'Cosmic lighthouses called pulsars', "kaynak": "evergreen", "skor": 900, "yas_saat": 0, "yorum_sayisi": 0},
    {"baslik": 'A supernova can briefly outshine an entire galaxy', "url": 'https://en.wikipedia.org/wiki/Supernova', "ozet": "A dying star's final flash", "kaynak": "evergreen", "skor": 900, "yas_saat": 0, "yorum_sayisi": 0},
    {"baslik": 'Mars has the tallest volcano in the Solar System', "url": 'https://en.wikipedia.org/wiki/Olympus_Mons', "ozet": 'Olympus Mons is three times Everest', "kaynak": "evergreen", "skor": 900, "yas_saat": 0, "yorum_sayisi": 0},
    {"baslik": "Saturn's moon Titan has lakes of liquid methane", "url": 'https://en.wikipedia.org/wiki/Titan_(moon)', "ozet": 'The only other world with surface liquid', "kaynak": "evergreen", "skor": 900, "yas_saat": 0, "yorum_sayisi": 0},
    {"baslik": 'The observable universe is 93 billion light years across', "url": 'https://en.wikipedia.org/wiki/Observable_universe', "ozet": "And that's just what we can see", "kaynak": "evergreen", "skor": 900, "yas_saat": 0, "yorum_sayisi": 0},
    {"baslik": 'Light from the Sun takes 8 minutes to reach Earth', "url": 'https://en.wikipedia.org/wiki/Sunlight', "ozet": 'You always see the Sun in the past', "kaynak": "evergreen", "skor": 900, "yas_saat": 0, "yorum_sayisi": 0},
    {"baslik": "A comet's tail always points away from the Sun", "url": 'https://en.wikipedia.org/wiki/Comet_tail', "ozet": 'Solar wind blows it back', "kaynak": "evergreen", "skor": 900, "yas_saat": 0, "yorum_sayisi": 0},
    {"baslik": 'The Moon is drifting away from Earth every year', "url": 'https://en.wikipedia.org/wiki/Orbit_of_the_Moon', "ozet": '3.8 cm farther, every single year', "kaynak": "evergreen", "skor": 900, "yas_saat": 0, "yorum_sayisi": 0},
]


def _evergreen_sec(adet: int = 3) -> list:
    """Gemini+Reddit boş dönerse evergreen havuzdan geçmişte-olmayan konu seç."""
    import random
    try:
        gecmis = _gecmisi_oku()
    except Exception:
        gecmis = set()
    taze = [k for k in EVERGREEN_KONULAR if _normalize_url(k["url"]) not in gecmis]
    havuz = taze if len(taze) >= adet else list(EVERGREEN_KONULAR)
    random.shuffle(havuz)
    return [dict(k) for k in havuz[:adet]]


def main() -> int:
    print("[haberci] Uzay/astronomi nişi — Reddit + Gemini fallback taranıyor...\n")
    secilenler = en_populer_3()

    if not secilenler:
        print("[haberci] Gemini+Reddit boş → EVERGREEN havuzdan seçiliyor (pipeline korunur)", flush=True)
        secilenler = _evergreen_sec(3)

    if not secilenler:
        print("[haberci] Hiç haber bulunamadı (evergreen de boş?!).")
        return 1

    cikti = {
        "uretim_zamani": _simdi_utc().isoformat(),
        "haberler": secilenler,
    }
    CIKTI_DOSYASI.write_text(json.dumps(cikti, ensure_ascii=False, indent=2), encoding="utf-8")
    _gecmise_ekle([h.get("url", "") for h in secilenler if h.get("url")])

    # Özet print SAVUNMACI: haberler.json zaten yazıldı. Gemini-fallback/sequel
    # dict'lerinde skor/yas_saat/kaynak olmayabilir — kozmetik print YÜZÜNDEN
    # pipeline ÇÖKMESİN (10 Tem: KeyError 'skor' kanalları durdurdu).
    for sira, h in enumerate(secilenler, 1):
        print(f"{sira}. [{h.get('kaynak','?')} · skor {h.get('skor','—')} · {h.get('yas_saat','—')} sa]")
        print(f"   {h.get('baslik','?')}")
        print(f"   {h.get('url','')}\n")

    print(f"[haberci] JSON dosyaya yazıldı: {CIKTI_DOSYASI.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
