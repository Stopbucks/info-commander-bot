# ---------------------------------------------------------
# S-Plan Fortress v2.9.1 (2026 鋼鐵加固合併版)
# 任務：1. 心跳 2. AI 接力 3. 役期交接 4. 重型物流 5. 403 自動換班
# 修正：1. 加入 FLY_LAX 2. 修正階段 5 縮排錯誤 3. 強化 256MB 內存鎖定 4. 動態副檔名偵測
# ---------------------------------------------------------
import os, time, json, requests, boto3, re, random, feedparser, threading, traceback, gc
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify, request
from supabase import create_client
from apscheduler.schedulers.background import BackgroundScheduler
from urllib.parse import urlparse 

app = Flask(__name__)

# === 🎖️ 情報控制面板 ===
# 已修正 FLY_LAX 重複問題並確保各組名單正確
INTEL_AUDIO_OFFICERS = ["ZEABUR", "FLY_LAX", "RENDER", "HUGGINGFACE"] 
INTEL_TXT_OFFICERS = ["ZEABUR", "KOYEB", "RENDER", "HUGGINGFACE", "FLY_LAX"]

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

# 🛡️ 任務鎖定標籤：防止 256MB 內存被多執行緒併發爆破 (v2.9 核心防護)
MISSION_LOCK = threading.Lock()
IS_RUNNING = False

# === 🛡️ 任務調度器 (序列化 + GC 資源回收版) ===
def trigger_intel_pipeline(sb):
    worker = CONFIG["WORKER_ID"]
    try:
        # 1. 先跑音訊組任務
        if worker in INTEL_AUDIO_OFFICERS:
            from src.pod_scra_intel_core import run_audio_to_stt_mission
            s_log(sb, "AI", "INFO", f"🎤 [音訊組] {worker} 啟動轉譯")
            run_audio_to_stt_mission() # 🚀 直接執行
            gc.collect()

        # 給系統喘息時間，防止資料庫連線過載
        time.sleep(random.randint(15, 30))

        # 2. 接著跑文字組任務
        if worker in INTEL_TXT_OFFICERS:
            from src.pod_scra_intel_core import run_stt_to_summary_mission
            s_log(sb, "AI", "INFO", f"✍️ [文字組] {worker} 啟動摘要")
            run_stt_to_summary_mission() # 🚀 直接執行
            gc.collect()
            
    except Exception as e:
        print(f"⚠️ [AI序列異常]: {e}"); gc.collect()

def run_integrated_mission():
    global IS_RUNNING
    if IS_RUNNING: return
    with MISSION_LOCK:
        IS_RUNNING = True
        sb = get_sb(); now = datetime.now(timezone.utc); now_iso = now.isoformat()
        
        try:
            # --- 階段 1-3：心跳與 AI 序列化執行 ---
            t_res = sb.table("pod_scra_tactics").select("*").eq("id", 1).single().execute()
            if not t_res.data: return
            tactic = t_res.data
            
            # 心跳蓋章
            health = tactic.get('workers_health', {}) or {}
            health[CONFIG['WORKER_ID']] = now_iso
            sb.table("pod_scra_tactics").update({"last_heartbeat_at": now_iso, "workers_health": health}).eq("id", 1).execute()

            # 🚀 序列化執行 AI 任務 (轉譯 -> 摘要)
            trigger_intel_pipeline(sb)

            # --- 階段 4：身分判定 ---
            if tactic['active_worker'] != CONFIG['WORKER_ID']:
                print(f"🛌 [待命] 非主將身分，結束巡邏。"); return

            # --- 階段 5：重型物流 (遇錯即休模式) ---
            print("🚛 [物流開火] 準備提取 T2 物資...")
            query = sb.table("mission_queue").select("*, mission_program_master(*)")\
                      .eq("scrape_status", "success").eq("assigned_troop", "T2")\
                      .lte("troop2_start_at", now_iso)

            tasks = (query.order("created_at", desc=True).limit(CONFIG['NEW_LIMIT']).execute().data or []) + \
                    (query.order("created_at", desc=False).limit(CONFIG['OLD_LIMIT']).execute().data or [])
            
            if not tasks:
                print("☕ 戰區暫無待處理物資。")
            else:
                s3 = get_s3(); bucket = os.environ.get("R2_BUCKET_NAME")
                for idx, m in enumerate(tasks):
                    f_url = m.get('audio_url')
                    if not f_url: continue
                    target_domain = urlparse(f_url).netloc
                    if any(b_domain in target_domain for b_domain in my_blacklist):
                        print(f"⏩ [ROE規避] {target_domain}處於禁閉期，跳過。")
                        continue

                    # 動態偵測副檔名並建立暫存路徑
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
                        s_log(sb, "DOWNLOAD", "SUCCESS", f"✅ 物資入庫: {file_name}")
                    
                    except requests.exceptions.HTTPError as he:
                        if he.response.status_code == 403:
                            # 🚀 紀律調整：不自作主張換班，僅寫入報警，交給 Vercel 裁決
                            target_domain = urlparse(f_url).netloc
                            s_log(sb, "SYSTEM", "ERROR", f"🚫 403 封鎖！{target_domain}，等待裁決")
                            sb.table("pod_scra_tactics").update({
                                "last_error_type": f"403_BANNED_{target_domain}"
                            }).eq("id", 1).execute()
                            return # 立即停止，進入休息狀態
                    
                    except Exception as e:
                        s_log(sb, "DOWNLOAD", "ERROR", f"❌ 搬運失敗: {str(e)}")
                    
                    finally:
                        if os.path.exists(tmp_path): 
                            try: os.remove(tmp_path)
                            except: pass
                        gc.collect() # 任務間強制回收記憶體
                    
                    if idx < len(tasks) - 1: 
                        time.sleep(random.randint(CONFIG['JITTER_BASE_MIN'], CONFIG['JITTER_BASE_MAX']))

        except Exception as e:
            s_log(sb, "SYSTEM", "ERROR", f"💥 系統崩潰: {str(e)}", traceback.format_exc())
        finally:
            IS_RUNNING = False
            gc.collect()

# --- 📡 接口與排程設定 ---
@app.route('/ping')
def trigger():
    token = request.args.get('token')
    if not token or token != CONFIG['CRON_SECRET']: return "Unauthorized", 401
    threading.Thread(target=run_integrated_mission, daemon=True).start()
    return f"📡 {CONFIG['WORKER_ID']} Fortress: Mission Triggered.", 202

@app.route('/')
def health(): return f"Fortress {CONFIG['WORKER_ID']} v2.9.1 (Safety Lock Active) Online", 200

scheduler = BackgroundScheduler()
scheduler.add_job(func=run_integrated_mission, trigger="interval", hours=CONFIG["INTERVAL_HOURS"])
scheduler.start()

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)