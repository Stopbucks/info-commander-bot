
# ---------------------------------------------------------
# S-Plan Fortress v2.4 (2026 規則執行版 - 最終修正)
# 任務：1. 心跳 2. AI 接力 3. 役期交接 4. 重型物流 5. 403 自動換班
# 修正：1. 啟動時領取黑名單 2. 遭遇 403 自動填寫規則表並換班 3. 簡化邏輯
# ---------------------------------------------------------

import os, time, json, requests, boto3, re, random, feedparser, threading, traceback
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify, request
from supabase import create_client
from apscheduler.schedulers.background import BackgroundScheduler
from urllib.parse import urlparse 

app = Flask(__name__)

# === 🎖️ 情報控制面板 ===
INTEL_AUDIO_OFFICERS = ["ZEABUR", "RENDER"]
INTEL_TXT_OFFICERS = ["ZEABUR","KOYEB", "RENDER", "HUGGINGFACE"]

CONFIG = {
    "WORKER_ID": os.environ.get("WORKER_ID", "UNKNOWN_NODE"),
    "INTERVAL_HOURS": 2,
    "NEW_LIMIT": 2, "OLD_LIMIT": 1,
    "JITTER_BASE_MIN": 180, "JITTER_BASE_MAX": 360,
    "CRON_SECRET": os.environ.get("CRON_SECRET")
}

def s_log(sb, task_type, status, message, err_stack=None):
    try:
        print(f"[{task_type}][{status}] {message}")
        if status in ["SUCCESS", "ERROR"] or "啟動" in message:
            sb.table("mission_logs").insert({
                "worker_id": CONFIG["WORKER_ID"], "task_type": task_type,
                "status": status, "message": message, "traceback": err_stack
            }).execute()
    except: pass

def get_sb(): return create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))
def get_s3():
    return boto3.client('s3', endpoint_url=os.environ.get("R2_ENDPOINT_URL"),
                        aws_access_key_id=os.environ.get("R2_ACCESS_KEY_ID"),
                        aws_secret_access_key=os.environ.get("R2_SECRET_ACCESS_KEY"), region_name="auto")

# --- 🚀 AI 引擎觸發器 (增加 s_log 回報) ---
def trigger_intel_pipeline(sb): # 🚀 傳入 sb 以便紀錄日誌
    worker = CONFIG["WORKER_ID"]
    try:
        if worker in INTEL_AUDIO_OFFICERS:
            from src.pod_scra_intel_core import run_audio_to_stt_mission
            threading.Thread(target=run_audio_to_stt_mission, daemon=True).start()
            s_log(sb, "AI", "INFO", f"🎤 [音訊組] {worker} 啟動轉譯")
            
        if worker in INTEL_TXT_OFFICERS:
            from src.pod_scra_intel_core import run_stt_to_summary_mission
            threading.Thread(target=run_stt_to_summary_mission, daemon=True).start()
            s_log(sb, "AI", "INFO", f"✍️ [文字組] {worker} 啟動摘要")
    except Exception as e:
        print(f"⚠️ [AI觸發異常]: {e}")

# --- 🕵️ 核心巡邏邏輯 (最終精煉) ---
def run_integrated_mission():
    sb = get_sb(); now = datetime.now(timezone.utc); now_iso = now.isoformat()
    s_log(sb, "PATROL", "INFO", "🚀 戰術巡邏模式啟動")

    try:
        # --- 階段 1：領取戰術規則與心跳 ---
        t_res = sb.table("pod_scra_tactics").select("*").eq("id", 1).single().execute()
        if not t_res.data: return
        tactic = t_res.data
        
        rule_res = sb.table("pod_scra_rules").select("domain").eq("worker_id", CONFIG["WORKER_ID"]).execute()
        my_blacklist = [r['domain'] for r in rule_res.data] if rule_res.data else []
        
        health = tactic.get('workers_health', {}) or {}
        health[CONFIG['WORKER_ID']] = now_iso
        sb.table("pod_scra_tactics").update({"last_heartbeat_at": now_iso, "workers_health": health}).eq("id", 1).execute()
        s_log(sb, "HEARTBEAT", "SUCCESS", f"💓 心跳成功 (黑名單數: {len(my_blacklist)})")

        # --- 階段 3：AI 情報接力 ---
        trigger_intel_pipeline(sb) # 🚀 傳入 sb
        time.sleep(5)

        # --- 階段 4：身分與輪值判定 ---
        is_my_turn = (tactic['active_worker'] == CONFIG['WORKER_ID'])
        roster = tactic.get('worker_roster', [])
        if not is_my_turn:
            print(f"🛌 [待命] 目前由 {tactic['active_worker']} 值勤。"); return

        # 4.1 役期檢查
        duty_start = datetime.fromisoformat(tactic.get('duty_start_at', now_iso).replace('Z', '+00:00'))
        if now > duty_start + timedelta(hours=tactic.get('rotation_hours', 48)):
            new_active = roster[(roster.index(CONFIG['WORKER_ID']) + 1) % len(roster)]
            s_log(sb, "DUTY", "SUCCESS", f"⏰ 役期屆滿，換班至: {new_active}")
            sb.table("pod_scra_tactics").update({"active_worker": new_active, "duty_start_at": now_iso}).eq("id", 1).execute()
            return 

