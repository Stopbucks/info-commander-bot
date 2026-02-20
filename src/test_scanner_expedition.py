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
# 一行註解：根據指令決定前往 PODBAY 還是 LISTEN_NOTES 進行測試。
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
    # 一行註解：領取 3 筆待處理任務。
    res = supabase.table("mission_queue").select("*").eq("scrape_status", "pending").limit(3).execute()
# -----(定位線)以下修改： ----    

    if not res.data:
        print("☕ [待命] 倉庫暫無積壓物資。")
        return

    print(f"🚀 [演習開始] 模式：{test_mode} | 站點：{target_site} | 任務數：{len(res.data)}")

    for index, task in enumerate(res.data):
        if index > 0: time.sleep(random.randint(10, 20)) # 模擬人類行為
        
        # 一行註解：根據目標站點與對應 Slug/ID 構造請求網址。
        if target_site == "LISTEN_NOTES":
            slug = task.get('listen_notes_id')
            target_url = f"https://www.listennotes.com/podcasts/{slug}/"
        else:
            slug = task.get('podbay_slug')
            target_url = f"https://podbay.fm/p/{slug}"

        print(f"🎯 [偵察中] 目標：{slug} | 供應商：{test_mode}")

        try:
            resp = fetch_html(test_mode, target_url, all_keys)

            # 一行註解：若回報 404，代表手動輸入的 Slug 或 ID 有誤，標記手動檢查。
            if resp and resp.status_code == 404:
                print(f"🚨 [導航錯誤] 404 失效目標：{slug}。請校對 Supabase 內容。")
                supabase.table("mission_queue").update({"scrape_status": "manual_check"}).eq("id", task['id']).execute()
                continue

            if resp and resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                # 一行註解：尋找 meta 標籤中的 MP3 連結，Listen Notes 與 Podbay 均有支援此標準。
                audio_meta = soup.find('meta', property=re.compile(r'(og:audio|twitter:player:stream)'))
                final_mp3_url = audio_meta.get('content') if audio_meta else None
                
                if final_mp3_url:
                    try:
                        # 一行註解：將挖掘到的情報寫回資料庫，若遇 23505 衝突則視為重複並跳過。
                        supabase.table("mission_queue").update({
                            "audio_url": final_mp3_url,
                            "scrape_status": "success",
                            "used_provider": f"{test_mode}_TEST_{target_site}"
                        }).eq("id", task['id']).execute()
                        print(f"✅ [成功] {target_site} 穿透成功！")
                    except Exception as db_e:
                        if "23505" in str(db_e):
                            print(f"♻️ [重複偵測] 網址已在庫存中，任務標記完成。")
                            supabase.table("mission_queue").update({"scrape_status": "success"}).eq("id", task['id']).execute()
                else:
                    print(f"🔎 [情報缺失] 網頁解析成功但無 MP3 連結。")
            else:
                print(f"❌ [失敗] {test_mode} 回報：{resp.status_code if resp else 'No Resp'}")

        except Exception as e:
            print(f"⚠️ [異常] {test_mode} 執行崩潰: {e}")
# -----(定位線)以上修改----
# -----(定位線)以上修改----
if __name__ == "__main__":
    run_expedition_test()