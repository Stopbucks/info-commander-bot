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

#---前面程式碼相同---#
# -----(定位線)以下修改為「直接覆蓋」邏輯----
def run_scout_mission():
    # 一行註解：領取偵察成功但尚未獲取最終座標的任務。
    tasks = supabase.table("mission_queue").select("*").eq("scrape_status", "success").eq("status", "pending").execute()
    
    for task in tasks.data:
        target_id = task['id']
        original_url = task['audio_url']
        
        print(f"📡 [火力偵察] 正在為任務 {target_id[:8]} 進行原地解析...")
        
        # 一行註解：透過 WebScraping.ai 代理發出標頭請求，獲取跳轉後的真實座標。
        api_key = os.environ.get("WEBSCRAP_API_KEY")
        proxy_url = f"https://api.webscraping.ai/html?api_key={api_key}&url={quote(original_url)}&on_error=status&proxy=datacenter"
        
        try:
            # 一行註解：執行 HEAD 請求追蹤跳轉，獲取最終實體檔案網址。
            resp = requests.head(proxy_url, allow_redirects=True, timeout=20)
            final_resolved_url = resp.url 

            # 一行註解：將最終網址「覆蓋」回 audio_url 欄位，並標記狀態。
            supabase.table("mission_queue").update({
                "audio_url": final_resolved_url,
                "scrape_status": "resolved" # 標記為 resolved 以防偵察兵重複解析。
            }).eq("id", target_id).execute()
            
            print(f"✅ [原地覆蓋成功] 運輸兵將可直連最終座標。")
            
        except Exception as e:
            print(f"❌ [解析攔截] 任務 {target_id[:8]} 失敗: {e}")


if __name__ == "__main__":
    run_scout_mission()