# --- 階段 5：重型物流 (動態副檔名) ---
        print("🚛 [物流開火] 準備提取 T2 物資...")
        
        # 修正：統一使用 query 變數名稱
        query = sb.table("mission_queue").select("*, mission_program_master(*)")\
                  .eq("scrape_status", "success")\
                  .eq("assigned_troop", "T2")\
                  .lte("troop2_start_at", now_iso)

        # 修正：將 query_base 改為 query
        tasks = (query.order("created_at", desc=True).limit(CONFIG['NEW_LIMIT']).execute().data or []) + \
                (query.order("created_at", desc=False).limit(CONFIG['OLD_LIMIT']).execute().data or [])
        
        if not tasks:
            print("☕ 戰區暫無待處理物資。"); return

        s3 = get_s3(); bucket = os.environ.get("R2_BUCKET_NAME")
        for idx, m in enumerate(tasks):
            f_url = m.get('audio_url')
            if not f_url: continue
            
            target_domain = urlparse(f_url).netloc
            if any(b_domain in target_domain for b_domain in my_blacklist):
                print(f"⏩ [ROE規避] {target_domain} 處於禁閉期，跳過。")
                continue

            # 🚀 修正：動態偵測副檔名
            path_part = urlparse(f_url).path
            ext = os.path.splitext(path_part)[1] or ".mp3" # 如果沒抓到就預設 .mp3
            tmp_path = f"/tmp/{now.strftime('%Y%m%d')}_{m['id'][:8]}{ext}"
            
            try:
                with requests.get(f_url, stream=True, timeout=120) as r:
                    r.raise_for_status()
                    with open(tmp_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=16384): f.write(chunk)
                
                file_name = os.path.basename(tmp_path)
                s3.upload_file(tmp_path, bucket, file_name)
                sb.table("mission_queue").update({"scrape_status": "completed", "r2_url": file_name}).eq("id", m['id']).execute()
                s_log(sb, "DOWNLOAD", "SUCCESS", f"✅ 物資入庫: {file_name}")

            except requests.exceptions.HTTPError as he:
                if he.response.status_code == 403:
                    new_commander = roster[(roster.index(CONFIG['WORKER_ID']) + 1) % len(roster)]
                    s_log(sb, "SYSTEM", "ERROR", f"🚫 403 封鎖！將 {target_domain} 列入黑名單，交接至: {new_commander}")
                    
                    sb.table("pod_scra_rules").insert({
                        "worker_id": CONFIG["WORKER_ID"],
                        "domain": target_domain,
                        "expired_at": (now + timedelta(days=7)).isoformat()
                    }).execute()
                    
                    sb.table("pod_scra_tactics").update({
                        "active_worker": new_commander, "duty_start_at": now_iso, "last_error_type": f"403_BANNED_{target_domain}"
                    }).eq("id", 1).execute()
                    return 
            except Exception as e:
                s_log(sb, "DOWNLOAD", "ERROR", f"❌ 搬運失敗: {str(e)}", traceback.format_exc())
            finally:
                if os.path.exists(tmp_path): 
                    try: os.remove(tmp_path)
                    except: pass
            
            if idx < len(tasks) - 1: time.sleep(random.randint(CONFIG['JITTER_BASE_MIN'], CONFIG['JITTER_BASE_MAX']))

    except Exception as e:
        s_log(sb, "SYSTEM", "ERROR", f"💥 系統崩潰: {str(e)}", traceback.format_exc())

# --- 📡 接口與排程設定 ---
@app.route('/ping')
def trigger():
    token = request.args.get('token')
    if not token or token != CONFIG['CRON_SECRET']: return "Unauthorized", 401
    threading.Thread(target=run_integrated_mission, daemon=True).start()
    return f"📡 {CONFIG['WORKER_ID']} Fortress: Mission Triggered.", 202

@app.route('/')
def health(): return f"Fortress {CONFIG['WORKER_ID']} v2.4 (Rules Active) Online", 200

# 🕒 背景排程
scheduler = BackgroundScheduler()
scheduler.add_job(func=run_integrated_mission, trigger="interval", hours=CONFIG["INTERVAL_HOURS"])
scheduler.start()

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)