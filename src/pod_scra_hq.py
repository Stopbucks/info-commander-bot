# ---------------------------------------------------------
# 本程式碼：src/pod_scra_hq.py v2.2 (GHA 專屬記帳版)
# 任務：1. 心跳蓋章 2. GHA 專屬下載計數 3. GHA 專屬翻譯計數
# ---------------------------------------------------------
import os
from supabase import create_client
from datetime import datetime, timezone

# =========================================================
# 🛠️ 戰區控制面板 (Commander Control Panel)
# =========================================================
SCOUT_TO_DOWNLOAD_RATIO = 2  # 每 2 次純偵察後，執行 1 次下載 (第 3 次執行)
SCOUT_TO_TRANSPORT_RATIO = 1 # 每 1 次純偵察後，執行 1 次翻譯 (第 2 次執行)
# =========================================================


def run_hq_decision():
    sb = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))
    t_res = sb.table("pod_scra_tactics").select("*").eq("id", 1).single().execute()
    t_data = t_res.data # 這裡是 t_data
    now_iso = datetime.now(timezone.utc).isoformat()

    print("=========================================")
    print(f"🛰️ [GITHUB HQ] 戰區報到 | 時間: {now_iso}")
    
    health_map = t_data.get('workers_health', {}) or {}
    health_map['GITHUB'] = now_iso
    
    update_payload = {
        "last_heartbeat_at": now_iso, 
        "workers_health": health_map
    }

    # 🚀 修正：使用 t_data 讀取欄位
    active_worker = t_data.get('active_worker', "UNKNOWN")
    gha_log_count = t_data.get('gha_logistics_counter') or 0
    gha_trans_count = t_data.get('gha_transport_counter') or 0
    
    should_download = "false"
    should_transport = "false"

    if active_worker == "GITHUB":
        if gha_log_count >= SCOUT_TO_DOWNLOAD_RATIO:
            update_payload["gha_logistics_counter"] = 0
            should_download = "true"
            print(f"🎯 [物流核准] 計數達標 ({gha_log_count}/{SCOUT_TO_DOWNLOAD_RATIO})。")
        else:
            update_payload["gha_logistics_counter"] = gha_log_count + 1
            print(f"☕ [物流待命] 能量累積: {gha_log_count + 1}/{SCOUT_TO_DOWNLOAD_RATIO}")
    else:
        print(f"🛡️ [巡邏模式] 目前主將為 {active_worker}。")

    if gha_trans_count >= SCOUT_TO_TRANSPORT_RATIO:
        update_payload["gha_transport_counter"] = 0
        should_transport = "true"
        print(f"🧠 [情報核准] 計數達標 ({gha_trans_count}/{SCOUT_TO_TRANSPORT_RATIO})。")
    else:
        update_payload["gha_transport_counter"] = gha_trans_count + 1
        print(f"☕ [情報待命] 能量累積: {gha_trans_count + 1}/{SCOUT_TO_TRANSPORT_RATIO}")

    sb.table("pod_scra_tactics").update(update_payload).eq("id", 1).execute()
    
    env_file = os.environ.get('GITHUB_ENV')
    if env_file:
        with open(env_file, 'a') as f:
            f.write(f"SHOULD_DOWNLOAD={should_download}\n")
            f.write(f"SHOULD_TRANSPORT={should_transport}\n")
    print("=========================================")

if __name__ == "__main__":
    run_hq_decision()