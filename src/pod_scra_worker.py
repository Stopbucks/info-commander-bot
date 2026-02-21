# ---------------------------------------------------------
# 本程式碼：src/pod_scra_worker.py v5.5 (通用物流版)
# 職責：領取任務 -> 串流下載 -> 直送 R2 (含 Metadata) -> 狀態更新
# 適用平台：GitHub Actions / Render / Koyeb
# ---------------------------------------------------------
import os, requests, boto3, re, urllib3
from supabase import create_client, Client
from datetime import datetime

# 禁用 SSL 警告，保持 Koyeb/Render 日誌畫面整潔。
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- [區塊一：物流技術中心] ---
def stream_to_r2_with_metadata(mission_data, s3_client, bucket_name):
    """
    一行註解：執行零磁碟串流搬運，將 Supabase 關鍵數據封裝進 R2 Metadata 中。
    """
    # 🚀 檔名規格化：2026_02_21_標題_節目.m4a
    safe_title = re.sub(r'[\\/:*?"<>|]', '_', mission_data['episode_title'])[:50]
    safe_source = re.sub(r'[\\/:*?"<>|]', '_', mission_data['source_name'])
    final_name = f"{datetime.now().strftime('%Y_%m_%d')}_{safe_title}_{safe_source}.m4a"

    # 🚀 標籤注入 (Metadata Tagging)
    # 將 Supabase ID 與標題綁入標頭，AI 分析局未來可直接讀取。
    meta = {
        "supabase_id": str(mission_data['id']),
        "title": safe_title,
        "source": safe_source
    }

    try:
        with requests.get(mission_data['audio_url'], stream=True, timeout=60) as r:
            r.raise_for_status()
            # 一行註解：upload_fileobj 是處理大檔案且記憶體受限環境（如 Koyeb）的最佳方案。
            s3_client.upload_fileobj(r.raw, bucket_name, final_name, 
                                     ExtraArgs={'ContentType': 'audio/mpeg', 'Metadata': meta})
        return final_name
    except Exception as e:
        print(f"❌ [傳輸潰敗] 檔案：{safe_title} 失敗：{e}")
        return None

# --- [區塊二：主調度邏輯] ---
def run_worker_mission():
    # 1. 初始化指揮中心
    sb: Client = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))
    r2 = boto3.client('s3', endpoint_url=f"https://{os.environ.get('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com",
                      aws_access_key_id=os.environ.get('R2_ACCESS_KEY_ID'), 
                      aws_secret_access_key=os.environ.get('R2_SECRET_ACCESS_KEY'))



    # 🚀 加入循環哨兵邏輯
    while True:
        print(f"🕒 [哨兵巡邏] {datetime.now().strftime('%H:%M:%S')} 正在檢索 Supabase 任務...")
        try:
            # 領取任務：鎖定狀態為 success 且 pending 的物資
            res = sb.table("mission_queue").select("*").eq("scrape_status", "success").eq("status", "pending").limit(1).execute()
            
            if res.data:
                mission = res.data[0]
                print(f"🚛 [起運] 正在搬運：{mission['episode_title']}")
                r2_path = stream_to_r2_with_metadata(mission, r2, os.environ.get("R2_BUCKET_NAME"))

                if r2_path:
                    sb.table("mission_queue").update({
                        "status": "stored_in_r2",
                        "r2_url": r2_path,
                        "mission_type": "logistics_completed"
                    }).eq("id", mission['id']).execute()
                    print(f"🏆 [結案] 檔案已安全入庫 R2：{r2_path}")
                
            else:
                print("☕ [物流部] 目前無待搬運物資。")

        except Exception as e:
            print(f"⚠️ [巡邏異常]：{e}")

        # 🚀 戰術休眠：每 30 分鐘巡邏一次，避免過度查詢資料庫
        idle_time = 1800 
        print(f"💤 進入戰術休眠 {idle_time//60} 分鐘...")
        time.sleep(idle_time)



if __name__ == "__main__":
    run_worker_mission()