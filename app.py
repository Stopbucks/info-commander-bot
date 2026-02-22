
# ---------------------------------------------------------
# 本程式碼：app.py v2.5 (極速收據版)
# 任務：徹底分離子程序、整合 Secret File 讀取、維持 24H 在線
# ---------------------------------------------------------
import subprocess, os, json
from flask import Flask, request, jsonify

app = Flask(__name__)

# ==========================================================================
# --- 🛡️ 核心憑證庫模組 (Vault Module) ---
# ==========================================================================
def get_secret(key, default=None):
    """一行註解：優先從 Render Secret File 獲取暗號，失敗則回退至系統變數。"""
    vault_path = "/etc/secrets/render_secret_vault.json"
    if os.path.exists(vault_path):
        with open(vault_path, 'r') as f:
            vault = json.load(f)
            val = vault.get("active_credentials", {}).get(key)
            if val: return val
    return os.environ.get(key, default)

# ==========================================================================
# --- 閘門管理區 ---
# ==========================================================================

@app.route('/ping', methods=['GET'])
def health_check():
    # 一行註解：回應 200 OK 狀態碼，配合 UptimeRobot 維持據點熱機。
    return "Service Online", 200

@app.route('/fallback', methods=['POST'])
def trigger_fallback():
    # 🎯 核心修正：使用與 GitHub 對齊的 get_secret 函式。
    auth_token = get_secret("CRON_SECRET")
    incoming_secret = request.headers.get('X-Cron-Secret')
    
    if incoming_secret != auth_token:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    
    # 🎯 關鍵戰術：徹底解耦 Popen (防止 Read timed out)
    # 一行註解：重導向所有串流至 DEVNULL，確保子程序完全脫離請求生命週期。
    subprocess.Popen(
        ["python", "src/pod_scra_fallback.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        close_fds=True,
        start_new_session=True
    )
    
    print("📡 [據點] 已收到轉運指令，收據已開，立即投入背景執行。")
    # 一行註解：立即回傳 202 訊號給 GitHub，不再等待子程序啟動。
    return jsonify({"status": "accepted", "message": "Mission in progress"}), 202

 
if __name__ == "__main__":
        
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)