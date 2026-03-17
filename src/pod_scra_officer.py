# ---------------------------------------------------------
# 本程式碼：src/pod_scra_officer.py v10.2  (GITHUB 專用)
# 任務：1. 偵查 6新+2舊 2. 失敗日誌回填(JSONB) 3. RSS 優先 4. 戰場清理
# [v10.2 升級] 1. 自動啟動留白的節目 (is_active 補齊)
# [v10.2 升級] 2. RSS 絕對霸權：有 RSS 則絕對不走 HTML，失敗直接寫入日誌。
# [v10.2 升級] 3. 攔截無效 Slug：遇到空值或純數字 Slug 拒絕出兵，阻絕 404 資源浪費。
# [戰術調整] 擴編偵察裝備庫 (1~5號)，切換至 2 號裝備，並將偵察火力提升至 6新+2舊。
# [戰術校準] 動態兵力指派：依據節目的 wait_days 設定，大於 0 天交由 T1 處理，否則由 T2 即時打擊。
# [黃金沉澱] T1 任務自動推遲 troop2_start_at 開火時間，完美實現 T1 延遲與 T2 即時的雙軌分流。
# ---------------------------------------------------------
import os, requests, time, re, json, random, feedparser
from urllib.parse import urlparse 
from datetime import datetime, timezone, timedelta 
from supabase import create_client, Client
from bs4 import BeautifulSoup
from pod_scra_scanner import fetch_html

