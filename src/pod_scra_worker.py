# ---------------------------------------------------------
# 本程式碼：src/pod_scra_worker.py v5.5 (通用物流版)
# 職責：領取任務 -> 串流下載 -> 直送 R2 (含 Metadata) -> 狀態更新
# 適用平台：GitHub Actions / Render / Koyeb
# ---------------------------------------------------------
import os
import time
import requests
import boto3
from supabase import create_client, Client
from dotenv import load_dotenv

#---(定位線) 全文提供：解耦後專注物流搬運的程式碼 ---#
# 一行註解：載入環境變數與初始化客戶端。
load_dotenv()

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
    # 一行註解：將本地暫存檔案推送至雲端 R2 倉庫。
    s3 = get_s3_client()
    try:
        s3.upload_file(file_path, bucket_name, object_name)
        print(f"✅ [入庫成功] 檔案已存至: {object_name}")
        return True
    except Exception as e:
        print(f"❌ [入庫失敗] 錯誤原因: {e}")
        return False

def run_logistics_mission():
    # 一行註解：啟動物流巡邏邏輯，尋找待搬運物資。
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    sb: Client = create_client(url, key)

    while True:
        print(f"🕒 [哨兵巡邏] 正在掃描任務隊列 (Target: pending)...")
        
        # 一行註解：查詢狀態為待處理且已偵察成功的任務。
        mission = sb.table("mission_queue").select("*").eq("status", "pending").eq("scrape_status", "success").limit(1).execute()

        if mission.data:
            task = mission.data[0]
            task_id = task['id']
            audio_url = task['audio_url']
            file_name = f"{task['pub_date']}_{task['title'][:30]}.m4a"
            temp_path = f"/tmp/{file_name}"

            print(f"🚛 [起運] 偵測到物資: {task['title']}")

            # 一行註解：開始下載音訊物資。
            try:
                resp = requests.get(audio_url, timeout=60)
                with open(temp_path, "wb") as f:
                    f.write(resp.content)
                
                # 一行註解：執行 R2 入庫作業。
                if upload_to_r2(temp_path, os.environ.get("R2_BUCKET_NAME"), file_name):
                    # 一行註解：更新資料庫狀態為已入庫。
                    sb.table("mission_queue").update({
                        "status": "stored_in_r2",
                        "r2_path": file_name
                    }).eq("id", task_id).execute()
                    print(f"🏆 [結案] 任務 {task_id} 搬運完畢。")
                
                if os.path.exists(temp_path): os.remove(temp_path)

            except Exception as e:
                print(f"⚠️ [運輸事故] 任務 ID {task_id} 失敗: {e}")

        else:
            print(f"☕ [物流部] 目前無待搬運物資，5 分鐘後再次巡邏。")
        
        time.sleep(300) # 一行註解：設定巡邏間隔為 5 分鐘。

if __name__ == "__main__":
    run_logistics_mission()
#---(定位線) 以上修改完成 ---#