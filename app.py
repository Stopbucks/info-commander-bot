
#  ---------------------------------------------------------
# S-Plan Fortress v2.2 (2026 鋼鐵黑盒子版)
# 任務：1. 心跳 2. AI 接力 3. 役期交接 4. 重型物流 5. 遠端日誌 (s_log)
# 修正：1. 整合 s_log 2. 移除冗餘判斷 3. 強化崩潰回報(traceback)
# ---------------------------------------------------------

import os, time, json, requests, boto3, re, random, feedparser, threading, traceback
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify, request
from supabase import create_client
from bs4 import BeautifulSoup
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

# === 🎖️ 情報特種兵控制面板 ===
INTEL_AUDIO_OFFICERS = ["ZEABUR", "FLY_LAX", "RENDER"]
INTEL_TXT_OFFICERS = ["KOYEB", "RENDER", "HUGGINGFACE"]

CONFIG = {
    "WORKER_ID": os.environ.get("WORKER_ID", "UNKNOWN_NODE"),
    "INTERVAL_HOURS": 2,
    "NEW_LIMIT": 2, "OLD_LIMIT": 1,
    "JITTER_BASE_MIN": 180, "JITTER_BASE_MAX": 360,
    "CRON_SECRET": os.environ.get("CRON_SECRET")
}

# --- 🚀 戰地通訊兵：精準黑盒子錄製 ---
def s_log(sb, task_type, status, message, err_stack=None):
    """
    將關鍵情報送往總部 (Supabase)，普通訊息保留在本地 print
    """
    try:
        # 本地依然 print，方便開發查看
        print(f"[{task_type}][{status}] {message}")
        
        # 僅針對關鍵節點(SUCCESS)與錯誤(ERROR)發送到 Supabase
        # 如果是單純的 INFO，我們可以選擇不發送以節省流量，除非您想看「誰起床了」
        if status in ["SUCCESS", "ERROR"] or "啟動" in message:
            sb.table("mission_logs").insert({
                "worker_id": CONFIG["WORKER_ID"],
                "task_type": task_type,
                "status": status,
                "message": message,
                "traceback": err_stack
            }).execute()
    except Exception as e:
        print(f"⚠️ [日誌發送失敗]: {e}")

def get_sb(): return create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))
def get_s3():
    return boto3.client('s3', endpoint_url=os.environ.get("R2_ENDPOINT_URL"),
                        aws_access_key_id=os.environ.get("R2_ACCESS_KEY_ID"),
                        aws_secret_access_key=os.environ.get("R2_SECRET_ACCESS_KEY"), region_name="auto")

# --- 🚀 AI 引擎觸發器 ---
def trigger_intel_pipeline():
    worker = CONFIG["WORKER_ID"]
    try:
        if worker in INTEL_AUDIO_OFFICERS:
            from src.pod_scra_intel_core import run_audio_to_stt_mission
            threading.Thread(target=run_audio_to_stt_mission, daemon=True).start()
            print(f"🎤 [音訊組] {worker} 啟動轉譯。")
            
        if worker in INTEL_TXT_OFFICERS:
            from src.pod_scra_intel_core import run_stt_to_summary_mission
            threading.Thread(target=run_stt_to_summary_mission, daemon=True).start()
            print(f"✍️ [文字組] {worker} 啟動摘要。")
    except Exception as e:
        print(f"⚠️ [AI觸發異常]: {e}")

