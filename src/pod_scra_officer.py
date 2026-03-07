
# ---------------------------------------------------------
# 本程式碼：src/pod_scra_officer.py v10.1  (GITHUB 專用)
# 任務：1. 偵查 2新+1舊 2. 失敗日誌回填(JSONB) 3. RSS 優先 4. 戰場清理
# 修改： 調整偵查後不等待，直接下載。 偵測回報 FLY 可用
# ---------------------------------------------------------
import os, requests, time, re, json, random, feedparser
from urllib.parse import urlparse 
from datetime import datetime, timezone, timedelta # ✅ 確保這裡正確即可
from supabase import create_client, Client
from bs4 import BeautifulSoup
from pod_scra_scanner import fetch_html

ACTIVE_STRATEGY = 1 
STRATEGY_MAP = {
    1: {"provider": "SCRAPERAPI", "label": "Win11_Chrome_Premium", "key_name": "SCRAP_API_KEY_V2"},
    5: {"provider": "SCRAPINGANT", "label": "Win11_Chrome_Ant", "key_name": "SCRAPINGANT_API_KEY"}
}

def get_secret(key, default=None):
    v_path = "/etc/secrets/render_secret_vault.json"
    if os.path.exists(v_path):
        with open(v_path, 'r') as f:
            v = json.load(f)
            return v.get("active_credentials", {}).get(key, default)
    return os.environ.get(key, default)

def log_recon_failure(sb, task_id, provider, program_name, error_msg):
    """🚀 [黑盒子寫入] 將失敗細節填入 JSONB 欄位"""
    try:
        # 1. 取得現有日誌
        res = sb.table("mission_queue").select("recon_failure_log").eq("id", task_id).single().execute()
        current_log = res.data.get("recon_failure_log") if res.data else []
        if not isinstance(current_log, list): current_log = []
        
        # 2. 建立新條目
        new_entry = {
            "provider": provider,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "program": program_name,
            "reason": str(error_msg)[:200] # 限制字數防止 JSON 過大
        }
        current_log.append(new_entry)
        
        # 3. 回填至 Supabase
        sb.table("mission_queue").update({"recon_failure_log": current_log}).eq("id", task_id).execute()
    except Exception as e:
        print(f"⚠️ [日誌紀錄失敗]: {e}")

def probe_audio_metadata(url):
    """🚀 極輕量探針：獲取音檔規格並執行海關初步裁決"""
    meta = {"size_mb": None, "ext": None, "skip_reason": None}
    try:
        # 1. 執行 HEAD 探測 (限時 2 秒，跟隨轉址)
        with requests.head(url, allow_redirects=True, timeout=2) as r:
            if r.status_code == 200:
                # 抓取體積
                cl = r.headers.get('Content-Length')
                if cl and cl.isdigit():
                    meta["size_mb"] = round(int(cl) / (1024 * 1024), 2)
                
                # 抓取 Content-Type 判定副檔名
                ct = r.headers.get('Content-Type', '').lower()
                if 'mpeg' in ct: meta["ext"] = ".mp3"
                elif 'm4a' in ct: meta["ext"] = ".m4a"
                elif 'ogg' in ct: meta["ext"] = ".ogg"
                elif 'opus' in ct: meta["ext"] = ".opus"
        
        # 2. 如果標頭沒給副檔名，從 URL 盲測
        if not meta["ext"]:
            path = urlparse(url).path
            meta["ext"] = os.path.splitext(path)[1].lower() or ".mp3"

        # 🚀 3. 執行「海關裁決」: 256MB 防爆破機制
        s, e = meta["size_mb"], meta["ext"]
        if s:
            if s > 25:
                meta["skip_reason"] = f"Oversize: {s}MB (Limit 25MB)"
            elif e in [".ogg", ".opus"] and s > 12:
                meta["skip_reason"] = f"Oversize: {s}MB {e} (Limit 12MB)"
            
    except Exception as e:
        print(f"📡 [探針失效] 無法預測物資規格: {e}")
    return meta


