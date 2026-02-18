
# ---------------------------------------------------------
# pod_scra_transport.py v0.4 (資安加固 & 深度延遲版)
# 限額傳輸 (每次3筆) -> 強制間隔 (60s+) -> 引入 Jitter
# 流程：領取門票 -> 檢查時間差 -> 模擬下載驗證
# 任務：修正欄位讀取 -> 強化異常日誌 -> 執行連線驗證
# ---------------------------------------------------------

import os, requests, time, random
from supabase import create_client, Client
from datetime import datetime, timezone

def run_transport_test():
    # 資安守則：從環境變數讀取金鑰，避免公開倉庫洩漏
    sb_url = os.environ.get("SUPABASE_URL")
    sb_key = os.environ.get("SUPABASE_KEY")
    
    if not sb_url or not sb_key:
        print("❌ [資安警報] 缺少資料庫環境變數，終止任務。")
        return

    supabase: Client = create_client(sb_url, sb_key)

    # 1. 領取任務：限制 3 筆，防止大量請求觸發 WAF 防火牆
    missions = supabase.table("mission_queue").select("*") \
        .eq("scrape_status", "success") \
        .eq("status", "pending") \
        .limit(3) \
        .execute()
    
    if not missions.data:
        print(f"☕ [{datetime.now().strftime('%H:%M:%S')}] 待命：目前無有效任務。")
        return

    print(f"📡 [情報站] 準備處理 {len(missions.data)} 筆任務，進入深度抖動模式...")

    for i, mission in enumerate(missions.data):
        # 安全取值：使用 get 避免欄位缺失導致程式崩潰
        audio_url = mission.get('audio_url') or mission.get('podbay_url')
        mission_id = mission.get('id')
        
        print(f"\n📦 [任務 {i+1}/3] 標的：{mission['source_name']}")
        
        if not audio_url or not mission_id:
            print(f"❌ [跳過] 任務數據不完整。")
            continue

        try:
            # 2. 執行模擬驗證 (資安提醒：僅抓取 Header 與前段，避免全量下載耗費頻寬)
            headers = {"Range": "bytes=0-524288"} 
            resp = requests.get(audio_url, headers=headers, timeout=45) # 加長 timeout 應對慢速網路
            
            if resp.status_code in [200, 206]:
                print(f"✅ [驗證成功] 音檔門票有效。")
            else:
                print(f"❌ [驗證失敗] 狀態碼：{resp.status_code}")
                # 一行註解：若失敗則標記為 expired。
                supabase.table("mission_queue").update({"status": "expired"}).eq("id", mission_id).execute()

        except Exception as e:
            print(f"⚠️ [連線異常]：{str(e)}")

        # 3. 執行深度 Jitter (最後一筆不需休息)
        if i < len(missions.data) - 1:
            # 一行註解：基礎休息 120 秒 + 隨機 30~90 秒大幅抖動，徹底模擬人為間歇操作。
            base_sleep = 120
            jitter = random.uniform(30, 90)
            total_sleep = base_sleep + jitter
            print(f"⏳ [深度冷卻] 安全考量，隨機休息 {total_sleep:.1f} 秒...")
            time.sleep(total_sleep)

    print(f"\n🏁 [{datetime.now().strftime('%H:%M:%S')}] 部隊搬運演習完成。")

if __name__ == "__main__":
    run_transport_test()