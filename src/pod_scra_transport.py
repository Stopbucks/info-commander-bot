# ---------------------------------------------------------
# pod_scra_transport.py v0.1 (門票時效演練版)
# 任務：領取門票 -> 檢查時間差 -> 模擬下載驗證
# ---------------------------------------------------------
import os, requests, time
from supabase import create_client, Client
from datetime import datetime, timezone

def run_transport_test():
    sb_url = os.environ.get("SUPABASE_URL")
    sb_key = os.environ.get("SUPABASE_KEY")
    supabase: Client = create_client(sb_url, sb_key)

    # 1. 領取已領票但尚未運輸的任務
    missions = supabase.table("mission_queue").select("*").eq("scrape_status", "success").eq("status", "pending").execute()
    
    if not missions.data:
        print("☕ [待命] 目前無有效門票可供測試。")
        return

    for mission in missions.data:
        audio_url = mission['podbay_url']
        # 💡 計算門票發放至今的時間 (分鐘)
        start_time = datetime.fromisoformat(mission['created_at'].replace('Z', '+00:00'))
        time_diff = (datetime.now(timezone.utc) - start_time).total_seconds() / 60
        
        print(f"\n🧪 [壓力測試] 目標：{mission['source_name']}")
        print(f"🕒 門票發放至今：{time_diff:.1f} 分鐘")

        try:
            # 2. 執行模擬下載 (僅抓取前 512KB 驗證連線是否有效)
            headers = {"Range": "bytes=0-524288"} 
            resp = requests.get(audio_url, headers=headers, timeout=30)
            
            if resp.status_code in [200, 206]:
                print(f"✅ [測試通過] 經過 {time_diff:.1f} 分鐘後，門票依然有效！")
                # 暫時不改狀態，讓我們可以在不同時段反覆測試同一連結
            else:
                print(f"❌ [門票失效] 錯誤代碼：{resp.status_code}。門票壽命約為 {time_diff:.1f} 分鐘。")
                supabase.table("mission_queue").update({"status": "expired"}).eq("id", mission['id']).execute()

        except Exception as e:
            print(f"⚠️ [連線異常]：{str(e)}")

if __name__ == "__main__":
    run_transport_test()