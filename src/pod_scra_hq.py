# ---------------------------------------------------------
# 本程式碼：src/pod_scra_hq.py v2.0 (雙計數器閉合版)
# 任務：1. 心跳蓋章 2. 下載頻率控制 3. AI翻譯頻率控制
# ---------------------------------------------------------
import os
from supabase import create_client
from datetime import datetime, timezone

# =========================================================
# 🛠️ 戰區控制面板 (Commander Control Panel)
# =========================================================
# 💡 戰術指南：設定「累積幾次純偵察後，才執行重裝任務」

# 1. MP3 下載頻率 (僅限 GITHUB 是主將時才生效)
SCOUT_TO_DOWNLOAD_RATIO = 2  

# 2. AI 翻譯頻率 (無條件生效，例如數值：2，代表每 3 次啟動，翻譯 1 次)
SCOUT_TO_TRANSPORT_RATIO = 1 
# =========================================================

def run_hq_decision():
    sb = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))
    t_res = sb.table("pod_scra_tactics").select("*").eq("id", 1).single().execute()
    t_data = t_res.data
    now_iso = datetime.now(timezone.utc).isoformat()

    print("=========================================")
    print(f"🛰️ [GITHUB HQ] 戰區報到 | 時間: {now_iso}")
    
    # 🚀 任務一：心跳蓋章
    health_map = t_data.get('workers_health', {}) or {}
    health_map['GITHUB'] = now_iso
    
    # 準備一次性更新的資料包
    update_payload = {
        "last_heartbeat_at": now_iso, 
        "workers_health": health_map
    }
    print("✅ [心跳印章] 已成功更新 GITHUB 生命跡象。")

    # 讀取雙計數器
    active_worker = t_data.get('active_worker')
    gha_log_count = t_data.get('gha_logistics_counter', 0)
    gha_trans_count = t_data.get('gha_transport_counter', 0)
    
    should_download = "false"
    should_transport = "false"

    # 🚀 任務二：判定 MP3 下載 (Logistics)
    if active_worker == "GITHUB":
        if gha_log_count >= SCOUT_TO_DOWNLOAD_RATIO:
            update_payload["gha_logistics_counter"] = 0
            should_download = "true"
            print(f"🎯 [MP3下載核准] 計數達標 ({gha_log_count}/{SCOUT_TO_DOWNLOAD_RATIO})，核准執行。")
        else:
            update_payload["gha_logistics_counter"] = gha_log_count + 1
            print(f"☕ [MP3下載待命] 累積能量中 (目前: {gha_log_count + 1}/{SCOUT_TO_DOWNLOAD_RATIO})。")
    else:
        print(f"🛡️ [身分判定] 平時巡邏模式 (當前主將: {active_worker})。跳過 MP3 下載。")

    # 🚀 任務三：判定 AI 翻譯 (Transport)
    if gha_trans_count >= SCOUT_TO_TRANSPORT_RATIO:
        update_payload["gha_transport_counter"] = 0
        should_transport = "true"
        print(f"🧠 [AI翻譯核准] 計數達標 ({gha_trans_count}/{SCOUT_TO_TRANSPORT_RATIO})，核准交接給 Gemini。")
    else:
        update_payload["gha_transport_counter"] = gha_trans_count + 1
        print(f"☕ [AI翻譯待命] 累積情報中 (目前: {gha_trans_count + 1}/{SCOUT_TO_TRANSPORT_RATIO})。")

    # 執行資料庫更新
    sb.table("pod_scra_tactics").update(update_payload).eq("id", 1).execute()
    print("=========================================")

    # 🚀 任務四：將決策寫入 GitHub 環境變數
    env_file = os.environ.get('GITHUB_ENV')
    if env_file:
        with open(env_file, 'a') as f:
            f.write(f"SHOULD_DOWNLOAD={should_download}\n")
            f.write(f"SHOULD_TRANSPORT={should_transport}\n")

if __name__ == "__main__":
    run_hq_decision()