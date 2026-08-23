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


def _kol(etiket: str) -> str | None:
    e = str(etiket or "")
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
    esik_yeni = (simdi - dt.timedelta(days=a.gun)).strftime("%Y-%m-%d")

    aday = {}
    for k in kayitlar:
        kol = _kol(k.get("kiyas_kapisi"))
        vid = k.get("video_id")
        if kol and vid and str(k.get("zaman", ""))[:10] >= esik_yeni:
            aday[vid] = kol
    if not aday:
        print("A/B kaydı yok — kapı A/B'si 23 Ağu'da başladı, en az 3 gün bekle.")
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
        if p < 0.05:
            kazanan = "KAPISIZ (G6 sert şartı ZARARLI → kaldır)" if fark > 0 else \
                      "KAPILI (G6 faydalı → kapı kalsın)"
            print(f"  🔴 ANLAMLI FARK → {kazanan}")
        else:
            print("  ⚪ Fark anlamlı değil. Kapı izlenmeyi AÇIKLAMIYOR → çöküşün sebebi "
                  "başka yerde; bekçi raporundaki kırılma penceresine bak.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
