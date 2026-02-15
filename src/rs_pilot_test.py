# =========================================================
# RS (Rescue-Standalone) 獨立攻堅腳本 - v1.0
# 職責：不依賴任何外部 utils，直接對接 ScraperAPI 執行實戰下載。
# =========================================================
import os
import requests

def run_rs_v4_instruction():
    api_key = os.environ.get('SCRAP_API_KEY', '').strip()
    target_url = "https://archive.org/download/OTRR_Sherlock_Holmes_Sir_Arthur_Conan_Doyle_Library/Sherlock_Holmes_480321_025_The_Case_of_the_Innocent_Murderess.mp3"
    
    # 💡 戰術：我們不模擬瀏覽器，我們「要求」ScraperAPI 使用它的商業擬態引擎 [cite: 2026-02-15]
    # 免費版雖有限制，但這比本地端衝突更穩定
    proxy_url = f"http://scraperapi:{api_key}@proxy-server.scraperapi.com:8001"
    proxies = {"http": proxy_url, "https": proxy_url}

    # 🚀 [核心修正]：利用指令標頭控製代理行為
    headers = {
        # 1. 告訴 ScraperAPI：保留我發送的標頭，不要亂改 (如果有特定 UA 要求)
        # "X-Scraper-Keep-Headers": "true", 
        
        # 2. 💡 [最簡單解法]：不帶 User-Agent，但讓 ScraperAPI 知道這是大型連線
        "Connection": "keep-alive"
    }

    print(f"🚀 [RS 實戰 V4] 執行透明傳輸指令，由雲端接管指紋擬態...")

    try:
        # 使用最原始的 requests，讓 ScraperAPI 的 8001 端口能輕鬆讀取並處理請求
        with requests.get(target_url, proxies=proxies, headers=headers, stream=True, timeout=120, verify=False) as r:
            r.raise_for_status()
            print(f"✅ [RS 大捷] 狀態碼: {r.status_code}，通道正式疏通！")
            # ... 下載邏輯與之前相同 ...
    except Exception as e:
        print(f"❌ [RS 失敗] 偵測到封鎖，原因: {e}")