# =========================================================
# RS (Rescue-Standalone) 獨立攻堅腳本 - v1.0
# 職責：不依賴任何外部 utils，直接對接 ScraperAPI 執行實戰下載。
# =========================================================
import os
import requests

def run_rs_mission():
    # 1. 領取裝備並過濾雜訊
    api_key = os.environ.get('SCRAP_API_KEY', '').strip()
    target_url = "https://archive.org/download/OTRR_Sherlock_Holmes_Sir_Arthur_Conan_Doyle_Library/Sherlock_Holmes_480321_025_The_Case_of_the_Innocent_Murderess.mp3"
    
    if not api_key:
        print("❌ [RS 失敗] 找不到 API KEY，請檢查 GitHub Secrets。")
        return

    print(f"🚀 [RS 啟動] 正在發起「自動編碼」攻堅任務...")
    print(f"🔑 Key 檢查：已載入 (長度: {len(api_key)})")

    # 💡 關鍵修正：使用 params 字典，讓 requests 自動處理網址編碼，根除 400 錯誤 [cite: 2026-02-15]
    payload = {
        'api_key': api_key,
        'url': target_url
    }

    try:
        # 💡 使用 https 確保通訊安全，並給予充足的 120 秒超時限制
        with requests.get('https://api.scraperapi.com', params=payload, stream=True, timeout=120) as r:
            r.raise_for_status()
            
            save_path = "rs_output_test.mp3"
            downloaded_size = 0
            limit_size = 1.0 * 1024 * 1024  # 鎖定 1MB [cite: 2026-02-15]

            with open(save_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        if downloaded_size >= limit_size:
                            print(f"✅ [RS 大捷] 成功擷取 {downloaded_size/(1024*1024):.2f} MB，執行熔斷。")
                            break
                            
        print(f"🏁 任務圓滿結束，檔案已存至: {save_path}")
        
    except Exception as e:
        print(f"❌ [RS 失敗] 原因: {e}")

if __name__ == "__main__":
    run_rs_mission()