
# ---------------------------------------------------------
# src/pod_scra_intel_control.py (V5.5 全軍戰術控制指揮所)
# [雷達] techcore.fetch_stt_tasks: 於techcore檔案過濾任務，重裝挑大檔，輕裝僅撿壓縮(opt_)小檔。
# [核心] core.py: 戰鬥中心，執行 FFmpeg 壓縮，並呼叫 AI (Gemini/Groq) 進行轉譯與摘要產線。
# [面板] control.py: 統御機甲權限。CAN_COMPRESS=True 才能壓縮；STT_LIMIT 決定單輪轉譯總數。
# [節拍] MAX_TICKS: 控制狀態機(trans.py)循環長度。FLY預設12步(低頻打擊)，主力預設2步(雙產線交替)。

# [輕裝範例] FLY: STT_LIMIT=1, CAN_COMPRESS=False。雷達僅給已壓縮檔，拿 1 筆直接送 AI 轉譯。
# [中型範例] RENDER: STT_LIMIT=2, CAN_COMPRESS=True。搭fetch_stt_tasks「軟失敗升冪」，選 2 筆
#            健康(失敗=0)的未壓縮檔，執行 FFmpeg 壓縮後轉譯；若遇軟失敗+1並優雅繞道。

# [重裝範例] HF: STT_LIMIT=5, CAN_COMPRESS=True。搭fetch_stt_tasks「軟失敗降冪與 null 優先」，
#             專撿取失敗任務或未知大檔，強勢輾壓 5 筆疑難雜症；達 6 次失敗則全軍隔離。
# ---------------------------------------------------------
import os
from supabase import create_client

# =========================================================
# ⚙️ 全軍戰術控制面板 (Dynamic Control Panel)
# =========================================================
def get_tactical_panel(worker_id):
    """依據機甲代號 (WORKER_ID)，動態發放戰鬥裝備與產能配額"""
    
    # 🛡️ 1. 預設防線：最低規格 (等同 FLY.io 輕裝模式)
    default_panel = {
        "MEM_TIER": 256,
        "RADAR_FETCH_LIMIT": 50,
        "STT_LIMIT": 1,
        "SUMMARY_LIMIT": 1,
        "SAFE_DURATION_SECONDS": 600,
        "CAN_COMPRESS": False,
        "SCOUT_MODE": False,
        "MAX_TICKS": 24               # ⏱️ 游擊隊專屬：24個檔次FLY30分鐘起床一次，低頻巡邏節拍 
    }

    # 🛡️ 2. 中型主力模板 (適用於 512MB 一般雲端節點)
    medium_panel = {
        "MEM_TIER": 512,
        "RADAR_FETCH_LIMIT": 100,
        "STT_LIMIT": 3,
        "SUMMARY_LIMIT": 2,
        "SAFE_DURATION_SECONDS": 1500,
        "CAN_COMPRESS": True,
        "SCOUT_MODE": False,
        "MAX_TICKS": 8                # ⏱️ 主力：8 個檔次 (1 小時起床 1 次進貨與轉譯/摘要輪替)
    }

    # 🚜 3. 重裝巨獸模板 (適用於高效能節點，專解疑難雜症)
    heavy_panel = {
        "MEM_TIER": 512,
        "RADAR_FETCH_LIMIT": 100,
        "STT_LIMIT": 5,
        "SUMMARY_LIMIT": 3,
        "SAFE_DURATION_SECONDS": 1500,
        "CAN_COMPRESS": True,
        "SCOUT_MODE": False,
        "MAX_TICKS": 8                # ⏱️ 重裝：8 個檔次 (1 小時起床 1 次)
    }

    # ⚔️ 4. 裝備配發：將名牌 (WORKER_ID) 綁定至對應的戰術模板
    panels = {
        "FLY_LAX": default_panel,
        
        "RENDER": medium_panel,
        "KOYEB": medium_panel,
        "ZEABUR": medium_panel,
        
        "DBOS": heavy_panel,
        "HUGGINGFACE": heavy_panel
    }
    
    return panels.get(worker_id, default_panel)

# =========================================================
# 🔑 機密與連線中樞 (Secrets & Connections)
# =========================================================
def get_secrets():
    return {
        "SB_URL": os.environ.get("SUPABASE_URL"), 
        "SB_KEY": os.environ.get("SUPABASE_KEY"),
        "GROQ_KEY": os.environ.get("GROQ_API_KEY"), 
        "GEMINI_KEY": os.environ.get("GEMINI_API_KEY"),
        "TG_TOKEN": os.environ.get("TELEGRAM_BOT_TOKEN"), 
        "TG_CHAT": os.environ.get("TELEGRAM_CHAT_ID"),
        "R2_URL": os.environ.get("R2_PUBLIC_URL")
    }

def get_sb():
    s = get_secrets()
    return create_client(s["SB_URL"], s["SB_KEY"])