# ---------------------------------------------------------
# 本程式碼：app.py (Render 據點通訊官 - 強化版)
# 任務：新增 /ping 閘門回應 UptimeRobot，維持據點 24H 在線
# ---------------------------------------------------------
import subprocess, os
from flask import Flask, request, jsonify

app = Flask(__name__)

# --- 🚀 新增：UptimeRobot 專用閘門 ---
@app.route('/ping', methods=['GET'])
def health_check():
    # 一行註解：回應 200 OK 狀態碼，讓 UptimeRobot 確認服務在線。
    return "Service Online", 200

@app.route('/fallback', methods=['POST'])
def trigger_fallback():
    # 驗證通行證 (CRON_SECRET)
    incoming_secret = request.headers.get('X-Cron-Secret')
    if incoming_secret != os.environ.get("CRON_SECRET"):
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    
    # 啟動背景行程執行任務
    # 一行註解：利用 Popen 啟動子程序，主程序立即結束並回傳 202 成功代碼。
    subprocess.Popen(["python", "src/pod_scra_fallback.py"])
    
    print("📡 [據點] 已收到轉運請求，轉交背景部隊執行。")
    return jsonify({"status": "accepted", "message": "Mission in progress"}), 202

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))