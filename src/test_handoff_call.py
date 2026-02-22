# ---------------------------------------------------------
# 本程式碼：src/test_handoff_call.py v1.2 (JSON 封裝版)
# 任務：測試 RENDER_WEBHOOK 透過 JSON Body 傳遞 Secret 的通訊方式
# ---------------------------------------------------------
# ---------------------------------------------------------
# 本程式碼：src/test_handoff_call.py v1.3 (資安強化版)
# 任務：執行遠端端點之通訊協議相容性驗證。
# ---------------------------------------------------------
import os
import requests
import json
from datetime import datetime, timezone
from dotenv import load_dotenv

# 一行註解：初始化環境變數載入機制。
load_dotenv()

#---環境變數讀取區塊相同---#


def run_protocol_verification():
    target_endpoint = os.environ.get("RENDER_WEBHOOK_URL")
    auth_token = os.environ.get("CRON_SECRET")
    
    if not target_endpoint or not auth_token:
        print("❌ [中止] 系統環境變數配置不全。")
        return

    # 一行註解：建立標準化通訊負載封裝。
    sync_data = {
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "trace_id": "handoff_v1.3",
        "system_msg": "protocol_test"
    }
    
    # 一行註解：整合驗證憑證與數據內容，確保結構對位。
    secure_payload = {
        "secret": auth_token, 
        "data": sync_data
    }

    print(f"📡 [通訊發動] 正在執行端點協議校驗...")
    try:
        # 一行註解：執行 POST 傳遞 JSON 數據，並限制請求超時以策安全。
        resp = requests.post(target_endpoint, json=secure_payload, timeout=30)
        
        print(f"📡 [回報] 狀態碼：{resp.status_code}")
        # 一行註解：僅輸出首 50 字元回應，防止日誌包含過多伺服器指紋資訊。
        print(f"📡 [回應摘要]：{resp.text[:50]}...")
        
        if resp.status_code in [200, 202]:
            print(f"✅ [成功] 端點身分驗證通過，鏈路已啟動。")
        else:
            print(f"⚠️ [異常] 通訊回傳非預期狀態碼。")
            
    except Exception:
        # 一行註解：遮蔽具體錯誤內容，防止異常堆疊資訊外洩至 GitHub 日誌。
        print("❌ [錯誤] 遠端鏈路連線異常。")

if __name__ == "__main__":
    run_protocol_verification()
