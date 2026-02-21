# ---------------------------------------------------------
# 本程式碼：src/test_chunked_transport.py v4.5 (純代理攻堅版)
# 職責：從 Supabase 領取 pending 任務 -> 透過 WebScraping.ai 解析 -> 儲存最終網址
# ---------------------------------------------------------
import os
import requests
from urllib.parse import quote
from supabase import create_client

# 一行註解：建立基地台連線。
supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))

def run_scout_mission():
    # 一行註解：從資料庫獲取偵察成功但尚未獲取最終座標的任務。
    tasks = supabase.table("mission_queue").select("*").eq("scrape_status", "success").eq("status", "pending").execute()
    
    for task in tasks.data:
        target_id = task['id']
        original_url = task['audio_url']
        
        print(f"📡 [領命成功] 正在為任務 {target_id[:8]} 探路...")
        
        # 一行註解：透過 WebScraping.ai 代理發出請求，封裝目標網址以避開反爬蟲。
        api_key = os.environ.get("WEBSCRAP_API_KEY")
        proxy_url = f"https://api.webscraping.ai/html?api_key={api_key}&url={quote(original_url)}&on_error=status&proxy=datacenter"
        
        try:
            # 一行註解：執行標頭請求以追蹤 Redirect，獲取最終檔案座標。
            resp = requests.head(proxy_url, allow_redirects=True, timeout=20)
            resolved_url = resp.url 

            # 一行註解：將獲取的最終網址更新至 resolved_url 欄位並標記為 resolved 狀態。
            supabase.table("mission_queue").update({
                "resolved_url": resolved_url,
                "scrape_status": "resolved"
            }).eq("id", target_id).execute()
            
            print(f"✅ [探路完畢] 真實座標已回存至資料庫。")
            
        except Exception as e:
            print(f"❌ [探路失敗] 任務 {target_id[:8]} 遭遇攔截: {e}")

if __name__ == "__main__":
    run_scout_mission()