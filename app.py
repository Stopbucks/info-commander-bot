# ---------------------------------------------------------
# 本程式碼：app.py (Render 據點通訊官)
# 任務：接收 GitHub 訊號 -> 立即回傳 OK -> 啟動背景轉運程序
# ---------------------------------------------------------
import subprocess, os
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/fallback', methods=['POST'])
def trigger_fallback():
    # 驗證通行證 (CRON_SECRET)
    incoming_secret = request.headers.get('X-Cron-Secret')
    if incoming_secret != os.environ.get("CRON_SECRET"):
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    
    # 執行「先回應再處理」戰術：啟動背景行程執行任務
    # 利用 Popen 啟動子程序，主程序立即結束並回傳結果。
    subprocess.Popen(["python", "src/pod_scra_fallback.py"])
    
    print("📡 [據點] 已收到轉運請求，轉交背景部隊執行。")
    return jsonify({"status": "accepted", "message": "Mission in progress"}), 202

if __name__ == "__main__":
    # 一行註解：Render 會自動指派 PORT，預設為 10000。
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))