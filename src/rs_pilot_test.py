# =========================================================
# RS (Rescue-Standalone) 獨立攻堅腳本 - v2.0
# 職責：不依賴任何外部 utils， ScraperAPI 執行實戰下載Podbay.fm 的網頁原始碼。
# =========================================================
import os
import requests

def run_sherlock_anatomy():
    """🕵️ [S-Plan 解剖] 抓取 Podbay 頁面原始碼，定位音訊特徵"""
    api_key = os.environ.get('SCRAP_API_KEY', '').strip()
    
    # 🎯 實驗對象：以 Odd Lots 某集為例 (Podbay 網址格式)
    # 指揮官可隨時更換為您想分析的具體集數網址
    target_url = "https://podbay.fm/p/odd-lots/e/1707994800" 
    
    if not api_key:
        print("❌ [RS] 找不到 API KEY。")
        return

    proxy_url = f"http://scraperapi:{api_key}@proxy-server.scraperapi.com:8001"
    proxies = {"http": proxy_url, "https": proxy_url}
    headers = {"User-Agent": "Mozilla/5.0"}

    print(f"📡 [偵察啟動] 正在解剖 Podbay 頁面：{target_url}")

    try:
        # 💡 S-Plan 核心：我們只抓 HTML (文字)，不抓音訊，ScraperAPI 100% 能過 [cite: 2026-02-15]
        resp = requests.get(target_url, proxies=proxies, headers=headers, timeout=30)
        resp.raise_for_status()
        
        html_content = resp.text
        print(f"✅ [情報回傳] 成功取得網頁，長度：{len(html_content)} 字元")

        # 🚀 [關鍵：尋找隱藏線索]
        # 我們在 Log 中過濾出可能的音訊標籤特徵
        clues = ["og:audio", "download", ".mp3", "audio_url", "enclosure"]
        print("\n🔍 [線索掃描報告]:")
        for clue in clues:
            found_idx = html_content.find(clue)
            if found_idx != -1:
                # 印出關鍵字前後 100 個字元供後續開發參考
                snippet = html_content[max(0, found_idx-50):found_idx+150].replace('\n', ' ')
                print(f"📍 發現標籤 [{clue}]: ...{snippet}...")

    except Exception as e:
        print(f"❌ [解剖失敗] 原因: {e}")

if __name__ == "__main__":
    run_sherlock_anatomy()