#--------------------------------------------
#本程式為測試用：src/test_tg_comms.py
#--------------------------------------------
import os, requests



def run_tg_test():
    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    tg_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    # 一行註解：若 Secret 沒被讀取到，直接點破問題所在。
    if not tg_token:
        print("❌ [致命傷] 程式抓不到 TELEGRAM_BOT_TOKEN，請檢查 YAML 縮進！")
        return
    
    print(f"📡 [身份驗證中...] Token 前 5 碼：{tg_token[:5]}...")
     
    # 一行註解：建立一則包含 Markdown 語法的測試訊息。
    test_msg = "🚨 **司令部通訊測試**\n\n這是一則自動化測試訊息，旨在驗證 S-Plan 4.0 通訊官連線是否正常。"
    
    url = f"https://api.telegram.org/bot{tg_token}/sendMessage"
    payload = {"chat_id": tg_chat_id, "text": test_msg, "parse_mode": "Markdown"}
    
    try:
        resp = requests.post(url, json=payload, timeout=10)
        # 一行註解：印出詳細回應，這是找出問題（如 400 錯誤）的關鍵。
        if resp.status_code == 200:
            print("✅ [成功] 訊息已順利送達 Telegram 頻道！")
        else:
            print(f"❌ [失敗] TG 回傳代碼 {resp.status_code}")
            print(f"🕵️ 錯誤細節：{resp.text}")
    except Exception as e:
        print(f"⚠️ [異常]：{str(e)}")

if __name__ == "__main__":
    run_tg_test()