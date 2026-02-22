# ---------------------------------------------------------
# 本程式碼：src/test_handoff_call.py v2.2 (第一管道決戰版)
# 任務：測試多種「遞紙條」路徑與密碼封裝方式，直擊 Render 轉運站。
# ---------------------------------------------------------
import os
import requests
from datetime import datetime, timezone
from urllib.parse import urlparse
from dotenv import load_dotenv

# 一行註解：啟動環境配置載入機制。
load_dotenv()

def run_shotgun_relay():
    # 一行註解：讀取 GitHub 映射變數。
    raw_url = os.environ.get("TARGET_A", "").strip()
    token = os.environ.get("TOKEN_A", "").strip()
    
    if not raw_url or not token:
        print("❌ [中止] 變數缺失。"); return

    # 🎯 座標清洗與路徑枚舉
    parsed = urlparse(raw_url)
    base_domain = f"{parsed.scheme}://{parsed.netloc}"
    
    # 一行註解：根據指揮官記憶，列出所有疑似「跑腿」的通訊路徑。
    paths = [
        "/api/webhook/podcast", # 記憶中的主要路徑
        "/webhook",             # 常見轉運入口
        "/api/podcast",         # 精簡版入口
        ""                      # 根目錄直接衝鋒
    ]

    # 一行註解：構建模擬情報負載。
    mock_data = {"cmd": "errand_test", "ts": datetime.now(timezone.utc).isoformat()}
    ua_headers = {"User-Agent": "Mozilla/5.0"}

    print(f"📡 [戰力全開] 開始對準 {base_domain} 進行 12 種組合掃描...")

    for path in paths:
        url = base_domain + path
        print(f"\n📍 偵測：{url if path else base_domain}")

        # --- ⚔️ 方案 A：最直覺的 JSON Body (遺產模式) ---
        # 結構：{"secret": "密碼", "data": {...}}
        try:
            r_body = requests.post(url, json={"secret": token, "data": mock_data}, headers=ua_headers, timeout=15)
            print(f"   [Body驗證] 狀態：{r_body.status_code}")
            if r_body.status_code in [200, 202]:
                print(f"🏆 [突破] 成功！路徑：{path} | 方式：JSON Body"); return
        except: pass

        # --- ⚔️ 方案 B：直覺的 Header (X-Cron-Secret) ---
        try:
            r_head = requests.post(url, json=mock_data, headers={"X-Cron-Secret": token, **ua_headers}, timeout=15)
            print(f"   [Header驗證] 狀態：{r_head.status_code}")
            if r_head.status_code in [200, 202]:
                print(f"🏆 [突破] 成功！路徑：{path} | 方式：X-Cron-Secret Header"); return
        except: pass

        # --- ⚔️ 方案 C：極致直接的 Query String (URL 參數) ---
        # 結構：...?secret=密碼
        try:
            r_query = requests.post(f"{url}?secret={token}", json=mock_data, headers=ua_headers, timeout=15)
            print(f"   [參數驗證] 狀態：{r_query.status_code}")
            if r_query.status_code in [200, 202]:
                print(f"🏆 [突破] 成功！路徑：{path} | 方式：Query Parameter"); return
        except: pass

    print("\n🚨 [回報] 12 種組合掃描完畢，未發現開放路徑。")

if __name__ == "__main__":
    run_shotgun_relay()