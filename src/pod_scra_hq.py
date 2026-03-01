# ---------------------------------------------------------
# 本程式碼：src/pod_scra_hq.py v2.1 (GHA 專屬記帳版)
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
    t_data = t_res.data
    now_iso = datetime.now(timezone.utc).isoformat()

    print("=========================================")
    print(f"🛰️ [GITHUB HQ] 戰區報到 | 時間: {now_iso}")
    
    # 🚀 任務一：心跳報到
    health_map = t_data.get('workers_health', {}) or {}
    health_map['GITHUB'] = now_iso
    
    update_payload = {
        "last_heartbeat_at": now_iso, 
        "workers_health": health_map
    }

    # 讀取 GHA 專屬欄位 (對標截圖欄位名)
    active_worker = tactic.get('active_worker', "UNKNOWN")
    # 💡 這裡加上預設值判定，若為空則視為 0
    gha_log_count = t_data.get('gha_logistics_counter') or 0
    gha_trans_count = t_data.get('gha_transport_counter') or 0
    
    should_download = "false"
    should_transport = "false"

    # 🚀 任務二：下載決策 (Logistics) - 僅在執勤時生效
    if active_worker == "GITHUB":
        if gha_log_count >= SCOUT_TO_DOWNLOAD_RATIO:
            update_payload["gha_logistics_counter"] = 0 # 達標歸零
            should_download = "true"
            print(f"🎯 [物流核准] 計數達標 ({gha_log_count}/{SCOUT_TO_DOWNLOAD_RATIO})，執行下載。")
        else:
            update_payload["gha_logistics_counter"] = gha_log_count + 1
            print(f"☕ [物流待命] 累積能量 (目前: {gha_log_count + 1}/{SCOUT_TO_DOWNLOAD_RATIO})。")
    else:
        print(f"🛡️ [巡邏模式] 目前主將為 {active_worker}，GHA 僅執行純偵察。")

    # 🚀 任務三：情報精煉決策 (Transport) - 全天候生效
    if gha_trans_count >= SCOUT_TO_TRANSPORT_RATIO:
        update_payload["gha_transport_counter"] = 0 # 達標歸零
        should_transport = "true"
        print(f"🧠 [情報核准] 計數達標 ({gha_trans_count}/{SCOUT_TO_TRANSPORT_RATIO})，執行精煉摘要。")
    else:
        update_payload["gha_transport_counter"] = gha_trans_count + 1
        print(f"☕ [情報待命] 累積物資 (目前: {gha_trans_count + 1}/{SCOUT_TO_TRANSPORT_RATIO})。")

    # 一次性更新所有黑板紀錄
    sb.table("pod_scra_tactics").update(update_payload).eq("id", 1).execute()
    
    # 🚀 任務四：將決策寫入環境變數
    env_file = os.environ.get('GITHUB_ENV')
    if env_file:
        with open(env_file, 'a') as f:
            f.write(f"SHOULD_DOWNLOAD={should_download}\n")
            f.write(f"SHOULD_TRANSPORT={should_transport}\n")
    print("=========================================")

if __name__ == "__main__":
    run_hq_decision()