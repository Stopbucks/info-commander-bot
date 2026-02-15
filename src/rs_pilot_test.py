# =========================================================
# RS (Rescue-Standalone) 獨立攻堅腳本 - v1.0
# 職責：不依賴任何外部 utils，直接對接 ScraperAPI 執行實戰下載。
# =========================================================
import os
import requests

def run_rs_mission():
    api_key = os.environ.get('SCRAP_API_KEY', '').strip()
    # 💡 戰術變更：使用 ScraperAPI 的 API 入口，而非 8001 代理端口，增加穩定性
    target_url = "https://archive.org/download/OTRR_Sherlock_Holmes_Sir_Arthur_Conan_Doyle_Library/Sherlock_Holmes_480321_025_The_Case_of_the_Innocent_Murderess.mp3"
    
    # 這是另一種對接方式，能有效解決 499 錯誤 [cite: 2026-02-15]
    scraper_url = f"http://api.scraperapi.com?api_key={api_key}&url={target_url}"

    print(f"🚀 [RS 啟動] 正在透過 API 端點發起攻堅...")

    try:
        # 使用流式下載，鎖定 1MB 
        with requests.get(scraper_url, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open("rs_test.mp3", "wb") as f:
                downloaded = 0
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if downloaded >= 1024 * 1024:
                            print(f"✅ [RS 大捷] 已成功獲取 1.0MB 樣本，戰術性切斷。")
                            break
    except Exception as e:
        print(f"❌ [RS 失敗] 原因: {e}")

if __name__ == "__main__":
    run_rs_mission()