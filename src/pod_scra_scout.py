# ---------------------------------------------------------
# 本程式碼：src/pod_scra_scout.py v1.1  (隱蔽斥候特遣隊)
# 任務：1. 智慧 RSS 巡邏 2. 深度 HTML 攻堅 3. 輕量探針 (HEAD) 4. DB 寫入避震
# [v1.0 誕生] 1. 職責分離：承接原 Officer 的核心解析能力，專精於對外索敵、爬蟲解析與情報建檔。
# [隱蔽戰術] 智慧排班過濾：update_frequency_days 檢查，未更新節目不處理，# 減少 70% 無效偵察。
# [防爆戰術] 資料庫避震器：Supabase Insert/Update ，加入 隨機 db_jitter (0.2~0.8秒) ，防鎖死。
# [降維打擊] 探針型別修復：自動 Content-Length 向下轉型為純整數，根除 22P02 資料庫型別衝突。
# [戰鬥協議] 延續 RSS 絕對霸權與無效 Slug 攔截，遇 403 封鎖自動上報 ROE 檢舉 (pod_scra_rules)。
# [偵查數量] 測試期間：4新 +1舊
# ---------------------------------------------------------


import os, time, random, json, feedparser
from urllib.parse import urlparse 
from datetime import datetime, timezone, timedelta 
from bs4 import BeautifulSoup
from pod_scra_scanner import fetch_html

# 🚀 [戰場搶修]：必須把武器庫配發給 Scout，它才能在戰場上自動換槍！
ACTIVE_STRATEGY = 2 
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

def db_jitter():
    """🛡️ [資料庫避震器] 寫入 Supabase 前隨機微延遲 (0.2~0.8秒)，防止高併發鎖死"""
    time.sleep(random.uniform(0.2, 0.8))

def log_recon_failure(sb, task_id, provider, program_name, error_msg):
    """🚀 [黑盒子寫入] 紀錄失敗原因"""
    try:
        db_jitter()
        res = sb.table("mission_queue").select("recon_failure_log").eq("id", task_id).single().execute()
        current_log = res.data.get("recon_failure_log") if res.data else []
        if not isinstance(current_log, list): current_log = []
        
        current_log.append({
            "provider": provider,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "program": program_name,
            "reason": str(error_msg)[:200] 
        })
        sb.table("mission_queue").update({"recon_failure_log": current_log}).eq("id", task_id).execute()
    except Exception as e:
        print(f"⚠️ [日誌紀錄失敗]: {e}")

def probe_audio_metadata(url, session):
    """🚀 [連線池探針] 獲取音檔規格"""
    meta = {"size_mb": None, "ext": None, "skip_reason": None}
    try:
        with session.head(url, allow_redirects=True, timeout=5) as r:
            if r.status_code == 200:
                cl = r.headers.get('Content-Length')
                if cl and cl.isdigit():
                    meta["size_mb"] = int(int(cl) / (1024 * 1024))

                ct = r.headers.get('Content-Type', '').lower()
                if 'mpeg' in ct: meta["ext"] = ".mp3"
                elif 'm4a' in ct: meta["ext"] = ".m4a"
                elif 'ogg' in ct: meta["ext"] = ".ogg"
                elif 'opus' in ct: meta["ext"] = ".opus"
        
        if not meta["ext"]:
            meta["ext"] = os.path.splitext(urlparse(url).path)[1].lower() or ".mp3"

        # 此處修改檔案大小判斷
        s, e = meta["size_mb"], meta["ext"]
        if s is not None:
            if s > 50: meta["skip_reason"] = f"Oversize: {s}MB (Limit 50MB)"
            elif e in [".ogg", ".opus"] and s > 12: meta["skip_reason"] = f"Oversize: {s}MB {e} (Limit 12MB)"
            
    except Exception as e:
        print(f"📡 [探針失效] 無法預測物資規格: {e}")
    return meta

