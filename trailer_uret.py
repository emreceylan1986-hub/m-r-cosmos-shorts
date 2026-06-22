#!/usr/bin/env python3
"""
trailer_uret.py — CosmoBytes kanal trailer (~23 sn).

YENİ STRATEJİ: Pillow ile telif-temiz cosmik sahneler üret. Her sahne için
zengin radial gradient + yıldız noktaları + büyük sembol. Profesyonel görünüm.

Çıktı:
    branding/trailer.mp4    1080x1920 Shorts dikey
    branding/trailer.mp3
    branding/trailer.txt
"""
import asyncio
import random
import shutil
import subprocess
import sys
from pathlib import Path

import edge_tts
from PIL import Image, ImageDraw, ImageFilter

PANEL = Path(__file__).parent
BRANDING = PANEL / "branding"
SAHNE_DIR = BRANDING / "trailer_sahneler"
SAHNE_DIR.mkdir(parents=True, exist_ok=True)

W, H = 1080, 1920

# 7 sahne — (üst_text, alt_text, palet [merkez_rgb, kenar_rgb], yildiz_sayi, sembol)
SAHNE = [
    {"ust": "WELCOME TO",      "alt": "COSMOBYTES",       "palet": [(60, 30, 120), (10, 5, 30)],   "yildiz": 220, "sembol": "🌌"},
    {"ust": "DAILY COSMIC",    "alt": "WONDER",           "palet": [(120, 40, 100), (15, 5, 35)],  "yildiz": 200, "sembol": "✨"},
    {"ust": "BLACK HOLES",     "alt": "BEND TIME",        "palet": [(80, 30, 150), (5, 0, 20)],    "yildiz": 250, "sembol": "⚫"},
    {"ust": "GALAXIES OLDER",  "alt": "THAN MEMORY",      "palet": [(40, 60, 140), (5, 10, 30)],   "yildiz": 280, "sembol": "🌀"},
    {"ust": "EXOPLANETS",      "alt": "TOO STRANGE",      "palet": [(150, 60, 40), (20, 5, 5)],    "yildiz": 180, "sembol": "🪐"},
    {"ust": "3 NEW SHORTS",    "alt": "EVERY DAY",        "palet": [(50, 100, 140), (5, 10, 30)],  "yildiz": 220, "sembol": "🚀"},
    {"ust": "HIT",             "alt": "SUBSCRIBE",        "palet": [(180, 50, 70), (20, 5, 10)],   "yildiz": 200, "sembol": "🔔"},
]

SCRIPT = """Welcome to CosmoBytes.

Your daily dose of cosmic wonder, in 30 seconds.

Black holes that bend time. Galaxies older than memory. Exoplanets too strange to imagine.

Three new shorts every day.

Hit subscribe. See you in the cosmos."""

SES = "en-US-AriaNeural"
HIZ = "-10%"
PERDE = "+3Hz"


def log(msg):
    print(f"[trailer] {msg}", flush=True)


