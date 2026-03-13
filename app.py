# ---------------------------------------------------------
# app.py (2026 RENDER/KOYEB V5.1 破冰守衛與軟失敗版)
# 任務：1. 接口防震 2. 30分鐘破冰守衛 3. 崩潰通報判官 4. 全軍狀態機
# ---------------------------------------------------------
import os, time, gc, random, threading, traceback
from datetime import datetime, timezone, timedelta
from flask import Flask, request
from supabase import create_client
from apscheduler.schedulers.background import BackgroundScheduler

from src.pod_scra_intel_trans import execute_fortress_stages 

app = Flask(__name__)
INTEL_AUDIO_OFFICERS = ["FLY_LAX", "RENDER", "HUGGINGFACE", "KOYEB", "DBOS"] 

CONFIG = {
    "WORKER_ID": os.environ.get("WORKER_ID", "UNKNOWN_NODE"),
    "INTERVAL_HOURS": 2, 
    "CRON_SECRET": os.environ.get("CRON_SECRET")
}

# 🚀 宣告火力為 512MB 部隊！ & KOYEB 為256MB，進行A/B測試。
os.environ["MEMORY_TIER"] = "512"

# 🛡️ 破冰守衛 (Watchdog) 系統配置
MISSION_LOCK = threading.Lock()
MISSION_STATE = {"is_running": False, "start_time": 0.0}
WATCHDOG_TIMEOUT = 1800  # 輕裝部隊寬限期：30 分鐘 (1800秒)

def get_sb(): 
    return create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))

def s_log(sb, task_type, status, message, err_stack=None):
    try:
        print(f"[{task_type}][{status}] {message}", flush=True)
        if status in ["SUCCESS", "ERROR"] or "啟動" in message or "V5.1" in message:
            sb.table("mission_logs").insert({
                "worker_id": CONFIG["WORKER_ID"], "task_type": task_type,
                "status": status, "message": message, "traceback": err_stack
            }).execute()
    except: pass

def report_soft_failure(sb, worker_id, error_msg):
    """【系統自救】回報軟失敗給 Vercel 判官"""
    try:
        print(f"🚨 [通報判官] 發生嚴重異常，寫入軟失敗紀錄！", flush=True)
        res = sb.table("pod_scra_tactics").select("consecutive_soft_failures").eq("id", 1).single().execute()
        current_fails = res.data.get("consecutive_soft_failures", 0) if res.data else 0
        
        sb.table("pod_scra_tactics").update({
            "consecutive_soft_failures": current_fails + 1,
            "last_error_type": f"{worker_id}_CRASH: {error_msg}"[:200]
        }).eq("id", 1).execute()
    except Exception as e: 
        print(f"軟失敗通報異常: {e}")

def run_integrated_mission():
    global MISSION_STATE
    sb = get_sb()
    try:
        # 🚀 專屬信號彈
        s_log(sb, "SYSTEM", "SUCCESS", f"🚀 [{CONFIG['WORKER_ID']} V5.1] 輕裝部隊連線，破冰守衛(30m)與自救機制就位！")
        # 🚀 呼叫全軍統一狀態機
        execute_fortress_stages(sb, CONFIG, s_log, lambda x: None, INTEL_AUDIO_OFFICERS)
        
    except Exception as e:
        error_msg = str(e)
        print(f"💥 戰場崩潰: {error_msg}")
        report_soft_failure(sb, CONFIG["WORKER_ID"], error_msg)
    finally:
        # 🛡️ 任務結束：安全歸還鎖定與清理
        MISSION_STATE["is_running"] = False
        if MISSION_LOCK.locked():
            try: MISSION_LOCK.release()
            except: pass
        del sb; gc.collect()
        print("🏁 [巡邏結束] READY。")


@app.route('/')
def health(): return "OK", 200

@app.route('/ping')
def trigger():
    global MISSION_STATE
    token = request.args.get('token')
    if not token or token != CONFIG['CRON_SECRET']: return "Unauthorized", 401
    
    current_time = time.time()
    
    # --- 🛡️ 破冰守衛：巡視與強制解鎖 ---
    if MISSION_STATE["is_running"]:
        elapsed = current_time - MISSION_STATE["start_time"]
        if elapsed > WATCHDOG_TIMEOUT:
            print(f"🚨 [破冰守衛] 任務死結 ({elapsed:.0f}s)！強制擊碎門鎖並通報判官！")
            sb = get_sb()
            report_soft_failure(sb, CONFIG["WORKER_ID"], "Watchdog_Timeout_Deadlock")
            MISSION_STATE["is_running"] = False
            if MISSION_LOCK.locked():
                try: MISSION_LOCK.release()
                except: pass
        else:
            return f"Busy ({elapsed:.0f}s elapsed)", 429

    time.sleep(random.uniform(1.0, 3.0))

    # --- 🚪 嘗試進入主防線 ---
    if not MISSION_LOCK.acquire(blocking=False): return "Locked", 429
    
    MISSION_STATE["is_running"] = True
    MISSION_STATE["start_time"] = time.time()
    
    threading.Thread(target=run_integrated_mission, daemon=True).start()
    return f"Mission Triggered", 202

# 內部備用排程器
scheduler = BackgroundScheduler()
run_next = datetime.now() + timedelta(minutes=5)
scheduler.add_job(func=run_integrated_mission, trigger="interval", hours=CONFIG["INTERVAL_HOURS"], next_run_time=run_next)
scheduler.start()

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000)) 
    app.run(host='0.0.0.0', port=port)