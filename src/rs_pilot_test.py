# =========================================================
# RS (Rescue-Standalone) 獨立攻堅腳本 - v1.0
# 職責：不依賴任何外部 utils，直接對接 ScraperAPI 執行實戰下載。
# =========================================================
import os
import requests

def run_rs_v5_nasa():
    """🚀 [RS 核心] 執行 NASA 網域穿透演習，驗證 ScraperAPI 住宅代理效能"""
    # 1. 領取裝備
    api_key = os.environ.get('SCRAP_API_KEY', '').strip()
    
    # 🎯 第二個目標：NASA 公共音訊節點 (Hubble Sounds)
    target_url = "https://www.nasa.gov/wp-content/uploads/2023/03/hubble-sounds-2.mp3"
    
    if not api_key:
        print("❌ [RS] 找不到 API KEY，任務中止。")
        return

    # 2. 建立 8001 通道 (維持驗證成功的極簡模式)
    proxy_url = f"http://scraperapi:{api_key}@proxy-server.scraperapi.com:8001"
    proxies = {"http": proxy_url, "https": proxy_url}

    # 3. 💡 [最高 CP 值策略]：完全不帶 User-Agent
    # 讓 ScraperAPI 免費版自行在雲端決定最適合對抗 NASA 防火牆的身分。 [cite: 2026-02-15]
    headers = {
        "Connection": "keep-alive",
        "Accept": "audio/mpeg, */*"
    }

    print(f"📡 [RS 啟動] 正在發起 NASA 穿透演習...")
    print(f"🔗 目標：{target_url}")

    try:
        # 使用 verify=False 確保不會因為 GitHub 端的 SSL 證書老舊而斷線
        with requests.get(target_url, proxies=proxies, headers=headers, stream=True, timeout=90, verify=False) as r:
            
            if r.status_code == 200:
                print(f"✅ [突破防線] 狀態碼: 200，成功進入 NASA 儲存庫！")
                
                save_path = "rs_nasa_test.mp3"
                downloaded = 0
                limit_size = 1.0 * 1024 * 1024 # 1MB 熔斷保護點數
                
                with open(save_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=32768):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if downloaded >= limit_size:
                                print(f"✅ [RS 大捷] 樣本提取成功：{downloaded/(1024*1024):.2f} MB")
                                break
                print(f"🏁 任務順利完成。")
            else:
                print(f"❌ [穿透失敗] 狀態碼: {r.status_code}。")
                if r.status_code == 401: print("💡 提示：請檢查 ScraperAPI 點數是否用盡。")
                if r.status_code == 403: print("💡 提示：NASA 封鎖了該代理節點。")

    except Exception as e:
        print(f"💥 [崩潰] 原因: {e}")

if __name__ == "__main__":
    run_rs_v5_nasa()