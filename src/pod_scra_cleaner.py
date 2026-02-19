
# ---------------------------------------------------------
# 本程式碼：src/pod_scra_cleaner.py v1.1 (法定標籤校準版)
# 任務：兩階段庫存管理 R2 & Supabase (7天重生 / 14天清除)
# 修正：精準對位 GitHub Secrets 標籤 R2_SECRET_ACCESS_KEY
# ---------------------------------------------------------
import os, boto3
from supabase import create_client, Client
from datetime import datetime, timedelta, timezone

def run_cleanup_plan():
    # 1. 初始化環境變數 (根據法定清單校準)
    sb_url = os.environ.get("SUPABASE_URL")
    sb_key = os.environ.get("SUPABASE_KEY")
    
    r2_id = os.environ.get("R2_ACCESS_KEY_ID")
    # 🚀 修正：對位法定清單中的名稱
    r2_secret = os.environ.get("R2_SECRET_ACCESS_KEY") 
    r2_account_id = os.environ.get("R2_ACCOUNT_ID")
    r2_bucket = os.environ.get("R2_BUCKET_NAME", "pod-scra-vault") # 優先使用 Secret 定義

    # 2. 安全性檢查：確保關鍵武器皆有彈藥
    if not all([sb_url, sb_key, r2_id, r2_secret, r2_account_id]):
        print("❌ [清理兵] 環境變數對位失敗，為避免誤刪，任務中止。")
        return

    # 初始化組件
    supabase: Client = create_client(sb_url, sb_key)
    s3_client = boto3.client(
        's3', 
        endpoint_url=f'https://{r2_account_id}.r2.cloudflarestorage.com',
        aws_access_key_id=r2_id, 
        aws_secret_access_key=r2_secret,
        region_name='auto' # 🚀 增加：明確指定 region 提高 boto3 穩定性
    )

    now = datetime.now(timezone.utc)
    seven_days_ago = (now - timedelta(days=7)).isoformat()
    fourteen_days_ago = (now - timedelta(days=14)).isoformat()

    # --- 階段一：7天重生計畫 (Rebirth) ---
    print(f"🔄 [階段一] 正在執行重生程序 (LT 7 Days)...")
    try:
        # 將超過 7 天且未完成的任務重置為 pending，由 Scanner 重新嘗試
        rebirth_query = supabase.table("mission_queue").update({
            "scrape_status": "pending",
            "status": "pending",
            "mission_type": "rebirth_retry"
        }).lt("created_at", seven_days_ago).neq("status", "completed").execute()
        print(f"✅ 重生完成，共計 {len(rebirth_query.data)} 筆任務重返戰場。")
    except Exception as e:
        print(f"⚠️ 階段一重生失敗: {e}")

    # --- 階段二：14天報廢清理 (Purge) ---
    print(f"🧹 [階段二] 正在清理 14 天前的陳舊數據與 R2 物資...")
    try:
        old_missions = supabase.table("mission_queue").select("id, r2_url") \
            .lt("created_at", fourteen_days_ago).execute()

        if old_missions.data:
            for m in old_missions.data:
                # 刪除 R2 實體檔案 (如果存在)
                if m.get('r2_url'):
                    try:
                        s3_client.delete_object(Bucket=r2_bucket, Key=m['r2_url'])
                        print(f"🗑️ 已移除 R2 殘骸: {m['r2_url']}")
                    except Exception as e:
                        print(f"⚠️ R2 物資移除異常 (可能已不存在): {e}")
                
                # 刪除 Supabase 紀錄
                supabase.table("mission_queue").delete().eq("id", m['id']).execute()
            
            print(f"✅ 報廢清理完畢，共移除了 {len(old_missions.data)} 筆歷史紀錄。")
        else:
            print("☕ 戰場清理完畢，目前無過期物資。")
    except Exception as e:
        print(f"⚠️ 階段二清理失敗: {e}")

if __name__ == "__main__":
    run_cleanup_plan()