def sahne_png_uret(i: int, cfg: dict) -> Path:
    """Tek sahne için 1080x1920 PNG üret — gradient + yıldız + sembol."""
    cikti = SAHNE_DIR / f"sahne_{i:02d}.png"
    merkez, kenar = cfg["palet"]
    img = Image.new("RGB", (W, H), kenar)
    px = img.load()

    # Radial gradient — merkezi parlak, kenarı koyu
    cx, cy = W // 2, int(H * 0.45)
    max_r = ((W // 2) ** 2 + (H // 2) ** 2) ** 0.5
    for y in range(H):
        for x in range(0, W, 4):  # 4'er piksel atlamayla hızlandır
            d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            t = min(d / max_r, 1.0)
            r = int(merkez[0] * (1 - t) + kenar[0] * t)
            g = int(merkez[1] * (1 - t) + kenar[1] * t)
            b = int(merkez[2] * (1 - t) + kenar[2] * t)
            for dx in range(4):
                if x + dx < W:
                    px[x + dx, y] = (r, g, b)

    # Yıldızlar — rastgele boyutta beyaz noktalar
    draw = ImageDraw.Draw(img)
    rng = random.Random(i * 1337)
    for _ in range(cfg["yildiz"]):
        x = rng.randint(0, W - 1)
        y = rng.randint(0, H - 1)
        boy = rng.choices([1, 2, 3, 4], weights=[60, 25, 10, 5])[0]
        parlaklik = rng.randint(160, 255)
        # Halo
        if boy >= 3:
            draw.ellipse([x - boy*2, y - boy*2, x + boy*2, y + boy*2], fill=(parlaklik//4, parlaklik//4, parlaklik//4))
        draw.ellipse([x - boy, y - boy, x + boy, y + boy], fill=(parlaklik, parlaklik, parlaklik))

    # Hafif blur — uzay sis efekti
    img = img.filter(ImageFilter.GaussianBlur(radius=0.5))

    # Sembol BÜYÜK ortada (üst orta) — emoji
    # Apple Color Emoji
    try:
        from PIL import ImageFont
        # Apple Color Emoji ttf
        font_emoji = ImageFont.truetype("/System/Library/Fonts/Apple Color Emoji.ttc", size=160)
        draw2 = ImageDraw.Draw(img)
        sembol = cfg["sembol"]
        # Text bbox
        bbox = draw2.textbbox((0, 0), sembol, font=font_emoji, embedded_color=True)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw2.text(((W - tw) // 2, int(H * 0.20)), sembol, font=font_emoji, embedded_color=True)
    except Exception as e:
        log(f"   ⚠ emoji çizilemedi: {e}")

    img.save(cikti, "PNG", optimize=True)
    return cikti


def sahne_video_yap(i: int, png: Path, ust_text: str, alt_text: str, sure: float, cikti: Path):
    """PNG → ken burns videoya çevir + ustte ust_text + altta alt_text."""
    fps = 30
    toplam_frame = int(sure * fps)
    safe_ust = ust_text.replace("'", "\\'")
    safe_alt = alt_text.replace("'", "\\'")

    vf = (
        f"scale=1080:1920,setsar=1,"
        f"zoompan=z='min(zoom+0.0008,1.10)':d={toplam_frame}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps={fps},"
        # Üst metin (sembol altı)
        f"drawtext=fontfile=/System/Library/Fonts/Helvetica.ttc:"
        f"text='{safe_ust}':fontcolor=white:fontsize=100:borderw=4:bordercolor=black@0.8:"
        f"x=(w-text_w)/2:y=h*0.50:"
        f"alpha='if(lt(t,0.3),t/0.3,if(gt(t,{sure-0.3}),({sure}-t)/0.3,1))',"
        # Alt metin
        f"drawtext=fontfile=/System/Library/Fonts/Helvetica.ttc:"
        f"text='{safe_alt}':fontcolor=white:fontsize=140:borderw=5:bordercolor=black@0.85:"
        f"x=(w-text_w)/2:y=h*0.62:"
        f"alpha='if(lt(t,0.5),(t-0.2)/0.3,if(gt(t,{sure-0.3}),({sure}-t)/0.3,1))',"
        "format=yuv420p"
    )
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(png),
        "-vf", vf,
        "-t", f"{sure:.2f}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-r", str(fps),
        str(cikti),
    ]
    sonuc = subprocess.run(cmd, capture_output=True)
    if sonuc.returncode != 0:
        sys.stderr.write(sonuc.stderr.decode()[-2000:])
        raise SystemExit(f"sahne {i} hata")


async def ses_uret(mp3_yol: Path):
    iletisim = edge_tts.Communicate(text=SCRIPT, voice=SES, rate=HIZ, pitch=PERDE)
    await iletisim.save(str(mp3_yol))


def ses_suresi(mp3: Path) -> float:
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", str(mp3)]
    return float(subprocess.check_output(cmd).decode().strip())


def sahneleri_birlestir(sahne_mp4: list, ses_mp3: Path, cikti: Path):
    liste = BRANDING / "trailer_concat.txt"
    liste.write_text("\n".join(f"file '{p.resolve()}'" for p in sahne_mp4))
    silent_v = BRANDING / "trailer_silent.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(liste),
         "-c", "copy", str(silent_v)],
        check=True, capture_output=True,
    )
    wav = ses_mp3.with_suffix(".wav")
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(ses_mp3), "-ar", "48000", "-ac", "2", str(wav)],
        check=True, capture_output=True,
    )
    cmd = [
        "ffmpeg", "-y",
        "-i", str(silent_v),
        "-i", str(wav),
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-shortest",
        str(cikti),
    ]
    sonuc = subprocess.run(cmd, capture_output=True)
    if sonuc.returncode != 0:
        sys.stderr.write(sonuc.stderr.decode()[-1500:])
        raise SystemExit(1)


def main():
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg yok")

    (BRANDING / "trailer.txt").write_text(SCRIPT, encoding="utf-8")

    log("1) Sahne PNG'leri üretiliyor...")
    png_yollari = []
    for i, cfg in enumerate(SAHNE):
        png = sahne_png_uret(i, cfg)
        log(f"   ✓ sahne {i+1}/{len(SAHNE)}: {cfg['ust']} {cfg['alt']}")
        png_yollari.append(png)

    log("2) Edge-TTS ses üretiliyor...")
    mp3 = BRANDING / "trailer.mp3"
    asyncio.run(ses_uret(mp3))
    toplam_ses = ses_suresi(mp3)
    log(f"   Ses süresi: {toplam_ses:.2f}sn")

    log("3) Sahne videoları üretiliyor...")
    pay = toplam_ses / len(SAHNE)
    sahne_mp4 = []
    for i, (cfg, png) in enumerate(zip(SAHNE, png_yollari)):
        cikti = SAHNE_DIR / f"sahne_{i:02d}.mp4"
        sahne_video_yap(i, png, cfg["ust"], cfg["alt"], pay, cikti)
        sahne_mp4.append(cikti)

    log("4) Birleştirme + ses mux...")
    final = BRANDING / "trailer.mp4"
    sahneleri_birlestir(sahne_mp4, mp3, final)

    # Geçici sahne dosyalarını sil (PNG + MP4)
    for p in png_yollari + sahne_mp4:
        p.unlink(missing_ok=True)
    (BRANDING / "trailer_silent.mp4").unlink(missing_ok=True)
    (BRANDING / "trailer_concat.txt").unlink(missing_ok=True)

    log("")
    log("=== ÖZET ===")
    log(f"  Video: {final}  ({toplam_ses:.1f}sn)")
    log(f"  Sonraki: python3 trailer_yukle.py")


if __name__ == "__main__":
    main()
