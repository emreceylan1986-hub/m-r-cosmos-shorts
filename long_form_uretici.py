#!/usr/bin/env python3
"""
long_form_uretici.py — Cosmos haftalık 8-12 dakikalık deep-dive video üretici.

ZINCIR:
  1. Konu seç (top performance Shorts'tan derinleştirilebilir biri)
  2. Gemini ile 1500-2000 kelime hikaye yapılı senaryo
  3. edge-tts ile sakin uzun seslendirme
  4. NASA arşivi + Pexels + Wikimedia'dan görsel topla (8-12dk için ~40-60 görsel)
  5. ffmpeg ile yatay 1920×1080 video (Ken Burns + slow pan)
  6. Bold all-caps dramatic thumbnail (Pillow)
  7. YouTube'a yükle (kategori 28 Science)

Kullanım:
  python long_form_uretici.py
  python long_form_uretici.py --konu "Rogue Planets"   # Konu zorla
  python long_form_uretici.py --kuru                    # Test, upload yapma
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

PANEL_KOK = Path(__file__).parent
TOKEN = PANEL_KOK / "token.json"
CIKTI_KOK = PANEL_KOK / "long_form_ciktilari"
CIKTI_KOK.mkdir(exist_ok=True)
LOG = PANEL_KOK / "long_form.log"

GEMINI_LONG_FORM_SISTEM = """You produce LONG-FORM (8-12 minute) deep-dive YouTube
SCIENCE / COSMOS scripts. Output ONLY a JSON object with keys: title, hook, intro,
chapters (array of {title, content}), conclusion, description, tags.

═══ TITLE RULES (CRITICAL for CTR) ═══
- 60-80 characters
- Use DRAMATIC nouns: 'The Lonely Wanderer', 'The Cosmic Tomb', 'Last Light'
- Optional bracket subtitle: 'Rogue Planets: Earth's Forgotten Cousins'
- AVOID 'Imagine', 'Did you know', 'Ever wonder'
- USE bold language: 'Hidden', 'Forbidden', 'Forgotten', 'Last', 'Final', 'Doomed'
- Reference scale: '8 Light-Years Wide', 'Older Than Time', '100,000 Galaxies'

═══ STRUCTURE (target 1500-2000 words total) ═══
1. HOOK (1 paragraph, 80-120 words) — punchy opening that asks "what if" or
   states a mind-bending fact. NO 'Did you know' / 'Ever wonder' / 'Imagine'.
2. INTRO (1 paragraph, 100-150 words) — set up the question, why it matters.
3. CHAPTERS (4-6 chapters, each 200-300 words) — each chapter is one fact,
   one event, one piece of evidence. Build the story progressively.
4. CONCLUSION (1 paragraph, 100-150 words) — big picture takeaway, leave the
   viewer thinking. End with "Subscribe for more cosmic deep-dives."

═══ STORY VOICE ═══
- Narrative, awe-struck, NOT teacher tone
- Use vivid metaphors and analogies
- Use concrete numbers and comparisons
- Avoid jargon; if you must use a technical term, explain it in next sentence
- 100% factually accurate — no debunked theories presented as fact

═══ VIRAL PATTERN (proven CosmoBytes top performers) ═══
- "Rogue Planets" (yalnızlık)
- "Europa's Ocean" (hayat ihtimali)
- "Sombrero Galaxy" (görsel benzetme)
- "Pillars of Creation" (soy isim)

