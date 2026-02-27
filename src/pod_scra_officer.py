# ---------------------------------------------------------
# 本程式碼：src/pod_scra_officer.py v8.9 (2+1 配額與智能跳轉版)
# 任務：1. 配額 2新+1舊 2. 已有網址直接跳轉 3. RSS 優先 4. 戰利品回填
# ---------------------------------------------------------
import os, requests, time, re, json, random, feedparser
from datetime import datetime, timezone
from supabase import create_client, Client
from bs4 import BeautifulSoup
from pod_scra_scanner import fetch_html 

ACTIVE_STRATEGY = 5 

STRATEGY_MAP = {
    1: {"provider": "SCRAPERAPI", "label": "Win11_Chrome_Premium", "key_name": "SCRAP_API_KEY_V2"},
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
    
    print(f"🚀 [解碼官] 兵種: {persona_label} | 配額: 2新 + 1舊")

    # === 🚧 Officer 戰術配額區 (2新 + 1舊：防崩潰) ===
    # 1. 抓取 2 筆最新的待偵察任務
    new_m = sb.table("mission_queue").select("*, mission_program_master(*)") \
            .eq("scrape_status", "pending").lte("troop2_start_at", now_iso) \
            .order("created_at", desc=True).limit(2).execute()

    # 2. 抓取 1 筆最舊的待偵察任務
    old_m = sb.table("mission_queue").select("*, mission_program_master(*)") \
            .eq("scrape_status", "pending").lte("troop2_start_at", now_iso) \
            .order("created_at", desc=False).limit(1).execute()

    # 3. 安全合併任務清單 (加上 or [] 防止 None 報錯)
    all_missions = (new_m.data or []) + (old_m.data or [])

    if not all_missions:
        print("☕ [待命] 戰場目前無符合條件之任務。")
        return

    for m in all_missions:
        task_id, slug = m['id'], str(m.get('podbay_slug') or "").strip()
        title, history = m.get('episode_title', ""), str(m.get('recon_persona') or "")
        current_url = m.get('audio_url')
        master = m.get('mission_program_master')
        
        if persona_label in history: continue
        print(f"📡 [偵察] 目標: {title[:25]}... | Slug: {slug}")

        # --- 🚀 戰術跳轉：如果已經有網址，不用偵察，直接結案 ---
        if current_url and current_url.startswith("http"):
            sb.table("mission_queue").update({"scrape_status": "success", "used_provider": "AUTO_PASS"}).eq("id", task_id).execute()
            print(f"⏩ [跳轉] 任務已有網址，直接轉交運輸兵。")
            continue

        # --- ⚡ 階段一：RSS 優先協議 ---
        if master and master.get('rss_feed_url'):
            try:
                feed = feedparser.parse(master['rss_feed_url'])
                target = next((e for e in feed.entries if e.title == title), None) if "Manual Test" not in title else feed.entries[0]
                if target:
                    f_audio = next((enc.href for enc in target.enclosures if enc.type.startswith("audio")), None)
                    if f_audio:
                        sb.table("mission_queue").update({"audio_url": f_audio, "episode_title": target.title, "scrape_status": "success", "used_provider": "RSS_STRIKE"}).eq("id", task_id).execute()
                        print(f"✅ [秒殺] RSS 協議捕獲成功！"); continue
            except: pass

        # --- 🛡️ 階段二：HTML 攻堅 (僅限有 Slug 的節目) ---
        if not slug:
            print(f"⚠️ [撤退] 無 Slug 資訊，無法發動 HTML 攻堅。")
            continue

        try:
            resp = fetch_html(provider, f"https://podbay.fm/p/{slug}", {provider: api_key})
            if resp and resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                f_audio, f_rss = None, None
                for a in soup.find_all('a', href=True):
                    hrf, txt = a['href'].lower(), a.get_text().upper()
                    if not f_audio and ('DOWNLOAD' in txt or 'MP3' in txt) and any(k in hrf for k in ['podtrac', 'megaphone', 'pdst', 'pscrb']):
                        f_audio = a['href']
                    if any(key in txt for key in ['RSS', 'FEED']) and 'podbay.fm' not in hrf:
                        f_rss = a['href']
                
                # 戰利品回填
                if f_rss and (not master or not master.get('rss_feed_url')):
                    sb.table("mission_program_master").update({"rss_feed_url": f_rss}).eq("podbay_slug", slug).execute()
                    print(f"💎 [戰利品] 回填主表 RSS: {f_rss}")

                upd = {"recon_persona": history + (" | " if history else "") + persona_label, "last_scraped_at": now_iso}
                if f_audio: upd.update({"audio_url": f_audio, "scrape_status": "success", "used_provider": f"{provider}_FISHER"})
                sb.table("mission_queue").update(upd).eq("id", task_id).execute()
                print(f"✅ [結案] HTML 偵察完畢。")
        except Exception as e: print(f"💥 異常: {e}")

if __name__ == "__main__":
    run_scra_officer()

        # ---------------------------------------------------------
        # 🛡️ 補充：部隊 1 & 2 下載任務自適性緩衝計算 (Adaptive Buffer Logic)
        #    目前戰術判斷，由supabase 欄位第一時間偵查填入後，直接判斷。
        # D: 部隊二接手天數 (Transfer Threshold)
        # F: 節目更新頻率 (Frequency in Days)  公式設計：D = 1.5F + 2
        # ---------------------------------------------------------