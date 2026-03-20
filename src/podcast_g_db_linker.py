# ---------------------------------------------------------
# 程式碼：src/podcast_g_db_linker.py (G-Squad 雲端聯絡官 v1.0)
# 任務：1. 執行 T1 獨立欄位蓋章 2. 領取溫養/實戰任務 3. 寫入全軍日誌
# 特色：高度可觀測性，讓指揮官直接在 Supabase 掌握 G-Squad 動向
# ---------------------------------------------------------

import os
from datetime import datetime, timezone, timedelta
from supabase import create_client, Client

class Troop1DBLinker:
    """
    🛰️ [T1 聯絡官] 專門處理 G-Squad 與 Supabase 的情報交換
    """
    def __init__(self):
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        if not url or not key:
            print("⚠️ [警告] 缺少 Supabase 金鑰，T1 聯絡官進入離線模式。")
            self.supabase = None
        else:
            self.supabase: Client = create_client(url, key)

    def s_log(self, worker_id: str, task_type: str, status: str, message: str, traceback: str = None):
        """
        📝 [戰情寫入] 將行動日誌打入全軍共用的 mission_logs 表格
        """
        if not self.supabase: return
        try:
            print(f"[{task_type}][{status}] {message}")
            self.supabase.table("mission_logs").insert({
                "worker_id": worker_id, 
                "task_type": task_type,
                "status": status, 
                "message": message, 
                "traceback": traceback
            }).execute()
        except Exception as e:
            print(f"⚠️ [日誌寫入失敗] {e}")

    def stamp_t1_heartbeat(self, worker_id: str):
        """
        💓 [T1 獨立蓋章] 將心跳寫入 pod_scra_tactics 的 _troop1 專屬欄位
        """
        if not self.supabase: return False
        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            res = self.supabase.table("pod_scra_tactics").select("workers_health_troop1").eq("id", 1).single().execute()
            if not res.data: return False

            health_t1 = res.data.get("workers_health_troop1") or {}
            health_t1[worker_id] = now_iso

            # 更新 T1 專屬欄位 (絕不干涉 T2)
            self.supabase.table("pod_scra_tactics").update({
                "active_worker_troop1": worker_id,
                "workers_health_troop1": health_t1,
                "last_heartbeat_at_troop1": now_iso
            }).eq("id", 1).execute()
            
            self.s_log(worker_id, "HEARTBEAT", "SUCCESS", f"T1 單位 {worker_id} 上線報到")
            return True
        except Exception as e:
            print(f"⚠️ [T1 報到異常]: {e}")
            return False

    # 🚀 修正：正確縮排 4 格，讓它歸屬於 Troop1DBLinker 類別
    def fetch_t1_mission(self, worker_id: str, mode: str = "combat"):
        """
        🎯 [任務分發 (雙軌升級版)] 
        實戰模式：軌道 A 優先接管 T1_RESCUE 救援任務；軌道 B 處理時間已達標的常規 T1 任務。
        溫養模式：僅處理 3 天後才開火的 T1 遠期目標。
        並在 mission_queue 留下明確的狀態標記供指揮官查閱。
        """
        if not self.supabase: return None
        now_iso = datetime.now(timezone.utc).isoformat()
        
        # 💡 [戰略參數]：距離交接給 T2 的時間底線。大於此線的才值得溫養。
        warmup_threshold = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat() 

        try:
            if mode == "warmup":
                # 💤 溫養模式：挑選還有 3 天以上才輪到 T2 的遠期目標
                res = self.supabase.table("mission_queue").select("*") \
                        .eq("scrape_status", "pending") \
                        .eq("assigned_troop", "T1") \
                        .gte("troop2_start_at", warmup_threshold) \
                        .order("troop2_start_at", desc=False).limit(1).execute()
                
                if not res.data: return None
                mission = res.data[0]
                
                persona_mark = f"[{worker_id}] 溫養偵察中"
                status_mark = "pending" # 保持 pending，因為今天只看不抓
                log_msg = "鎖定長線目標進行溫養"

            else:
                # ⚔️ 實戰模式 (雙軌接管)
                mission = None
                
                # 軌道 A：優先搜索 T1_RESCUE 救援任務 (無視時間，強制破門)
                rescue_res = self.supabase.table("mission_queue").select("*") \
                            .eq("scrape_status", "pending") \
                            .eq("assigned_troop", "T1_RESCUE") \
                            .order("created_at", desc=False).limit(1).execute()
                
                if rescue_res.data:
                    mission = rescue_res.data[0]
                    log_msg = "🚨 發起 T1_RESCUE 403 破門救援"
                
                # 軌道 B：若無救援，則搜索常規 T1 任務 (必須時間已達標)
                if not mission:
                    reg_res = self.supabase.table("mission_queue").select("*") \
                            .eq("scrape_status", "pending") \
                            .eq("assigned_troop", "T1") \
                            .lte("troop2_start_at", now_iso) \
                            .order("created_at", desc=False).limit(1).execute()
                    
                    if reg_res.data:
                        mission = reg_res.data[0]
                        log_msg = "發起常規 T1 實戰突擊"

                if not mission: return None
                
                persona_mark = f"[{worker_id}] 實戰突擊中"
                status_mark = "processing" # 鎖定為處理中，防止重複抓取

            # 🚀 在 Supabase 留下明確的「準備動作」標記
            self.supabase.table("mission_queue").update({
                "scrape_status": status_mark,
                "recon_persona": persona_mark
            }).eq("id", mission["id"]).execute()
            
            self.s_log(worker_id, "MISSION_CLAIM", "INFO", f"{log_msg}: {mission['source_name']}")
            return mission
            
        except Exception as e:
            self.s_log(worker_id, "MISSION_CLAIM", "ERROR", f"T1 索取任務失敗: {e}")
            return None