# ---------------------------------------------------------
# app.py (V5.3 主力 512MB 輕鬆回訊與非同步防禦版)
# 適用：RENDER, KOYEB, ZEABUR | 規格：512MB (MEMORY_TIER="512")
# [任務] 1. 接口防震 (秒回202) 2. 60分破冰守衛 3. 崩潰判官通報 4. 驅動全軍狀態機
# [機制] 外部呼叫 /ping 時，無論 MISSION_LOCK 是否被佔用，皆立即回傳 202 Accepted。
# [機制] 拒絕 429 報錯！真正的情報產線會被打包成 Thread，在背景「非同步」默默執行。
# [守衛] 若背景任務卡死超過 WATCHDOG_TIMEOUT (60分)，下次 ping 將強制擊碎門鎖自救。
# [修改] 1. 導入 Fire-and-Forget 秒回模式，徹底消除 UptimeRobot 等外部監控的誤報。
# [修改] 2. 將 MISSION_LOCK 上鎖判定移入背景，確保 Scheduler 與 API 呼叫皆受絕對保護。
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

# 🚀 宣告火力為 512MB 主力部隊！
os.environ["MEMORY_TIER"] = "512"

# 🛡️ 破冰守衛 (Watchdog) 系統配置
MISSION_LOCK = threading.Lock()
MISSION_STATE = {"is_running": False, "start_time": 0.0}
# 搭配 core.py 的 25 分鐘軟撤退，這裡設 60 分鐘作為最後硬防線
WATCHDOG_TIMEOUT = 3600  

def get_sb(): 
    return create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))

def s_log(sb, task_type, status, message, err_stack=None):
    try:
        print(f"[{task_type}][{status}] {message}", flush=True)
        if status in ["SUCCESS", "ERROR"] or "啟動" in message or "V5.3" in message:
            sb.table("mission_logs").insert({
                "worker_id": CONFIG["WORKER_ID"], "task_type": task_type,
                "status": status, "message": message, "traceback": err_stack
            }).execute()
    except: pass

def report_soft_failure(sb, worker_id, error_msg):
    """【系統自救】精準軟失敗通報：嚴格區分主將與後勤兵"""
    try:
        print(f"🚨 [通報判官] 發生異常，正在評估影響範圍...", flush=True)
        res = sb.table("pod_scra_tactics").select("active_worker, consecutive_soft_failures, worker_status").eq("id", 1).single().execute()
        if not res.data: return
        
        tactic = res.data
        active_worker = tactic.get("active_worker")
        current_fails = tactic.get("consecutive_soft_failures", 0)
        
        if worker_id == active_worker:
            sb.table("pod_scra_tactics").update({
                "consecutive_soft_failures": current_fails + 1,
                "last_error_type": f"🚨 [主將] {worker_id} 崩潰: {error_msg}"[:200]
            }).eq("id", 1).execute()
            print(f"⚠️ 身為主將，已觸發軟失敗計數 ({current_fails + 1}/3)")
        else:
            w_status = tactic.get("worker_status", {})
            w_status[f"{worker_id}_last_err"] = str(error_msg)[:100]
            sb.table("pod_scra_tactics").update({
                "worker_status": w_status,
                "last_error_type": f"⚠️ [後勤] {worker_id} 局部異常: {error_msg}"[:200]
            }).eq("id", 1).execute()
            print(f"ℹ️ 身為後勤兵，已將異常寫入日誌，不影響主將輪替。")
            
    except Exception as e: 
        print(f"通報系統本身發生異常: {e}")

def run_integrated_mission():
    """【任務大腦】將鎖定邏輯移入，確保排程與 API 呼叫都受保護"""
    global MISSION_STATE
    
    # --- 🚪 嘗試進入主防線 ---
    if not MISSION_LOCK.acquire(blocking=False):
        print("🔒 [防線守衛] 機甲正在執行任務，本次呼叫/排程將在背景被忽略。", flush=True)
        return

    sb = get_sb()
    MISSION_STATE["is_running"] = True
    MISSION_STATE["start_time"] = time.time()
    
    try:
        # 🚀 專屬信號彈
        s_log(sb, "SYSTEM", "SUCCESS", f"🚀 [{CONFIG['WORKER_ID']} V5.3] 主力部隊連線，輕鬆回訊與非同步防禦就位！")
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
def health(): return f"Fortress {CONFIG['WORKER_ID']} V5.3 Active", 200

@app.route('/ping')
def trigger():
    global MISSION_STATE
    token = request.args.get('token')
    if not token or token != CONFIG['CRON_SECRET']: return "Unauthorized", 401
    
    current_time = time.time()
    response_msg = "Mission Triggered (Async)"
    
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
            # 🚀 輕鬆回訊：如果在忙，直接笑著說 OK 並附上進度，不再報錯 429！
            return f"Already running ({elapsed:.0f}s elapsed). {response_msg}", 202

    # --- 🚀 非同步啟動：立刻回傳 202 給呼叫者，讓工作在背景執行 ---
    threading.Thread(target=run_integrated_mission, daemon=True).start()
    
    return response_msg, 202

# 內部備用排程器
scheduler = BackgroundScheduler()
run_next = datetime.now() + timedelta(minutes=5)
scheduler.add_job(func=run_integrated_mission, trigger="interval", hours=CONFIG["INTERVAL_HOURS"], next_run_time=run_next)
scheduler.start()

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000)) 
    app.run(host='0.0.0.0', port=port)