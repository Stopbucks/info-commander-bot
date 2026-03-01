
# ---------------------------------------------------------
# 本程式碼：src/pod_scra_hq.py v2.3 (多軌決策版)
# 任務：1. 心跳蓋章 2. 下載頻率控制 3. AI翻譯頻率控制 4. 倉庫壓縮許可
# ---------------------------------------------------------
import os
from supabase import create_client
from datetime import datetime, timezone

# =========================================================
# 🛠️ 戰區控制面板 (Commander Control Panel)
# =========================================================
SCOUT_TO_DOWNLOAD_RATIO = 2  
SCOUT_TO_TRANSPORT_RATIO = 1 
# =========================================================

def run_hq_decision():
    sb = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))
    t_res = sb.table("pod_scra_tactics").select("*").eq("id", 1).single().execute()
    t_data = t_res.data
    now_iso = datetime.now(timezone.utc).isoformat()

    print("=========================================")
    print(f"🛰️ [GITHUB HQ] 戰區報到 | 時間: {now_iso}")
    
    health_map = t_data.get('workers_health', {}) or {}
    health_map['GITHUB'] = now_iso
    update_payload = {"last_heartbeat_at": now_iso, "workers_health": health_map}

    active_worker = t_data.get('active_worker', "UNKNOWN")
    gha_log_count = t_data.get('gha_logistics_counter') or 0
    gha_trans_count = t_data.get('gha_transport_counter') or 0
    
    should_download = "false"
    should_transport = "false"
    # 🚀 倉庫補救壓縮：GHA 每次醒來都允許執行 (處理 2 筆舊檔)
    should_compress = "true" 

    # 任務二：判定是否執行【新下載】
    if active_worker == "GITHUB":
        if gha_log_count >= SCOUT_TO_DOWNLOAD_RATIO:
            update_payload["gha_logistics_counter"] = 0
            should_download = "true"
            print(f"🎯 [新下載核准] 計數達標，將執行 2新+1舊 任務。")
        else:
            update_payload["gha_logistics_counter"] = gha_log_count + 1
            print(f"☕ [新下載待命] 能量累積中: {gha_log_count + 1}/{SCOUT_TO_DOWNLOAD_RATIO}")
    else:
        print(f"🛡️ [巡邏模式] 目前主將為 {active_worker}。")

    # 任務三：判定是否執行【AI 翻譯】
    if gha_trans_count >= SCOUT_TO_TRANSPORT_RATIO:
        update_payload["gha_transport_counter"] = 0
        should_transport = "true"
        print(f"🧠 [情報核准] 計數達標，核准呼叫 Gemini。")
    else:
        update_payload["gha_transport_counter"] = gha_trans_count + 1
        print(f"☕ [情報待命] 能量累積中: {gha_trans_count + 1}/{SCOUT_TO_TRANSPORT_RATIO}")

    sb.table("pod_scra_tactics").update(update_payload).eq("id", 1).execute()
    
    # 🚀 將所有決策傳遞給 YML
    env_file = os.environ.get('GITHUB_ENV')
    if env_file:
        with open(env_file, 'a') as f:
            f.write(f"SHOULD_DOWNLOAD={should_download}\n")
            f.write(f"SHOULD_TRANSPORT={should_transport}\n")
            f.write(f"SHOULD_COMPRESS={should_compress}\n")
    print("✅ [決策發布] 戰略信號已寫入環境變數。")
    print("=========================================")

if __name__ == "__main__":
    run_hq_decision()