# --- 🕵️ 核心巡邏邏輯 ---
def run_integrated_mission():
    sb = get_sb(); now = datetime.now(timezone.utc); now_iso = now.isoformat()
    # 🚩 節點 1：巡邏啟動回報
    s_log(sb, "PATROL", "INFO", "🚀 鋼鐵巡邏模式啟動")

    try:
        # --- 階段 1：基礎心跳 ---
        t_res = sb.table("pod_scra_tactics").select("*").eq("id", 1).single().execute()
        if not t_res.data: return
        tactic = t_res.data
        
        health = tactic.get('workers_health', {}) or {}
        health[CONFIG['WORKER_ID']] = now_iso
        sb.table("pod_scra_tactics").update({"last_heartbeat_at": now_iso, "workers_health": health}).eq("id", 1).execute()
        # 🚩 節點 2：心跳成功 (Success)
        s_log(sb, "HEARTBEAT", "SUCCESS", "💓 心跳簽到成功")

        # --- 階段 2：Watchdog (由 Vercel 負責，此處留白) ---

        # --- 階段 3：AI 情報接力 ---
        trigger_intel_pipeline()
        time.sleep(5) 

        # --- 階段 4：身分與輪值判定 ---
        is_my_turn = (tactic['active_worker'] == CONFIG['WORKER_ID'])
        if not is_my_turn:
            print(f"🛌 [待命] 目前由 {tactic['active_worker']} 值勤。")
            return

        # 役期交接檢查
        roster = tactic.get('worker_roster', [])
        duty_start_str = tactic.get('duty_start_at', now_iso).replace('Z', '+00:00')
        duty_start = datetime.fromisoformat(duty_start_str)
        rotation_hours = tactic.get('rotation_hours', 48)

        if now > duty_start + timedelta(hours=rotation_hours):
            curr_idx = roster.index(CONFIG['WORKER_ID']) if CONFIG['WORKER_ID'] in roster else 0
            new_active = roster[(curr_idx + 1) % len(roster)]
            new_next = roster[(curr_idx + 2) % len(roster)]
            # 🚩 節點 3：役期交接
            s_log(sb, "DUTY", "SUCCESS", f"⏰ 役期屆滿，移交予: {new_active}")
            sb.table("pod_scra_tactics").update({
                "active_worker": new_active, "next_worker": new_next,
                "duty_start_at": now_iso, "consecutive_soft_failures": 0 
            }).eq("id", 1).execute()
            return 

        # --- 階段 5：重型物流下載 ---
        print("🚛 [物流] 準備提取音檔...")
        query_base = sb.table("mission_queue").select("*, mission_program_master(*)") \
                       .eq("scrape_status", "success").lte("troop2_start_at", now_iso)

        new_tasks = query_base.order("created_at", desc=True).limit(CONFIG['NEW_LIMIT']).execute().data or []
        old_tasks = query_base.not_.in_("id", [t['id'] for t in new_tasks]).order("created_at", desc=False).limit(CONFIG['OLD_LIMIT']).execute().data or []
        
        missions = new_tasks + old_tasks
        if not missions:
            print("☕ 戰區暫無待處理物資。")
            return

        s3 = get_s3(); bucket = os.environ.get("R2_BUCKET_NAME")
        for idx, m in enumerate(missions):
            task_id, f_audio = m['id'], m.get('audio_url')
            if not f_audio: continue
            
            try:
                file_name = f"{now.strftime('%Y%m%d')}_{task_id[:8]}.mp3"
                tmp_path = f"/tmp/{file_name}"
                
                with requests.get(f_audio, stream=True, timeout=120) as r:
                    r.raise_for_status()
                    with open(tmp_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=16384): f.write(chunk)
                
                s3.upload_file(tmp_path, bucket, file_name)
                sb.table("mission_queue").update({
                    "scrape_status": "completed", "r2_url": file_name, 
                    "recon_persona": f"{CONFIG['WORKER_ID']}_v2.2_Logged" 
                }).eq("id", task_id).execute()
                
                # 🚩 節點 4：物流成功 (Success)
                s_log(sb, "DOWNLOAD", "SUCCESS", f"✅ 物資入庫完成: {file_name}")
                if os.path.exists(tmp_path): os.remove(tmp_path)
                
                if idx < len(missions) - 1:
                    wait = random.randint(CONFIG['JITTER_BASE_MIN'], CONFIG['JITTER_BASE_MAX'])
                    time.sleep(wait)
            except Exception as e:
                # 🚩 節點 5：物流失敗 (Error)
                stack = traceback.format_exc()
                s_log(sb, "DOWNLOAD", "ERROR", f"❌ 搬運失敗: {str(e)}", stack)

    except Exception as e:
        # 🚩 節點 6：系統總體崩潰 (Error)
        stack = traceback.format_exc()
        s_log(sb, "SYSTEM", "ERROR", f"💥 巡邏系統總體崩潰: {str(e)}", stack)

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