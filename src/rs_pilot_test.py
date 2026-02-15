# =========================================================
# RS (Rescue-Standalone) 獨立攻堅腳本 - v1.0
# 職責：不依賴任何外部 utils，直接對接 ScraperAPI 執行實戰下載。
# =========================================================
import os
import requests

def run_rs_v4_instruction():
    """🚀 [RS 核心] 執行透明傳輸指令，由雲端接管指紋擬態"""
    # 1. 領取裝備
    api_key = os.environ.get('SCRAP_API_KEY', '').strip()
    target_url = "https://archive.org/download/OTRR_Sherlock_Holmes_Sir_Arthur_Conan_Doyle_Library/Sherlock_Holmes_480321_025_The_Case_of_the_Innocent_Murderess.mp3"
    
    if not api_key:
        print("❌ [RS] 找不到 API KEY，請確認 GitHub Secrets。")
        return

    # 2. 建立 8001 通道 (最適合免費版與大檔案)
    proxy_url = f"http://scraperapi:{api_key}@proxy-server.scraperapi.com:8001"
    proxies = {"http": proxy_url, "https": proxy_url}

    # 3. 💡 [解決衝突關鍵]：不要帶 User-Agent，讓 ScraperAPI 雲端引擎自行分配
    # 這樣能避免您擔心的「本地 UA 與雲端擬態衝突」導致 400 錯誤。 [cite: 2026-02-15]
    headers = {
        "Connection": "keep-alive", # 保持長連線，防止 499 錯誤
        "Accept": "*/*"
    }

    print(f"📡 [RS 啟動] 正在發起實戰提取演習... (目標: Archive.org)")

    try:
        # 使用 verify=False 避開 SSL 證書校驗衝突
        with requests.get(target_url, proxies=proxies, headers=headers, stream=True, timeout=120, verify=False) as r:
            r.raise_for_status()
            
            print(f"✅ [連線成功] 狀態碼: {r.status_code}，正在接收數據流...")
            
            save_path = "rs_final_test.mp3"
            downloaded = 0
            limit_size = 1.0 * 1024 * 1024  # 鎖定 1MB 樣本
            
            with open(save_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=32768):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if downloaded >= limit_size:
                            print(f"✅ [RS 大捷] 成功抓回樣本：{downloaded/(1024*1024):.2f} MB")
                            break
                            
        print(f"🏁 任務圓滿結束，檔案已存至本地。")

    except Exception as e:
        print(f"❌ [RS 失敗] 原因: {e}")

# 🚀 [核心修正]：加上執行入口，確保 Actions 啟動時會真的跑這段代碼 [cite: 2026-02-15]
if __name__ == "__main__":
    run_rs_v4_instruction()