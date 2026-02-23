# ---------------------------------------------------------
# 本程式碼：src/pod_scra_worker.py v7.0 (解耦值星版)
# 職責：讀取戰術板 -> 48H輪替 -> 極低頻搬運 -> 檔名規格化
# ---------------------------------------------------------
import os
import time
import json
import requests
import boto3
import re
from datetime import datetime, timezone, timedelta
from supabase import create_client, Client
from dotenv import load_dotenv

# 一行註解：啟動環境變數加載。
load_dotenv()

def get_secret(key, default=None):
    # 一行註解：跨環境憑證識別器，優先讀取內部 Vault，若無則回退至環境變數。
    vault_path = "/etc/secrets/render_secret_vault.json"
    if os.path.exists(vault_path):
        with open(vault_path, 'r') as f:
            vault = json.load(f)
            val = vault.get("active_credentials", {}).get(key)
            if val: return val
    return os.environ.get(key, default)

def get_supabase_client() -> Client:
    # 一行註解：統一由憑證識別器獲取 Supabase 連線資訊。
    url = get_secret("SUPABASE_URL", "").strip()
    key = get_secret("SUPABASE_KEY", "").strip()
    if not url or not key:
        raise ValueError("❌ [錯誤] Supabase 憑證缺失")
    return create_client(url, key)

def get_s3_client():
    # 一行註解：建立與 R2 倉庫的通訊連接。
    return boto3.client(
        's3',
        endpoint_url=get_secret("R2_ENDPOINT_URL"),
        aws_access_key_id=get_secret("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=get_secret("R2_SECRET_ACCESS_KEY"),
        region_name="auto"
    )

def sanitize_filename(text, max_length):
    # 一行註解：移除非法路徑字元，保留文字、數字與基本符號，並截斷長度防溢出。
    clean_text = re.sub(r'[\\/*?:"<>|]', "", text)
    return clean_text[:max_length].strip()

def check_and_rotate_shift(sb: Client, current_worker: str):
    # 一行註解：檢視戰術板，確認是否輪到自己執勤，或是否需要交接。
    res = sb.table("pod_scra_tactics").select("*").eq("id", 1).execute()
    if not res.data: return False
    
    tactics = res.data[0]
    active_worker = tactics.get("active_worker")
    
    # 轉換 ISO 時間字串為 datetime 物件 (處理結尾 +00:00)
    duty_start_str = tactics.get("duty_start_at", "").replace("Z", "+00:00")
    try:
        duty_start = datetime.fromisoformat(duty_start_str)
    except ValueError:
        duty_start = datetime.now(timezone.utc)
        
    rotation_hours = tactics.get("rotation_hours", 48)
    now = datetime.now(timezone.utc)
    
    # 判斷是否到期需交接
    if active_worker == current_worker and now > duty_start + timedelta(hours=rotation_hours):
        # 一行註解：定義輪班順序，自動尋找下一任值星官。
        roster = ["RENDER", "KOYEB", "ZEABUR", "GITHUB"]
        next_idx = (roster.index(current_worker) + 1) % len(roster)
        next_worker = roster[next_idx]
        
        print(f"⏰ [輪值交接] {current_worker} 役期屆滿，交棒給 {next_worker}...")
        sb.table("pod_scra_tactics").update({
            "active_worker": next_worker,
            "duty_start_at": now.isoformat(),
            "last_error_type": "ROTATION_SCHEDULE"
        }).eq("id", 1).execute()
        return False # 交接後立刻下哨
        
    # 判斷目前是否為自己執勤
    if active_worker != current_worker:
        print(f"🛌 [待命中] 目前值星官為 {active_worker}，{current_worker} 繼續休眠...")
        return False
        
    return True

def run_logistics_mission():
    # 一行註解：抓取當前兵種代號 (必須在雲端後台設定 WORKER_ID 變數)。
    worker_id = get_secret("WORKER_ID", "UNKNOWN").upper()
    
    print(f"🚀 [啟動] 運輸兵 ({worker_id}) 準備就緒。")
    sb = get_supabase_client()
    s3 = get_s3_client()
    r2_bucket = get_secret("R2_BUCKET_NAME")

    while True:
        try:
            # 一行註解：先核對戰術板，不是自己的班就進入長休眠。
            if not check_and_rotate_shift(sb, worker_id):
                time.sleep(3600) # 非值班期間，每小時醒來確認一次班表即可
                continue

            print(f"🕒 [{worker_id} 執勤中] 正在掃描任務隊列 (Target: pending)...")
            
            # 一行註解：單發點射模式，每次只抓取 1 筆待處理物資。
            mission = sb.table("mission_queue").select("*").eq("status", "pending").eq("scrape_status", "success").limit(1).execute()
            
            if mission.data:
                task = mission.data[0]
                task_id = task['id']
                audio_url = task['audio_url']
                
                # 一行註解：萃取節目頻道與單集標題，保留原始字元以防去重誤判。
                source_name = task.get('source_name', 'UnknownChannel')
                episode_title = task.get('episode_title', 'UnknownTitle')
                
                # 一行註解：依照「抓取日_頻道25碼_標題80碼」規格化檔名。
                fetch_date = datetime.now(timezone.utc).strftime("%Y%m%d")
                clean_channel = sanitize_filename(source_name, 25)
                clean_title = sanitize_filename(episode_title, 80)
                
                file_name = f"{fetch_date}_{clean_channel}_{clean_title}.m4a"
                temp_path = f"/tmp/{file_name}"

                print(f"🚛 [起運] 鎖定物資: {file_name}")

                # 一行註解：使用串流下載以節省內存空間，掛載 60 秒 Timeout 護盾。
                resp = requests.get(audio_url, timeout=60, stream=True)
                resp.raise_for_status()
                
                with open(temp_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                # 一行註解：將暫存檔案推送至 R2 倉庫。
                s3.upload_file(temp_path, r2_bucket, file_name)
                print(f"✅ [入庫成功] 檔案已存至: {file_name}")
                
                # 一行註解：精準對位 r2_url 欄位，並將狀態更新為 completed。
                sb.table("mission_queue").update({
                    "status": "completed",
                    "r2_url": file_name
                }).eq("id", task_id).execute()
                
                print(f"🏆 [結案] 任務 {task_id} 搬運完畢。")
                if os.path.exists(temp_path): os.remove(temp_path)
                
                # 一行註解：防封鎖極低頻冷卻，搬完 1 筆後直接強制休眠 12 小時 (一天兩次)。
                print("🧊 [極限隱蔽] 進入 12 小時深度休眠...")
                time.sleep(43200) # 12 小時 = 43200 秒
                continue # 休眠結束後重新進入下一次 while 循環

            else:
                print(f"☕ [物流部] 目前無待搬運物資，1 小時後再次巡邏。")
                time.sleep(3600)
        
        except Exception as e:
            print(f"⚠️ [巡邏波動] 異常回報: {e}")
            time.sleep(300) # 發生報錯時，冷卻 5 分鐘再試

if __name__ == "__main__":
    run_logistics_mission()