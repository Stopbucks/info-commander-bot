
# ---------------------------------------------------------
# 本程式碼：src/test_chunked_transport.py v4.6 (座標解碼測試版)
# 任務：測試 WebScraping.ai 能否成功解析跳轉網址並「原地更新」
# ---------------------------------------------------------
import os
import requests
from urllib.parse import quote
from supabase import create_client
from dotenv import load_dotenv

# 一行註解：載入環境配置並建立基地台連線。
load_dotenv()
supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))

# -----(定位線)以下為今晚「座標解碼」核心測試邏輯----
def run_scout_test():
    # 一行註解：選取 3 筆待命物資進行跳轉追蹤測試。
    tasks = supabase.table("mission_queue").select("*").eq("scrape_status", "success").eq("status", "pending").limit(3).execute()
    
    if not tasks.data:
        print("☕ [戰場觀察] 目前無待命物資，演習取消。")
        return

    for task in tasks.data:
        target_id = task['id']
        original_url = task['audio_url']
        
        print(f"📡 [偵察啟動] 任務 {target_id[:8]} 正在解析跳轉層級...")
        
        # 一行註解：透過 WebScraping.ai 發起代理請求，封裝原始網址。
        api_key = os.environ.get("WEBSCRAP_API_KEY")
        proxy_url = f"https://api.webscraping.ai/html?api_key={api_key}&url={quote(original_url)}&on_error=status&proxy=datacenter"
        
        try:
            # 一行註解：執行輕量 HEAD 請求，allow_redirects=True 是打通座標的關鍵。
            resp = requests.head(proxy_url, allow_redirects=True, timeout=30)
            final_resolved_url = resp.url 

            # 一 step 更新：將解析後的直連網址覆蓋回 audio_url。
            supabase.table("mission_queue").update({
                "audio_url": final_resolved_url,
                "scrape_status": "resolved" # 標記為 resolved，運輸兵之後憑此標籤領貨。
            }).eq("id", target_id).execute()
            
            print(f"✅ [解析成功] 真實座標已寫入：{final_resolved_url[:50]}...")
            
        except Exception as e:
            print(f"❌ [解析攔截] 任務 {target_id[:8]} 失敗: {e}")

if __name__ == "__main__":
    run_scout_test()
