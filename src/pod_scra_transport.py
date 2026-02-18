
# ---------------------------------------------------------
# pod_scra_transport.py v0.3 (透明加固版)
# 限額傳輸 (每次3筆) -> 強制間隔 (60s+) -> 引入 Jitter
# 流程：領取門票 -> 檢查時間差 -> 模擬下載驗證
# 任務：修正欄位讀取 -> 強化異常日誌 -> 執行連線驗證
# ---------------------------------------------------------

import os, requests, time, random
from supabase import create_client, Client
from datetime import datetime, timezone

def run_transport_test():
    sb_url = os.environ.get("SUPABASE_URL")
    sb_key = os.environ.get("SUPABASE_KEY")
    supabase: Client = create_client(sb_url, sb_key)

    # 1. 領取門票：限制每次最高處理 3 筆，避免請求爆量
    # 一行註解：使用 .limit(3) 確保單次執行對 R2 的 A 類操作請求在安全範圍內。
    missions = supabase.table("mission_queue").select("*") \
        .eq("scrape_status", "success") \
        .eq("status", "pending") \
        .limit(3) \
        .execute()
    
    if not missions.data:
        print(f"☕ [{datetime.now().strftime('%H:%M:%S')}] 待命：目前無有效門票可供搬運。")
        return

    print(f"📡 [情報站] 發現 {len(missions.data)} 筆符合條件任務，準備進入限速運輸模式...")

    for i, mission in enumerate(missions.data):
        # 修正欄位讀取邏輯
        audio_url = mission.get('audio_url') or mission.get('podbay_url')
        
        # 💡 透明日誌探針
        print(f"\n📦 [任務 {i+1}/3] 目標：{mission['source_name']}")
        
        if not audio_url:
            print(f"❌ [跳過] 任務 {mission['id']} 無效網址。")
            continue

        try:
            # 2. 執行模擬下載 (驗證連線)
            headers = {"Range": "bytes=0-524288"} 
            resp = requests.get(audio_url, headers=headers, timeout=30)
            
            if resp.status_code in [200, 206]:
                print(f"✅ [驗證通過] MP3 門票有效。")
                # 這裡預留日後上傳 R2 的程式碼區塊
            else:
                print(f"❌ [驗證失敗] 錯誤代碼：{resp.status_code}")
                supabase.table("mission_queue").update({"status": "expired"}).eq("id", mission['id']).execute()

        except Exception as e:
            print(f"⚠️ [連線異常]：{str(e)}")

        # 3. 執行間隔休息與 Jitter (最後一筆不需休息)
        if i < len(missions.data) - 1:
            # 一行註解：基礎休息 60 秒 + 隨機 5~15 秒抖動，模擬人類行為並平滑請求壓力。
            base_sleep = 60
            jitter = random.uniform(5, 15)
            total_sleep = base_sleep + jitter
            print(f"⏳ [安全冷卻] 為了保護 R2 配額，休息 {total_sleep:.1f} 秒後處理下一筆...")
            time.sleep(total_sleep)

    print(f"\n🏁 [{datetime.now().strftime('%H:%M:%S')}] 運輸任務完成，部隊進入休整狀態。")

if __name__ == "__main__":
    run_transport_test()