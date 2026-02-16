#---------------------------------------------------------------
# 本程式碼為：podcast_scra_officer.py 
# 從 mission_queue 領命(scrape_status = 'pending')，以ScraperAPI (8001 端口) 
# 前往 Podbay 精確定位集數，提取 MP3 門票網址，帶回網址寫入 podbay_url 並標記為 success。
#---------------------------------------------------------------

import os, requests, urllib.parse, time, re  # 🚀 關鍵修正：加上 re
from supabase import create_client, Client
from bs4 import BeautifulSoup

def run_scra_officer():
    # ---------------------------------------------------------
    # 1. 戰備檢查：環境變數加載
    # ---------------------------------------------------------
    sb_url = os.environ.get("SUPABASE_URL")
    sb_key = os.environ.get("SUPABASE_KEY")
    scra_key = os.environ.get("SCRAP_API_KEY")

    if not all([sb_url, sb_key, scra_key]):
        print("❌ [資安警報] 缺少必要的雲端憑證或金鑰。")
        return

    supabase: Client = create_client(sb_url, sb_key)
    # 一行註解：建立 ScraperAPI 標準代理連線字串。
    proxy_url = f"http://scraperapi:{scra_key}@proxy-server.scraperapi.com:8001"
    proxies = {"http": proxy_url, "https": proxy_url}

    # ---------------------------------------------------------
    # 2. 領取任務：從中繼站獲取待偵察情報
    # ---------------------------------------------------------
    # 一行註解：只領取一筆待處理任務，確保單次點數消耗受控。
    mission = supabase.table("mission_queue").select("*").eq("scrape_status", "pending").limit(1).execute()

    if not mission.data:
        print("☕ [休假中] 目前沒有待處理的偵察任務。")
        return

    target = mission.data[0]
    task_id = target['id']
    search_title = target['episode_title']
    print(f"📡 [接獲任務] 準備解碼：{search_title[:30]}...")

    # ---------------------------------------------------------
    # 3. 雲端攻堅：Podbay 定位與連結剝離
    # ---------------------------------------------------------
    try:
        # 一行註解：將標題轉為搜尋參數。
        encoded_query = urllib.parse.quote(search_title)
        podbay_search = f"https://podbay.fm/search?q={encoded_query}"
        
        # 一行註解：透過 ScraperAPI 抓取搜尋結果網頁。
        resp = requests.get(podbay_search, proxies=proxies, timeout=30, verify=False)
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        # 一行註解：尋找最匹配的集數連結。
        # 💡 S-Plan 技巧：Podbay 搜尋結果首位通常是 /p/podcast-id/e/episode-id 格式
        ep_link_tag = soup.find('a', href=re.compile(r'/p/.+/e/.+'))
        
        if not ep_link_tag:
            print("⚠️ [定位失敗] Podbay 搜尋結果未命中。")
            supabase.table("mission_queue").update({"scrape_status": "not_found"}).eq("id", task_id).execute()
            return

        full_ep_url = f"https://podbay.fm{ep_link_tag['href']}"
        print(f"🎯 [發現目標] 進入集數頁面：{full_ep_url}")

        # 一行註解：進入最終集數頁面提取 MP3 (這通常不需要 ScraperAPI，本地抓即可省點數)。
        # 💡 為保險起見，此處仍延用代理確保穿透力。
        ep_resp = requests.get(full_ep_url, proxies=proxies, timeout=30, verify=False)
        ep_soup = BeautifulSoup(ep_resp.text, 'html.parser')
        
        # 一行註解：尋找 Open Graph 音訊標籤或下載按鈕。
        audio_tag = ep_soup.find('meta', property="og:audio")
        final_mp3_url = audio_tag['content'] if audio_url else ""

        if final_mp3_url:
            # ---------------------------------------------------------
            # 4. 情報回填：存回門票並標記狀態
            # ---------------------------------------------------------
            supabase.table("mission_queue").update({
                "podbay_url": final_mp3_url,
                "scrape_status": "success"
            }).eq("id", task_id).execute()
            print(f"✅ [解碼大捷] 已取得 MP3 門票，情報已入庫。")
        else:
            print("❌ [門票遺失] 頁面內找不到 MP3 連結。")

    except Exception as e:
        print(f"💥 [解碼故障] 技術細節：{str(e)[:100]}")

if __name__ == "__main__":
    run_scra_officer()