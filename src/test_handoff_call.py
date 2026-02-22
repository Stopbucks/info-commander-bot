# ---------------------------------------------------------
# 本程式碼：src/test_handoff_call.py v2.0 (全路徑直擊版)
# 任務：以 6 種組合模式嘗試與 Render 握手，找出最直接的通訊路徑。
# ---------------------------------------------------------
import os
import requests
import json
from datetime import datetime, timezone
from dotenv import load_dotenv

# 一行註解：初始化環境變數。
load_dotenv()

def run_direct_shotgun_test():
    # 一行註解：讀取 GitHub 注入的原始座標與暗號。
    raw_url = os.environ.get("TARGET_A", "").strip()
    token = os.environ.get("TOKEN_A", "").strip()
    
    if not raw_url or not token:
        print("❌ [中止] 缺少關鍵作戰座標或暗號。")
        return

    # 一行註解：清洗網址，移除末端可能的斜槓。
    base_url = raw_url.rstrip('/')
    
    # 🎯 拼接嘗試清單：嘗試所有可能的入口。
    endpoints = [
        f"{base_url}/fallback",  # 方案 1：精準側門 (app.py 標記點)
        base_url,                # 方案 2：原始路徑 (GitHub Secret 原樣)
        f"{base_url}/"           # 方案 3：根目錄閉合
    ]

    # 一行註解：建立中性化測試負載。
    test_data = {"msg": "handshake_v2.0", "ts": datetime.now(timezone.utc).isoformat()}
    
    # 一行註解：偽裝真實瀏覽器指紋，繞過 WAF 攔截。
    browser_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

    print(f"🚀 [決戰開啟] 準備進行多維度座標測試...")

    for i, url in enumerate(endpoints, 1):
        print(f"\n📍 測試路徑 {i}: {url[-25:]}")

        # --- ⚔️ 模式 A：遺產 JSON Body 驗證 (最直覺的舊法) ---
        print("   🔹 [模式 A] 嘗試 Body Secret...")
        try:
            r_body = requests.post(
                url, 
                json={"secret": token, "data": test_data},
                headers={"User-Agent": browser_ua},
                timeout=15
            )
            print(f"      回報：{r_body.status_code} | 回應：{r_body.text[:30]}")
            if r_body.status_code in [200, 202]:
                print(f"🏆 [大獲全勝] 成功座標：{url} | 模式：Body Secret"); return
        except: print("      ❌ 網路潰敗")

        # --- ⚔️ 模式 B：現役 X-Cron-Secret Header 驗證 ---
        print("   🔹 [模式 B] 嘗試 Header Secret...")
        try:
            r_head = requests.post(
                url, 
                json=test_data,
                headers={"X-Cron-Secret": token, "User-Agent": browser_ua},
                timeout=15
            )
            print(f"      回報：{r_head.status_code}")
            if r_head.status_code in [200, 202]:
                print(f"🏆 [大獲全勝] 成功座標：{url} | 模式：Header Secret"); return
        except: print("      ❌ 網路潰敗")

    print("\n🚨 [警告] 本輪 6 種組合皆未擊中目標。請確認 Render 服務名稱是否正確。")

if __name__ == "__main__":
    run_direct_shotgun_test()