def execute_rss_recon(sb, current_time, session, alarm_callback):
    """📡 [任務一] 全量 RSS 偵察與智慧排班"""
    current_iso = current_time.isoformat()
    sources = sb.table("mission_program_master").select("*").eq("is_active", True).execute().data
    
    for s in sources:
        if not s.get("rss_feed_url"): continue

        freq_days = s.get("update_frequency_days") or 1
        last_check = s.get("last_checked_at")
        if last_check:
            last_check_dt = datetime.fromisoformat(last_check.replace("Z", "+00:00"))
            if (current_time - last_check_dt).days < freq_days:
                continue 

        try:
            feed = feedparser.parse(s["rss_feed_url"])
            if feed.entries:
                entry = feed.entries[0]
                audio_url = next((e.href for e in entry.enclosures if e.type.startswith("audio")), None)
                
                if audio_url:
                    exists = sb.table("mission_queue").select("id").eq("audio_url", audio_url).execute()
                    
                    if not exists.data:
                        print(f"🔎 發現新物資: {s['program_name']}，執行海關核驗...")
                        meta = probe_audio_metadata(audio_url, session)
                        
                        wait_days = s.get("wait_days") or 0
                        t2_start = (current_time + timedelta(days=wait_days)).isoformat()
                        assigned = "T1" if wait_days > 0 else "T2"

                        payload = {
                            "source_name": s["program_name"], "audio_url": audio_url,
                            "episode_title": entry.title[:100], "podbay_slug": s.get("podbay_slug"), 
                            "scrape_status": "success", "used_provider": "RSS_STRIKE",
                            "assigned_troop": assigned, "troop2_start_at": t2_start, 
                            "audio_size_mb": meta["size_mb"], "audio_ext": meta["ext"], "skip_reason": meta["skip_reason"] 
                        }
                        
                        db_jitter()
                        sb.table("mission_queue").insert(payload).execute()
                        status_msg = f"✅ 已發送物流" if not meta["skip_reason"] else f"🛑 海關攔截 ({meta['skip_reason']})"
                        print(f"{status_msg}: {s['program_name']}")

            db_jitter()
            sb.table("mission_program_master").update({"last_checked_at": current_iso}).eq("podbay_slug", s["podbay_slug"]).execute()
            time.sleep(random.uniform(0.5, 1.5))
            
        except Exception as e:
            err_str = str(e)
            print(f"⚠️ 偵察 {s['program_name']} 時遇到干擾: {err_str}")
            if "invalid input syntax" in err_str or "quota" in err_str.lower():
                alarm_callback(err_str)

