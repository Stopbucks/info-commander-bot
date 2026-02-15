# ---------------------------------------------------------
# Podcast_rescuer ： 03:00 救援兵 v1.6.2 (混合雲補檔核心)
# 週一、五、六：由 ScraperAPI 擔任破甲兵
# 職責：處理失敗任務與次新集補檔，具備 GitHub 2+3+4 配額管控
# ---------------------------------------------------------
import os
import time
from datetime import datetime, timezone, timedelta
from podcast_processor import PodcastProcessor
from podcast_navigator import NetworkNavigator

class PodcastRescuer(PodcastProcessor):
    """
    🏹 [救援部隊] - 根據日期自動切換武裝，執行非對稱補檔任務
    """

    def _check_github_quota(self):
        """
        🛡️ [配額盾牌] 執行 GitHub 專屬救援限額檢查
        規則：當日 <= 2, 72小時內 <= 4
        """
        history = self.monitor.data.get("github_rescue_log", [])
        now_ts = time.time()
        
        # 1. 清理超過 72 小時的舊紀錄
        history = [ts for ts in history if now_ts - ts < (72 * 3600)]
        self.monitor.data["github_rescue_log"] = history
        
        # 2. 計算配額
        count_24h = sum(1 for ts in history if now_ts - ts < (24 * 3600))
        count_72h = len(history)
        
        print(f"📊 [配額檢查] GitHub 救援紀錄：24h內 {count_24h}/2, 72h內 {count_72h}/4")
        
        # 3. 判定 (當日不超過 2 且 3 天內不超過 4)
        if count_24h >= 2 or count_72h >= 4:
            return False
        return True

    def run_rescue_mission(self): 
        """🏹 03:00 救援行動核心調度邏輯"""
        print("\n🚀 [啟動] 03:00 混合救援行動正式開始...")
        self._sync_cloud_to_local()
        
        # 0. 篩選待辦任務
        pending_list = [m for m in self.monitor.data.get("pending_missions", []) if m["status"] == "pending"]
        if not pending_list:
            print("✅ [報告] 派工單已清空，無須救援。")
            return

        # 1. 領取基礎結構裝備
        rescue_config = self.outfitter.get_squad_config(time.time(), force_rescue=True)

        # 2. 環境判定 (台北時間對齊)
        now_tpe = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
        weekday = now_tpe.weekday() # 0=Mon, 6=Sun
        
        should_execute_now = False

        # --- 3. 戰術分流判斷 ---
        if weekday in [1, 2, 3, 6]: # 週二、三、四、日：由 GitHub 擔任清道夫
            if self._check_github_quota():
                print(f"📅 [GitHub 救援] 配額許可，準備穿戴 Edge 裝備直連下載。")
                rescue_config["transport_proxy"] = "GitHub_Runner_Direct"
                rescue_config["path_id"] = "GIT-RE"
                should_execute_now = True
            else:
                print("⏳ [配額滿載] GitHub 救援額度已滿，進入堆積模式。")

        elif weekday in [0, 4, 5]: # 週一、五、六：由 ScraperAPI 擔任破甲兵
            current_balance = self.monitor.data.get("scrap_api_vault", {}).get("current_balance", 0)
            if current_balance >= 25.0:
                print(f"💎 [ScraperAPI 救援] 餘額 {current_balance} 充足，啟動穿透任務。")
                should_execute_now = True
            else:
                print(f"🚨 [餘額不足] ScraperAPI 點數耗盡 ({current_balance})。")

        # --- 4. 執行循環 ---
        if should_execute_now:
            with NetworkNavigator(rescue_config) as nav:
                self._process_rescue_loop(nav, pending_list, rescue_config)
        else:
            print("🏁 [戰情報告] 未符合出勤條件，維持後勤堆積。")

        # 5. 後勤同步
        self._sync_local_to_cloud()
        print("🔚 [結束] 03:00 救援行動狀態同步完畢。")

    def _process_rescue_loop(self, nav, pending_list, rescue_config):
        """🚀 [實戰循環] 下載、配額更新與 AI 分析"""
        check = nav.run_pre_flight_check()
        if not check["status"]:
            print("🛑 [告警] 救援出口無法建立連線，撤退。")
            return

        is_git = (rescue_config.get("path_id") == "GIT-RE")

        for i, task in enumerate(pending_list):
            try:
                # 判定本趟循環配額
                if is_git:
                    can_run = (i < 2) # GitHub 每次啟動最多救 2 個
                else:
                    is_safe, c24, c48 = self.monitor.check_scrapi_heavy_limit()
                    can_run = (i < 2 and is_safe)

                if can_run:
                    target_url = task['audio_url']
                    #if not is_git: # 非 GitHub 模式需進行 ScraperAPI 編碼
                    #    import urllib.parse
                    #    target_url = urllib.parse.quote(target_url, safe='')
                    
                    raw_mp3 = f"rescue_raw_{i}.mp3"

                    # 🎬 發起實戰下載
                    if nav.download_podcast(target_url, raw_mp3): 
                        # --- 下載成功後的結算 ---
                        task["status"] = "completed"
                        task["completed_at"] = time.time()
                        
                        # 🚀 [紀錄點] 根據小隊類型寫入對應記憶卡
                        if is_git:
                            self.monitor.log_github_rescue_success()
                            print("📊 [軍需官] 紀錄成功：GitHub 救援額度 -1。")
                        else:
                            self.monitor.log_scrapi_success()
                            self.monitor.data["scrap_api_vault"]["current_balance"] -= 25.0
                            print(f"💎 [軍需官] 紀錄成功：ScraperAPI 扣除 25 點。")

                        # --- AI 分析戰報 ---
                        print(f"🧠 [AI 任務] 正在產出救援分析報告...")
                        analysis, q_score, duration = self.ai_agent.generate_gold_analysis(raw_mp3)
                        msg = self.ai_agent.format_mission_report(
                            "Rescue", f"補檔: {task['source_name']}", task['audio_url'], 
                            analysis, "Success", duration, task["source_name"]
                        )
                        self.send_webhook(nav, {"tier": "Gold", "title": "救援補檔成功", "content": msg})
                    
                    # 清理臨時音檔
                    if os.path.exists(raw_mp3): os.remove(raw_mp3)
                else:
                    reason = "單次限額(2)" if i >= 2 else "週期頻率限制"
                    print(f"📡 [暫緩] 任務「{task['source_name']}」因 {reason} 進入堆積。")
                    break 

            except Exception as err:
                print(f"❌ [任務異常] {err}")

if __name__ == "__main__":
    rescuer = PodcastRescuer()
    rescuer.run_rescue_mission()