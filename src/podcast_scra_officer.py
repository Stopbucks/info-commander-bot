#---------------------------------------------------------------
# 本程式碼為：podcast_scra_officer.py 
# 從 mission_queue 領命(scrape_status = 'pending')，以ScraperAPI (8001 端口) 
# 前往 Podbay 精確定位集數，提取 MP3 門票網址，帶回網址寫入 podbay_url 並標記為 success。
#---------------------------------------------------------------

import os, requests, urllib.parse, time, re
from supabase import create_client, Client
from bs4 import BeautifulSoup

def clean_title(title):
    # 🚀 戰術洗滌 v2.4：處理噪音、括號與過長字串
    # 1. 移除常見噪音前綴 (如 Replay -, Update -) [cite: 2026-02-16]
    title = re.sub(r'^(Replay|Update|Special)\s*[-:]\s*', '', title, flags=re.IGNORECASE)
    # 2. 移除括號內容 (如 (溫養日))
    title = re.sub(r'\(.*?\)', '', title)
    # 3. 移除冒號與破折號後面的內容 (通常是子標題，會干擾搜尋)
    title = title.split(' - ')[0].split(': ')[0]
    # 4. 只取前 5 個單字，增加搜尋寬容度 [cite: 2026-02-16]
    words = title.split()
    return " ".join(words[:5]).strip()

def run_scra_officer():
    sb_url = os.environ.get("SUPABASE_URL")
    sb_key = os.environ.get("SUPABASE_KEY")
    scra_key = os.environ.get("SCRAP_API_KEY")

    if not all([sb_url, sb_key, scra_key]):
        print("❌ [憑證遺失]")
        return

    supabase: Client = create_client(sb_url, sb_key)
    proxy_url = f"http://scraperapi:{scra_key}@proxy-server.scraperapi.com:8001"
    proxies = {"http": proxy_url, "https": proxy_url}

    # 🚀 模擬自動化：領取 3 筆待處理任務 (包含您剛才在 Supabase 手動重置的筆數)
    missions = supabase.table("mission_queue").select("*").eq("scrape_status", "pending").limit(3).execute()

    if not missions.data:
        print("☕ [庫存清空] 沒有 pending 任務。")
        return

    for target in missions.data:
        task_id = target['id']
        raw_title = target['episode_title']
        search_query = clean_title(raw_title)
        
        print(f"\n📡 [測試任務] 原始：{raw_title[:30]}...")
        print(f"🔍 [洗滌關鍵字]：{search_query}")

        try:
            encoded_query = urllib.parse.quote(search_query)
            podbay_search = f"https://podbay.fm/search?q={encoded_query}"
            
            # 使用 ScraperAPI 攻堅
            #resp = requests.get(podbay_search, proxies=proxies, timeout=40, verify=False)
            #兩個網站攻堅，拉長時間
            resp = requests.get(target_url, proxies=proxies, timeout=60, verify=False)
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # 搜尋匹配集數連結
            ep_link_tag = soup.find('a', href=re.compile(r'/p/.+/e/.*'))
            
            if ep_link_tag:
                full_ep_url = f"https://podbay.fm{ep_link_tag['href']}"
                print(f"🎯 [定位成功] 網址：{full_ep_url}")

                ep_resp = requests.get(full_ep_url, proxies=proxies, timeout=30, verify=False)
                ep_soup = BeautifulSoup(ep_resp.text, 'html.parser')
                
                audio_tag = ep_soup.find('meta', property="og:audio")
                final_mp3_url = audio_tag['content'] if audio_tag else ""

                if final_mp3_url:
                    supabase.table("mission_queue").update({
                        "podbay_url": final_mp3_url,
                        "scrape_status": "success"
                    }).eq("id", task_id).execute()
                    print(f"✅ [入庫成功] MP3 已就緒。")
                else:
                    print("❌ [門票遺失] 頁面內找不到 MP3。")
            else:
                print(f"⚠️ [搜尋失敗] Podbay 找不到：{search_query}")
                supabase.table("mission_queue").update({"scrape_status": "failed"}).eq("id", task_id).execute()

        except Exception as e:
            print(f"💥 [故障] {str(e)}")
        
        time.sleep(2) # 戰術喘息

if __name__ == "__main__":
    run_scra_officer()