For the input topic, write a 1500-2000 word documentary-style script. Be specific,
vivid, and emotionally engaging."""

# Top viral Cosmos konuları (derinleştirilebilir)
DEEP_DIVE_KONULARI = [
    "Rogue Planets Drift Alone in Interstellar Space Without a Sun",
    "Europa's Ocean: Could Hide Life Under Ice",
    "Sombrero Galaxy: Cosmic Hat with a Billion-Sun Black Hole",
    "Pillars of Creation: Cosmic Nurseries Forming New Stars",
    "Veil Nebula: A Star That Exploded 10,000 Years Ago",
    "Boomerang Nebula: Coldest Place in the Universe",
    "TON 618: A Black Hole 66 Billion Times the Mass of the Sun",
    "Wolf-Rayet Stars: The Universe's Most Violent Stars",
    "Ultima Thule: Our Most Distant Visited Object",
    "Tabby's Star: The Strangest Star Discovered",
]

YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    satir = f"[{ts}] LONG-FORM {msg}"
    print(satir, flush=True)
    try:
        LOG.write_text((LOG.read_text() if LOG.exists() else "") + satir + "\n")
    except Exception:
        pass


def konu_sec(zorla=None):
    """Konu seç — daha önce kullanılmamış olanlardan."""
    if zorla:
        return zorla
    gecmis_yolu = PANEL_KOK / "long_form_gecmis.json"
    gecmis = []
    if gecmis_yolu.exists():
        try:
            gecmis = json.loads(gecmis_yolu.read_text()).get("konular", [])
        except Exception:
            pass
    for konu in DEEP_DIVE_KONULARI:
        if konu not in gecmis:
            return konu
    # Tüm konular kullanıldı, rotate
    return DEEP_DIVE_KONULARI[len(gecmis) % len(DEEP_DIVE_KONULARI)]


def konu_kaydet(konu):
    gecmis_yolu = PANEL_KOK / "long_form_gecmis.json"
    g = {"konular": []}
    if gecmis_yolu.exists():
        try:
            g = json.loads(gecmis_yolu.read_text())
        except Exception:
            pass
    if konu not in g["konular"]:
        g["konular"].append(konu)
    gecmis_yolu.write_text(json.dumps(g, ensure_ascii=False, indent=2))


def gemini_senaryo_uret(konu):
    """Gemini ile 1500-2000 kelime hikaye yapılı script üret."""
    import bridge
    prompt = (
        f"Topic: {konu}\n\n"
        f"Write a 1500-2000 word long-form documentary script about this topic. "
        f"Follow the structure (hook, intro, 4-6 chapters, conclusion) and "
        f"return as a JSON object."
    )
    yanit = bridge.gemini_metin_uret(
        prompt=prompt,
        sistem_promptu=GEMINI_LONG_FORM_SISTEM,
        sicaklik=0.85,
        max_token=8192,
    )
    m = re.search(r"\{.*\}", yanit, re.DOTALL)
    if not m:
        raise RuntimeError("Gemini JSON döndürmedi")
    return json.loads(m.group(0))


def script_birlestir(senaryo):
    """JSON senaryoyu tek bir metin haline getir (TTS için)."""
    parcalar = [
        senaryo.get("hook", ""),
        senaryo.get("intro", ""),
    ]
    for b in senaryo.get("chapters", []):
        parcalar.append(b.get("content", ""))
    parcalar.append(senaryo.get("conclusion", ""))
    return "\n\n".join(p.strip() for p in parcalar if p.strip())


def edge_tts_uret(metin, hedef_mp3):
    """edge-tts ile sakin, derin ses üret."""
    import edge_tts
    import asyncio

    async def _uret():
        communicate = edge_tts.Communicate(
            metin,
            voice="en-US-GuyNeural",  # sakin derin erkek ses
            rate="-5%",  # biraz yavaş, deep-dive tonu
        )
        await communicate.save(str(hedef_mp3))

    asyncio.run(_uret())
    log(f"  ✓ TTS üretildi: {hedef_mp3.name}")


def gorseller_topla(konu, hedef_klasor, adet=50):
    """NASA images + Pexels + Wikimedia'dan görsel topla."""
    import requests
    hedef_klasor.mkdir(exist_ok=True)
    indirilen = 0

    # 1. NASA Image Library (telifsiz, official)
    try:
        nasa_anahtarlar = konu.lower().split()[:3]
        nasa_arama = " ".join(nasa_anahtarlar)
        r = requests.get(
            "https://images-api.nasa.gov/search",
            params={"q": nasa_arama, "media_type": "image"},
            timeout=20,
        )
        if r.ok:
            items = r.json().get("collection", {}).get("items", [])[:25]
            for i, it in enumerate(items):
                try:
                    link = it.get("links", [{}])[0].get("href")
                    if not link:
                        continue
                    img = requests.get(link, timeout=20).content
                    (hedef_klasor / f"nasa_{i:03d}.jpg").write_bytes(img)
                    indirilen += 1
                    if indirilen >= adet * 0.6:  # %60 NASA
                        break
                except Exception:
                    continue
        log(f"  ✓ NASA'dan {indirilen} görsel")
    except Exception as h:
        log(f"  ⚠️ NASA hata: {h}")

    # 2. Pexels (kalan slot)
    try:
        envf = PANEL_KOK / ".env"
        pexels_key = os.environ.get("PEXELS_API_KEY")
        if not pexels_key and envf.exists():
            for line in envf.read_text().splitlines():
                if line.startswith("PEXELS_API_KEY="):
                    pexels_key = line.split("=", 1)[1].strip()
                    break
        if pexels_key:
            arama = "space astronomy " + konu.split()[0].lower()
            r = requests.get(
                "https://api.pexels.com/v1/search",
                params={"query": arama, "per_page": adet, "orientation": "landscape"},
                headers={"Authorization": pexels_key},
                timeout=20,
            )
            if r.ok:
                photos = r.json().get("photos", [])
                for i, p in enumerate(photos):
                    if indirilen >= adet:
                        break
                    try:
                        src = p["src"].get("large2x") or p["src"].get("large")
                        img = requests.get(src, timeout=20).content
                        (hedef_klasor / f"pexels_{i:03d}.jpg").write_bytes(img)
                        indirilen += 1
                    except Exception:
                        continue
            log(f"  ✓ Pexels eklendi (toplam {indirilen})")
    except Exception as h:
        log(f"  ⚠️ Pexels hata: {h}")

    return indirilen


