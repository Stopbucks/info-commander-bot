
# ---------------------------------------------------------
# 程式碼：src/pod_scra_intel_trans.py  (V4.6  S-Plan 物流防禦官)
# 任務：執行三位一體巡邏、T2 重型物流下載、403 威脅雷達與動態冰封
# 修改：新增冰封期間
# ---------------------------------------------------------

import os, requests, time, random, gc, json
from urllib.parse import urlparse
from datetime import datetime, timezone, timedelta
from src.pod_scra_intel_r2 import get_s3_client

def execute_fortress_stages(sb, config, s_log_func, trigger_intel_func, officers_list):
    """
    【總指揮程序】執行全階段巡邏任務
    包含：簽到、喚醒 AI 產線、執行主將專屬的重型物流
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    worker_id = config["WORKER_ID"]
    try:
        t_res = sb.table("pod_scra_tactics").select("*").eq("id", 1).single().execute()
        if not t_res.data: return
        tactic = t_res.data
        
        # 📌 階段一：發送心跳訊號，向 Vercel 判官證明存活
        health = tactic.get('workers_health', {}) or {}
        health[worker_id] = now_iso
        sb.table("pod_scra_tactics").update({"last_heartbeat_at": now_iso, "workers_health": health}).eq("id", 1).execute()
        s_log_func(sb, "HEARTBEAT", "SUCCESS", f"💓 {worker_id} 心跳簽到")

        # 📌 階段二：觸發 AI 情報處理鏈 (STT & Summary)
        trigger_intel_func(sb)

        # 📌 階段三：物流派送 (僅限目前輪值的主將執行)
        if tactic.get('active_worker') == worker_id:
            # 🛡️ 聯合作戰防禦：同時讀取「我的專屬冰封名單」與「全軍警戒名單」
            rule_res = sb.table("pod_scra_rules").select("domain").in_("worker_id", [worker_id, "ALL"]).gte("expired_at", now_iso).execute()
            my_blacklist = [r['domain'] for r in rule_res.data] if rule_res.data else []
            
            run_logistics_engine(sb, config, now_iso, get_s3_func, s_log_func, my_blacklist)
            
    except Exception as e:
        s_log_func(sb, "SYSTEM", "ERROR", f"💥 運輸異常: {str(e)}")

def run_logistics_engine(sb, config, now_iso, s_log_func, my_blacklist):
    """
    【核心物流引擎】
    負責下載音檔至本機，上傳至 R2，並具備 403 遇襲後的「威脅建檔」與「指數冰封」能力。
    """
    query = sb.table("mission_queue").select("*, mission_program_master(*)").eq("scrape_status", "success").is_("r2_url", "null").lte("troop2_start_at", now_iso).order("created_at", desc=True).limit(2)
    tasks = query.execute().data or []
    if not tasks: return
    
    s3 = get_s3_client()
    bucket = os.environ.get("R2_BUCKET_NAME")
    worker_id = config.get('WORKER_ID', 'UNKNOWN')
    
    # 🎭【戰術迷彩包】提供 3 組市佔率最高的真實瀏覽器指紋，隨機切換以降低封鎖率
    UAS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0"
    ]
    
    for m in tasks:
        f_url = m.get('audio_url')
        if not f_url: continue
        
        target_domain = urlparse(f_url).netloc
        
        # ⚠️【雷區規避】如果目標網站正處於冰封或警戒狀態，直接跳過不碰
        if any(b in target_domain for b in my_blacklist): continue 

        ext = os.path.splitext(urlparse(f_url).path)[1] or ".mp3"
        tmp_path = f"/tmp/dl_{m['id'][:8]}{ext}"
        
        try:
            headers = {
                "User-Agent": random.choice(UAS), 
                "Accept": "audio/webm,audio/ogg,audio/wav,audio/*;q=0.9,application/ogg;q=0.7,video/*;q=0.6,*/*;q=0.5"
            }
            
            # 📥【執行下載】披上偽裝表頭進行串流下載
            with requests.get(f_url, stream=True, timeout=120, headers=headers) as r:
                r.raise_for_status()
                with open(tmp_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=64*1024): f.write(chunk)
                    
            s3.upload_file(tmp_path, bucket, os.path.basename(tmp_path))
            sb.table("mission_queue").update({"scrape_status": "completed", "r2_url": os.path.basename(tmp_path)}).eq("id", m['id']).execute()
            s_log_func(sb, "DOWNLOAD", "SUCCESS", f"✅ 物資入庫: {m['id'][:8]}")
            
        except requests.exceptions.HTTPError as he:
            # 🚨【戰損防禦機制】遭遇 403/401 嚴格防火牆
            if he.response.status_code in [403, 401, 429]:
                error_msg = f"🚫 [{worker_id}] 遭 {target_domain} 封鎖 ({he.response.status_code})"
                s_log_func(sb, "DOWNLOAD", "ERROR", error_msg)
                
                # [動作 1] 通報總部：將封鎖資訊寫入戰術表，供 Vercel 判斷是否換將
                sb.table("pod_scra_tactics").update({"last_error_type": f"{he.response.status_code}_BANNED_{target_domain}"}).eq("id", 1).execute()
                
                # [動作 2] 歷史計算：查詢本機被該網站封鎖的歷史次數
                history = sb.table("pod_scra_rules").select("id").eq("worker_id", worker_id).eq("domain", target_domain).eq("rule_type", "AUTO_COOLDOWN").execute()
                strike_count = len(history.data) + 1 if history.data else 1
                
                # [動作 3] 指數冰封：本機禁足 (第一次 24h, 第二次 48h, 第三次 96h)
                victim_hours = 24 * (2 ** (strike_count - 1))
                victim_freeze = (datetime.now(timezone.utc) + timedelta(hours=victim_hours)).isoformat()
                
                # [動作 4] 全軍警戒：其他節點緩衝禁足 (固定 12h)
                ally_freeze = (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat()
                
                sb.table("pod_scra_rules").insert([
                    {"worker_id": worker_id, "domain": target_domain, "rule_type": "AUTO_COOLDOWN", "expired_at": victim_freeze},
                    {"worker_id": "ALL", "domain": target_domain, "rule_type": "VIGILANCE", "expired_at": ally_freeze}
                ]).execute()
                
                # [動作 5] 威脅建檔：將遇襲紀錄永久寫入該任務的 JSON 檔案中，作為未來分析依據
                old_log = m.get('recon_failure_log')
                if not old_log: old_log = []
                elif isinstance(old_log, str): 
                    try: old_log = json.loads(old_log)
                    except: old_log = []
                
                old_log.append({
                    "event": f"STRICT_FIREWALL_{he.response.status_code}",
                    "worker": worker_id,
                    "timestamp": now_iso
                })
                
                # 任務退回佇列，增加軟性失敗次數，並將本網域加入當前迴圈黑名單
                sb.table("mission_queue").update({"soft_failure_count": m.get('soft_failure_count', 0) + 1, "recon_failure_log": old_log}).eq("id", m['id']).execute()
                my_blacklist.append(target_domain) 
            else:
                s_log_func(sb, "DOWNLOAD", "ERROR", f"❌ 搬運 HTTP 異常: {he.response.status_code}")
                
        except Exception as e: 
            s_log_func(sb, "DOWNLOAD", "ERROR", f"❌ 搬運失敗: {str(e)}")
            
        finally:
            if os.path.exists(tmp_path): os.remove(tmp_path)
            gc.collect()