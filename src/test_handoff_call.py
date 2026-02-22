# ---------------------------------------------------------
# 本程式碼：src/test_handoff_call.py v2.5 (Gunicorn 對位版)
# 任務：進行Render & gunicorn 啟動環境，進行最後的精準衝鋒。
# ---------------------------------------------------------
import os
import requests
from datetime import datetime, timezone
from urllib.parse import urlparse
from dotenv import load_dotenv

# 一行註解：初始化環境配置，對接 GitHub Secrets。
load_dotenv()

def run_gunicorn_handshake():
    # 一行註解：讀取映射變數，確保原始 Secret 安全。
    raw_url = os.environ.get("TARGET_A", "").strip()
    token = os.environ.get("TOKEN_A", "").strip()
    
    if not raw_url or not token:
        print("❌ [中止] 變數缺失。")
        return

    # 🎯 核心校準：強制指向截圖中 app:app 所代表的入口。
    parsed = urlparse(raw_url)
    target_url = f"{parsed.scheme}://{parsed.netloc}/fallback"

    # 一行註解：模擬真實瀏覽器，防止 Render 免費版 WAF 攔截。
    headers = {
        "X-Cron-Secret": token,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/json"
    }

    # 一行註解：建立符合第一管道遺產結構的負載。
    payload = {
        "secret": token, 
        "data": {"cmd": "final_handshake", "ts": datetime.now(timezone.utc).isoformat()}
    }

    print(f"📡 [精準衝鋒] 鎖定入口：{target_url[-15:]}")
    try:
        # 一行註解：發送帶有雙驗證資訊的 POST 請求。
        resp = requests.post(target_url, json=payload, headers=headers, timeout=60)
        
        print(f"📡 [回報] 狀態碼：{resp.status_code}")
        print(f"📡 [摘要]：{resp.text[:50]}...")
        
        if resp.status_code == 202:
            print(f"🏆 [突破] 成功！Render 基地已由 gunicorn 接收指令。")
        elif resp.status_code == 404:
            print(f"⚠️ [迷航] 404！請確認 app.py 內是否有定義 /fallback 路徑。")
        elif resp.status_code == 403:
            print(f"🚫 [驗證失敗] 403！請比對 Render Dashboard 內的 CRON_SECRET 與 GitHub 是否一致。")
            
    except Exception:
        print("❌ [失敗] 通訊實體鏈路斷裂。")

if __name__ == "__main__":
    run_gunicorn_handshake()