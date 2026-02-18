
# ---------------------------------------------------------
# 本程式碼：src/pod_scra_transport.py v0.5 (實戰入庫版)
# 任務：全量下載 -> 串流上傳至 R2 (pod-scra-vault)
# 流程：領取已解碼門票 -> 下載 MP3 -> 推向 R2 倉庫 -> 結案
# ---------------------------------------------------------
import os, requests, time, random, boto3, io
from supabase import create_client, Client
from datetime import datetime, timezone

def run_transport_test():
    # 1. 資安守則：嚴格由 Secrets 讀取補給物資
    sb_url = os.environ.get("SUPABASE_URL")
    sb_key = os.environ.get("SUPABASE_KEY")
    r2_id = os.environ.get("R2_ACCESS_KEY_ID")
    r2_secret = os.environ.get("R2_SECRET_ACCESS_KEY")
    r2_account_id = os.environ.get("R2_ACCOUNT_ID")
    
    if not all([sb_url, sb_key, r2_id, r2_secret, r2_account_id]):
        print("❌ [資安警報] 缺少 R2 或資料庫環境變數，終止運輸任務。")
        return

    # 初始化 R2 運輸鏈
    supabase: Client = create_client(sb_url, sb_key)
    s3_client = boto3.client(
        's3',
        endpoint_url=f'https://{r2_account_id}.r2.cloudflarestorage.com',
        aws_access_key_id=r2_id,
        aws_secret_access_key=r2_secret,
        region_name='auto'
    )

    # 2. 領取任務：限制處理 1 筆 (配合單發狙擊計畫，節省系統資源)
    missions = supabase.table("mission_queue").select("*") \
        .eq("scrape_status", "success") \
        .eq("status", "pending") \
        .limit(1) \
        .execute()
    
    if not missions.data:
        print(f"☕ [{datetime.now().strftime('%H:%M:%S')}] 待命：倉庫目前無待搬運物資。")
        return

    mission = missions.data[0]
    audio_url = mission.get('audio_url') or mission.get('podbay_url')
    source_name = mission.get('source_name', 'unknown').replace(" ", "_")
    
    # 一行註解：以時間戳記與節目名命名，防止 R2 檔案覆蓋。
    file_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{source_name}.mp3"
    
    print(f"📡 [情報站] 目標任務：{source_name}")
    print(f"🔗 來源網址：{str(audio_url)[:50]}...")

    try:
        # 3. 全量下載：移除 Range 限制，執行完整檔案提取
        print(f"📥 [下載中] 正在提取完整音檔...")
        # 一行註解：加長 timeout 以應對大型 Podcast 檔案。
        resp = requests.get(audio_url, timeout=300, stream=True) 
        
        if resp.status_code == 200:
            content = resp.content
            print(f"✅ [提取完成] 檔案大小：{len(content) / 1024 / 1024:.2f} MB")
            
            # 4. 實彈上傳：將檔案推入 pod-scra-vault
            print(f"🚀 [運輸中] 正在將檔案送往 R2: pod-scra-vault...")
            # 一行註解：使用記憶體流直接中轉，不佔用 Runner 實體硬碟空間。
            s3_client.upload_fileobj(
                io.BytesIO(content),
                'pod-scra-vault', # 💡 已根據截圖修正為正確的 Bucket 名稱
                file_name,
                ExtraArgs={'ContentType': 'audio/mpeg'}
            )
            
            # 5. 回報結案：更新 Supabase 狀態
            supabase.table("mission_queue").update({
                "status": "completed",
                "r2_url": file_name, # 紀錄入庫檔名
                "mission_type": "transport_finished"
            }).eq("id", mission['id']).execute()
            
            print(f"🏆 [結案成功] 檔案已成功入庫：{file_name}")
            
        else:
            print(f"❌ [傳輸失敗] 門票無效，狀態碼：{resp.status_code}")
            supabase.table("mission_queue").update({"status": "failed"}).eq("id", mission['id']).execute()

    except Exception as e:
        print(f"⚠️ [運輸崩潰] 連線異常：{str(e)}")

    print(f"\n🏁 [{datetime.now().strftime('%H:%M:%S')}] 部隊搬運任務結束。")

if __name__ == "__main__":
    run_transport_test()