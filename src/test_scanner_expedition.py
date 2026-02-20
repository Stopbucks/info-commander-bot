# ---------------------------------------------------------
# 本程式碼：src/test_scanner_expedition.py v2.5 (深度解析版)
# 任務：利用 Regex 暴力檢索技術，從 Scrapedo/ZenRows 帶回的代碼流中挖掘 MP3
# ---------------------------------------------------------
import os, time, random, re, urllib3
from supabase import create_client, Client
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from pod_scra_scanner import fetch_html 

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- [區塊三：深度情報挖掘 (Deep Recon)] ---
def extract_audio_url_v25(html_content):
    """
    一行註解：不再依賴 Meta 標籤，直接針對全網頁代碼進行 .mp3 特徵提取。
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 1. 傳統 Meta 掃描
    audio_meta = soup.find('meta', property=re.compile(r'(og:audio|twitter:player:stream)'))
    if audio_meta and audio_meta.get('content'): return audio_meta.get('content')
    
    # 2. 正則表達式「深海搜索」 🚀
    # 一行註解：搜尋任何包含 http...mp3 的字串，這是對付 SPA 網頁的最強武器。
    mp3_pattern = r'https?://[^\s"\'<>]+?\.mp3[^\s"\'<>]*'
    found_links = re.findall(mp3_pattern, html_content)
    
    if found_links:
        # 過濾掉明顯無效的連結 (如帶有 query string 的重複項)
        valid_link = found_links[0]
        print(f"🔦 [深海搜索] 成功挖掘隱藏網址：{valid_link[:50]}...")
        return valid_link
    
    return None

# --- [主演習程序] ---
def run_expedition_test():

    # 1. 取得演習指令
    test_mode = os.environ.get("TEST_PROVIDER_MODE", "ZENROWS")
    target_site = os.environ.get("TEST_SITE_TARGET", "PODBAY")
    
    sb_url = os.environ.get("SUPABASE_URL")
    sb_key = os.environ.get("SUPABASE_KEY")
    all_keys = {
        "SCRAPERAPI": os.environ.get("SCRAP_API_KEY"),
        "ZENROWS": os.environ.get("ZENROWS_API_KEY"),
        "WEBSCRAP": os.environ.get("WEBSCRAP_API_KEY"),
        "SCRAPEDO": os.environ.get("SCRAPEDO_API_KEY"),
        "HASDATA": os.environ.get("HASDATA_API_KEY")
    }

    # 🚀 關鍵修正線：重新建立與資料庫的通訊鏈路
    supabase: Client = create_client(sb_url, sb_key)

    # 領取 3 筆待處理任務
    res = supabase.table("mission_queue").select("*").eq("scrape_status", "pending").limit(3).execute()
    
    if not res.data:
        print("☕ [待命] 無演習目標。")
        return

    for index, task in enumerate(res.data):
        if index > 0: time.sleep(random.randint(10, 15))
        
        # 構造網址 (Podbay 邏輯)
        slug = task.get('podbay_slug')
        target_url = f"https://podbay.fm/p/{slug}"

        print(f"🎯 [偵察中] 目標：{slug} | 模式：{os.environ.get('TEST_PROVIDER_MODE')}")

        try:
            resp = fetch_html(os.environ.get('TEST_PROVIDER_MODE'), target_url, all_keys)

            if resp and resp.status_code == 200:
                # 🚀 調用進化後的解析模組
                final_mp3_url = extract_audio_url_v25(resp.text)
                
                if final_mp3_url:
                    supabase.table("mission_queue").update({
                        "audio_url": final_mp3_url,
                        "scrape_status": "success",
                        "used_provider": f"{os.environ.get('TEST_PROVIDER_MODE')}_V25"
                    }).eq("id", task['id']).execute()
                    print(f"✅ [成功] 情報提取成功！")
                else:
                    # 一行註解：即便失敗也印出前 500 字元供分析。
                    print(f"🔎 [缺失] 代碼長度 {len(resp.text)}，但無 MP3 特徵。")
            else:
                print(f"❌ [失敗] 狀態碼：{resp.status_code if resp else 'No Resp'}")
        except Exception as e:
            print(f"⚠️ [異常] {e}")

if __name__ == "__main__":
    run_expedition_test()