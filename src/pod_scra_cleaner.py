# ---------------------------------------------------------
# 本程式碼：src/pod_scra_cleaner.py v1.0
# 任務：兩階段庫存管理 R2 & Supabase (7天重生 / 14天清除)
# ---------------------------------------------------------
import os, boto3
from supabase import create_client, Client
from datetime import datetime, timedelta, timezone

def run_cleanup_plan():
    # 1. 初始化
    sb_url = os.environ.get("SUPABASE_URL")
    sb_key = os.environ.get("SUPABASE_KEY")
    supabase: Client = create_client(sb_url, sb_key)
    
    r2_id = os.environ.get("R2_ACCESS_KEY_ID")
    r2_secret = os.environ.get("R2_SECRET_ACCESS_KEY")
    r2_account_id = os.environ.get("R2_ACCOUNT_ID")
    s3_client = boto3.client(
        's3', endpoint_url=f'https://{r2_account_id}.r2.cloudflarestorage.com',
        aws_access_key_id=r2_id, aws_secret_access_key=r2_secret
    )

    now = datetime.now(timezone.utc)
    seven_days_ago = (now - timedelta(days=7)).isoformat()
    fourteen_days_ago = (now - timedelta(days=14)).isoformat()

    # --- 階段一：7天重生計畫 (Rebirth) ---
    # 將超過 7 天且 scrape_status 為 manual_check 或 pending 的任務重置
    print(f"🔄 [階段一] 正在重置 7 天前的積壓任務...")
    rebirth_query = supabase.table("mission_queue").update({
        "scrape_status": "pending",
        "status": "pending",
        "mission_type": "rebirth_retry"
    }).lt("created_at", seven_days_ago).neq("status", "completed").execute()
    print(f"✅ 重置完成，共計 {len(rebirth_query.data)} 筆任務獲得重生機會。")

    # --- 階段二：14天報廢清理 (Purge) ---
    print(f"🧹 [階段二] 正在清理 14 天前的陳舊數據...")
    # 先找出 14 天前的所有任務
    old_missions = supabase.table("mission_queue").select("id, r2_url") \
        .lt("created_at", fourteen_days_ago).execute()

    if old_missions.data:
        for m in old_missions.data:
            # 刪除 R2 實體檔案
            if m.get('r2_url'):
                try:
                    s3_client.delete_object(Bucket='pod-scra-vault', Key=m['r2_url'])
                    print(f"🗑️ 已刪除 R2 檔案: {m['r2_url']}")
                except Exception as e:
                    print(f"⚠️ R2 刪除失敗: {e}")
            
            # 刪除 Supabase 紀錄
            supabase.table("mission_queue").delete().eq("id", m['id']).execute()
        
        print(f"✅ 清理完畢，共移除了 {len(old_missions.data)} 筆過期紀錄。")
    else:
        print("☕ 目前無須清理的陳舊數據。")

if __name__ == "__main__":
    run_cleanup_plan()