# ---------------------------------------------------------
# 本程式碼：src/test_scanner_expedition.py (多軌測試版)
# 任務：根據指令測試特定供應商能力，清理積壓任務。
# ---------------------------------------------------------
import os, time, random, re, urllib3
from supabase import create_client, Client
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from pod_scra_scanner import fetch_html 

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def run_expedition_test():
    # 1. 取得測試指令 (由 YML 傳入)
    # 一行註解：讀取外部指令，預設為 ZENROWS 以確保基礎戰力。
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

    supabase: Client = create_client(sb_url, sb_key)
    # 一行註解：領取 3 筆待處理任務。
    res = supabase.table("mission_queue").select("*").eq("scrape_status", "pending").limit(3).execute()
    
    if not res.data:
        print("☕ [待命] 尚無積壓物資需偵察。")
        return

    print(f"🚀 [演習開始] 模式：{test_mode} | 任務數：{len(res.data)}")

    for index, task in enumerate(res.data):
        if index > 0: time.sleep(random.randint(10, 20)) # 隨機抖動
        
        target_url = f"https://podbay.fm/p/{task['podbay_slug']}"
        print(f"🎯 [偵察中] 目標：{task['podbay_slug']} | 供應商：{test_mode}")

        try:
            # 一行註解：依據 test_mode 標籤呼叫統一掃描器。
            resp = fetch_html(test_mode, target_url, all_keys)

            if resp and resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                # ... (此處維持原本的 BeautifulSoup 解析與資料庫回填邏輯) ...
                print(f"✅ [成功] {test_mode} 穿透成功！")
            else:
                print(f"❌ [失敗] {test_mode} 回報狀態：{resp.status_code if resp else 'No Resp'}")

        except Exception as e:
            print(f"⚠️ [異常] {test_mode} 執行崩潰: {e}")

if __name__ == "__main__":
    run_expedition_test()