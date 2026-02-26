# ---------------------------------------------------------
# 本程式碼：src/pod_scra_officer.py v8.8 (全域採集最終版)
# 任務：1. RSS 優先秒殺 2. Manual Test 特殊處理 3. HTML 關鍵字獵殺 4. 戰利品自動歸庫
# ---------------------------------------------------------
import os, requests, time, re, json, random, feedparser
from datetime import datetime, timezone
from supabase import create_client, Client
from bs4 import BeautifulSoup
from pod_scra_scanner import fetch_html 

# === 🛠️ 偵察控制面板 ===
ACTIVE_STRATEGY = 5  # 👈 指揮官可隨時切換 [1=Premium, 5=Ant]

STRATEGY_MAP = {
    1: {"provider": "SCRAPERAPI", "label": "Win11_Chrome_Premium", "key_name": "SCRAP_API_KEY_V2"},
    2: {"provider": "WEBSCRAPING", "label": "WebScraping_AI_JS", "key_name": "WEBSCRAP_API_KEY"},
    3: {"provider": "SCRAPEDO", "label": "ScrapeDo_Render_Ops", "key_name": "SCRAPEDO_API_KEY"},
    4: {"provider": "HASDATA", "label": "HasData_Residential", "key_name": "HASDATA_API_KEY"},
    5: {"provider": "SCRAPINGANT", "label": "Win11_Chrome_Ant", "key_name": "SCRAPINGANT_API_KEY"}
}

def get_secret(key, default=None):
    v_path = "/etc/secrets/render_secret_vault.json"
    if os.path.exists(v_path):
        with open(v_path, 'r') as f:
            v = json.load(f); return v.get("active_credentials", {}).get(key, default)
    return os.environ.get(key, default)

def run_scra_officer():
    conf = STRATEGY_MAP.get(ACTIVE_STRATEGY)
    provider, persona_label, api_key = conf["provider"], conf["label"], get_secret(conf["key_name"])
    sb = create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))
    now_iso = datetime.now(timezone.utc).isoformat()
    
    print(f"🚀 [解碼官出擊] 兵種: {persona_label} | 目標: 領取已過期之緩衝任務")

    # 🚧 聯表查詢任務 (帶入主表 RSS 資訊，對位 rss_feed_url 欄位)
    mission_res = (sb.table("mission_queue").select("*, mission_program_master(*)")
                 .eq("scrape_status", "pending")
                 .lte("troop2_start_at", now_iso)
                 .order("created_at", desc=True).limit(2).execute())
    
    if not mission_res.data:
        print("☕ [待命] 戰場目前無符合條件之任務。")
        return

    for m in mission_res.data:
        task_id, slug = m['id'], str(m.get('podbay_slug') or "").strip()
        title, history = m.get('episode_title', ""), str(m.get('recon_persona') or "")
        master = m.get('mission_program_master')
        
        # 🛡️ 履歷章制度：跳過失敗過的兵種
        if persona_label in history: continue
        print(f"📡 [偵察] 攻堅 {slug} | 目標: {title[:30]}...")

        # --- ⚡ 階段一：情報優勢 (RSS 優先協議) ---
        if master and master.get('rss_feed_url'):
            print(f"🔑 [情報優勢] 發現 RSS 連結，嘗試直接解鎖...")
            try:
                feed = feedparser.parse(master['rss_feed_url'])
                target_entry = None
                
                # 🧪 處理 Manual Test 標題（人造靶標特殊邏輯）
                if "Manual Test" in title:
                    target_entry = feed.entries[0] if feed.entries else None
                    print(f"🧪 [實驗室] 偵測到模擬任務，自動導向 RSS 最新集數。")
                else:
                    # 正常匹配標題
                    target_entry = next((e for e in feed.entries if e.title == title), None)

                if target_entry:
                    f_audio = next((enc.href for enc in target_entry.enclosures if enc.type.startswith("audio")), None)
                    if f_audio:
                        upd_data = {
                            "audio_url": f_audio, 
                            "episode_title": target_entry.title, # 覆蓋人造標題為真實標題
                            "scrape_status": "success", 
                            "used_provider": "RSS_STRIKE",
                            "last_scraped_at": now_iso
                        }
                        sb.table("mission_queue").update(upd_data).eq("id", task_id).execute()
                        print(f"✅ [秒殺] RSS 協議直接捕獲成功！")
                        continue # 直接進入下一個任務
            except Exception as rss_err:
                print(f"⚠️ RSS 協議解析中斷: {rss_err}")

        # --- 🛡️ 階段二：HTML 攻堅與戰利品收集 (漁翁得利模式) ---
        try:
            resp = fetch_html(provider, f"https://podbay.fm/p/{slug}", {provider: api_key})
            if resp and resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                f_audio, f_rss = None, None
                
                # 🛠️ [戰利品關鍵字]：尋找 RSS Pass
                rss_keywords = ['RSS', 'FEED', 'XML', 'SUBSCRIBE', 'PODCAST FEED']
                
                for a in soup.find_all('a', href=True):
                    hrf, txt = a['href'].lower(), a.get_text().upper()
                    
                    # 1. 尋找音檔下載點
                    if not f_audio and ('DOWNLOAD' in txt or 'MP3' in txt) and any(k in hrf for k in ['podtrac', 'megaphone', 'pdst', 'pscrb', 'akamaized']):
                        f_audio = a['href']
                    
                    # 2. 🚀 [順手牽羊] 尋找 RSS 戰利品 (回填主表)
                    if any(key in txt or key in hrf.upper() for key in rss_keywords):
                        if 'podbay.fm' not in hrf and hrf.startswith('http'): # 排除站內連結
                            f_rss = a['href']
                
                # 嘗試從 meta link 抓取標準 RSS
                rtag = soup.find('link', type='application/rss+xml', href=True)
                if rtag: f_rss = rtag['href']

                # 🚀 [戰利品歸庫]：若發現新 RSS 且主表原本為空，自動更新主表
                if f_rss and (not master or not master.get('rss_feed_url')):
                    sb.table("mission_program_master").update({"rss_feed_url": f_rss}).eq("podbay_slug", slug).execute()
                    print(f"💎 [戰利品] 發現隱藏 RSS，已自動歸庫主表：{f_rss}")

                # 結案回填任務表
                updated_history = history + (" | " if history else "") + persona_label
                upd = {"recon_persona": updated_history, "last_scraped_at": now_iso, "scrape_count": (m.get('scrape_count') or 0) + 1}
                
                if f_audio:
                    upd.update({"audio_url": f_audio, "scrape_status": "success", "used_provider": f"{provider}_FISHER"})
                    print(f"✅ [成功] HTML 掃描攻堅完成。")
                else:
                    print(f"🔎 [蓋章] 無標籤章。")
                
                sb.table("mission_queue").update(upd).eq("id", task_id).execute()
        except Exception as e:
            print(f"💥 攻堅異常: {e}")

if __name__ == "__main__":
    run_scra_officer()

        # ---------------------------------------------------------
        # 🛡️ 補充：部隊 1 & 2 下載任務自適性緩衝計算 (Adaptive Buffer Logic)
        #    目前戰術判斷，由supabase 欄位第一時間偵查填入後，直接判斷。
        # D: 部隊二接手天數 (Transfer Threshold)
        # F: 節目更新頻率 (Frequency in Days)  公式設計：D = 1.5F + 2
        # ---------------------------------------------------------