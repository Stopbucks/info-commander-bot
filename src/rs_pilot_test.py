# =========================================================
# RS (Rescue-Standalone) 獨立攻堅腳本 - v1.0
# 職責：不依賴任何外部 utils，直接對接 ScraperAPI 執行實戰下載。
# =========================================================
import os
import requests

def run_podcast_rs():
    # 1. 領取金鑰
    api_key = os.environ.get('SCRAP_API_KEY', '').strip()
    if not api_key:
        print("❌ [RS] 找不到 API KEY。")
        return

    # 2. 建立 8001 通道 (剛才驗證成功的模式)
    proxy_url = f"http://scraperapi:{api_key}@proxy-server.scraperapi.com:8001"
    proxies = {"http": proxy_url, "https": proxy_url}
    
    # 🎯 實戰目標：Archive.org 音檔
    target_url = "https://archive.org/download/OTRR_Sherlock_Holmes_Sir_Arthur_Conan_Doyle_Library/Sherlock_Holmes_480321_025_The_Case_of_the_Innocent_Murderess.mp3"
    
    print(f"🚀 [RS 實戰] 通道已確認，正在提取音檔樣本...")

    try:
        # 💡 使用 stream=True 避免大檔案撐爆記憶體 [cite: 2026-02-15]
        # 💡 verify=False 避免 GitHub 環境的憑證衝突
        with requests.get(target_url, proxies=proxies, stream=True, timeout=60, verify=False) as r:
            r.raise_for_status()
            
            save_path = "rs_final_test.mp3"
            downloaded = 0
            limit_size = 1.0 * 1024 * 1024  # 🚀 嚴格鎖定 1.0MB
            
            with open(save_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=16384): # 加大 chunk 提高傳輸效率
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        # 🛡️ 達成 1MB 即刻熔斷
                        if downloaded >= limit_size:
                            print(f"✅ [RS 大捷] 成功抓回樣本：{downloaded/(1024*1024):.2f} MB")
                            break
                            
        print(f"🏁 任務成功完成，檔案路徑: {save_path}")

    except Exception as e:
        print(f"❌ [RS 失敗] 原因: {e}")

if __name__ == "__main__":
    run_podcast_rs()