def video_render(mp3, gorseller_klasor, hedef_mp4):
    """ffmpeg ile yatay 1920x1080 video — slow zoom her görselde."""
    # Mp3 süresi
    sure = float(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(mp3)
    ]).strip())

    gorseller = sorted(gorseller_klasor.glob("*.jpg"))
    if not gorseller:
        raise RuntimeError("Görsel yok")

    # Her görsel ~10-15 saniye
    her_gorsel_sure = max(8, sure / len(gorseller))
    log(f"  Süre: {sure:.0f}sn, {len(gorseller)} görsel, her görsel {her_gorsel_sure:.1f}sn")

    # Concat input listesi (her görsel için zoompan filter)
    tmp_dir = hedef_mp4.parent / "tmp_klipler"
    tmp_dir.mkdir(exist_ok=True)
    klip_listesi = []
    for i, g in enumerate(gorseller):
        klip = tmp_dir / f"klip_{i:03d}.mp4"
        # Ken Burns zoom: 1.0 → 1.15
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-loop", "1", "-i", str(g),
            "-vf", f"scale=1920:1080:force_original_aspect_ratio=increase,"
                   f"crop=1920:1080,"
                   f"zoompan=z='min(zoom+0.0008,1.15)':d={int(her_gorsel_sure*25)}:s=1920x1080",
            "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            "-t", str(her_gorsel_sure), "-r", "25",
            str(klip)
        ], check=True)
        klip_listesi.append(klip)

    # Concat
    liste_dosya = tmp_dir / "klipler.txt"
    liste_dosya.write_text("\n".join(f"file '{k.resolve()}'" for k in klip_listesi))
    birlesik_video = tmp_dir / "birlesik.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", str(liste_dosya),
        "-c", "copy", str(birlesik_video)
    ], check=True)

    # Ses ekle + son 18 saniyede END SCREEN overlay (SUBSCRIBE CTA)
    # Toplam süre - 18 saniyeden itibaren ortada büyük "↓ SUBSCRIBE ↓" yazısı
    cta_filtre = (
        f"drawtext=text='SUBSCRIBE FOR MORE COSMIC DEEP DIVES':"
        f"fontsize=64:fontcolor=yellow:fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
        f"x=(w-text_w)/2:y=h-200:"
        f"box=1:boxcolor=black@0.7:boxborderw=20:"
        f"enable='gte(t,{max(0, sure-18)})'"
    )
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(birlesik_video), "-i", str(mp3),
        "-vf", cta_filtre,
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest", str(hedef_mp4)
    ], check=True)

    # Temizlik
    for k in klip_listesi:
        k.unlink()
    liste_dosya.unlink()
    birlesik_video.unlink()
    tmp_dir.rmdir()

    log(f"  ✓ Video render bitti: {hedef_mp4.name} (son 18sn SUBSCRIBE CTA dahil)")