# =========================================================
# 🎯 [戰術裝備庫] HTML 攻堅破防 API 配置表 (USAGE)
# 1. SCRAPERAPI  : [主力部隊] 強制開啟渲染與高級住宅代理。(⚠️目前額度已耗盡)
# 2. WEBSCRAPING : [轉運專員] 強化轉址處理。擁有豐沛偵察點數，每月自動回補。(👉 目前啟用)
# 3. SCRAPEDO    : [備援破城槌] 快速渲染衝鋒，輕量且快速的突擊武力。
# 4. HASDATA     : [特種部隊] 最強住宅代理，專攻 Cloudflare 高防禦目標。
# 5. SCRAPINGANT : [通用步兵] 穩定渲染，常規備用軍力，中規中矩。
# =========================================================
ACTIVE_STRATEGY = 3 
STRATEGY_MAP = {
    1: {"provider": "SCRAPERAPI", "label": "Win11_Chrome_Premium", "key_name": "SCRAP_API_KEY_V2"},
    2: {"provider": "WEBSCRAPING", "label": "Win11_Chrome_WebScraping", "key_name": "WEBSCRAPING_API_KEY"},
    3: {"provider": "SCRAPEDO", "label": "Win11_Chrome_ScrapeDo", "key_name": "SCRAPEDO_API_KEY"},
    4: {"provider": "HASDATA", "label": "Win11_Chrome_HasData", "key_name": "HASDATA_API_KEY"},
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
        res = sb.table("mission_queue").select("recon_failure_log").eq("id", task_id).single().execute()
        current_log = res.data.get("recon_failure_log") if res.data else []
        if not isinstance(current_log, list): current_log = []
        
        new_entry = {
            "provider": provider,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "program": program_name,
            "reason": str(error_msg)[:200] 
        }
        current_log.append(new_entry)
        sb.table("mission_queue").update({"recon_failure_log": current_log}).eq("id", task_id).execute()
    except Exception as e:
        print(f"⚠️ [日誌紀錄失敗]: {e}")

def probe_audio_metadata(url):
    """🚀 極輕量探針：獲取音檔規格並執行海關初步裁決"""
    meta = {"size_mb": None, "ext": None, "skip_reason": None}
    try:
        with requests.head(url, allow_redirects=True, timeout=2) as r:
            if r.status_code == 200:
                cl = r.headers.get('Content-Length')
                if cl and cl.isdigit():
                    meta["size_mb"] = round(int(cl) / (1024 * 1024), 2)
                
                ct = r.headers.get('Content-Type', '').lower()
                if 'mpeg' in ct: meta["ext"] = ".mp3"
                elif 'm4a' in ct: meta["ext"] = ".m4a"
                elif 'ogg' in ct: meta["ext"] = ".ogg"
                elif 'opus' in ct: meta["ext"] = ".opus"
        
        if not meta["ext"]:
            path = urlparse(url).path
            meta["ext"] = os.path.splitext(path)[1].lower() or ".mp3"

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
    
    print(f"🚀 [解碼官 v10.2] 啟動黑盒子監測掃描... 目前啟用戰術: {ACTIVE_STRATEGY} ({provider})")

    # 🧹 [自動防呆] 掃描留白的 is_active 並自動啟用
    try:
        sb.table("mission_program_master").update({"is_active": True}).is_("is_active", "null").execute()
    except: pass

    # === ⚡ 任務一：全量 RSS 偵察 (海關預檢 + 立即領料版) ===
    print("📡 [情報站] 正在進行全量節目巡邏...")
    sources = sb.table("mission_program_master").select("*").eq("is_active", True).execute().data
    
    for s in sources:
        if not s.get("rss_feed_url"): continue

        try:
            feed = feedparser.parse(s["rss_feed_url"])
            if feed.entries:
                entry = feed.entries[0]
                audio_url = next((e.href for e in entry.enclosures if e.type.startswith("audio")), None)
                
                if audio_url:
                    exists = sb.table("mission_queue").select("id").eq("audio_url", audio_url).execute()
                    
                    if not exists.data:
                        print(f"🔎 發現新物資: {s['program_name']}，執行海關核驗...")
                        meta = probe_audio_metadata(audio_url)
                        
                        # 🚀 [戰略校準] 計算精準的部隊開火時間與標籤
                        wait_days = s.get("wait_days") or 0
                        t2_start = (now + timedelta(days=wait_days)).isoformat()
                        assigned = "T1" if wait_days > 0 else "T2"

                        payload = {
                            "source_name": s["program_name"],
                            "audio_url": audio_url,
                            "episode_title": entry.title[:100],
                            "podbay_slug": s.get("podbay_slug"), 
                            "scrape_status": "success",     
                            "used_provider": "RSS_STRIKE",
                            "assigned_troop": assigned,     # 👈 動態指派 T1 或 T2
                            "troop2_start_at": t2_start,    # 👈 加上等待天數的未來時間
                            "audio_size_mb": meta["size_mb"],
                            "audio_ext": meta["ext"],
                            "skip_reason": meta["skip_reason"] 
                        }
                        
                        sb.table("mission_queue").insert(payload).execute()
                        status_msg = f"✅ 已發送物流" if not meta["skip_reason"] else f"🛑 海關攔截 ({meta['skip_reason']})"
                        print(f"{status_msg}: {s['program_name']}")

            sb.table("mission_program_master").update({"last_checked_at": now_iso}).eq("podbay_slug", s["podbay_slug"]).execute()
            
        except Exception as e:
            print(f"⚠️ 偵察 {s['program_name']} 時遇到干擾: {e}")


    # === ⚡ 任務二：補漏偵察 (HTML 攻堅並紀錄失敗) ===
    print(f"\n🔦 [攻堅模組] 兵種: {persona_label} | 開始處理到期任務...")
    
    # 🔍 [偵察數量設定]：6 筆新任務 + 2 筆舊任務 (因點數豐沛，恢復第一線高強度偵察)
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

        has_rss = bool(master and master.get('rss_feed_url'))
        
        # --- 🛡️ 絕對防線：RSS 優先協議 ---
        if has_rss:
            try:
                feed = feedparser.parse(master['rss_feed_url'])
                target = next((e for e in feed.entries if e.title == title), None)
                if target:
                    f_audio = next((enc.href for enc in target.enclosures if enc.type.startswith("audio")), None)
                    if f_audio:
                        sb.table("mission_queue").update({"audio_url": f_audio, "scrape_status": "success", "used_provider": "RSS_STRIKE"}).eq("id", task_id).execute()
                        print(f"✅ [秒殺] RSS 協議捕獲成功！")
                        continue
                
                log_recon_failure(sb, task_id, "RSS_STRIKE", source_name, "RSS_ENTRY_NOT_FOUND")
                print(f"⚠️ [RSS 落空] {source_name} - {title[:20]}... 禁止降級至 HTML 攻堅。")
            except Exception as e:
                log_recon_failure(sb, task_id, "RSS_STRIKE", source_name, f"RSS_PARSE_ERROR")
            
            # 🚀 只要有填 RSS，無論成功失敗，絕對禁止走 HTML 攻堅！直接跳下一個任務。
            upd = {"recon_persona": history + (" | " if history else "") + "RSS_ONLY", "last_scraped_at": now_iso}
            sb.table("mission_queue").update(upd).eq("id", task_id).execute()
            continue

        # --- 🚧 攔截無效 Slug ---
        is_valid_slug = bool(slug and slug.lower() != "null" and not slug.isdigit())
        if not is_valid_slug:
            reason = f"INVALID_OR_EMPTY_SLUG: '{slug}'"
            log_recon_failure(sb, task_id, provider, source_name, reason)
            print(f"🚫 [攔截] {source_name} 無有效 Slug (空值或純數字)，拒絕 HTML 攻堅以防 404。")
            upd = {"recon_persona": history + (" | " if history else "") + "INVALID_SLUG", "last_scraped_at": now_iso}
            sb.table("mission_queue").update(upd).eq("id", task_id).execute()
            continue

        # --- ⚔️ HTML 深度攻堅 (僅限無 RSS 且有合法 Slug 的節目) ---
        try:
            resp = fetch_html(provider, f"https://podbay.fm/p/{slug}", {provider: api_key})
            
            if resp and resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                f_audio, f_rss = None, None
                
                for a in soup.find_all('a', href=True):
                    hrf, txt = a['href'].lower(), a.get_text().upper()
                    if not f_audio and ('DOWNLOAD' in txt or 'MP3' in txt) and \
                        any(k in hrf for k in ['podtrac', 'megaphone', 'pdst', 'pscrb']):
                        f_audio = a['href']
                    if any(key in txt for key in ['RSS', 'FEED']) and 'podbay.fm' not in hrf:
                        f_rss = a['href']
                
                if f_rss and (not master or not master.get('rss_feed_url')):
                    sb.table("mission_program_master").update({"rss_feed_url": f_rss}).eq("podbay_slug", slug).execute()

                upd = {"recon_persona": history + (" | " if history else "") + persona_label, "last_scraped_at": now_iso}

                if f_audio:
                    meta = probe_audio_metadata(f_audio) 
                    
                    # 🚀 [戰略校準] HTML 攻堅也必須遵守等待天數規則
                    wait_days = master.get("wait_days") if master else 0
                    t2_start = (now + timedelta(days=wait_days)).isoformat()
                    assigned = "T1" if wait_days > 0 else "T2"

                    upd.update({
                        "audio_url": f_audio, 
                        "scrape_status": "success", 
                        "used_provider": f"{provider}_FISHER",
                        "assigned_troop": assigned,         # 👈 動態指派 T1 或 T2
                        "troop2_start_at": t2_start,        # 👈 加上等待天數的未來時間
                        "audio_size_mb": meta["size_mb"], 
                        "audio_ext": meta["ext"],          
                        "skip_reason": meta["skip_reason"] 
                    })
                    sb.table("mission_queue").update(upd).eq("id", task_id).execute()
                    print(f"✅ [結案] HTML 偵察完畢。指派: {assigned} | 規格: {meta['size_mb']}MB")
                else:
                    log_recon_failure(sb, task_id, provider, source_name, "AUDIO_NOT_FOUND_ON_PAGE")
                    sb.table("mission_queue").update(upd).eq("id", task_id).execute()
                    print(f"⚠️ [偵察失敗] 頁面已開但無有效音檔連結。")

            elif resp and resp.status_code == 403: 
                target_domain = urlparse(f"https://podbay.fm/p/{slug}").netloc
                print(f"🚫 [ROE檢舉] GITHUB 偵察遭遇 403：{target_domain}")
                sb.table("pod_scra_rules").insert({
                    "worker_id": "GITHUB_OFFICER", "domain": target_domain,
                    "expired_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
                }).execute()
                log_recon_failure(sb, task_id, provider, source_name, "HTTP_403_FORBIDDEN")
            
            else:
                reason = f"HTTP_{resp.status_code}" if resp else "NO_RESPONSE"
                log_recon_failure(sb, task_id, provider, source_name, reason)
                print(f"❌ [攻堅受阻] {source_name}: {reason}")

        except Exception as e:
            log_recon_failure(sb, task_id, provider, source_name, str(e))
            print(f"💥 HTML 攻堅異常: {e}")

    # =========================================================
    # ⚡ 任務五：Supabase 資料庫垃圾清運 (17 天舊物資紀錄)
    # [評估結論] 必須保留！R2 清理的是「實體音檔」，此處清理的是「資料庫文字紀錄」。
    # 若不清理，mission_queue 會無限膨脹拖垮查詢效能。
    # =========================================================
    print("\n🧹 [清理員] 啟動戰場掃除...")
    try:
        seventeen_days_ago = (now - timedelta(days=17)).isoformat()
        sb.table("mission_queue").delete().lt("created_at", seventeen_days_ago).execute()
        print("✅ 清理完成：17天前的舊任務紀錄已自資料庫移除。")
    except Exception as e:
        print(f"⚠️ 清理失敗: {e}")

if __name__ == "__main__":
    run_scra_officer()