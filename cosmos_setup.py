"""
cosmos_setup.py — Luna Verhaaltjes → CosmoBytes tek seferlik dönüşüm.

Quota yenilenmesi sonrası (TR 03:00 UTC 00:00 sonrası) çalıştırılır:
    python3 cosmos_setup.py

Yaptıkları (YouTube Data API):
  1. Kanal adı: Luna Verhaaltjes → CosmoBytes
  2. Açıklama (SEO optimize, branding doc'tan)
  3. Banner upload (branding/banner.png) + kanal'a bağla
  4. Eski Hollandaca videoyu PRIVATE yap

YAPILAMAYAN (YouTube API kısıtlaması):
  - Profil avatar (sadece Studio'dan, elle)
  - Handle değişikliği (sadece Studio'dan, elle)
"""
import sys
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

PANEL_KOK = Path(__file__).parent
SCOPES = ["https://www.googleapis.com/auth/youtube",
          "https://www.googleapis.com/auth/youtube.force-ssl"]
CHANNEL_ID = "UC_rWMx7nuPiLIvZKTSVpX6Q"

ACIKLAMA = """🌌 Daily astronomy & cosmic wonder shorts in 30 seconds.

CosmoBytes brings you the most mind-blowing facts about black holes, galaxies, exoplanets, neutron stars, and the strange physics of the cosmos — all in bite-sized 30-second Shorts.

🚀 Fresh cosmic facts uploaded 3 times daily.
🪐 Designed for the curious mind, the wanderer, the dreamer.

For more cosmic discoveries → subscribe.

Business inquiries: emreceylan55555@gmail.com"""


def main():
    creds = Credentials.from_authorized_user_file(str(PANEL_KOK / "token.json"), SCOPES)
    if creds.expired and creds.refresh_token: creds.refresh(Request())
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)

    print("=" * 60)
    print("LUNA VERHAALTJES → COSMOBYTES dönüşümü")
    print("=" * 60)

    # 1. Kanal adı + açıklama + keywords
    print("\n[1/4] Kanal adı + açıklama...")
    try:
        yt.channels().update(
            part="brandingSettings",
            body={
                "id": CHANNEL_ID,
                "brandingSettings": {
                    "channel": {
                        "title": "CosmoBytes",
                        "description": ACIKLAMA,
                        "keywords": 'space astronomy cosmos universe science blackhole galaxy planet exoplanet nebula nasa hubble jwst spacefacts astrofacts cosmology shorts didyouknow',
                        "defaultLanguage": "en",
                        "country": "US",
                    }
                }
            }
        ).execute()
        print("   ✓ Kanal adı + açıklama + keywords güncellendi")
    except Exception as h:
        print(f"   ✗ {str(h)[:300]}")

    # 2. Banner upload
    print("\n[2/4] Banner upload (2048×1152)...")
    try:
        banner = (PANEL_KOK / "branding" / "banner.png")
        if not banner.exists():
            print(f"   ✗ {banner} yok"); banner_url = None
        else:
            r = yt.channelBanners().insert(
                media_body=MediaFileUpload(str(banner), mimetype="image/png", resumable=True)
            ).execute()
            banner_url = r["url"]
            print(f"   ✓ Banner upload: {banner_url[:70]}...")

        # 3. Banner kanal'a bağla
        if banner_url:
            print("\n[3/4] Banner kanal'a bağla...")
            yt.channels().update(
                part="brandingSettings",
                body={
                    "id": CHANNEL_ID,
                    "brandingSettings": {"image": {"bannerExternalUrl": banner_url}}
                }
            ).execute()
            print("   ✓ Banner aktif")
    except Exception as h:
        print(f"   ✗ {str(h)[:300]}")

    # 4. Eski Hollandaca video PRIVATE
    print("\n[4/4] Eski Hollandaca video PRIVATE...")
    try:
        ch = yt.channels().list(part="contentDetails", id=CHANNEL_ID).execute()
        uploads = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        pl = yt.playlistItems().list(part="contentDetails,snippet", playlistId=uploads, maxResults=20).execute()
        for it in pl.get("items", []):
            vid = it["contentDetails"]["videoId"]
            title = it["snippet"]["title"]
            # Sadece Hollandaca eski içerik
            if any(k in title for k in ["Snorharen", "Kapitein", "Pips", "Dromerige"]):
                yt.videos().update(
                    part="status",
                    body={"id": vid, "status": {"privacyStatus": "private"}}
                ).execute()
                print(f"   ✓ '{title[:60]}' → PRIVATE")
    except Exception as h:
        print(f"   ✗ {str(h)[:300]}")

    # SONUÇ
    print("\n" + "=" * 60)
    print("SONUÇ — Kanal mevcut durumu:")
    try:
        ch = yt.channels().list(part="snippet,brandingSettings,statistics", id=CHANNEL_ID).execute()
        c = ch["items"][0]
        print(f"   Ad:       {c['snippet']['title']}")
        print(f"   Handle:   {c['snippet'].get('customUrl','?')}")
        print(f"   Abone:    {c['statistics'].get('subscriberCount')}")
        print(f"   Video:    {c['statistics'].get('videoCount')}")
        print(f"   Banner:   {c.get('brandingSettings',{}).get('image',{}).get('bannerExternalUrl','—')[:80]}")
    except Exception as h:
        print(f"   ✗ {str(h)[:300]}")
    print("=" * 60)
    print("\n📝 Emre Bey'in yapacağı (Studio'da elle, 1 dk):")
    print("   1. Profil avatar: branding/profile.png yükle (API'de yok)")
    print("   2. Handle: @cosmobytes (API'de yok)")
    print("   3. Settings → Audience → 'No, not made for kids'")


if __name__ == "__main__":
    sys.exit(main() or 0)
