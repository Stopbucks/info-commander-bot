import os
import json
import feedparser
from datetime import datetime, timezone
from supabase import create_client, Client
from email.utils import parsedate_to_datetime

class CloudScout:
    def __init__(self):
        # 從 Secrets 載入 Supabase 憑證
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        self.supabase: Client = create_client(url, key)
        self.sources = self._load_sources()

    def _load_sources(self):
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "podcast_sources.json")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def scan_all_feeds(self):
        """核心偵察邏輯：掃描所有頻道並掛號新任務"""
        print(f"📡 [偵察啟動] 時間: {datetime.now(timezone.utc)}")
        
        for source in self.sources:
            print(f"🔍 掃描頻道: {source['name']}")
            feed = feedparser.parse(source["url"])
            
            if feed.bozo:
                print(f"  ❌ RSS 解析失敗: {source['name']}")
                continue

            # 遍歷最近的 3 集 (避免遺漏)
            for entry in feed.entries[:3]:
                audio_url = next((enc.href for enc in entry.enclosures if enc.type.startswith("audio")), "")
                if not audio_url: continue

                # 🚀 [核心變革]：檢查此網址是否已在 Supabase 任務表中
                exists = self.supabase.table("global_missions")\
                    .select("id")\
                    .eq("audio_url", audio_url)\
                    .execute()

                if not exists.data:
                    # 若不存在，則執行「雲端掛號」
                    self._register_mission(source, entry, audio_url)
                else:
                    print(f"  ✅ 已存在，跳過: {entry.title[:20]}...")

    def _register_mission(self, source, entry, audio_url):
        """將新發現的任務寫入 Supabase"""
        data = {
            "source_name": source["name"],
            "audio_url": audio_url,
            "status": "pending",
            "mission_type": "scout_found",
            "added_at": datetime.now(timezone.utc).isoformat()
        }
        res = self.supabase.table("global_missions").insert(data).execute()
        if res.data:
            print(f"  📌 [掛號成功] 新任務: {source['name']} - {entry.title[:20]}")

if __name__ == "__main__":
    scout = CloudScout()
    scout.scan_all_feeds()