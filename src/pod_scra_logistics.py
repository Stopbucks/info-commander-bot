# ---------------------------------------------------------
# 本程式碼：src/pod_scra_logistics.py v5.1 (終極閉合物流版)
# 任務：1. Jitter 避震 2. 領取到期任務(2新1舊) 3. 下載並上傳 R2 4. 隨機長冷卻
# ---------------------------------------------------------
import os, time, random, requests, boto3, re
from datetime import datetime, timezone
from supabase import create_client

def get_secret(k): return os.environ.get(k)

def get_sb(): return create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))

def get_s3():
    return boto3.client('s3', endpoint_url=get_secret("R2_ENDPOINT_URL"),
                        aws_access_key_id=get_secret("R2_ACCESS_KEY_ID"),
                        aws_secret_access_key=get_secret("R2_SECRET_ACCESS_KEY"), region_name="auto")

def run_logistics_mission():
    # === 🛠️ 戰術配置 ===
    NEW_LIMIT = 2        # 每次抓 2 筆最新
    OLD_LIMIT = 1        # 每次抓 1 筆最舊補漏
    SLEEP_MIN, SLEEP_MAX = 180, 360  # 下載完一筆後，休息 180~360 秒 (3~6分鐘)
    # ===================

    # 🚀 Jitter：啟動前隨機冷卻，避免平台碰撞
    init_wait = random.randint(10, 45)
    print(f"🕒 [物流避震] 啟動前冷卻 {init_wait} 秒...")
    time.sleep(init_wait)

    print(f"🚛 [GITHUB 物流兵] 正在整備物資...")
    sb = get_sb(); s3 = get_s3(); bucket = get_secret("R2_BUCKET_NAME")
    now_iso = datetime.now(timezone.utc).isoformat()
    
    # 1. 領取「偵察成功」且「已到開火時間」且「尚未搬運」的任務
    # 領最新 2 筆
    new_res = sb.table("mission_queue").select("*")\
                .eq("scrape_status", "success").eq("status", "pending")\
                .lte("troop2_start_at", now_iso)\
                .order("created_at", desc=True).limit(NEW_LIMIT).execute()
    
    # 領最舊 1 筆 (補漏)
    excluded = [t['id'] for t in new_res.data] if new_res.data else []
    old_res = sb.table("mission_queue").select("*")\
                .eq("scrape_status", "success").eq("status", "pending")\
                .lte("troop2_start_at", now_iso)\
                .not_.in_("id", excluded)\
                .order("created_at", desc=False).limit(OLD_LIMIT).execute()
    
    combined = (new_res.data or []) + (old_res.data or [])

    if not combined:
        print("☕ [物流部] 戰場清空，目前無到期待搬運物資。"); return

    print(f"📦 [掃描] 發現 {len(combined)} 筆到期物資，準備進入運輸線。")

    for idx, task in enumerate(combined):
        task_id = task['id']
        audio_url = task['audio_url']
        title = task.get('episode_title', 'Untitled')
        
        print(f"🚀 [搬運 {idx+1}/{len(combined)}] 正在下載: {title[:30]}...")
        
        try:
            file_name = f"{datetime.now(timezone.utc).strftime('%Y%m%d')}_{task_id[:8]}.mp3"
            temp_path = f"/tmp/{file_name}"
            
            # 下載音檔 (超時設為 180 秒確保大檔案安全)
            with requests.get(audio_url, stream=True, timeout=180) as r:
                r.raise_for_status()
                with open(temp_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
            
            # 送往 R2 金庫
            s3.upload_file(temp_path, bucket, file_name)
            
            # ✅ [關鍵更新]：同時標記 status 與 scrape_status，確保與 Transport 兵完美對接
            sb.table("mission_queue").update({
                "status": "completed", 
                "scrape_status": "completed",
                "r2_url": file_name,
                "recon_persona": "GHA_v5.1_Logistics"
            }).eq("id", task_id).execute()
            
            print(f"✅ [物流成功] 任務 {task_id} 已入庫。")
            if os.path.exists(temp_path): os.remove(temp_path)
            
            # 🕒 [指揮官要求]：下載完一筆後，執行長冷卻
            if idx < len(combined) - 1:
                wait = random.randint(SLEEP_MIN, SLEEP_MAX)
                print(f"⏳ [避震] 搬運完成。執行擬人化休息 {wait} 秒 (約 {wait/60:.1f} 分鐘)...")
                time.sleep(wait)

        except Exception as e:
            print(f"❌ [物流異常] 任務 {task_id}: {e}")

if __name__ == "__main__":
    run_logistics_mission()