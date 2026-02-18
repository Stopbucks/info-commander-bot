
# ---------------------------------------------------------
# pod_scra_transport.py v0.2 (透明監控加固版)
# 流程：領取門票 -> 檢查時間差 -> 模擬下載驗證
# 任務：修正欄位讀取 -> 強化異常日誌 -> 執行連線驗證
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
        print("☕ [待命] 目前無有效門票 (scrape_status=success) 可供測試。")
        return

    print(f"📡 [情報站] 發現 {len(missions.data)} 筆待驗證門票...")

    for mission in missions.data:
        # #---定位線：修正欄位讀取邏輯---#
        # 一行註解：優先讀取 audio_url，若無則降級讀取 podbay_url。
        audio_url = mission.get('audio_url') or mission.get('podbay_url')
        
        # # -----(定位線)以下修改-----
        
        # 💡 透明日誌：在執行前先列印出抓到的網址(前30字)
        print(f"\n🧪 [壓力測試] 目標：{mission['source_name']}")
        print(f"🔗 門票網址樣貌：{str(audio_url)[:50]}...")

        if not audio_url:
            print(f"❌ [跳過] 任務 {mission['id']} 欄位缺失，無法執行下載。")
            continue

        # 計算門票發放至今的時間
        try:
            # 修改解析方式以應對不同 ISO 格式
            created_at = mission['created_at'].replace(' ', 'T')
            start_time = datetime.fromisoformat(created_at)
            time_diff = (datetime.now(timezone.utc) - start_time).total_seconds() / 60
            print(f"🕒 門票發放至今：{time_diff:.1f} 分鐘")
        except Exception as e:
            print(f"⚠️ [時間解析警告]：{str(e)}")
            time_diff = 0

        try:
            # 2. 執行模擬下載 (僅抓取前 512KB)
            headers = {"Range": "bytes=0-524288"} 
            resp = requests.get(audio_url, headers=headers, timeout=30)
            
            if resp.status_code in [200, 206]:
                print(f"✅ [測試通過] 經過 {time_diff:.1f} 分鐘後，門票依然有效！")
            else:
                print(f"❌ [門票失效] 錯誤代碼：{resp.status_code}。")
                supabase.table("mission_queue").update({"status": "expired"}).eq("id", mission['id']).execute()

        except Exception as e:
            print(f"⚠️ [連線異常]：{str(e)}")

if __name__ == "__main__":
    run_transport_test()