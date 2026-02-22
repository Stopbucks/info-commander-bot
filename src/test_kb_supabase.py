# ---------------------------------------------------------
# 本程式碼：src/test_supabase.py v1.0 (Koyeb 專屬偵錯版)
# 任務：孤立測試 Supabase 連線，排除環境變數迷航。
# ---------------------------------------------------------
import os

# 一行註解：嘗試導入 supabase 庫，若此處報錯代表 requirements.txt 未安裝成功。
try:
    from supabase import create_client
except ImportError:
    print("❌ [缺失] 找不到 supabase 庫，請檢查 requirements.txt。")
    exit(1)

def test_koyeb_env():
    # 一行註解：讀取環境變數，並遮蔽敏感資訊僅顯示頭尾用於對位。
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")

    print("--- 🔍 環境變數掃描 ---")
    print(f"🌐 URL: {url[:15]}..." if url else "🌐 URL: [MISSING]")
    print(f"🔑 KEY: {key[:10]}..." if key else "🔑 KEY: [MISSING]")

    if not url or not key:
        print("❌ [失敗] Koyeb 後台環境變數未正確設定。")
        return

    try:
        # 一行註解：發動連線握手，測試 API 密鑰的實體有效性。
        print("📡 正在發動連線握手...")
        sb = create_client(url, key)
        # 一行註解：執行極輕量讀取任務（僅抓取戰術板 ID 1 號）。
        res = sb.table("pod_scra_tactics").select("id").eq("id", 1).execute()
        
        if res.data:
            print(f"✅ [成功] 已成功與 Supabase 倉庫對接，取得戰術板數據。")
        else:
            print("⚠️ [無資料] 連線成功，但 table 內找不到資料。")
            
    except Exception as e:
        # 一行註解：捕捉實體報錯訊息，這將揭露 SSL 或 403 封鎖的真相。
        print(f"❌ [報錯細節]: {str(e)}")

if __name__ == "__main__":
    test_koyeb_env()