# =========================================================
# RS (Rescue-Standalone) 獨立攻堅腳本 - v1.0
# 職責：不依賴任何外部 utils，直接對接 ScraperAPI 執行實戰下載。
# =========================================================
import os
import requests

def run_simple_rs():
    # 1. 領取裝備 (API KEY)
    api_key = os.environ.get('SCRAP_API_KEY', '').strip()
    if not api_key:
        print("❌ [RS] 找不到 API KEY，請檢查 GitHub Secrets。")
        return

    # 2. 封裝最標準的代理地址
    proxy_url = f"http://scraperapi:{api_key}@proxy-server.scraperapi.com:8001"
    proxies = {"http": proxy_url, "https": proxy_url}

    # 🎯 先測試 Google (極簡目標)，再測試 Archive (實戰目標)
    test_url = "http://www.google.com" 
    
    print(f"📡 [RS 低空偵察] 正在嘗試透過 8001 端口連線至: {test_url}")

    try:
        # 💡 戰術核心：不自定義任何標頭，讓標準 requests 處理所有必要欄位
        # 💡 使用 http (非 s) 測試，進一步降低握手失敗風險
        resp = requests.get(test_url, proxies=proxies, timeout=30, verify=False)
        
        print(f"🚩 [偵察回報] 狀態碼: {resp.status_code}")
        if resp.status_code == 200:
            print("✅ [首戰大捷] 代理通道完全暢通！免費版支援此路徑。")
        else:
            print(f"⚠️ [連線成功但被擋] 伺服器回傳: {resp.text[:100]}")

    except Exception as e:
        print(f"💥 [偵察崩潰] 原因: {e}")

if __name__ == "__main__":
    run_simple_rs()