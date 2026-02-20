# ---------------------------------------------------------
# 本程式碼：src/test_scanner_expedition.py v2.0 (全維度模組化版)
# 任務：測試各供應商（ZENROWS, WEBSCRAPING...）對各大站點的穿透與活性化能力。
# ---------------------------------------------------------
import os, time, random, re, urllib3
from supabase import create_client, Client
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from pod_scra_scanner import fetch_html 

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- [區塊一：分類偵測與智能調度] ---
def get_scra_response(target_url, test_mode, all_keys):
    """
    一行註解：根據網址特徵判斷是否值得執行 Scraping，並調用掃描器。
    """
    direct_hosts = ["megaphone.fm", "omny.fm", "blubrry.com", "acast.com", "buzzsprout.com", ".mp3"]
    is_direct = any(host in target_url for host in direct_hosts)

    if is_direct and test_mode == "WEBSCRAPING":
        print(f"⚠️ [成本警報] 目標為直連連結，測試 WebScraping 穿透力...")
    
    # 呼叫統一掃描器邏輯
    return fetch_html(test_mode, target_url, all_keys)

# --- [區塊二：網址構造模組] ---
def build_target_url(task, target_site):
    """
    一行註解：根據 YML 指令（PODBAY/LISTEN_NOTES/OFFICIAL）建構偵察座標。
    """
    if target_site == "LISTEN_NOTES":
        slug = task.get('listen_notes_id')
        return f"https://www.listennotes.com/podcasts/{slug}/" if slug else None
    elif target_site == "OFFICIAL":
        # 官方模式：拿起 Vercel 發現的原始 URL 作為活性化種子
        return task.get('audio_url')
    else: # 預設 PODBAY
        slug = task.get('podbay_slug')
        return f"https://podbay.fm/p/{slug}" if slug else None

# --- [區塊三：情報挖掘模組] ---
def extract_audio_url(html_content):
    """
    一行註解：從 HTML 中挖掘具時效性的 MP3 網址。
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    # 優先搜尋 meta 標準標籤 (og:audio 或 twitter 播放器)
    audio_meta = soup.find('meta', property=re.compile(r'(og:audio|twitter:player:stream)'))
    if audio_meta:
        return audio_meta.get('content')
    
    # 備援：搜尋 HTML5 audio 標籤
    audio_tag = soup.find('audio')
    if audio_tag:
        return audio_tag.get('src')
    
    return None

# --- [主程序：演習核心] ---
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

    supabase: Client = create_client(sb_url, sb_key)
    # 領取 3 筆待處理任務
    res = supabase.table("mission_queue").select("*").eq("scrape_status", "pending").limit(3).execute()
    
    if not res.data:
        print("☕ [待命] 倉庫暫無積壓物資。")
        return

    print(f"🚀 [演習開始] 模式：{test_mode} | 站點：{target_site} | 規模：{len(res.data)} 筆")

    for index, task in enumerate(res.data):
        if index > 0: time.sleep(random.randint(10, 20)) # 模擬真人 Jitter
        
        # A. 建構目標 URL
        target_url = build_target_url(task, target_site)
        if not target_url:
            print(f"⏩ [跳過] 任務 ID {task['id']} 缺少站點 {target_site} 所需的 ID/Slug。")
            continue

        print(f"🎯 [偵察中] 目標：{target_url[:60]}...")

        try:
            # B. 執行抓取
            resp = get_scra_response(target_url, test_mode, all_keys)

            if resp and resp.status_code == 404:
                print(f"🚨 [導航錯誤] 404 失效。請校對 Supabase 對標資料。")
                supabase.table("mission_queue").update({"scrape_status": "manual_check"}).eq("id", task['id']).execute()
                continue

            if resp and resp.status_code == 200:
                # C. 挖掘活性化網址
                final_mp3_url = extract_audio_url(resp.text)
                
                if final_mp3_url:
                    try:
                        # D. 入庫並實施 23505 靜默忽略策略
                        supabase.table("mission_queue").update({
                            "audio_url": final_mp3_url,
                            "scrape_status": "success",
                            "used_provider": f"{test_mode}_TEST_{target_site}"
                        }).eq("id", task['id']).execute()
                        print(f"✅ [報捷] {target_site} 活性化成功！")
                    except Exception as db_e:
                        if "23505" in str(db_e):
                            print(f"♻️ [重複偵測] 網址已在庫存中，任務標記為 success。")
                            supabase.table("mission_queue").update({"scrape_status": "success"}).eq("id", task['id']).execute()
                else:
                    print(f"🔎 [情報缺失] 網頁解析成功但無 MP3。內容長度：{len(resp.text)}")
            else:
                print(f"❌ [失敗] {test_mode} 回報：{resp.status_code if resp else 'No Resp'}")

        except Exception as e:
            print(f"⚠️ [異常] {test_mode} 執行崩潰: {e}")

if __name__ == "__main__":
    run_expedition_test()