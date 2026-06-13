"""
oauth_kurulum.py — CosmoBytes ilk OAuth flow.

Tek seferlik çalıştırılır. client_secret.json'dan başlayarak Google'da
CosmoBytes kanalını seçtirir, sonra 3 scope'lu token.json yazar.

Kullanım:
    1. CosmoBytes Google hesabına Chrome'da login ol
    2. Bu repo'ya client_secret.json kopyala (TrendCatcher'dakiyle aynı,
       çünkü AYNI Google Cloud Project)
    3. python3 oauth_kurulum.py
    4. Tarayıcı açılır → CosmoBytes hesabını seç → "İzin ver" tıkla
    5. token.json oluşur — bu içeriği GitHub Secrets > TOKEN_JSON'a yapıştır

SCOPES:
    - youtube              (upload + delete + thumbnail)
    - yt-analytics.readonly (retention, CTR)
    - youtube.force-ssl    (caption + comment)
"""
import sys
from pathlib import Path

PANEL_KOK = Path(__file__).parent
CLIENT_SECRET = PANEL_KOK / "client_secret.json"
TOKEN_DOSYASI = PANEL_KOK / "token.json"

SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


def main() -> int:
    from google_auth_oauthlib.flow import InstalledAppFlow

    if not CLIENT_SECRET.exists():
        print(f"❌ {CLIENT_SECRET} yok")
        print(f"\nÇözüm: TrendCatcher repo'sundan client_secret.json'u buraya kopyala.")
        print(f"  cp ../denetleme_paneli/client_secret.json .")
        return 1

    print(f"🌐 Tarayıcı açılıyor — CosmoBytes Google hesabı + 3 izin onayı bekleniyor:")
    for s in SCOPES:
        print(f"  - {s.split('/')[-1]}")
    print()

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
    creds = flow.run_local_server(
        port=0,
        prompt="consent",
        access_type="offline",
        open_browser=True,
    )

    TOKEN_DOSYASI.write_text(creds.to_json(), encoding="utf-8")
    print(f"\n✅ Token kaydedildi: {TOKEN_DOSYASI.name}")
    print(f"\n📋 Scope kontrolü:")
    for s in creds.scopes or []:
        print(f"     ✓ {s}")

    # Canlı test — kanal bilgisi
    print(f"\n📺 Kanal bilgisi çekiliyor...")
    try:
        from googleapiclient.discovery import build
        yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
        ch = yt.channels().list(part="snippet,statistics", mine=True).execute()
        if ch.get("items"):
            c = ch["items"][0]
            print(f"  Kanal: {c['snippet']['title']}")
            print(f"  Handle: {c['snippet'].get('customUrl','—')}")
            print(f"  Abone: {c['statistics'].get('subscriberCount','?')}")
            print(f"  Video: {c['statistics'].get('videoCount','?')}")
        else:
            print(f"  ⚠️ Kanal bulunamadı")
    except Exception as h:
        print(f"  ✗ Test fail: {h}")

    print(f"\n📦 GitHub Secrets güncelle:")
    print(f"  gh secret set TOKEN_JSON < token.json -R emreceylan1986-hub/m-r-cosmos-shorts")
    print(f"  gh secret set CLIENT_SECRET_JSON < client_secret.json -R emreceylan1986-hub/m-r-cosmos-shorts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
