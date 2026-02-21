# ---------------------------------------------------------
# 本程式碼：src/test_handoff_call.py
# 職責：驗證 RENDER_WEBHOOK 與 CRON_SECRET 的通訊活性。
# ---------------------------------------------------------
import os
import requests
from dotenv import load_dotenv

# 一行註解：載入環境配置。
load_dotenv()

def test_render_webhook():
    # 一行註解：從 Secrets 讀取標竿網址。
    webhook_url = os.environ.get("RENDER_WEBHOOK_URL")
    if not webhook_url:
        print("❌ [跳過] RENDER_WEBHOOK_URL 未設定。")
        return

    print(f"📡 [方案 A] 正在發送直連 Webhook：{webhook_url[:40]}...")
    try:
        # 一行註解：執行 POST 請求，這是 Render Deploy Hook 的標準動作。
        resp = requests.post(webhook_url, timeout=15)
        print(f"📡 [回報] 狀態碼：{resp.status_code} | 回應：{resp.text[:100]}")
    except Exception as e:
        print(f"❌ [失敗] 網路潰敗: {e}")

def test_cron_secret_call():
    # 一行註解：測試是否需要透過 CRON_SECRET 驗證特定 API 節點。
    # 這裡假設您的 Render 或 Vercel 服務需要一個 Authorization Header。
    target_url = os.environ.get("VERCEL_SCOUT_URL") or os.environ.get("RENDER_WEBHOOK_URL")
    secret = os.environ.get("CRON_SECRET")
    
    if not secret or not target_url:
        print("❌ [跳過] CRON_SECRET 或目標 URL 缺失。")
        return

    print(f"🔐 [方案 B] 正在發送帶有 Secret 驗證的請求...")
    headers = {"Authorization": f"Bearer {secret}"}
    try:
        # 一行註解：執行帶有驗證標頭的 GET 請求。
        resp = requests.get(target_url, headers=headers, timeout=15)
        print(f"🔐 [回報] 狀態碼：{resp.status_code} | 回應：{resp.text[:100]}")
    except Exception as e:
        print(f"❌ [失敗] 驗證鏈路中斷: {e}")

if __name__ == "__main__":
    print("🚀 [通訊檢測啟動]")
    test_render_webhook()
    print("-" * 30)
    test_cron_secret_call()