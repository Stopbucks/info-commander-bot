
# ---------------------------------------------------------
# 本程式碼：src/pod_scra_officer.py v8.5 (自適性調度版)
# 任務：1-5 兵種切換、1.5F+2 自適性緩衝、頻率學習更新
# ---------------------------------------------------------
import os, requests, time, re, json, random, math
from datetime import datetime, timezone, timedelta
from supabase import create_client, Client
from bs4 import BeautifulSoup
from pod_scra_scanner import fetch_html 

# === 🛠️ 偵察控制面板 (策略中樞) ===
ACTIVE_STRATEGY = 1  # 👈 [1=Premium, 5=Ant]

STRATEGY_MAP = {
    1: {"provider": "SCRAPERAPI", "label": "Win11_Chrome_Premium", "key_name": "SCRAP_API_KEY_V2"},
    2: {"provider": "WEBSCRAPING", "label": "WebScraping_AI_JS", "key_name": "WEBSCRAP_API_KEY"},
    3: {"provider": "SCRAPEDO", "label": "ScrapeDo_Render_Ops", "key_name": "SCRAPEDO_API_KEY"},
    4: {"provider": "HASDATA", "label": "HasData_Residential", "key_name": "HASDATA_API_KEY"},
    5: {"provider": "SCRAPINGANT", "label": "Win11_Chrome_Ant", "key_name": "SCRAPINGANT_API_KEY"}
}
# =========================

def get_secret(key, default=None):
    vault_path = "/etc/secrets/render_secret_vault.json"
    if os.path.exists(vault_path):
        with open(vault_path, 'r') as f:
            vault = json.load(f); return vault.get("active_credentials", {}).get(key, default)
    return os.environ.get(key, default)

def run_scra_officer():
    conf = STRATEGY_MAP.get(ACTIVE_STRATEGY)
    provider, persona_label, api_key = conf["provider"], conf["label"], get_secret(conf["key_name"])
    sb = create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))
    
    print(f"🚀 [行動啟動] 策略: {ACTIVE_STRATEGY} | 兵種: {persona_label}")

    # === 🚧 戰術配額區 (小螢幕括號法) ===
    # 聯表查詢：從 mission_program_master 獲取更新頻率與預設權限
    new_m = (sb.table("mission_queue")
             .select("*, mission_program_master(*)")
             .eq("scrape_status", "pending")
             .order("created_at", desc=True)
             .limit(1).execute())

    old_m = (sb.table("mission_queue")
             .select("*, mission_program_master(*)")
             .eq("scrape_status", "pending")
             .order("created_at", desc=False)
             .limit(1).execute())
    # ===================================
    
    all_missions = new_m.data + old_m.data
    now_utc = datetime.now(timezone.utc)

    for idx, mission in enumerate(all_missions):
        task_id, podbay_slug, history = mission['id'], str(mission.get('podbay_slug') or "").strip(), str(mission.get('recon_persona') or "")
        current_count = (mission.get('scrape_count') or 0) + 1
        master = mission.get('mission_program_master')
        pub_date = datetime.fromisoformat(mission['pub_date'].replace('Z', '+00:00'))

        # ---------------------------------------------------------
        # 🛡️ 戰術判定：自適性緩衝計算 (Adaptive Buffer Logic)
        # 公式設計：D = 1.5F + 2
        # D: 部隊二接手天數 (Transfer Threshold)
        # F: 節目更新頻率 (Frequency in Days)
        # ---------------------------------------------------------
        # 若主表 wait_days 設為 0，代表 11-18 號目標，部隊二即刻接手
        if master and master.get('wait_days') == 0:
            threshold_days = 0
        else:
            freq = master.get('update_frequency_days', 1) if master else 1
            threshold_days = math.ceil(1.5 * freq + 2) # 👈 [工程師驚嘆點：線性擴張法]
        
        if now_utc < (pub_date + timedelta(days=threshold_days)):
            print(f"🕒 [緩衝期] {podbay_slug} (F:{freq}D -> 門檻:{threshold_days}D) 由部隊一防守中。")
            continue

        # 🛡️ 履歷重複性檢查
        if persona_label in history:
            print(f"⏭️ [跳過] {persona_label} 曾失敗過，待輪替。"); continue

        print(f"📡 [偵察 {idx+1}/{len(all_missions)}] 攻堅 {podbay_slug}...")

        try:
            # 🚀 學習模組：更新該節目的頻率資訊 (若有上集發布紀錄)
            if master and master.get('last_pub_date'):
                last_pub = datetime.fromisoformat(master['last_pub_date'].replace('Z', '+00:00'))
                if pub_date > last_pub:
                    new_freq = (pub_date - last_pub).days
                    if new_freq > 0:
                        sb.table("mission_program_master").update({"update_frequency_days": new_freq, "last_pub_date": pub_date.isoformat()}).eq("podbay_slug", podbay_slug).execute()
                        print(f"📈 [學習] 偵測到頻率變動，已更新 F={new_freq}")

            # 🚀 偵察行為執行 (優先檢查 RSS，再進行網頁地毯掃描)
            final_audio_url = None
            if master and master.get('rss_feed_url'):
                print(f"🔑 [情報優勢] 使用已存 RSS 下載路徑。")

            resp = fetch_html(provider, f"https://podbay.fm/p/{podbay_slug}", {provider: api_key})
            if resp and resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                final_rss_url = None

                # 解析：音檔網址
                for a in soup.find_all('a', href=True):
                    href, txt = a['href'].lower(), a.get_text().upper()
                    if ('DOWNLOAD' in txt or 'MP3' in txt) and any(k in href for k in ['podtrac', 'megaphone', 'pdst', 'pscrb', 'akamaized']):
                        final_audio_url = a['href']; break
                
                # 解析：RSS FEED (若主表未紀錄，自動補全)
                if not master or not master.get('rss_feed_url'):
                    rtag = soup.find('link', type='application/rss+xml', href=True)
                    final_rss_url = rtag['href'] if rtag else None

                # 數據歸檔與履歷蓋章
                updated_history = history + (" | " if history else "") + persona_label
                upd = {"recon_persona": updated_history, "last_scraped_at": now_utc.isoformat(), "scrape_count": current_count}
                
                if final_audio_url:
                    upd.update({"audio_url": final_audio_url, "scrape_status": "success", "used_provider": f"{provider}_{persona_label}"})
                    if final_rss_url: upd["podbay_url"] = final_rss_url # 標記以便後續回填 master
                    print(f"✅ [大捷] 成功獲取網址。")
                else:
                    sb.table("mission_queue").update(upd).eq("id", task_id).execute()
                    print(f"🔎 [蓋章] 渲染成功但無標籤。")
            else:
                print(f"⚠️ [受阻] 狀態碼: {resp.status_code if resp else 'N/A'}")
        except Exception as e:
            print(f"💥 異常: {e}")

        if idx < len(all_missions) - 1: time.sleep(random.randint(30, 60))

if __name__ == "__main__":
    run_scra_officer()