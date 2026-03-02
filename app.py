
# ---------------------------------------------------------
# S-Plan Fortress v1.8 最終整合修正版
# 任務：1. 心跳 2. AI 接力(AB組) 3. 役期交接 4. 物流下載
# ---------------------------------------------------------

import os, time, json, requests, boto3, re, random, feedparser, threading
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify, request
from supabase import create_client
from bs4 import BeautifulSoup
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

# === 🎖️ 情報特種兵作戰控制面板 ===
INTEL_AUDIO_OFFICERS = ["ZEABUR"] 
INTEL_TXT_OFFICERS = ["KOYEB"] 

CONFIG = {
    "WORKER_ID": os.environ.get("WORKER_ID", "UNKNOWN_NODE"),
    "INTERVAL_HOURS": 2,
    "NEW_LIMIT": 2,
    "OLD_LIMIT": 1,
    "JITTER_BASE_MIN": 180,
    "JITTER_BASE_MAX": 360,
    "CRON_SECRET": os.environ.get("CRON_SECRET")
}

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
            print(f"🎤 [音訊組] {worker} 啟動：執行轉譯任務。")
            from src.pod_scra_intel_core import run_audio_to_stt_mission
            threading.Thread(target=run_audio_to_stt_mission).start()
        elif worker in INTEL_TXT_OFFICERS:
            print(f"✍️ [文字組] {worker} 啟動：執行摘要任務。")
            from src.pod_scra_intel_core import run_stt_to_summary_mission
            threading.Thread(target=run_stt_to_summary_mission).start()
    except Exception as e:
        print(f"⚠️ [AI觸發異常]: {e}")

# --- 🕵️ 核心巡邏邏輯 ---
def run_integrated_mission():
    sb = get_sb(); now = datetime.now(timezone.utc); now_iso = now.isoformat()
    print(f"🚀 [{CONFIG['WORKER_ID']}] 潛行巡邏啟動...")

    try:
        # 1. 取得最新戰術清單
        t_res = sb.table("pod_scra_tactics").select("*").eq("id", 1).single().execute()
        if not t_res.data: return
        tactic = t_res.data
        
        # 2. 心跳簽到
        health = tactic.get('workers_health', {}) or {}
        health[CONFIG['WORKER_ID']] = now_iso
        sb.table("pod_scra_tactics").update({"last_heartbeat_at": now_iso, "workers_health": health}).eq("id", 1).execute()
        print(f"💓 心跳簽到成功。")

        # 3. 啟動 AI 接力賽 (獨立執行，不影響主線)
        trigger_intel_pipeline()

        # 4. 判定是否為值勤主將
        is_my_turn = (tactic['active_worker'] == CONFIG['WORKER_ID'])
        roster = tactic.get('worker_roster', [])

        # 5. 役期與交接檢查
        duty_start_str = tactic.get('duty_start_at', now_iso).replace('Z', '+00:00')
        duty_start = datetime.fromisoformat(duty_start_str)
        rotation_hours = tactic.get('rotation_hours', 48)
        is_expired = (now > duty_start + timedelta(hours=rotation_hours))

        if is_my_turn and is_expired:
            curr_idx = roster.index(CONFIG['WORKER_ID']) if CONFIG['WORKER_ID'] in roster else 0
            new_active = roster[(curr_idx + 1) % len(roster)]
            new_next = roster[(curr_idx + 2) % len(roster)]
            print(f"⏰ [交接] 移交予: {new_active}")
            sb.table("pod_scra_tactics").update({
                "active_worker": new_active, "next_worker": new_next,
                "duty_start_at": now_iso, "consecutive_soft_failures": 0 
            }).eq("id", 1).execute()
            return 

        if not is_my_turn:
            print(f"🛌 [待命] 目前由 {tactic['active_worker']} 執行下載任務。")
            return

        # 6. 執行【物流下載】任務 (2新+1舊)
        print("🚛 [物流開火] 下載程序啟動...")
        query_base = sb.table("mission_queue").select("*, mission_program_master(*)") \
                       .eq("scrape_status", "success").lte("troop2_start_at", now_iso)

        new_tasks = query_base.order("created_at", desc=True).limit(CONFIG['NEW_LIMIT']).execute().data or []
        old_tasks = query_base.not_.in_("id", [t['id'] for t in new_tasks]).order("created_at", desc=False).limit(CONFIG['OLD_LIMIT']).execute().data or []
        
        missions = new_tasks + old_tasks
        if not missions:
            print("☕ 暫無到期待搬運任務。")
            return

        s3 = get_s3(); bucket = os.environ.get("R2_BUCKET_NAME")
        for idx, m in enumerate(missions):
            task_id, f_audio = m['id'], m.get('audio_url')
            if not f_audio: continue
            
            try:
                # 注意：這裡我們暫時維持 MP3 下載，直到 GHA 完全接管 Opus 壓縮
                file_name = f"{now.strftime('%Y%m%d')}_{task_id[:8]}.mp3"
                tmp_path = f"/tmp/{file_name}"
                
                with requests.get(f_audio, stream=True, timeout=120) as r:
                    r.raise_for_status()
                    with open(tmp_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
                
                s3.upload_file(tmp_path, bucket, file_name)
                sb.table("mission_queue").update({
                    "scrape_status": "completed", "r2_url": file_name, 
                    "recon_persona": f"{CONFIG['WORKER_ID']}_v1.8_Stealth" 
                }).eq("id", task_id).execute()
                
                print(f"✅ {file_name} 入庫完成。")
                if os.path.exists(tmp_path): os.remove(tmp_path)
                
                if idx < len(missions) - 1:
                    wait = random.randint(CONFIG['JITTER_BASE_MIN'], CONFIG['JITTER_BASE_MAX'])
                    print(f"⏳ [Jitter] 休息 {wait} 秒...")
                    time.sleep(wait)
            except Exception as e:
                print(f"❌ 搬運出錯: {e}")

    except Exception as e:
        print(f"⚠️ 巡邏系統總體崩潰: {e}")

# --- 📡 接口定義 ---
@app.route('/ping')
def trigger():
    token = request.args.get('token')
    if not token or token != CONFIG['CRON_SECRET']: return "Unauthorized", 401
    threading.Thread(target=run_integrated_mission).start()
    return f"📡 {CONFIG['WORKER_ID']} Fortress: Mission Triggered.", 202

@app.route('/')
def health(): return f"Fortress {CONFIG['WORKER_ID']} v1.8 Online", 200

# --- 🕒 背景排程 ---
scheduler = BackgroundScheduler()
scheduler.add_job(func=run_integrated_mission, trigger="interval", hours=CONFIG["INTERVAL_HOURS"])
scheduler.start()

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)