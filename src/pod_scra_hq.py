# ---------------------------------------------------------
# 本程式碼：src/pod_scra_hq.py v1.0 (戰區報到與決策中樞)
# 任務：1. GITHUB 心跳蓋章 2. 檢查 active_worker 3. 執行 2:1 比例調度
# ---------------------------------------------------------
import os
from supabase import create_client
from datetime import datetime, timezone

# =========================================================
# 🛠️ 戰區控制面板 (Commander Control Panel)
# =========================================================
# 💡 戰術指南：設定「需要累積幾次純偵察後，才准許執行 1 次下載任務」。
# 
# - 設為 2 (代表累積 2 次純偵查後，第 3 次執行下載)
# - 設為 5 (代表累積 5 次純偵查後，第 6 次執行下載)
# - ⚠️ 測試模式：設為 0 (代表只要是值勤日，每次醒來必定立刻下載)

SCOUT_TO_DOWNLOAD_RATIO = 2  # 🚀 目前設定 2！


def run_hq_decision():
    sb = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))
    t_res = sb.table("pod_scra_tactics").select("*").eq("id", 1).single().execute()
    t_data = t_res.data
    now_iso = datetime.now(timezone.utc).isoformat()

    print("=========================================")
    print(f"🛰️ [GITHUB HQ] 戰區報到 | 時間: {now_iso}")
    
    # 🚀 任務一：心跳蓋章 (向 Vercel 哨站證明存活)
    health_map = t_data.get('workers_health', {}) or {}
    health_map['GITHUB'] = now_iso
    sb.table("pod_scra_tactics").update({
        "last_heartbeat_at": now_iso, 
        "workers_health": health_map
    }).eq("id", 1).execute()
    print("✅ [心跳印章] 已成功更新 GITHUB 生命跡象。")

    # 🚀 任務二：身分判定與動態比例調度
    active_worker = t_data.get('active_worker')
    current_count = t_data.get('logistics_counter', 0)
    should_download = "false"

    if active_worker == "GITHUB":
        print(f"🎖️ [身分判定] GITHUB 目前為輪值主將！")
        
        if current_count >= SCOUT_TO_DOWNLOAD_RATIO:
            # 達標：歸零計數器，發送下載指令
            sb.table("pod_scra_tactics").update({"logistics_counter": 0}).eq("id", 1).execute()
            should_download = "true"
            print(f"🎯 [物流核准] 計數器達標 ({current_count}/{SCOUT_TO_DOWNLOAD_RATIO})，准許執行【重裝物流】任務。")
        else:
            # 未達標：計數器 +1，跳過下載
            sb.table("pod_scra_tactics").update({"logistics_counter": current_count + 1}).eq("id", 1).execute()
            print(f"☕ [物流待命] 累積偵察能量 (目前: {current_count + 1}/{SCOUT_TO_DOWNLOAD_RATIO})，跳過物流。")
    else:
        print(f"🛡️ [身分判定] 平時巡邏模式 (當前主將: {active_worker})。專注偵察與提煉。")

    print("=========================================")

    # 🚀 任務三：將決策寫入 GitHub 環境變數 (供後續 YML 步驟讀取)
    env_file = os.environ.get('GITHUB_ENV')
    if env_file:
        with open(env_file, 'a') as f:
            f.write(f"SHOULD_DOWNLOAD={should_download}\n")

if __name__ == "__main__":
    run_hq_decision()