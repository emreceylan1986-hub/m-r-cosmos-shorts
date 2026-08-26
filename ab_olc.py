#!/usr/bin/env python3
"""
ab_olc.py — G6 KIYAS KAPISI A/B ÖLÇÜMÜ (23 Ağu 2026).

Neden var: 11 Ağu'da G6 kapısı "kıyaslı başlıklar 1.74x izleniyor" ölçümüne
dayanarak konuldu. Ama o ölçüm, kıyaslı başlıkların YALNIZ %12 olduğu dönemde
yapılmıştı — yani kıyas o zaman FARKLI olmanın bir yoluydu. 15 Ağu'da kapı %100
uygulanır olunca hem farklılık kayboldu hem de KONTROL GRUBU yok oldu; aynı hafta
kanal izlenmesi -%70 düştü. Sebep-sonuç ancak eşzamanlı kontrol koluyla ölçülür.

Ne yapar: yuklemeler.json'daki `kiyas_kapisi` etiketine göre iki kolu ayırır
(GECTI = kapı açık · AB_KAPISIZ = kontrol), izlenmeleri YAYIN SAATİNE normalize
eder (saat etkisi bu kanalda 2-3 kat) ve permütasyon testiyle p değeri üretir.

Kullanım:  python ab_olc.py [--gun 7] [--asgari-yas 3]
"""
import argparse
import datetime as dt
import json
import random
import re
import statistics as st
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

KOK = Path(__file__).parent


def _servisler():
    c = Credentials.from_authorized_user_file(str(KOK / "token.json"))
    if c.expired and c.refresh_token:
        c.refresh(Request())
    return (build("youtube", "v3", credentials=c, cache_discovery=False),
            build("youtubeAnalytics", "v2", credentials=c, cache_discovery=False))


# 26 Ağu: A/B SIFIRLANDI. 23-25 Ağu'daki kontrol kolu gerçek kontrol değildi —
# "kıyas serbest ama zorunlu değil" demek yetmemiş, o kolun başlıklarının %83'ünde
# yine kıyas kalıbı çıkmıştı (kapılı kolda %100). O kontrastla hiçbir şey ölçülemezdi.
# Kıyas artık kontrol kolunda YASAK ve kapıyla zorlanıyor; ölçüm bu tarihten başlar.
AB_BASLANGIC = "2026-08-26"


def _kol(etiket: str) -> str | None:
    e = str(etiket or "")
    if e.startswith("AB_KAPISIZ_KIRLI"):
        return None   # 3 denemede temizlenemedi → kontrol sayılmaz, ölçüme girmez
    if e.startswith("AB_KAPISIZ"):
        return "KAPISIZ"
    if e == "GECTI" or e.startswith("RED:"):
        return "KAPILI"   # RED de kapılı kolun parçası: kapı denendi, geçemedi
    return None           # OLCULMEDI / A/B öncesi kayıtlar ölçüme girmez