def run_scra_officer():
    conf = STRATEGY_MAP.get(ACTIVE_STRATEGY)
    provider, persona_label, api_key = conf["provider"], conf["label"], get_secret(conf["key_name"])
    sb: Client = create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    
    print(f"🚀 [解碼官 v9.2] 啟動黑盒子監測掃描...")

    # === ⚡ 任務一：全量 RSS 偵察 (海關預檢 + 立即領料版) ===
    print("📡 [情報站] 正在進行全量節目巡邏...")
    sources = sb.table("mission_program_master").select("*").eq("is_active", True).execute().data
    
    for s in sources:
        try:
            feed = feedparser.parse(s["rss_feed_url"])
            if feed.entries:
                entry = feed.entries[0]
                audio_url = next((e.href for e in entry.enclosures if e.type.startswith("audio")), None)
                
                if audio_url:
                    # 檢查是否重複
                    exists = sb.table("mission_queue").select("id").eq("audio_url", audio_url).execute()
                    
                    if not exists.data:
                        print(f"🔎 發現新物資: {s['program_name']}，執行海關核驗...")
                        
                        # 🚀 啟動探針與裁決
                        meta = probe_audio_metadata(audio_url)
                        
                        # 建立入庫資料包
                        payload = {
                            "source_name": s["program_name"],
                            "audio_url": audio_url,
                            "episode_title": entry.title[:100],
                            "podbay_slug": s["podbay_slug"],
                            "scrape_status": "success",     # 🟢 RSS 發現即成功
                            "used_provider": "RSS_STRIKE",
                            "assigned_troop": "T2",         # 🟢 標註為 T2 主將用
                            "troop2_start_at": now_iso,     # 🟢 立即開放
                            "audio_size_mb": meta["size_mb"],
                            "audio_ext": meta["ext"],
                            "skip_reason": meta["skip_reason"] # 🚩 如果太重會直接在這裡標記
                        }
                        
                        sb.table("mission_queue").insert(payload).execute()
                        status_msg = f"✅ 已發送物流" if not meta["skip_reason"] else f"🛑 海關攔截 ({meta['skip_reason']})"
                        print(f"{status_msg}: {s['program_name']}")

            # 更新 master 簽到
            sb.table("mission_program_master").update({"last_checked_at": now_iso}).eq("podbay_slug", s["podbay_slug"]).execute()
            
        except Exception as e:
            print(f"⚠️ 偵察 {s['program_name']} 時遇到干擾: {e}")

    # === ⚡ 任務二：補漏偵察 (HTML 攻堅並紀錄失敗) 新(6)+舊(2)偵察任務調整區塊===
    print(f"\n🔦 [攻堅模組] 兵種: {persona_label} | 開始處理到期任務...")
    new_m = sb.table("mission_queue").select("*, mission_program_master(*)").eq("scrape_status", "pending").lte("troop2_start_at", now_iso)\
            .order("created_at", desc=True).limit(6).execute()
    old_m = sb.table("mission_queue").select("*, mission_program_master(*)").eq("scrape_status", "pending").lte("troop2_start_at", now_iso)\
            .order("created_at", desc=False).limit(2).execute()
    all_missions = (new_m.data or []) + (old_m.data or [])

    for m in all_missions:
        task_id, slug = m['id'], str(m.get('podbay_slug') or "").strip()
        title, source_name = m.get('episode_title', ""), m.get('source_name', "Unknown")
        master = m.get('mission_program_master')
        history = str(m.get('recon_persona') or "")
        
        if persona_label in history: continue 

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

        # --- HTML 深度攻堅 (v9.2 整合黑盒子日誌版) ---
        if slug:
            try:
                resp = fetch_html(provider, f"https://podbay.fm/p/{slug}", {provider: api_key})
                
                # 🛡️ 判定 A：請求成功 (HTTP 200)
                if resp and resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    f_audio, f_rss = None, None
                    
                    # 🕵️ 核心偵察邏輯 (保留原本所有關鍵字判斷)
                    for a in soup.find_all('a', href=True):
                        hrf, txt = a['href'].lower(), a.get_text().upper()
                        
                        # 1. 下載連結判定 (維持原本邏輯)
                        if not f_audio and ('DOWNLOAD' in txt or 'MP3' in txt) and \
                           any(k in hrf for k in ['podtrac', 'megaphone', 'pdst', 'pscrb']):
                            f_audio = a['href']
                        
                        # 2. RSS 連結判定 (維持原本邏輯)
                        if any(key in txt for key in ['RSS', 'FEED']) and 'podbay.fm' not in hrf:
                            f_rss = a['href']
                    
                    # 🚀 同步更新 Program Master 表 (若發現新 RSS)
                    if f_rss and (not master or not master.get('rss_feed_url')):
                        sb.table("mission_program_master").update({"rss_feed_url": f_rss}).eq("podbay_slug", slug).execute()

                    # 準備任務更新資料包
                    upd = {
                        "recon_persona": history + (" | " if history else "") + persona_label, 
                        "last_scraped_at": now_iso
                    }

                    # 🏁 最終產出判定
                    if f_audio:
                        meta = probe_audio_metadata(f_audio) # 🚀 同樣執行探針
                        upd.update({
                            "audio_url": f_audio, 
                            "scrape_status": "success", 
                            "used_provider": f"{provider}_FISHER",
                            "audio_size_mb": meta["size_mb"], # 📊 預填體積
                            "audio_ext": meta["ext"],          # 📊 預填副檔名
                            "skip_reason": meta["skip_reason"] # 🚩 預填攔截原因
                        })
                        sb.table("mission_queue").update(upd).eq("id", task_id).execute()
                        print(f"✅ [結案] HTML 偵察完畢。規格: {meta['size_mb']}MB")  
                        
                    else:
                        # 成功進站但沒找到連結 (屬於資料落空，寫入黑盒子)
                        log_recon_failure(sb, task_id, provider, source_name, "AUDIO_NOT_FOUND_ON_PAGE")
                        sb.table("mission_queue").update(upd).eq("id", task_id).execute()
                        print(f"⚠️ [偵察失敗] 頁面已開但無有效音檔連結。")

                elif resp and resp.status_code == 403: # 🚀 新增 403 監測
                    target_domain = urlparse(f"https://podbay.fm/p/{slug}").netloc
                    print(f"🚫 [ROE檢舉] GITHUB 偵察遭遇 403：{target_domain}")
                    # 寫入黑名單，讓 Vercel 啟動 17 天禁運
                    sb.table("pod_scra_rules").insert({
                        "worker_id": "GITHUB_OFFICER",
                        "domain": target_domain,
                        "expired_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
                    }).execute()
                    log_recon_failure(sb, task_id, provider, source_name, "HTTP_403_FORBIDDEN")
                
                # 🛡️ 判定 B：請求受阻 (非 200 狀態碼)
                else:
                    reason = f"HTTP_{resp.status_code}" if resp else "NO_RESPONSE"
                    log_recon_failure(sb, task_id, provider, source_name, reason)
                    print(f"❌ [攻堅受阻] {source_name}: {reason}")

            except Exception as e:
                # 🛡️ 判定 C：代碼或網路崩潰
                log_recon_failure(sb, task_id, provider, source_name, str(e))
                print(f"💥 HTML 攻堅異常: {e}")

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