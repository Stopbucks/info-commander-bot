# ---------------------------------------------------------
# 本程式碼：src/pod_scra_officer.py v8.4 (分級補位版)
# 任務：1-5 兵種切換、4天緩衝判定、RSS優先、分級補位
# ---------------------------------------------------------
import os, requests, time, re, json, random
from datetime import datetime, timezone, timedelta
from supabase import create_client, Client
from bs4 import BeautifulSoup
from pod_scra_scanner import fetch_html 

# === 🛠️ 偵察控制面板 (策略中樞) ===
# 1=SCRAPERAPI, 2=WEBSCRAPING, 3=SCRAPEDO, 4=HASDATA, 5=SCRAPINGANT
ACTIVE_STRATEGY = 1  # 👈 [修改此數字即可更換全套兵種]

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

    # === 🚧 戰術注意區：調整任務領取配額 (小螢幕括號排版) ===
    # 領取邏輯：由 mission_queue 聯表 mission_program_master 獲取 wait_days
    # -------------------------------------------------------
    new_m = (sb.table("mission_queue")
             .select("*, mission_program_master(*)")
             .eq("scrape_status", "pending")
             .order("created_at", desc=True)
             .limit(1)    # 👈 [新任務配額]
             .execute())

    old_m = (sb.table("mission_queue")
             .select("*, mission_program_master(*)")
             .eq("scrape_status", "pending")
             .order("created_at", desc=False)
             .limit(1)    # 👈 [舊任務配額]
             .execute())
    # ========================================================
    
    all_missions = new_m.data + old_m.data
    now_utc = datetime.now(timezone.utc)

    for idx, mission in enumerate(all_missions):
        task_id = mission['id']
        podbay_slug = str(mission.get('podbay_slug') or "").strip()
        history = str(mission.get('recon_persona') or "")
        current_count = (mission.get('scrape_count') or 0) + 1
        
        # 🛡️ 戰術判定 A：檢查 3-4 天緩衝期 (禮讓部隊一)
        master_data = mission.get('mission_program_master')
        wait_days = master_data.get('wait_days', 0) if master_data else 0
        pub_date = datetime.fromisoformat(mission['pub_date'].replace('Z', '+00:00'))
        
        if now_utc < (pub_date + timedelta(days=wait_days)):
            print(f"🕒 [靜默等待] {podbay_slug} 尚在部隊一負責期 ({wait_days}天)，部隊二不介入。")
            continue

        # 🛡️ 戰術判定 B：履歷章制度 (避免重複無效點數)
        if persona_label in history:
            print(f"⏭️ [跳過] {persona_label} 曾偵察過 {podbay_slug}，等待輪替。"); continue

        print(f"📡 [偵察 {idx+1}/{len(all_missions)}] 正在攻堅 {podbay_slug}...")

        # 🚀 執行偵察行為 (優先嘗試從 RSS/官網/Podbay 提取)
        try:
            # 優先檢查是否已有 master RSS 可直接使用 (不需要再掃描網頁)
            final_audio_url = None
            if master_data and master_data.get('rss_feed_url'):
                # 這裡未來可擴充 RSS 解析邏輯，目前我們先標註已掌握 RSS
                print(f"🔑 [情報優勢] 已掌握該節目 RSS: {master_data['rss_feed_url']}")
            
            # 若無直接連結，啟動對位掃描
            resp = fetch_html(provider, f"https://podbay.fm/p/{podbay_slug}", {provider: api_key})
            if resp and resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                final_rss_url = None

                # 1. 地毯搜索：音檔連結 (<a> -> Meta -> Regex)
                for a in soup.find_all('a', href=True):
                    href, txt = a['href'].lower(), a.get_text().upper()
                    if ('DOWNLOAD' in txt or 'MP3' in txt) and any(k in href for k in ['podtrac', 'megaphone', 'pdst', 'pscrb', 'akamaized']):
                        final_audio_url = a['href']; break
                
                if not final_audio_url:
                    meta = soup.find('meta', property=re.compile(r'(og:audio|twitter:player:stream)'))
                    final_audio_url = meta.get('content') if meta else None

                # 2. 地毯搜索：RSS FEED 連結 (若主表沒有，順手牽羊抓回來)
                if not master_data or not master_data.get('rss_feed_url'):
                    rss_tag = soup.find('link', type='application/rss+xml', href=True)
                    final_rss_url = rss_tag['href'] if rss_tag else None
                    if not final_rss_url:
                        for a in soup.find_all('a', href=True):
                            if 'RSS' in a.get_text().upper(): final_rss_url = a['href']; break

                # --- 數據歸檔 ---
                now_iso = datetime.now(timezone.utc).isoformat()
                updated_history = history + (" | " if history else "") + persona_label
                update_data = {"recon_persona": updated_history, "last_scraped_at": now_iso, "scrape_count": current_count}
                
                if final_audio_url:
                    update_data.update({"audio_url": final_audio_url, "scrape_status": "success", "used_provider": f"{provider}_{persona_label}"})
                    if final_rss_url: update_data["podbay_url"] = final_rss_url
                    print(f"✅ [大捷] 已獲取連結。")
                else:
                    sb.table("mission_queue").update(update_data).eq("id", task_id).execute()
                    print(f"🔎 [蓋章] 偵察完成但無網址。")
            else:
                print(f"⚠️ [連線受阻] 狀態碼: {resp.status_code if resp else 'N/A'}")
        except Exception as e:
            print(f"💥 異常: {e}")

        if idx < len(all_missions) - 1: time.sleep(random.randint(30, 60))

if __name__ == "__main__":
    run_scra_officer()