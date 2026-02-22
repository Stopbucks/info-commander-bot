# ---------------------------------------------------------
# 本程式碼：src/test_handoff_call.py v1.6 (雙模偵察版)
# 任務：同時驗證 Body-Secret 與 Header-Secret 兩條通路。
# ---------------------------------------------------------
import os
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv

# 一行註解：初始化環境變數。
load_dotenv()

def run_dual_protocol_test():
    # 一行註解：讀取映射變數，避免暴露原始 Secret 名稱。
    target_url = os.environ.get("TARGET_A")
    token = os.environ.get("TOKEN_A")
    
    if not target_url or not token:
        print("❌ [中止] 變數缺失。")
        return

    # 一行註解：建構中性化的測試數據。
    test_data = {"status": "sync_test", "utc": datetime.now(timezone.utc).isoformat()}

    # --- ⚔️ 第一輪：老派戰術 (JSON Body 封裝) ---
    print(f"📡 [嘗試 1/2] 正在發送 JSON Body 驗證包...")
    payload_body = {"secret": token, "data": test_data}
    
    try:
        r1 = requests.post(target_url, json=payload_body, timeout=30)
        print(f"📡 [回報] 狀態碼：{r1.status_code} | 回應：{r1.text[:50]}...")
        if r1.status_code in [200, 202]:
            print("🏆 [突破] 確定使用：JSON Body 驗證 (老派戰術有效)！")
            return
    except Exception:
        print("❌ [失敗] 第一通路斷裂。")

    # --- ⚔️ 第二輪：現役戰術 (X-Cron-Secret Header) ---
    print(f"📡 [嘗試 2/2] 正在發送 Header 標頭驗證...")
    custom_headers = {"X-Cron-Secret": token, "Content-Type": "application/json"}
    
    try:
        r2 = requests.post(target_url, json=test_data, headers=custom_headers, timeout=30)
        print(f"📡 [回報] 狀態碼：{r2.status_code} | 回應：{r2.text[:50]}...")
        if r2.status_code in [200, 202]:
            print("🏆 [突破] 確定使用：X-Cron-Secret Header (現代戰術有效)！")
            return
    except Exception:
        print("❌ [失敗] 第二通路斷裂。")

    print("🚨 [警告] 雙路徑皆未回傳成功訊號，請檢查 URL 是否包含路徑尾碼。")

if __name__ == "__main__":
    run_dual_protocol_test()