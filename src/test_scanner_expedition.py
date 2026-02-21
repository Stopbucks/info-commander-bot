# ---------------------------------------------------------
# 本程式碼：src/test_scanner_expedition.py v2.6 (終極整合版)
# 職責：Podbay 攻堅 -> Regex 深海搜索 -> 跳轉解析 -> 原地覆蓋座標
# ---------------------------------------------------------
import os, time, random, re, urllib3, requests
from supabase import create_client, Client
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from urllib.parse import quote
from pod_scra_scanner import fetch_html 

# 一行註解：停用不安全的請求警告，確保日誌整潔。
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- [區塊：深度情報挖掘 (Deep Recon)] ---
def extract_audio_url_v25(html_content):
    # 一行註解：搜尋 HTML 中所有包含 http...mp3 的字串，無視網頁框架限制。
    mp3_pattern = r'https?://[^\s"\'<>]+?\.mp3[^\s"\'<>]*'
    found_links = re.findall(mp3_pattern, html_content)
    
    if found_links:
        # 一行註解：回傳第一個匹配成功的 MP3 連結作為初始座標。
        valid_link = found_links[0]
        print(f"🔦 [深海搜索] 挖掘到初步網址：{valid_link[:50]}...")
        return valid_link
    return None

# --- [主演習程序] ---
def run_expedition_test():
    # 一行註解：讀取環境變數與 API 金鑰字典。
    test_mode = os.environ.get("TEST_PROVIDER_MODE", "ZENROWS")
    sb_url = os.environ.get("SUPABASE_URL")
    sb_key = os.environ.get("SUPABASE_KEY")
    all_keys = {
        "SCRAPERAPI": os.environ.get("SCRAP_API_KEY"),
        "ZENROWS": os.environ.get("ZENROWS_API_KEY"),
        "WEBSCRAP": os.environ.get("WEBSCRAP_API_KEY"),
        "SCRAPEDO": os.environ.get("SCRAPEDO_API_KEY"),
        "HASDATA": os.environ.get("HASDATA_API_KEY")
    }

    # 一行註解：初始化 Supabase 基地台連線。
    supabase: Client = create_client(sb_url, sb_key)

    # 一行註解：領取 3 筆待處理任務 (scrape_status 為 pending)。
    res = supabase.table("mission_queue").select("*").eq("scrape_status", "pending").limit(3).execute()
    
    if not res.data:
        print("☕ [待命] 掃描區域無待處理任務。")
        return

    for index, task in enumerate(res.data):
        # 一行註解：執行戰術休眠，防止被 Podbay 偵測頻率。
        if index > 0: time.sleep(random.randint(5, 10))
        
        slug = task.get('podbay_slug')
        target_url = f"https://podbay.fm/p/{slug}"
        print(f"🎯 [攻堅開始] 目標：{slug} | 模式：{test_mode}")

        try:
            # 一行註解：第一步：透過指定的代理供應商獲取 Podbay HTML。
            resp = fetch_html(test_mode, target_url, all_keys)

            if resp and resp.status_code == 200:
                # 一行註解：第二步：挖掘隱藏在 JS 或 SPA 代碼中的 MP3 連結。
                found_mp3_url = extract_audio_url_v25(resp.text)
                
                if found_mp3_url:
                    # -----(定位線)以下執行座標解碼邏輯-----
                    print(f"🔗 [解析中] 正在追蹤重定向層級...")
                    try:
                        # 一行註解：第三步：執行標頭請求獲取最終檔案座標，不下載實體檔案。
                        # 若目標伺服器較嚴格，日後此處可改由 WebScraping.ai 代理執行。
                        resolve_resp = requests.head(found_mp3_url, allow_redirects=True, timeout=15)
                        final_coords = resolve_resp.url
                        print(f"✅ [解析成功] 最終座標：{final_coords[:50]}...")
                    except:
                        # 一行註解：解析失敗時的保險機制，保留原始挖掘連結。
                        final_coords = found_mp3_url

                    # 一行註解：第四步：原地更新 audio_url 並標記為成功。
                    supabase.table("mission_queue").update({
                        "audio_url": final_coords,
                        "scrape_status": "success",
                        "used_provider": f"{test_mode}_V26"
                    }).eq("id", task['id']).execute()
                    
                    print(f"🏆 [任務達成] 情報已洗白並入庫。")
                    # -----(定位線)以上更新完畢-----
                else:
                    print(f"🔎 [缺失] 網頁代碼抓取成功，但未發現 MP3 特徵。")
            else:
                print(f"❌ [失敗] 代理回傳異常狀態碼：{resp.status_code if resp else 'N/A'}")

        except Exception as e:
            print(f"⚠️ [異常] 偵察兵於任務執行中負傷: {e}")

if __name__ == "__main__":
    run_expedition_test()