def execute_html_recon(sb, current_time, session, provider_key, persona_label, api_key, alarm_callback):
    """🔦 [任務二] 補漏偵察 (HTML 攻堅)"""
    current_iso = current_time.isoformat()
    
    db_jitter()
    new_m = sb.table("mission_queue").select("*, mission_program_master(*)").eq("scrape_status", "pending").lte("troop2_start_at", current_iso)\
            .order("created_at", desc=True).limit(4).execute() # 🚀 套用 4新
    db_jitter()
    old_m = sb.table("mission_queue").select("*, mission_program_master(*)").eq("scrape_status", "pending").lte("troop2_start_at", current_iso)\
            .order("created_at", desc=False).limit(1).execute() # 🚀 套用 1舊
    
    all_missions = (new_m.data or []) + (old_m.data or [])

    for m in all_missions:
        task_id, slug = m['id'], str(m.get('podbay_slug') or "").strip()
        title, source_name = m.get('episode_title', ""), m.get('source_name', "Unknown")
        master = m.get('mission_program_master')
        history = str(m.get('recon_persona') or "")
        
        scrape_count = m.get('scrape_count') or 0
        if scrape_count >= 3:
            db_jitter()
            sb.table("mission_queue").update({"scrape_status": "failed", "skip_reason": "HTML攻堅失敗達3次"}).eq("id", task_id).execute()
            print(f"🛑 [任務放棄] {source_name} 攻堅失敗達 3 次，標記為 failed。")
            continue

        dyn_s = [2, 3, 4][scrape_count % 3]
        curr_provider = STRATEGY_MAP[dyn_s]["provider"]
        curr_persona = STRATEGY_MAP[dyn_s]["label"]
        curr_api_key = get_secret(STRATEGY_MAP[dyn_s]["key_name"])
        
        has_rss = bool(master and master.get('rss_feed_url'))

        if has_rss:
            rss_success = False
            try:
                feed = feedparser.parse(master['rss_feed_url'])
                match_rule = lambda t1, t2: len(set(t1.lower().split()) & set(t2.lower().split())) >= min(3, len(t1.split()) * 0.5)
                target = next((e for e in feed.entries if match_rule(title, e.title)), None)
                
                if target:
                    f_audio = next((enc.href for enc in target.enclosures if enc.type.startswith("audio")), None)
                    if f_audio:
                        db_jitter()
                        sb.table("mission_queue").update({"audio_url": f_audio, "scrape_status": "success", "used_provider": "RSS_STRIKE"}).eq("id", task_id).execute()
                        print(f"✅ [秒殺] RSS 模糊比對捕獲成功！")
                        rss_success = True
                        continue  
                
                if not rss_success:
                    print(f"⚠️ [RSS 落空] 找不到 '{title[:15]}...'，啟動降級 HTML 攻堅！")
            
            except Exception as e:
                print(f"⚠️ [RSS 錯誤] 解析失敗，啟動降級 HTML 攻堅！")

        if not bool(slug and slug.lower() != "null" and not slug.isdigit()):
            log_recon_failure(sb, task_id, curr_provider, source_name, f"INVALID_OR_EMPTY_SLUG: '{slug}'")
            db_jitter()
            sb.table("mission_queue").update({"recon_persona": f"{history} | INVALID_SLUG", "last_scraped_at": current_iso, "scrape_count": scrape_count + 1}).eq("id", task_id).execute()
            continue

        try:
            print(f"🔦 [換將攻堅] 第 {scrape_count+1} 次嘗試，派遣 {curr_persona}...")
            resp = fetch_html(curr_provider, f"https://podbay.fm/p/{slug}", {curr_provider: curr_api_key})
            
            upd_fail = {"recon_persona": f"{history} | {curr_persona}", "last_scraped_at": current_iso, "scrape_count": scrape_count + 1}
            
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
                    db_jitter()
                    sb.table("mission_program_master").update({"rss_feed_url": f_rss}).eq("podbay_slug", slug).execute()

                if f_audio:
                    meta = probe_audio_metadata(f_audio, session) 
                    wait_days = master.get("wait_days") if master else 0
                    t2_start = (current_time + timedelta(days=wait_days)).isoformat()
                    assigned = "T1" if wait_days > 0 else "T2"

                    db_jitter()
                    sb.table("mission_queue").update({
                        "audio_url": f_audio, "scrape_status": "success", "used_provider": f"{curr_provider}_FISHER",
                        "assigned_troop": assigned, "troop2_start_at": t2_start, 
                        "audio_size_mb": meta["size_mb"], "audio_ext": meta["ext"], "skip_reason": meta["skip_reason"],
                        "recon_persona": upd_fail["recon_persona"], "last_scraped_at": current_iso  
                    }).eq("id", task_id).execute()
                    print(f"✅ [結案] HTML 偵察完畢。指派: {assigned} | 規格: {meta['size_mb']}MB")
                else:
                    log_recon_failure(sb, task_id, curr_provider, source_name, "AUDIO_NOT_FOUND_ON_PAGE")
                    db_jitter()
                    sb.table("mission_queue").update(upd_fail).eq("id", task_id).execute()

            elif resp and resp.status_code == 403: 
                target_domain = urlparse(f"https://podbay.fm/p/{slug}").netloc
                db_jitter()
                sb.table("pod_scra_rules").insert({"worker_id": "GITHUB_SCOUT", "domain": target_domain, "expired_at": (current_time + timedelta(days=7)).isoformat()}).execute()
                log_recon_failure(sb, task_id, curr_provider, source_name, "HTTP_403_FORBIDDEN")
                db_jitter()
                sb.table("mission_queue").update(upd_fail).eq("id", task_id).execute()
            else:
                reason = f"HTTP_{resp.status_code}" if resp else "NO_RESPONSE"
                log_recon_failure(sb, task_id, curr_provider, source_name, reason)
                db_jitter()
                sb.table("mission_queue").update(upd_fail).eq("id", task_id).execute()

        except Exception as e:
            err_str = str(e)
            log_recon_failure(sb, task_id, curr_provider, source_name, err_str)
            db_jitter()
            sb.table("mission_queue").update({"recon_persona": f"{history} | {curr_persona}_ERR", "last_scraped_at": current_iso, "scrape_count": scrape_count + 1}).eq("id", task_id).execute()
            if any(k in err_str.lower() for k in ["quota", "unauthorized", "429", "invalid input syntax"]):
                alarm_callback(err_str)