# ---------------------------------------------------------
# 本程式碼：src/pod_scra_worker.py v5.7 (語法修正版)
# 職責：領取任務 -> 串流下載 -> 直送 R2 -> 狀態更新
# ---------------------------------------------------------
import os
import time
import requests
import boto3
from supabase import create_client, Client
from dotenv import load_dotenv

# 一行註解：啟動環境變數加載。
load_dotenv()

def get_supabase_client():
    # 一行註解：獲取並強制修剪變數空白以防認證錯誤。
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_KEY", "").strip()
    
    if not url or not key:
        print("❌ [錯誤] 環境變數讀取失敗，請檢查設定")
        return None

    try:
        # 一行註解：建立與 Supabase 的認證連線。
        return create_client(url, key)
    except Exception as e:
        print(f"❌ [連線報錯] {str(e)}")
        raise e

def get_s3_client():
    # 一行註解：建立與 R2 倉庫的通訊連接。
    return boto3.client(
        's3',
        endpoint_url=os.environ.get("R2_ENDPOINT_URL"),
        aws_access_key_id=os.environ.get("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("R2_SECRET_ACCESS_KEY"),
        region_name="auto"
    )

def upload_to_r2(file_path, bucket_name, object_name):
    # 一行註解：將暫存檔案推送至 R2 倉庫。
    s3 = get_s3_client()
    try:
        s3.upload_file(file_path, bucket_name, object_name)
        print(f"✅ [入庫成功] 檔案已存至: {object_name}")
        return True
    except Exception as e:
        print(f"❌ [入庫失敗] 錯誤原因: {e}")
        return False

def run_logistics_mission():
    # 一行註解：啟動自動化物流巡邏。
    sb = get_supabase_client()
    
    if not sb:
        print("❌ [物流部] 通行證校驗失敗，任務中止。")
        return

    while True:
        print(f"🕒 [哨兵巡邏] 正在掃描任務隊列 (Target: pending)...")
        
        try:
            # 一行註解：抓取待處理且偵察成功的任務。
            mission = sb.table("mission_queue").select("*").eq("status", "pending").eq("scrape_status", "success").limit(1).execute()
            
            if mission.data:
                task = mission.data[0]
                task_id = task['id']
                audio_url = task['audio_url']
                file_name = f"{task['pub_date']}_{task['title'][:30]}.m4a"
                temp_path = f"/tmp/{file_name}"

                print(f"🚛 [起運] 偵測到物資: {task['title']}")

                # 一行註解：使用串流下載以節省內存空間。
                resp = requests.get(audio_url, timeout=60, stream=True)
                resp.raise_for_status()
                
                with open(temp_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                if upload_to_r2(temp_path, os.environ.get("R2_BUCKET_NAME"), file_name):
                    # 一行註解：完成後同步更新資料庫狀態。
                    sb.table("mission_queue").update({
                        "status": "stored_in_r2",
                        "r2_path": file_name
                    }).eq("id", task_id).execute()
                    print(f"🏆 [結案] 任務 {task_id} 搬運完畢。")
                
                if os.path.exists(temp_path): os.remove(temp_path)

            else:
                print(f"☕ [物流部] 目前無待搬運物資，5 分鐘後再次巡邏。")
        
        except Exception as e:
            print(f"⚠️ [巡邏波動] 異常回報: {e}")
            time.sleep(60)
            continue
        
        time.sleep(300)

if __name__ == "__main__":
    run_logistics_mission()