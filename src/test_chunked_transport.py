# ---------------------------------------------------------
# 本程式碼：src/test_chunked_transport.py v4.5 (純代理攻堅版)
# 職責：從 Supabase 領取 pending 任務 -> 透過 WebScraping.ai 解析 -> 儲存最終網址
# ---------------------------------------------------------
# ---------------------------------------------------------
# 本程式碼：src/test_chunked_transport.py v4.8 (保險版)
# 任務：解析最終網址並存入 resolved_url，不破壞原始數據。
# ---------------------------------------------------------
import os
import requests
from urllib.parse import quote
from supabase import create_client
from dotenv import load_dotenv

# 一行註解：載入配置。
load_dotenv()
supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))


def run_scout_mission():
    # 一行註解：選取偵察成功但尚未獲取精準座標的 3 筆目標。
    tasks = supabase.table("mission_queue").select("*").eq("scrape_status", "success").eq("status", "pending").limit(3).execute()
    
    if not tasks.data:
        print("☕ [守備中] 暫無需要解析的物資。")
        return

    for task in tasks.data:
        target_id = task['id']
        original_url = task['audio_url']
        
        print(f"📡 [精準解析] 任務 {target_id[:8]} 正在透過 WebScraping.ai 獲取座標...")
        
        # 一行註解：封裝原始網址請求。
        api_key = os.environ.get("WEBSCRAP_API_KEY")
        proxy_url = f"https://api.webscraping.ai/html?api_key={api_key}&url={quote(original_url)}&on_error=status&proxy=datacenter"
        
        try:
            # 一行註解：追蹤跳轉，獲取最終實體檔案連結。
            resp = requests.head(proxy_url, allow_redirects=True, timeout=30)
            final_resolved_url = resp.url 

            # 一行註解：將結果存入新欄位「resolved_url」，並標記狀態。
            supabase.table("mission_queue").update({
                "resolved_url": final_resolved_url,
                "scrape_status": "resolved"
            }).eq("id", target_id).execute()
            
            print(f"✅ [入庫成功] 最終座標已存入 resolved_url 欄位。")
            
        except Exception as e:
            print(f"❌ [解析攔截] {target_id[:8]} 失敗: {e}")

if __name__ == "__main__":
    run_scout_mission()
