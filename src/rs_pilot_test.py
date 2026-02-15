# =========================================================
# RS (Rescue-Standalone) 獨立攻堅腳本 - v1.0
# 職責：不依賴任何外部 utils，直接對接 ScraperAPI 執行實戰下載。
# =========================================================
import os
import requests
import random
import time

# 🚀 專業實踐：模擬人類閱讀或點擊後的反應時間
rest_time = random.uniform(3.5, 7.2) 
print(f"🕒 [擬態中] 任務間隙：休息 {rest_time:.1f} 秒...")
time.sleep(rest_time)

def run_rs_full_diagnostic():
    """🚀 [RS 全頻譜] 診斷 ScraperAPI：文字 vs 圖片 vs 音訊"""
    api_key = os.environ.get('SCRAP_API_KEY', '').strip()
    if not api_key:
        print("❌ [RS] 遺失金鑰。")
        return

    proxy_url = f"http://scraperapi:{api_key}@proxy-server.scraperapi.com:8001"
    proxies = {"http": proxy_url, "https": proxy_url}
    
    # 🎯 偵察目標清單
    missions = [
        {"name": "NASA 純文字 (robots.txt)", "url": "https://www.nasa.gov/robots.txt", "type": "text"},
        {"name": "NASA 圖片 (Small JPG)", "url": "https://www.nasa.gov/wp-content/themes/nasa/assets/images/nasa-logo.svg", "type": "image"},
        {"name": "LibriVox 音訊 (HTTP MP3)", "url": "http://www.archive.org/download/short_story_007_librivox/tobias_mindernickel_mann_64kb.mp3", "type": "audio"}
    ]

    # 💡 使用極簡擬態，避免與代理引擎衝突 [cite: 2026-02-15]
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "*/*"}

    print(f"📡 [RS 指揮部] 啟動全頻譜診斷程序...")

    for task in missions:
        print(f"\n--- 🛰️ 正在執行任務：{task['name']} ---")
        try:
            # 💡 針對不同類型設定不同的超時與串流策略
            is_stream = task['type'] != "text"
            resp = requests.get(task['url'], proxies=proxies, headers=headers, stream=is_stream, timeout=45, verify=False)
            
            print(f"🚩 伺服器回應狀態碼: {resp.status_code}")
            
            if resp.status_code == 200:
                if task['type'] == "text":
                    print(f"✅ [文字突破] 內容片段: {resp.text[:50]}...")
                else:
                    # 測試前 10KB 確保傳輸通道未被熔斷
                    content_chunk = next(resp.iter_content(chunk_size=10240))
                    print(f"✅ [{task['type'].upper()}突破] 成功獲取 {len(content_chunk)/1024:.1f} KB 數據流。")
            else:
                print(f"❌ [任務受阻] 原因: {resp.reason}")
                
        except Exception as e:
            print(f"💥 [技術故障] 該路徑崩潰: {str(e)[:50]}")

    print("\n🏁 [全頻譜偵察完畢] 請根據上方狀態碼判斷停損點。")

if __name__ == "__main__":
    run_rs_full_diagnostic()