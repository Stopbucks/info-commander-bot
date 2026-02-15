# =========================================================
# RS (Rescue-Standalone) 獨立攻堅腳本 - v1.0
# 職責：不依賴任何外部 utils，直接對接 ScraperAPI 執行實戰下載。
# =========================================================
import os
import requests

def run_rs_v3_minimal():
    api_key = os.environ.get('SCRAP_API_KEY', '').strip()
    if not api_key:
        print("❌ [RS] 找不到 API KEY。")
        return

    proxy_url = f"http://scraperapi:{api_key}@proxy-server.scraperapi.com:8001"
    proxies = {"http": proxy_url, "https": proxy_url}
    
    target_url = "https://archive.org/download/OTRR_Sherlock_Holmes_Sir_Arthur_Conan_Doyle_Library/Sherlock_Holmes_480321_025_The_Case_of_the_Innocent_Murderess.mp3"
    
    # 🚀 [核心修正]：使用 ScraperAPI 專屬命令標頭，不使用標準 User-Agent [cite: 2026-02-15]
    # 💡 這能告訴代理伺服器「幫我擬態」，但不會產生協議層的衝突
    headers = {
        "keep-alive": "true" # 僅保留連線優化標頭，身分交給代理處理
    }

    print(f"🚀 [RS 實戰 V3] 使用純淨代理路徑，發起下載...")

    try:
        # 💡 重點：不再手動定義 UA，讓 ScraperAPI 免費版自動分配最穩定的身分
        with requests.get(target_url, proxies=proxies, headers=headers, stream=True, timeout=60, verify=False) as r:
            # 偵測是否被代理層擋下
            if r.status_code == 400:
                print("❌ [RS 失敗] 依然觸發 400，代表 Archive.org 強制要求本地擬態，準備執行最後備案。")
                return

            r.raise_for_status()
            
            save_path = "rs_final_success.mp3"
            downloaded_size = 0
            limit_size = 1.0 * 1024 * 1024 

            with open(save_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=16384):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        if downloaded_size >= limit_size:
                            print(f"✅ [RS 大捷] 通道全線通車！抓回樣本：{downloaded_size/(1024*1024):.2f} MB")
                            break
                            
        print(f"🏁 測試完成。")

    except Exception as e:
        print(f"❌ [RS 失敗] 系統異常: {e}")

if __name__ == "__main__":
    run_rs_v3_minimal()