# ---------------------------------------------------------
# 本程式碼：app.py v3.1 (自驅動戰術交接版)
# 任務：身分自動對位、48H 週期判定、自主交接指揮權
# ---------------------------------------------------------
import subprocess, os, json, time
from flask import Flask, jsonify
from supabase import create_client, Client
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

# ==========================================================================
# --- 🛡️ 憑證庫與戰術讀取 (Vault & Tactics) ---
# ==========================================================================

def get_secret(key, default=None):
    """一行註解：跨環境憑證讀取，確保在 Render 與 GitHub 均能獲取正確金鑰。"""
    vault_path = "/etc/secrets/render_secret_vault.json"
    if os.path.exists(vault_path):
        with open(vault_path, 'r') as f:
            vault = json.load(f); return vault.get("active_credentials", {}).get(key)
    return os.environ.get(key, default)

def get_supabase_client():
    """一行註解：初始化 Supabase 戰略客戶端。"""
    return create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))

# ==========================================================================
# --- ⚔️ 自主巡邏與交接邏輯 (Patrol & Handover) ---
# ==========================================================================

def run_base_patrol():
    """
    🕵️ [巡邏隊] 自主判定執勤狀態：
    1. 檢查是否為 RENDER 執勤
    2. 檢查執勤時間是否過期 -> 若過期則交棒給 GITHUB
    """
    sb = get_supabase_client()
    # 一行註解：從戰術板獲取當前全球執勤派令。
    res = sb.table("pod_scra_tactics").select("*").eq("id", 1).execute()
    if not res.data: return
    
    tactics = res.data[0]
    now = datetime.now(timezone.utc)
    duty_start = datetime.fromisoformat(tactics['duty_start_at'].replace('Z', '+00:00'))
    rotation_limit = duty_start + timedelta(hours=tactics['rotation_hours'])

    # 🎯 邏輯 A：判定是否該交棒回 GitHub
    if tactics['active_worker'] == 'RENDER' and now > rotation_limit:
        print("⏰ [交接] Render 執勤期滿，指揮權移交 GitHub...")
        sb.table("pod_scra_tactics").update({
            "active_worker": "GITHUB",
            "duty_start_at": now.isoformat(),
            "last_error_type": "NORMAL_ROTATION"
        }).eq("id", 1).execute()
        return

    # 🎯 邏輯 B：執行執勤任務
    if tactics['active_worker'] == 'RENDER':
        print("📡 [執行] Render 正在崗位，發動背景運輸任務...")
        base_dir = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.join(base_dir, "src", "pod_scra_fallback.py")
        subprocess.Popen(["python3", script_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    else:
        print(f"💤 [靜默] 當前由 {tactics['active_worker']} 執勤，Render 轉為熱機備援。")

# --- 🚀 啟動自主排程引擎 (每 20 分鐘巡邏一次) ---
scheduler = BackgroundScheduler()
scheduler.add_job(func=run_base_patrol, trigger="interval", minutes=20)
scheduler.start()

@app.route('/ping', methods=['GET'])
def health_check():
    return "Base Fully Operational & Autonomous", 200

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)