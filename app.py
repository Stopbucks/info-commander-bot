# ---------------------------------------------------------
# S-Plan Fortress v2.5 (FLY_LAX 特種武裝版)
# 任務：1. 領取黑名單 2. 僅執行 T2 任務 3. 動態副檔名 4. 403 檢舉換班
# ---------------------------------------------------------

import os, time, json, requests, boto3, re, random, feedparser, threading, traceback
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify, request
from supabase import create_client
from urllib.parse import urlparse # 🚀 新增

app = Flask(__name__)

# === 🎖️ 控制面板 (FLY_LAX 專屬) ===
INTEL_AUDIO_OFFICERS = ["ZEABUR", "FLY_LAX", "RENDER"]
INTEL_TXT_OFFICERS = ["KOYEB", "RENDER", "HUGGINGFACE"]

CONFIG = {
    "WORKER_ID": "FLY_LAX", # 🚀 確保這裡寫死或從環境變數抓
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
def get_s3(): return boto3.client('s3', endpoint_url=os.environ.get("R2_ENDPOINT_URL"), aws_access_key_id=os.environ.get("R2_ACCESS_KEY_ID"), aws_secret_access_key=os.environ.get("R2_SECRET_ACCESS_KEY"), region_name="auto")

def trigger_intel_pipeline(sb):
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
    except Exception as e: print(f"⚠️ [AI觸發異常]: {e}")

def run_integrated_mission():
    sb = get_sb(); now = datetime.now(timezone.utc); now_iso = now.isoformat()
    s_log(sb, "PATROL", "INFO", "🚀 戰術巡邏啟動")
    try:
        # 1. 心跳與規則領取
        t_res = sb.table("pod_scra_tactics").select("*").eq("id", 1).single().execute()
        tactic = t_res.data
        rule_res = sb.table("pod_scra_rules").select("domain").eq("worker_id", CONFIG["WORKER_ID"]).execute()
        my_blacklist = [r['domain'] for r in rule_res.data] if rule_res.data else []
        
        health = tactic.get('workers_health', {})
        health[CONFIG['WORKER_ID']] = now_iso
        sb.table("pod_scra_tactics").update({"last_heartbeat_at": now_iso, "workers_health": health}).eq("id", 1).execute()
        
        trigger_intel_pipeline(sb)

        # 2. 輪值判定
        if tactic['active_worker'] != CONFIG['WORKER_ID']:
            print(f"🛌 [待命] 目前主將為 {tactic['active_worker']}"); return

        # 3. 物流區：加入 T2 識別碼與黑名單規避
        query = sb.table("mission_queue").select("*, mission_program_master(*)")\
                  .eq("scrape_status", "success")\
                  .eq("assigned_troop", "T2")\
                  .lte("troop2_start_at", now_iso)
        
        tasks = (query.order("created_at", desc=True).limit(CONFIG['NEW_LIMIT']).execute().data or []) + \
                (query.order("created_at", desc=False).limit(CONFIG['OLD_LIMIT']).execute().data or [])

        if not tasks: return

        s3 = get_s3(); bucket = os.environ.get("R2_BUCKET_NAME")
        for idx, m in enumerate(tasks):
            f_url = m.get('audio_url')
            target_domain = urlparse(f_url).netloc
            if any(b in target_domain for b in my_blacklist): continue

            # 動態偵測副檔名
            ext = os.path.splitext(urlparse(f_url).path)[1] or ".mp3"
            tmp_path = f"/tmp/{now.strftime('%Y%m%d')}_{m['id'][:8]}{ext}"
            
            try:
                with requests.get(f_url, stream=True, timeout=120) as r:
                    r.raise_for_status()
                    with open(tmp_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=16384): f.write(chunk)
                
                file_name = os.path.basename(tmp_path)
                s3.upload_file(tmp_path, bucket, file_name)
                sb.table("mission_queue").update({"scrape_status": "completed", "r2_url": file_name}).eq("id", m['id']).execute()
                s_log(sb, "DOWNLOAD", "SUCCESS", f"✅ 入庫: {file_name}")
            except requests.exceptions.HTTPError as he:
                if he.response.status_code == 403:
                    # 🚀 新兵受傷，立即回報並換班
                    roster = tactic.get('worker_roster', [])
                    new_active = roster[(roster.index(CONFIG['WORKER_ID']) + 1) % len(roster)]
                    s_log(sb, "SYSTEM", "ERROR", f"🚫 403 封鎖！將 {target_domain} 列入黑名單，交接至: {new_active}")
                    sb.table("pod_scra_rules").insert({"worker_id": CONFIG["WORKER_ID"], "domain": target_domain, "expired_at": (now + timedelta(days=7)).isoformat()}).execute()
                    sb.table("pod_scra_tactics").update({"active_worker": new_active, "duty_start_at": now_iso}).eq("id", 1).execute()
                    return
            finally:
                if os.path.exists(tmp_path): os.remove(tmp_path)
            
            if idx < len(tasks) - 1: time.sleep(random.randint(CONFIG['JITTER_BASE_MIN'], CONFIG['JITTER_BASE_MAX']))
    except Exception as e: s_log(sb, "SYSTEM", "ERROR", f"💥 崩潰: {str(e)}", traceback.format_exc())


# --- 📡 接口與排程設定 ---
@app.route('/ping')
def trigger():
    token = request.args.get('token')
    if not token or token != CONFIG['CRON_SECRET']: return "Unauthorized", 401
    threading.Thread(target=run_integrated_mission, daemon=True).start()
    return f"📡 {CONFIG['WORKER_ID']} Fortress: Mission Triggered.", 202

@app.route('/')
def health(): return f"Fortress {CONFIG['WORKER_ID']} v2.2 (Blackbox Mode) Online", 200

# 🕒 全域背景排程啟動器 (確保 Gunicorn 環境下也能點火)
scheduler = BackgroundScheduler()
scheduler.add_job(func=run_integrated_mission, trigger="interval", hours=CONFIG["INTERVAL_HOURS"])
scheduler.start()

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)