def thumbnail_uret(baslik, hedef_png):
    """Bold all-caps dramatic thumbnail (Erkan Kolcu tarzı)."""
    from PIL import Image, ImageDraw, ImageFont
    import requests

    # Pexels'tan dramatik uzay görseli arka plan
    try:
        envf = PANEL_KOK / ".env"
        pexels_key = os.environ.get("PEXELS_API_KEY")
        if not pexels_key and envf.exists():
            for line in envf.read_text().splitlines():
                if line.startswith("PEXELS_API_KEY="):
                    pexels_key = line.split("=", 1)[1].strip()
                    break
        if pexels_key:
            r = requests.get(
                "https://api.pexels.com/v1/search",
                params={"query": "nebula space dramatic", "per_page": 5,
                        "orientation": "landscape"},
                headers={"Authorization": pexels_key},
                timeout=15,
            )
            if r.ok and r.json().get("photos"):
                src = r.json()["photos"][0]["src"]["large2x"]
                img_bytes = requests.get(src, timeout=15).content
                tmp = hedef_png.with_suffix(".tmp.jpg")
                tmp.write_bytes(img_bytes)
                bg = Image.open(tmp).convert("RGB").resize((1280, 720))
                tmp.unlink()
            else:
                bg = Image.new("RGB", (1280, 720), (10, 10, 30))
        else:
            bg = Image.new("RGB", (1280, 720), (10, 10, 30))
    except Exception:
        bg = Image.new("RGB", (1280, 720), (10, 10, 30))

    # Karanlıklaştır — bottom gradient (üst görsel kalsın, alt metin alanı koyu)
    karaltma = Image.new("RGBA", bg.size, (0, 0, 0, 0))
    karaltma_draw = ImageDraw.Draw(karaltma)
    for y_grad in range(720):
        if y_grad < 360:
            alpha = int(60 * (y_grad / 360))  # üst hafif
        else:
            alpha = int(60 + 140 * ((y_grad - 360) / 360))  # alt koyu
        karaltma_draw.line([(0, y_grad), (1280, y_grad)], fill=(0, 0, 0, alpha))
    bg = bg.convert("RGBA")
    bg = Image.alpha_composite(bg, karaltma)
    draw = ImageDraw.Draw(bg)

    # DEEP DIVE badge — sol-üst kırmızı kutu
    try:
        badge_font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Impact.ttf", 38)
    except Exception:
        try: badge_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 38)
        except: badge_font = ImageFont.load_default()
    badge = "🌌 DEEP DIVE"
    bbox = draw.textbbox((0, 0), badge, font=badge_font)
    bw = bbox[2] - bbox[0]
    bh = bbox[3] - bbox[1]
    # Kırmızı arka kutu
    draw.rectangle([30, 30, 30 + bw + 30, 30 + bh + 25], fill=(220, 30, 30, 255))
    draw.text((45, 35), badge, fill=(255, 255, 255), font=badge_font)

    # Font yükle
    font_yollari = [
        "/System/Library/Fonts/Supplemental/Impact.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/HelveticaNeue.ttc",
    ]
    font = None
    for y in font_yollari:
        try:
            font = ImageFont.truetype(y, 110)
            break
        except Exception:
            continue
    if not font:
        font = ImageFont.load_default()

    # ALL CAPS başlık, max 3 satır
    baslik_caps = baslik.upper()
    kelimeler = baslik_caps.split()
    satirlar = []
    mevcut = ""
    for k in kelimeler:
        deneme = (mevcut + " " + k).strip()
        bbox = draw.textbbox((0, 0), deneme, font=font)
        if (bbox[2] - bbox[0]) > 1100 and mevcut:
            satirlar.append(mevcut)
            mevcut = k
        else:
            mevcut = deneme
    if mevcut:
        satirlar.append(mevcut)
    satirlar = satirlar[:3]

    # Metin yaz (sarı + siyah outline)
    y = 720 - len(satirlar) * 130 - 40
    for s in satirlar:
        bbox = draw.textbbox((0, 0), s, font=font)
        w = bbox[2] - bbox[0]
        x = (1280 - w) // 2
        # Outline (siyah)
        for dx, dy in [(-3, 0), (3, 0), (0, -3), (0, 3), (-3, -3), (3, 3), (-3, 3), (3, -3)]:
            draw.text((x + dx, y + dy), s, fill="black", font=font)
        # Asıl metin (sarı)
        draw.text((x, y), s, fill=(255, 220, 0), font=font)
        y += 130

    bg.convert("RGB").save(hedef_png, "PNG")
    log(f"  ✓ Thumbnail üretildi: {hedef_png.name}")


