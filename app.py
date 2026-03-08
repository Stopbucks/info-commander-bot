# ---------------------------------------------------------
# S-Plan Fortress v4.1   (2026 RENDER + KOYEB；512MB 記憶體)
# 任務：1. 接口防震 2. 指令下達 3. 排程管理 4. 線程安全鎖
# 核心：本檔案僅負責「流程調控」，具體「物流/AI」由 src/ 模組執行
# ---------------------------------------------------------
import os, time, json, requests, random, threading, traceback, gc
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify, request
from supabase import create_client
from apscheduler.schedulers.background import BackgroundScheduler

# 🚀 核心模組導入 (分割後的邏輯)
from src.pod_scra_intel_trans import execute_fortress_stages 

app = Flask(__name__)

# === 🎖️ 指揮部配置 ===
# 任務編組：定義哪些節點需要執行轉譯或摘要
INTEL_AUDIO_OFFICERS = ["FLY_LAX", "RENDER", "HUGGINGFACE", "KOYEB"] 
INTEL_TXT_OFFICERS =   ["FLY_LAX", "RENDER", "HUGGINGFACE", "KOYEB"]

CONFIG = {
    "WORKER_ID": os.environ.get("WORKER_ID", "UNKNOWN_NODE"),
    "INTERVAL_HOURS": 2,
    "CRON_SECRET": os.environ.get("CRON_SECRET"),
    "JITTER_BASE_MIN": 180, "JITTER_BASE_MAX": 360, # 隨機抖動區間 (秒)
    "RETRY_TOTAL": 2
}

# --- 🛠️ 指揮部輔助工具 ---

def s_log(sb, task_type, status, message, err_stack=None):
    """標準化戰情紀錄"""
    try:
        print(f"[{task_type}][{status}] {message}")
        if status in ["SUCCESS", "ERROR"] or "啟動" in message:
            sb.table("mission_logs").insert({
                "worker_id": CONFIG["WORKER_ID"], "task_type": task_type,
                "status": status, "message": message, "traceback": err_stack
            }).execute()
    except: pass

def get_sb(): 
    """獲取資料庫連線"""
    return create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))

def get_s3():
    """獲取 R2 倉庫連線 (交由 trans 模組呼叫)"""
    import boto3 # 延遲載入以節省啟動內存
    return boto3.client('s3', endpoint_url=os.environ.get("R2_ENDPOINT_URL"),
                        aws_access_key_id=os.environ.get("R2_ACCESS_KEY_ID"),
                        aws_secret_access_key=os.environ.get("R2_SECRET_ACCESS_KEY"), region_name="auto")

# 🛡️ 戰術防護鎖：防止 256MB/512MB 被併發請求衝垮
MISSION_LOCK = threading.Lock()
IS_RUNNING = False

# --- 🛰️ AI 情報工廠線 (裝甲強化版) ---

def trigger_intel_pipeline(sb):
    """呼叫 AI 加工中心執行轉譯與摘要"""
    worker = CONFIG["WORKER_ID"]
    try:
        gc.collect() # 啟動前清理
        
        # 1. 音訊轉譯接力
        if worker in INTEL_AUDIO_OFFICERS: 
            from src.pod_scra_intel_core import run_audio_to_stt_mission 
            s_log(sb, "AI", "INFO", f"🎤 [音訊組] {worker} 啟動轉譯流水線")
            run_audio_to_stt_mission() 
            gc.collect()
        
        # 給系統 30 秒冷卻，讓內存寫入 Swap 或完全釋放
        time.sleep(30) 

        # 2. 文字摘要接力
        if worker in INTEL_TXT_OFFICERS: 
            from src.pod_scra_intel_core import run_stt_to_summary_mission
            s_log(sb, "AI", "INFO", f"✍️ [文字組] {worker} 啟動摘要加工")
            run_stt_to_summary_mission() 
            gc.collect()
            
    except Exception as e:
        print(f"⚠️ [AI流水線異常]: {e}")
        gc.collect()

# --- 🚛 綜合巡邏任務 (總引擎加固版) ---
def run_integrated_mission():
    """本函式作為『發令官』，強化了內存與連線回收機制"""
    global IS_RUNNING
    if MISSION_LOCK.locked(): 
        return

    with MISSION_LOCK:
        IS_RUNNING = True 
        sb = None
        try:
            sb = get_sb()
            # 🚀 序列化指令下達：嚴格按照 1.簽到 2.AI加工 3.物流 的順序
            execute_fortress_stages(
                sb=sb,
                config=CONFIG,
                s_log_func=s_log,
                trigger_intel_func=trigger_intel_pipeline,
                get_s3_func=get_s3,
                officers_list=INTEL_AUDIO_OFFICERS
            )
        except Exception as e:
            print(f"💥 戰場大崩潰: {e}")
            traceback.print_exc()
        finally:
            # 🚀 鋼鐵防線：強制銷毀對象與回收內存
            if sb: del sb
            IS_RUNNING = False
            gc.collect()
            print("🏁 [巡邏結束] 指揮中心已釋放所有資源並重置 READY。")

# --- 📡 接口與排程 ( 512MB 裝甲通用版) ---

@app.route('/')
def health(): 
    # 🚀 輕量化安檢：降低 LOG 堆積壓力
    print(f"🔔 [{CONFIG['WORKER_ID']} 安檢] 收到巡檢請求，系統正常。")
    return f"Fortress {CONFIG['WORKER_ID']} v4.1 (Active Defense) Online", 200


@app.route('/ping')
def trigger():
    global IS_RUNNING
    # 🚀 1：第一道門防衛 (優先權限核驗，減少無效開銷)
    token = request.args.get('token')
    if not token or token != CONFIG['CRON_SECRET']:
        return "Unauthorized", 401
    
    # 🚀 2：第二道門防衛 (瞬發 Busy Check，不進入 sleep)
    if IS_RUNNING or MISSION_LOCK.locked():
        return "Too Many Requests - Mission in Progress", 429

    # 🚀 3：避震抖動 (僅對獲准者執行延遲)
    time.sleep(random.uniform(3.0, 8.0))

    # 🚀 4：雙重確認 (Double-Check)，確保延遲期間無併發任務
    if IS_RUNNING or MISSION_LOCK.locked():
        return "Locked", 429

    # 🚀 5： 點火執行
    threading.Thread(target=run_integrated_mission, daemon=True).start()
    return f"Mission Triggered", 202

# 🕒 排程啟動系統 (修正啟動邏輯)
scheduler = BackgroundScheduler()
# 🚀 延遲 5 分鐘後啟動首次自動巡邏，避開部署初期的資源尖峰
run_next = datetime.now() + timedelta(minutes=5)
scheduler.add_job(
    func=run_integrated_mission, 
    trigger="interval", 
    hours=CONFIG["INTERVAL_HOURS"],
    next_run_time=run_next
)
scheduler.start()

if __name__ == "__main__":
    # 🚀 自動偵測雲端環境 Port (Render 預設 10000, Koyeb 預設 8080)
    port = int(os.environ.get('PORT', 10000)) 
    app.run(host='0.0.0.0', port=port)