def permutasyon(a: list, b: list, tur: int = 20000) -> float:
    """İki kolun medyan farkı için iki yönlü p değeri."""
    gercek = abs(st.median(a) - st.median(b))
    hepsi = a + b
    n = len(a)
    rnd = random.Random(20260823)
    buyuk = 0
    for _ in range(tur):
        rnd.shuffle(hepsi)
        if abs(st.median(hepsi[:n]) - st.median(hepsi[n:])) >= gercek:
            buyuk += 1
    return buyuk / tur


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gun", type=int, default=14, help="kaç günlük pencere")
    ap.add_argument("--asgari-yas", type=int, default=3, help="video en az kaç günlük olmalı")
    a = ap.parse_args()

    yt, ya = _servisler()
    kayitlar = json.loads((KOK / "yuklemeler.json").read_text(encoding="utf-8"))
    simdi = dt.datetime.now(dt.timezone.utc)
    esik_yeni = max((simdi - dt.timedelta(days=a.gun)).strftime("%Y-%m-%d"), AB_BASLANGIC)

    aday = {}
    for k in kayitlar:
        kol = _kol(k.get("kiyas_kapisi"))
        vid = k.get("video_id")
        if kol and vid and str(k.get("zaman", ""))[:10] >= esik_yeni:
            aday[vid] = kol
    if not aday:
        print(f"A/B kaydı yok — ölçüm {AB_BASLANGIC} tarihinden başlıyor, "
              f"kol başına 3 olgun video birikmesini bekle.")
        return 0

    idler = list(aday)
    bilgi = {}
    for i in range(0, len(idler), 50):
        for v in yt.videos().list(part="snippet,status,contentDetails",
                                  id=",".join(idler[i:i + 50])).execute()["items"]:
            m = re.match(r"PT(?:(\d+)M)?(?:(\d+)S)?", v["contentDetails"]["duration"])
            bilgi[v["id"]] = {
                "pub": v["snippet"]["publishedAt"],
                "sn": (int(m.group(1) or 0) * 60 + int(m.group(2) or 0)) if m else 0,
                "gizli": v["status"]["privacyStatus"],
                "baslik": v["snippet"]["title"]}
    r = ya.reports().query(ids="channel==MINE",
                           startDate=(simdi - dt.timedelta(days=a.gun + 2)).strftime("%Y-%m-%d"),
                           endDate=simdi.strftime("%Y-%m-%d"), metrics="views",
                           dimensions="video", sort="-views", maxResults=200).execute()
    izl = {x[0]: x[1] for x in r.get("rows", [])}

    kol_veri = {"KAPILI": [], "KAPISIZ": []}
    saat_havuz = {}
    secili = []
    for vid, kol in aday.items():
        b = bilgi.get(vid)
        if not b or b["gizli"] != "public" or b["sn"] > 180:
            continue
        yas = (simdi - dt.datetime.fromisoformat(b["pub"].replace("Z", "+00:00"))).days
        if yas < a.asgari_yas:
            continue
        secili.append((vid, kol, b, izl.get(vid, 0)))
        saat_havuz.setdefault(b["pub"][11:13], []).append(izl.get(vid, 0))

    if len(secili) < 6:
        print(f"Henüz {len(secili)} olgun A/B videosu var — güvenilir ölçüm için en az 6 "
              f"(kol başına 3) gerekir. Birkaç gün daha bekle.")
        for vid, kol, b, v in sorted(secili, key=lambda x: x[2]["pub"]):
            print(f"   {b['pub'][:16]} {kol:8s} izl={v:5d} {b['baslik'][:50]}")
        return 0

    saat_medyan = {h: st.median(l) for h, l in saat_havuz.items()}
    genel = st.median([v for _, _, _, v in secili]) or 1
    for vid, kol, b, v in secili:
        taban = saat_medyan.get(b["pub"][11:13]) or genel
        kol_veri[kol].append(v / (taban or 1))   # saate normalize edilmiş izlenme

    print(f"G6 KIYAS KAPISI A/B — son {a.gun} gün, {len(secili)} olgun video\n")
    for kol, l in kol_veri.items():
        if l:
            ham = [v for _, k, _, v in secili if k == kol]
            print(f"  {kol:8s} n={len(l):2d} · ham medyan izlenme {st.median(ham):6.0f} "
                  f"· saate-normalize medyan {st.median(l):.2f}")
    if kol_veri["KAPILI"] and kol_veri["KAPISIZ"] and min(map(len, kol_veri.values())) >= 3:
        p = permutasyon(kol_veri["KAPILI"], kol_veri["KAPISIZ"])
        fark = st.median(kol_veri["KAPISIZ"]) - st.median(kol_veri["KAPILI"])
        print(f"\n  permütasyon p = {p:.4f}  (20.000 tur, iki yönlü)")
        asgari = min(map(len, kol_veri.values()))
        if p < 0.05:
            kazanan = "KAPISIZ (G6 sert şartı ZARARLI → kapıyı KALDIR)" if fark > 0 else \
                      "KAPILI (G6 faydalı → kapı KALSIN)"
            print(f"  🔴 ANLAMLI FARK → {kazanan}")
            _karar_yaz(f"KARAR: {kazanan}", kol_veri, secili, p)
        elif asgari >= 10:
            # Kol başına 10+ videoya rağmen fark yoksa bu da bir sonuçtur:
            # kapı izlenmeyi açıklamıyor, sert şart bedava kısıt demektir.
            print("  ⚪ Kol başına 10+ video, fark YOK → kapı izlenmeyi AÇIKLAMIYOR. "
                  "Sert şart bedava kısıt; çöküşün sebebi başka yerde.")
            _karar_yaz("KARAR: fark yok — G6 sert şartı izlenmeyi açıklamıyor",
                       kol_veri, secili, p)
        else:
            print(f"  ⏳ Henüz karar yok (kol başına en az {asgari} video, "
                  f"anlamlılık için ya p<0,05 ya da kol başına 10 video gerekir).")
    return 0


def _karar_yaz(baslik, kol_veri, secili, p):
    """Bekçi workflow'u bu dosyayı görürse issue açar — karar kimseye bağlı kalmaz."""
    sat = [f"## {baslik}", "",
           f"Permütasyon p = **{p:.4f}** (20.000 tur, yayın saatine normalize).", ""]
    for kol, l in kol_veri.items():
        ham = [v for _, k, _, v in secili if k == kol]
        if l:
            sat.append(f"- **{kol}** n={len(l)} · ham medyan izlenme {st.median(ham):.0f} "
                       f"· normalize medyan {st.median(l):.2f}")
    sat += ["", "### Ne yapılacak",
            "- KAPISIZ kazandıysa: `yukleyici.METADATA_SISTEM_PROMPTU` içindeki "
            "`HARD REQUIREMENT (G6)` bloğu ve `haberci._baslik_kapisi` kaldırılır, "
            "`_ab_kolu` da silinir (G7 muğlak-sıfat yasağı KALIR).",
            "- KAPILI kazandıysa: A/B kapatılır, kapı %100'e döner ve çöküşün sebebi "
            "bekçi raporundaki kırılma penceresinde aranır.",
            "- Fark yoksa: sert şart kaldırılır (bedava kısıt), sebep aramaya devam.", "",
            "*Bu issue `ab_olc.py` tarafından otomatik açıldı.*"]
    Path(KOK / ".ab_karar").write_text("\n".join(sat), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
