# ---------------------------------------------------------
# 本程式碼：src/pod_scra_logistics.py v1.0 (獨立物流兵)
# 任務：1. Jitter 避震 2. 從 Supabase 領單 3. 下載音檔並送達 R2
# ---------------------------------------------------------
import os, time, random, requests, boto3
from datetime import datetime, timezone
from supabase import create_client

def get_secret(k): return os.environ.get(k)

def run_logistics():
    # 🚀 Jitter：隨機等待 10 到 45 秒，避免與其他平台瞬間碰撞
    wait_time = random.randint(10, 45)
    print(f"🕒 [物流避震] 啟動前冷卻 {wait_time} 秒...")
    time.sleep(wait_time)

    sb = create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))
    s3 = boto3.client('s3', endpoint_url=get_secret("R2_ENDPOINT_URL"),
                      aws_access_key_id=get_secret("R2_ACCESS_KEY_ID"),
                      aws_secret_access_key=get_secret("R2_SECRET_ACCESS_KEY"), region_name="auto")
    bucket = get_secret("R2_BUCKET_NAME")
    now_iso = datetime.now(timezone.utc).isoformat()
    
    # 領取任務
    query = sb.table("mission_queue").select("*").eq("scrape_status", "success").lte("troop2_start_at", now_iso).limit(1).execute().data
    
    if not query:
        print("☕ [物流] 任務庫清空，目前無待搬運音檔。")
        return

    m = query[0]
    task_id = m['id']
    title = m.get('episode_title', "Untitled")
    f_audio = m.get('audio_url')
    
    print(f"🎯 [物流攻堅] 開始搬運: {title[:30]}")

    if f_audio:
        file_name = f"{datetime.now(timezone.utc).strftime('%Y%m%d')}_{task_id[:8]}.mp3"
        tmp_path = f"/tmp/{file_name}"
        
        try:
            with requests.get(f_audio, stream=True, timeout=180) as r:
                r.raise_for_status()
                with open(tmp_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
            
            s3.upload_file(tmp_path, bucket, file_name)
            
            sb.table("mission_queue").update({
                "scrape_status": "completed", "r2_url": file_name, 
                "recon_persona": "GITHUB_v5.0" 
            }).eq("id", task_id).execute()
            
            print(f"✅ [物流成功] {file_name} 已安全送達 R2。")
        except Exception as e:
            print(f"🚛 [物流異常]: {e}")
        finally:
            if os.path.exists(tmp_path): os.remove(tmp_path)

if __name__ == "__main__":
    run_logistics()