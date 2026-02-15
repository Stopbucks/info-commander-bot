# =========================================================
# RS (Rescue-Standalone) 獨立攻堅腳本 - v1.0
# 職責：不依賴任何外部 utils，直接對接 ScraperAPI 執行實戰下載。
# =========================================================
import os
import requests
import time

def run_rs_mission():
    # --- 1. [裝備領取] ---
    # 💡 專業防錯：加上 .strip() 避免 Secrets 隱形空格 [cite: 2026-02-15]
    api_key = os.environ.get('SCRAP_API_KEY', '').strip()
    
    if not api_key or api_key == "GitHub_Runner_Direct":
        print("❌ [RS 失敗] 找不到有效的 SCRAP_API_KEY。")
        return

    # 💡 封裝 ScraperAPI 專用代理格式 [cite: 2026-02-15]
    proxy_url = f"http://scraperapi:{api_key}@proxy-server.scraperapi.com:8001"
    
    target_url = "https://archive.org/download/OTRR_Sherlock_Holmes_Sir_Arthur_Conan_Doyle_Library/Sherlock_Holmes_480321_025_The_Case_of_the_Innocent_Murderess.mp3"
    save_path = "rs_output_test.mp3"

    print(f"🚀 [RS 指揮部] 啟動單獨路徑攻堅：{target_url}")

    # --- 2. [連線配置] ---
    # 💡 戰術原則：採用標準 requests 引擎，並淨化 Session [cite: 2026-02-15]
    session = requests.Session()
    session.proxies = {"http": proxy_url, "https": proxy_url}
    
    # 🚀 [關鍵修正]：提供最基礎的標頭，避免 400 錯誤且讓 ScraperAPI 接手擬態 [cite: 2026-02-15]
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    })

    # --- 3. [實戰提取] ---
    try:
        print(f"📡 [執行] 跳過巡航與體檢，直突目標 (Fast-In Fast-Out)... [cite: 2026-02-15]")
        
        # 💡 verify=False 繞過環境憑證限制
        with session.get(target_url, stream=True, timeout=60, verify=False) as r:
            r.raise_for_status()
            
            downloaded_size = 0
            limit_size = 1.0 * 1024 * 1024  # 🚀 嚴格鎖定 1MB [cite: 2026-02-15]
            
            with open(save_path, "wb") as f:
                # 💡 每 chunk 8KB，完美適應 512MB RAM [cite: 2026-02-15]
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        # 🛡️ 達成 1MB 即刻熔斷，節省點數 [cite: 2026-02-15]
                        if downloaded_size >= limit_size:
                            print(f"✅ [RS 大捷] 已擷取 1.0MB 取樣，執行戰術切斷。")
                            break
                            
        print(f"🏁 任務成功完成，檔案已存放至: {save_path}")
        
    except Exception as e:
        print(f"💥 [RS 崩潰] 錯誤原因: {str(e)}")
    finally:
        session.close()

if __name__ == "__main__":
    run_rs_mission()