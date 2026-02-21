# ---------------------------------------------------------
# 本程式碼：src/test_chunked_transport.py v4.7 (精準座標解碼版)
# 任務：測試 WebScraping.ai 解析最終網址並「原地更新」
# ---------------------------------------------------------
import os
import requests
from urllib.parse import quote
from supabase import create_client
from dotenv import load_dotenv

# 一行註解：載入環境配置並建立基地台連線。
load_dotenv()
supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))

def run_scout_test():
    # 一行註解：領取 3 筆待命物資進行跳轉追蹤測試。
    tasks = supabase.table("mission_queue").select("*").eq("scrape_status", "success").eq("status", "pending").limit(3).execute()
    
    if not tasks.data:
        print("☕ [戰場觀察] 目前無待命物資，演習取消。")
        return

    for task in tasks.data:
        target_id = task['id']
        original_url = task['audio_url']
        
        print(f"📡 [解析啟動] 任務 {target_id[:8]} 正在追蹤跳轉路徑...")
        
        # 一行註解：構建 WebScraping.ai 代理請求。
        api_key = os.environ.get("WEBSCRAP_API_KEY")
        # 🎯 關鍵修正：加入 on_error=status 確保能正確追蹤重定向。
        proxy_url = f"https://api.webscraping.ai/html?api_key={api_key}&url={quote(original_url)}&on_error=status&proxy=datacenter"
        
        try:
            # 
            # 一行註解：使用 GET 並開啟 stream=True，只拿 Headers 不下載檔案主體。
            resp = requests.get(proxy_url, allow_redirects=True, timeout=30, stream=True)
            
            # 🎯 核心邏輯修正：
            # WebScraping.ai 的 API 會在 Header 中回傳目標的最終網址 (通常是 x-final-url)。
            # 如果 Header 沒提供，我們則取 response 記錄中最後一次跳轉的網址。
            final_resolved_url = resp.headers.get('x-final-url') or resp.url
            
            # 一行註解：防呆檢查，如果拿到的依然是 WebScraping.ai 的 API 網址，表示解析不完整。
            if "webscraping.ai" in final_resolved_url:
                print(f"⚠️ [解析不完全] 僅拿到 API 網址，跳過寫入。")
                continue

            # 一步更新：將解析後的真實下載網址覆蓋回 audio_url。
            supabase.table("mission_queue").update({
                "audio_url": final_resolved_url,
                "scrape_status": "resolved" 
            }).eq("id", target_id).execute()
            
            print(f"✅ [解析成功] 真實座標已寫入：{final_resolved_url[:60]}...")
            
            # 一行註解：關閉流連線，節省資源。
            resp.close()
            
        except Exception as e:
            print(f"❌ [解析攔截] 任務 {target_id[:8]} 失敗: {e}")

if __name__ == "__main__":
    run_scout_test()