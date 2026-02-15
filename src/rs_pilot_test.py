# =========================================================
# RS (Rescue-Standalone) 獨立攻堅腳本 - v2.0
# 職責：不依賴任何外部 utils， ScraperAPI 執行實戰下載Podbay.fm 的網頁原始碼。
# =========================================================
import os
import requests
import feedparser
import random
import time

# 🚀 隨機休息：確保啟動時的擬態安全性 [cite: 2026-02-15]
time.sleep(random.uniform(3, 6))

def run_s_plan_integrated_test():
    """🚀 [S-Plan 整合測試] 從 RSS 提取標題 -> 前往 Podbay 偵察網址"""
    api_key = os.environ.get('SCRAP_API_KEY', '').strip()
    
    # 📋 指揮官提供的兵力部署清單 (JSON 模擬)
    squad_targets = [
        {"name": "Odd Lots-Bloomberg", "url": "https://omnycontent.com/d/playlist/e73c998e-6e60-432f-8610-ae210140c5b1/8A94442E-5A74-4FA2-8B8D-AE27003A8D6B/982F5071-765C-403D-969D-AE27003A8D83/podcast.rss"},
        {"name": "FT - unhedged", "url": "https://feeds.acast.com/public/shows/6478a825654260001190a7cb"}
    ]

    print(f"📡 [S-Plan 啟動] 正在執行整合偵察任務...")

    for target in squad_targets:
        print(f"\n--- 🛰️ 正在解析 RSS：{target['name']} ---")
        try:
            # Step 1: 解析 RSS 獲取最新集數資訊 [cite: 2026-01-16]
            feed = feedparser.parse(target['url'])
            if not feed.entries:
                print(f"❌ 無法讀取 RSS 內容")
                continue
            
            latest_title = feed.entries[0].title
            print(f"📍 獲取最新集標題：{latest_title[:40]}...")

            # Step 2: 構造 Podbay 搜尋連結 (模擬偵察兵尋找目標) [cite: 2026-02-15]
            # 💡 技巧：將標題放入 Podbay 搜尋，ScraperAPI 會幫我們拿到搜尋結果頁
            search_query = latest_title.replace(" ", "+")
            podbay_search_url = f"https://podbay.fm/search?q={search_query}"
            
            # Step 3: 使用 ScraperAPI 執行網頁解剖 (HTML 抓取)
            proxy_url = f"http://scraperapi:{api_key}@proxy-server.scraperapi.com:8001"
            proxies = {"http": proxy_url, "https": proxy_url}
            headers = {"User-Agent": "Mozilla/5.0"}
            
            print(f"🔍 [雲端偵察] 正在透過 ScraperAPI 尋找鏡像門票...")
            # 🚀 加上 verify=False 修復之前的 SSL 報警 [cite: 2026-02-15]
            resp = requests.get(podbay_search_url, proxies=proxies, headers=headers, timeout=30, verify=False)
            
            if resp.status_code == 200:
                print(f"✅ [偵察大捷] 成功取得 Podbay 搜尋結果！頁面大小：{len(resp.text)//1024} KB")
                # 這裡我們暫時只檢測標籤是否存在，作為下一步 Selector 的依據
                if latest_title[:10] in resp.text:
                    print(f"🎯 狀態：已在 HTML 中定位到目標集數。")
                else:
                    print(f"⚠️ 警告：HTML 中未發現匹配標題，可能需要更精確的搜尋。")
            else:
                print(f"❌ [偵察受阻] 狀態碼：{resp.status_code}")

        except Exception as e:
            print(f"💥 [技術故障] 該目標執行失敗: {str(e)[:60]}")

    print("\n🏁 [S-Plan 階段測試結束]")

if __name__ == "__main__":
    run_s_plan_integrated_test()