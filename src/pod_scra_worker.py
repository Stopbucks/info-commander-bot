# ---------------------------------------------------------
# 本程式碼：src/pod_scra_worker.py v8.0 (新舊混編序列版)
# 職責：2新1舊任務混編 -> 序列下載 -> 動態 Jitter -> 直送 R2
# ---------------------------------------------------------
import os
import time
import json
import requests
import boto3
import re
import random
from datetime import datetime, timezone, timedelta
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

def get_secret(key, default=None):
    # 跨環境憑證識別器，優先讀取內部 Vault。
    vault_path = "/etc/secrets/render_secret_vault.json"
    if os.path.exists(vault_path):
        with open(vault_path, 'r') as f:
            vault = json.load(f)
            val = vault.get("active_credentials", {}).get(key)
            if val: return val
    return os.environ.get(key, default)

def get_supabase_client() -> Client:
    url = get_secret("SUPABASE_URL", "").strip()
    key = get_secret("SUPABASE_KEY", "").strip()
    if not url or not key:
        raise ValueError("❌ [錯誤] Supabase 憑證缺失")
    return create_client(url, key)

def get_s3_client():
    return boto3.client(
        's3',
        endpoint_url=get_secret("R2_ENDPOINT_URL"),
        aws_access_key_id=get_secret("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=get_secret("R2_SECRET_ACCESS_KEY"),
        region_name="auto"
    )

def sanitize_filename(text, max_length):
    clean_text = re.sub(r'[\\/*?:"<>|]', "", text)
    return clean_text[:max_length].strip()

def check_and_rotate_shift(sb: Client, current_worker: str):
    res = sb.table("pod_scra_tactics").select("*").eq("id", 1).execute()
    if not res.data: return False
    
    tactics = res.data[0]
    active_worker = tactics.get("active_worker")
    duty_start_str = tactics.get("duty_start_at", "").replace("Z", "+00:00")
    
    try:
        duty_start = datetime.fromisoformat(duty_start_str)
    except ValueError:
        duty_start = datetime.now(timezone.utc)
        
    rotation_hours = tactics.get("rotation_hours", 48)
    now = datetime.now(timezone.utc)
    
    if active_worker == current_worker and now > duty_start + timedelta(hours=rotation_hours):
        roster = ["RENDER", "KOYEB", "ZEABUR", "GITHUB"]
        next_idx = (roster.index(current_worker) + 1) % len(roster)
        next_worker = roster[next_idx]
        
        print(f"⏰ [輪值交接] {current_worker} 役期屆滿，交棒給 {next_worker}...")
        sb.table("pod_scra_tactics").update({
            "active_worker": next_worker,
            "duty_start_at": now.isoformat(),
            "last_error_type": "ROTATION_SCHEDULE"
        }).eq("id", 1).execute()
        return False 
        
    if active_worker != current_worker:
        print(f"🛌 [待命中] 目前值星官為 {active_worker}，{current_worker} 繼續休眠...")
        return False
        
    return True

def run_logistics_mission():
    # === 🛠️ 戰術參數配置區 (易於維護) ===
    WORKER_ID = get_secret("WORKER_ID", "UNKNOWN").upper()
    NEW_MISSION_LIMIT = 2    # 每次搬運最新物資的數量
    OLD_MISSION_LIMIT = 1    # 每次搬運最舊物資的數量
    DEEP_SLEEP_HOURS = 12    # 完成批次後的隱蔽休眠時間
    # ===================================

    print(f"🚀 [啟動] 運輸兵 ({WORKER_ID}) 準備就緒。")
    sb = get_supabase_client()
    s3 = get_s3_client()
    r2_bucket = get_secret("R2_BUCKET_NAME")

    while True:
        try:
            if not check_and_rotate_shift(sb, WORK_ID := WORKER_ID):
                time.sleep(3600) 
                continue

            print(f"🕒 [{WORKER_ID} 執勤中] 正在領取混編任務 (目標: {NEW_MISSION_LIMIT}新 + {OLD_MISSION_LIMIT}舊)...")
            
            # 領取最新任務。
            new_tasks = sb.table("mission_queue").select("*").eq("status", "pending")\
                .eq("scrape_status", "success").order("created_at", desc=True).limit(NEW_MISSION_LIMIT).execute()
            
            # 領取最舊任務 (排除剛才已選中的 ID 以防重複)。
            excluded_ids = [t['id'] for t in new_tasks.data]
            old_tasks = sb.table("mission_queue").select("*").eq("status", "pending")\
                .eq("scrape_status", "success").not_.in_("id", excluded_ids)\
                .order("created_at", desc=False).limit(OLD_MISSION_LIMIT).execute()
            
            # 任務合流。
            combined_missions = new_tasks.data + old_tasks.data
            
            if combined_missions:
                total = len(combined_missions)
                print(f"📦 [清點完畢] 本次序列搬運共計 {total} 筆任務。")

                for idx, task in enumerate(combined_missions):
                    task_id = task['id']
                    audio_url = task['audio_url']
                    source_name = task.get('source_name', 'UnknownChannel')
                    episode_title = task.get('episode_title', 'UnknownTitle')
                    
                    fetch_date = datetime.now(timezone.utc).strftime("%Y%m%d")
                    file_name = f"{fetch_date}_{sanitize_filename(source_name, 25)}_{sanitize_filename(episode_title, 80)}.m4a"
                    temp_path = f"/tmp/{file_name}"

                    print(f"🚛 [運輸中 {idx+1}/{total}] 鎖定: {file_name}")

                    # 串流下載。
                    resp = requests.get(audio_url, timeout=60, stream=True)
                    resp.raise_for_status()
                    with open(temp_path, "wb") as f:
                        for chunk in resp.iter_content(chunk_size=8192): f.write(chunk)
                    
                    # 測量大小以決定 Jitter 策略。
                    file_size_mb = os.path.getsize(temp_path) / (1024 * 1024)
                    print(f"📏 [規格確認] 檔案大小: {file_size_mb:.2f} MB")

                    # 直送 R2。
                    s3.upload_file(temp_path, r2_bucket, file_name)
                    
                    # 更新狀態。
                    sb.table("mission_queue").update({"status": "completed", "r2_url": file_name}).eq("id", task_id).execute()
                    print(f"✅ [成功入庫] 任務 {task_id} 已結案。")
                    if os.path.exists(temp_path): os.remove(temp_path)

                    # 序列間隔 Jitter 邏輯。
                    if idx < total - 1:
                        if file_size_mb < 20:
                            wait_time = random.randint(300, 600) # 5~10 分鐘
                        else:
                            wait_time = random.randint(600, 1200) # 10~20 分鐘
                        print(f"⏳ [隨機干擾] 等待 {wait_time//60} 分鐘後執行下一筆...")
                        time.sleep(wait_time)

                print(f"🧊 [任務完成] 批次清空，進入 {DEEP_SLEEP_HOURS} 小時深度休眠...")
                time.sleep(DEEP_SLEEP_HOURS * 3600)
                
            else:
                print(f"☕ [物流部] 目前無待搬運物資，1 小時後再次巡邏。")
                time.sleep(3600)
        
        except Exception as e:
            print(f"⚠️ [異常]：{e}")
            time.sleep(300)

if __name__ == "__main__":
    run_logistics_mission()