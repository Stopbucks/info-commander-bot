# ---------------------------------------------------------
# 本程式碼：src/pod_scra_officer.py v9.0 
# 任務：1. 配額 2新+1舊 2. 有網址直接抓 3. RSS 優先 4. 戰利品回填 5.清理supabase 6.重新偵查
# ---------------------------------------------------------
import os, requests, time, re, json, random, feedparser
from datetime import datetime, timezone, timedelta # 🚀 修正：補上 timedelta
from supabase import create_client, Client
from bs4 import BeautifulSoup
from pod_scra_scanner import fetch_html 

ACTIVE_STRATEGY = 5 
STRATEGY_MAP = {
    1: {"provider": "SCRAPERAPI", "label": "Win11_Chrome_Premium", "key_name": "SCRAP_API_KEY_V2"},
    5: {"provider": "SCRAPINGANT", "label": "Win11_Chrome_Ant", "key_name": "SCRAPINGANT_API_KEY"}
}

def get_secret(key, default=None):
    # 支援 Render Vault 與 GitHub Secrets 雙環境
    v_path = "/etc/secrets/render_secret_vault.json"
    if os.path.exists(v_path):
        with open(v_path, 'r') as f:
            v = json.load(f)
            return v.get("active_credentials", {}).get(key, default)
    return os.environ.get(key, default)

def run_scra_officer():
    conf = STRATEGY_MAP.get(ACTIVE_STRATEGY)
    provider, persona_label, api_key = conf["provider"], conf["label"], get_secret(conf["key_name"])
    sb: Client = create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat() # 🚀 修正：定義 now_iso 供回填使用
    
    print(f"🚀 [解碼官 v9.0] 啟動系統掃描...")

    # =========================================================
    # ⚡ 任務一：全量 RSS 偵察 (智慧延時計算)
    # =========================================================
    print("📡 [情報站] 正在進行全量節目巡邏...")
    sources = sb.table("mission_program_master").select("*").eq("is_active", True).execute().data
    
    for s in sources:
        try:
            feed = feedparser.parse(s["rss_feed_url"])
            if feed.entries:
                entry = feed.entries[0]
                audio_url = next((e.href for e in entry.enclosures if e.type.startswith("audio")), None)
                
                if audio_url:
                    exists = sb.table("mission_queue").select("id").eq("audio_url", audio_url).execute()
                    if not exists.data:
                        # 🚀 [計算智慧延時]：1.5 * freq + 2
                        freq = float(s.get("update_frequency_days") or 1)
                        delay_days = (freq * 1.5) + 2
                        fire_time = now + timedelta(days=delay_days)
                        
                        sb.table("mission_queue").insert({
                            "source_name": s["program_name"],
                            "audio_url": audio_url,
                            "episode_title": entry.title[:100],
                            "podbay_slug": s["podbay_slug"],
                            "scrape_status": "pending",
                            "troop2_start_at": fire_time.isoformat()
                        }).execute()
                        print(f"✅ 發現新集數: {s['program_name']} | 預定 {delay_days:.1f} 天後開火")
            
            sb.table("mission_program_master").update({"last_checked_at": now_iso}).eq("podbay_slug", s["podbay_slug"]).execute()
        except Exception as e:
            print(f"⚠️ 偵察 {s['program_name']} 時遇到干擾: {e}")

    # =========================================================
    # ⚡ 任務二：補漏偵察 (原本的 2新 + 1舊 HTML 攻堅)
    # =========================================================
    print(f"\n🔦 [攻堅模組] 兵種: {persona_label} | 開始處理到期任務...")
    
    # 修正：加上 LTE 判斷，只抓「已到開火時間」的任務
    new_m = sb.table("mission_queue").select("*, mission_program_master(*)").eq("scrape_status", "pending").lte("troop2_start_at", now_iso)\
            .order("created_at", desc=True).limit(2).execute()      # ⚡新任務筆數
    old_m = sb.table("mission_queue").select("*, mission_program_master(*)").eq("scrape_status", "pending").lte("troop2_start_at", now_iso)\
            .order("created_at", desc=False).limit(1).execute()     # ⚡舊任務筆數
    all_missions = (new_m.data or []) + (old_m.data or [])

    for m in all_missions:
        task_id, slug = m['id'], str(m.get('podbay_slug') or "").strip()
        title, current_url = m.get('episode_title', ""), m.get('audio_url')
        master = m.get('mission_program_master') # 🚀 修正：定義 master
        history = str(m.get('recon_persona') or "") # 🚀 修正：定義 history
        
        if persona_label in history: continue # 已執行過則跳過

        # --- 戰術跳轉：已有網址直接轉成功 ---
        if current_url and current_url.startswith("http"):
            sb.table("mission_queue").update({"scrape_status": "success", "used_provider": "AUTO_PASS"}).eq("id", task_id).execute()
            print(f"⏩ [跳轉] {title[:20]} 已有資料，直接結案。")
            continue

        # --- RSS 優先協議 ---
        if master and master.get('rss_feed_url'):
            try:
                feed = feedparser.parse(master['rss_feed_url'])
                target = next((e for e in feed.entries if e.title == title), None)
                if target:
                    f_audio = next((enc.href for enc in target.enclosures if enc.type.startswith("audio")), None)
                    if f_audio:
                        sb.table("mission_queue").update({"audio_url": f_audio, "scrape_status": "success", "used_provider": "RSS_STRIKE"}).eq("id", task_id).execute()
                        print(f"✅ [秒殺] RSS 協議捕獲成功！"); continue
            except: pass

        # --- HTML 深度攻堅 ---
        if slug:
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
                    
                    if f_rss and (not master or not master.get('rss_feed_url')):
                        sb.table("mission_program_master").update({"rss_feed_url": f_rss}).eq("podbay_slug", slug).execute()

                    upd = {"recon_persona": history + (" | " if history else "") + persona_label, "last_scraped_at": now_iso}
                    if f_audio: upd.update({"audio_url": f_audio, "scrape_status": "success", "used_provider": f"{provider}_FISHER"})
                    sb.table("mission_queue").update(upd).eq("id", task_id).execute()
                    print(f"✅ [結案] HTML 偵察完畢。")
            except Exception as e: print(f"💥 HTML 攻堅異常: {e}")

    # =========================================================
    # ⚡ 任務五：Supabase 倉庫清理 (17 天舊物資)
    # =========================================================
    print("\n🧹 [清理員] 啟動戰場掃除...")
    try:
        seventeen_days_ago = (now - timedelta(days=17)).isoformat()
        sb.table("mission_queue").delete().lt("created_at", seventeen_days_ago).execute()
        print("✅ 清理完成：17天前的舊任務已移除。")
    except Exception as e:
        print(f"⚠️ 清理失敗: {e}")

if __name__ == "__main__":
    run_scra_officer()

        # ---------------------------------------------------------
        # 🛡️ 補充：部隊 1 & 2 下載任務自適性緩衝計算 (Adaptive Buffer Logic)
        #    目前戰術判斷，由supabase 欄位第一時間偵查填入後，直接判斷。
        # D: 部隊二接手天數 (Transfer Threshold)
        # F: 節目更新頻率 (Frequency in Days)  公式設計：D = 1.5F + 2
        # ---------------------------------------------------------