# ---------------------------------------------------------
# 本程式碼：src/test_handoff_call.py v1.5 (資安與語法修正版)
# 任務：執行端點之通訊協議相容性驗證與握手測試。
# ---------------------------------------------------------


import os, requests, json
from datetime import datetime, timezone
from dotenv import load_dotenv

# 一行註解：初始化環境配置。
load_dotenv()

def run_legacy_handshake():
    # 一行註解：讀取映射變數，確保公開倉庫不留原名。
    target_url = os.environ.get("TARGET_A")
    secret_key = os.environ.get("TOKEN_A")
    
    if not target_url or not secret_key:
        print("❌ [中止] 缺乏通訊座標或憑證。")
        return

    # 一行註解：建立與遺產代碼一致的數據負載。
    data_payload = {
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "mission_type": "legacy_handshake_test"
    }
    
    # 🎯 核心回歸：將 secret 放在 JSON Body 內而非 Header。
    # 一行註解：這是之前 PodcastProcessor 成功發送訊息的關鍵包裝結構。
    final_payload = {
        "secret": secret_key, 
        "data": data_payload
    }

    print(f"📡 [回歸測試] 正在發送 JSON 封裝負載...")
    try:
        # 一行註解：執行 POST 請求，讓 requests 自動處理 JSON 序列化。
        resp = requests.post(target_url, json=final_payload, timeout=30)
        
        print(f"📡 [回報] 狀態碼：{resp.status_code}")
        print(f"📡 [回應摘要]：{resp.text[:50]}...")
        
        if resp.status_code in [200, 202]:
            print(f"🏆 [突破] 握手成功！遺產邏輯在當前環境依然有效。")
        else:
            print(f"⚠️ [未果] 握手失敗，伺服器不接受此封裝格式。")
            
    except Exception:
        print("❌ [錯誤] 通訊鏈路實體斷裂。")

if __name__ == "__main__":
    run_legacy_handshake()

