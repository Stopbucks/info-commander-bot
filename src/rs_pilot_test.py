# =========================================================
# RS (Rescue-Standalone) 獨立攻堅腳本 - v2.0
# 職責：不依賴任何外部 utils， ScraperAPI 執行實戰下載Podbay.fm 的網頁原始碼。
# =========================================================
import os
import requests

def run_sherlock_anatomy_v2():
    """🕵️ [S-Plan 解剖] 修復 SSL 報警，精確提取 Podbay 線索"""
    api_key = os.environ.get('SCRAP_API_KEY', '').strip()
    target_url = "https://podbay.fm/p/odd-lots/e/1707994800" 
    
    if not api_key:
        print("❌ [RS] 找不到 API KEY。")
        return

    proxy_url = f"http://scraperapi:{api_key}@proxy-server.scraperapi.com:8001"
    proxies = {"http": proxy_url, "https": proxy_url}
    
    # 💡 專業建議：維持極簡 Header，僅加上 Accept 讓請求更像瀏覽器 [cite: 2026-02-15]
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/html,application/xhtml+xml,xml;q=0.9,*/*;q=0.8"
    }

    print(f"📡 [偵察啟動] 正在執行 S-Plan 頁面解剖...")

    try:
        # 🚀 [核心修正]：verify=False 徹底繞過 SSL 證書錯誤 [cite: 2026-02-15]
        resp = requests.get(target_url, proxies=proxies, headers=headers, timeout=45, verify=False)
        resp.raise_for_status()
        
        print(f"✅ [成功突破] 網頁已載入，長度：{len(resp.text)} 字元")

        # 🎯 S-Plan 關鍵定位符搜索
        for clue in ["og:audio", "download-link", ".mp3", "audio-player"]:
            pos = resp.text.find(clue)
            if pos != -1:
                # 抓取特徵前後文 100 字元，這是我們寫 Regex 的依據 [cite: 2026-02-15]
                snippet = resp.text[max(0, pos-40):pos+120].replace('\n', '')
                print(f"📍 線索 [{clue}]: ...{snippet}...")

    except Exception as e:
        print(f"❌ [任務潰敗] 原因: {e}")

if __name__ == "__main__":
    run_sherlock_anatomy_v2()