def youtube_yukle(video_mp4, thumbnail_png, senaryo, kuru=False):
    """YouTube'a yükle: kategori 28 (Science)."""
    if kuru:
        log(f"  [KURU] Yükleme atlandı: {video_mp4.name}")
        return None

    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    creds = Credentials.from_authorized_user_file(str(TOKEN), YOUTUBE_SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)

    body = {
        "snippet": {
            "title": senaryo.get("title", "Cosmic Deep Dive")[:100],
            "description": senaryo.get("description", "Cosmic deep dive.")[:5000],
            "tags": senaryo.get("tags", ["space", "astronomy", "cosmos"])[:15],
            "categoryId": "28",  # Science & Technology
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(str(video_mp4), mimetype="video/mp4", resumable=True)
    log(f"  ⬆️ Yükleniyor: {senaryo['title'][:60]}...")
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        status, response = req.next_chunk()
        if status:
            log(f"    {int(status.progress() * 100)}% yüklendi")
    video_id = response["id"]
    log(f"  ✓ Yayında: https://youtu.be/{video_id}")

    # Thumbnail set
    try:
        yt.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(str(thumbnail_png), mimetype="image/png")
        ).execute()
        log(f"  ✓ Thumbnail set")
    except HttpError as e:
        log(f"  ⚠️ Thumbnail set fail: {str(e)[:120]}")

    return video_id


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--konu", help="Konu zorla (default: rotasyondan)")
    p.add_argument("--kuru", action="store_true", help="Test modu, upload yok")
    args = p.parse_args()

    log("=== LONG-FORM ÜRETİM BAŞLA ===")
    konu = konu_sec(args.konu)
    log(f"Konu: {konu}")

    damga = datetime.now().strftime("%Y%m%d_%H%M%S")
    is_kok = CIKTI_KOK / damga
    is_kok.mkdir(parents=True)

    log("1) Gemini senaryo...")
    senaryo = gemini_senaryo_uret(konu)
    (is_kok / "senaryo.json").write_text(json.dumps(senaryo, ensure_ascii=False, indent=2))
    metin = script_birlestir(senaryo)
    (is_kok / "metin.txt").write_text(metin)
    kelime_sayisi = len(metin.split())
    log(f"  ✓ {kelime_sayisi} kelime")

    log("2) edge-tts seslendirme...")
    mp3 = is_kok / "ses.mp3"
    edge_tts_uret(metin, mp3)

    log("3) Görsel topla (NASA + Pexels)...")
    gorseller_klasor = is_kok / "gorseller"
    adet = gorseller_topla(konu, gorseller_klasor, adet=50)
    if adet < 10:
        raise RuntimeError(f"Sadece {adet} görsel bulundu, yetersiz")

    log("4) Video render...")
    video_mp4 = is_kok / "video.mp4"
    video_render(mp3, gorseller_klasor, video_mp4)

    log("5) Thumbnail...")
    thumbnail_png = is_kok / "thumbnail.png"
    thumbnail_uret(senaryo.get("title", konu), thumbnail_png)

    log("6) YouTube yükle...")
    video_id = youtube_yukle(video_mp4, thumbnail_png, senaryo, kuru=args.kuru)

    if video_id:
        konu_kaydet(konu)
        log(f"🎉 BAŞARI: https://youtu.be/{video_id}")

    log("=== LONG-FORM ÜRETİM BİTTİ ===")


if __name__ == "__main__":
    main()
