#!/usr/bin/env python3
"""
video_durum.py — Bir video'nun YouTube'daki tam durumunu çek.

Çağrılış: python video_durum.py oCJRwhyQMSQ
"""
import sys
import json
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


def main():
    if len(sys.argv) < 2:
        print("Kullanım: python video_durum.py <video_id>"); sys.exit(1)
    video_id = sys.argv[1]

    creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)

    r = yt.videos().list(
        part="snippet,status,statistics,contentDetails,suggestions,processingDetails,topicDetails",
        id=video_id,
    ).execute()

    if not r.get("items"):
        print(f"❌ Video bulunamadı veya erişim yok: {video_id}")
        sys.exit(2)

    v = r["items"][0]
    snippet = v.get("snippet", {})
    status = v.get("status", {})
    stats = v.get("statistics", {})
    suggestions = v.get("suggestions", {})
    processing = v.get("processingDetails", {})

    print(f"═══════ VIDEO DURUMU: {video_id} ═══════")
    print(f"Başlık: {snippet.get('title')}")
    print(f"Yüklendi: {snippet.get('publishedAt')}")
    print(f"Kanal: {snippet.get('channelTitle')}")
    print()
    print(f"── STATUS ──")
    print(f"  privacyStatus: {status.get('privacyStatus')}")
    print(f"  uploadStatus: {status.get('uploadStatus')}")
    print(f"  embeddable: {status.get('embeddable')}")
    print(f"  publicStatsViewable: {status.get('publicStatsViewable')}")
    print(f"  selfDeclaredMadeForKids: {status.get('selfDeclaredMadeForKids')}")
    print(f"  madeForKids: {status.get('madeForKids')}")
    if status.get('failureReason'):
        print(f"  ⚠️ failureReason: {status.get('failureReason')}")
    if status.get('rejectionReason'):
        print(f"  🚨 rejectionReason: {status.get('rejectionReason')}")
    print()
    print(f"── STATISTICS ──")
    print(f"  viewCount: {stats.get('viewCount')}")
    print(f"  likeCount: {stats.get('likeCount')}")
    print(f"  commentCount: {stats.get('commentCount')}")
    print()
    print(f"── PROCESSING ──")
    print(f"  processingStatus: {processing.get('processingStatus')}")
    if processing.get('processingFailureReason'):
        print(f"  🚨 processingFailureReason: {processing.get('processingFailureReason')}")
    print()
    if suggestions:
        print(f"── SUGGESTIONS (YouTube içerik önerileri) ──")
        for k, v_ in suggestions.items():
            if v_: print(f"  {k}: {v_}")
        print()

    # Tam JSON da yazdır (debug)
    print(f"═══════ FULL JSON ═══════")
    print(json.dumps(v, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
