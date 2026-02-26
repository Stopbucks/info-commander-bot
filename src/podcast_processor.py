# ---------------------------------------------------------
# Podcast_processor ： 第一管道主邏輯判斷，管理任務生命週期與雙軌調度
# ---------------------------------------------------------
import os
import sys   
import time
import random
import json
import subprocess # 🚀 引入子進程模組，修復音訊壓縮崩潰問題 [cite: 2026-02-15]
from supabase import create_client, Client  # 🚀 引入雲端指揮官
from datetime import datetime, timezone, timedelta
from podcast_monitor import MemoryManager
from podcast_outfitter import TacticalOutfitter
from podcast_navigator import NetworkNavigator
from podcast_ai_agent import AIAgent
from podcast_proxy_medic import ProxyMedic  # 🚀 引入軍需官系統 
from email.utils import parsedate_to_datetime       # 🚀 置頂部解析UTC時間
from podcast_gcp_storager import GCPStorageManager  # 🚀 讀取GCP決策動態路徑


class PodcastProcessor:
    def __init__(self, monitor_file="podcast_monitor.json"): # 🚀 參數化
        # 🚀 修正 1：將傳入的檔名存入實例變數，供後續 sync_to_cloud 使用
        self.monitor_file = monitor_file 
        
        # 🚀 修正 2：使用 self.monitor_file 變數而不是寫死的字串
        from podcast_monitor import MemoryManager
        self.monitor = MemoryManager(self.monitor_file) 
        
        print(f"🏛️ [中心] 已加載【{self.monitor_file}】戰略記憶庫。")
        # ==================================================
        # ================================================== 
        self.outfitter = TacticalOutfitter()
        self.ai_agent = AIAgent()
   # 🚀 [雲端對接] 初始化 Supabase 指揮系統
        self.supabase_url = os.environ.get("SUPABASE_URL")
        self.supabase_key = os.environ.get("SUPABASE_KEY")     
    # 💡 防禦性檢查：確保雲端金鑰存在
        if not self.supabase_url or not self.supabase_key:
            print("❌ [嚴重錯誤] 遺失 SUPABASE 密鑰，偵察連線無法建立。")
            raise ValueError("Missing Supabase credentials")
            
        self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
        
        # 💡 [瘦身紀錄] 已移除 self.sources，任務改由 execute_daily_mission 動態領取 [cite: 2026-01-16]

        self.gcp = GCPStorageManager()   #  GCP 管理員固定為小隊編制化
        # 🚀 修正：改由直發 TG， 
        self.tg_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        self.tg_chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    def sync_to_cloud(self):
        # 🚀 確保上傳時使用的是對應的檔案名稱
        self.gcp.upload_memory(self.monitor.file_path, self.monitor_file)


    # --- [全新通訊區塊：取代 send_webhook] ---
    def send_telegram_report(self, content):
        """🚀 [通訊官] 直接將情報推播至 Telegram 頻道，達成零中轉、高隱私目標 [cite: 2026-02-15]"""
        import requests # 內部引入確保模組獨立性
        
        if not self.tg_token or not self.tg_chat_id:
            print("⚠️ [通訊失敗] 偵測到 Telegram 金鑰缺失，請檢查 GitHub Secrets 設定。")
            return False

        url = f"https://api.telegram.org/bot{self.tg_token}/sendMessage"
        payload = {
            "chat_id": self.tg_chat_id,
            "text": content,
            "parse_mode": "Markdown" # 支援 Markdown 讓戰報呈現專業排版
        }

        # 🚀 執行：具備 3 次重試機制，對抗 GitHub Runner 偶發的網路抖動
        for i in range(3):
            try:
                resp = requests.post(url, json=payload, timeout=30)
                if resp.status_code == 200:
                    print("✅ [情報發送] Telegram 戰報已送達基地。")
                    return True # 成功發送，回傳 True
            except Exception as e:
                print(f"⚠️ [嘗試 {i+1}] 發送失敗: {str(e)[:20]}...")
                time.sleep(5) # 失敗後稍作喘息再重試
        return False # 三次嘗試皆失敗，回報通訊中斷
    # ---------------------------------------------------------
    # 新增：雲端任務領取與鎖定邏輯
    # ---------------------------------------------------------
 
#------以下更新定位線------------ 
    def fetch_cloud_mission(self):
        """
        🚀 [大一統] 部隊一專屬：領取『現在時間 < troop2_start_at』且尚未完成的任務
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        print("📡 [領命] 正在偵察部隊一緩衝區任務...")
        
        # 邏輯：pending 狀態 且 現在時間 < troop2_start_at (代表未達部隊二開火線)
        # 如果該任務沒有 troop2_start_at (例如舊任務)，則優先領取
        response = self.supabase.table("mission_queue") \
            .select("*") \
            .eq("scrape_status", "pending") \
            .or_(f"troop2_start_at.gt.{now_iso},troop2_start_at.is.null") \
            .order("created_at", desc=False) \
            .limit(1).execute()

        if not response.data:
            print("☕ [待命] 目前無部隊一可攔截之任務。")
            return None
        
        mission = response.data[0]
        # 鎖定狀態為 processing
        self.supabase.table("mission_queue").update({"scrape_status": "processing"}).eq("id", mission["id"]).execute()
        return mission
#------以上更新定位線------------ 

    def finalize_cloud_mission(self, mission_id, status="completed"):
        """
        更新任務最終執行狀態 (完成或戰損)
        """
        self.supabase.table("global_missions") \
            .update({"status": status}) \
            .eq("id", mission_id) \
            .execute()
        print(f"🏁 [結案] 任務 ID {mission_id} 狀態更新為: {status}")
        

    def _get_selected_proxy(self) -> str:
        """[軍需調度] 委託 ProxyMedic 提供今日隊員 [cite: 2026-02-02]"""
        # 💡 邏輯已移至軍需官，指揮官只需負責簽收
        return ProxyMedic.get_random_proxy()


    def execute_daily_mission(self, diagnostic_mode=False):
        """
        🚀 [核心指揮] 執行任務生命週期：調度 -> 延遲 -> 自檢 -> 戰鬥 -> 養護
        """
        
        # 🚀 1. 鎖定唯一的真理時間 (UTC) 
        now_utc = datetime.now(timezone.utc)
        now_ts = now_utc.timestamp()

        # 🚀 2. 啟動前同步記憶 (確保軍需官拿到最新的指紋分佈)
        self._sync_cloud_to_local() 
        
        # 🚀 3. 領取小隊裝備 (獲取 Outfitter v4.3 完整字典結構)
        squad_config = self.outfitter.get_squad_config(now_ts)
        if not squad_config: 
            print("❌ [錯誤] 無法領取今日裝備，行動中止。")
            return

        # 4. 戰術診斷提示
        if diagnostic_mode and squad_config.get('is_warmup'):
            print("💡 診斷模式：今日為溫養日，將驗證基礎擬態路徑。")

        # 5. ⚖️ 代理策略與導航員初始化
        proxy_url = squad_config.get('transport_proxy', "GitHub_Runner_Direct")
        
        nav = NetworkNavigator(squad_config)

        # 6. 隨機啟動延遲 (Jitter)
        if not diagnostic_mode:
            launch_delay = random.randint(0, squad_config['launch_window_max'])
            print(f"🕒 [計畫] 預計隨機延遲 {launch_delay // 60} 分鐘後發起任務...")
            time.sleep(launch_delay)

        try:
            # ==== [修改後：Step 7 優化區塊] ===========

            # 7. 🚀 [精準偵察 雙重安全性 校對漂移比對]
            # 💡 以防禦性寫法獲取數據，確保 Navigator 即使回傳空值也不會觸發 KeyError

            check_result = nav.run_pre_flight_check()
            recon_data = check_result.get("data", {})
            path_id = squad_config['path_id']
            current_org = recon_data.get("org", "Unknown")

            # (A) 💡 [雙重檢查]：若第一來源為 Unknown，啟動備援 API 驗證 (解決誤殺)
            if current_org == "Unknown":
                backup_data = self.monitor.trigger_double_check(nav)
                if backup_data:
                    print(f"📡 [校對成功] 二次檢查確認 ISP 為: {backup_data['org']}")
                    recon_data.update(backup_data)
                    current_org = backup_data['org']

            # (B) 🧠 [風險判定]：送交監視器執行 ISP 安全性與 IP 漂移分析
            # 💡 這裡會自動處理 process_recon_data 的所有存檔與統計
            report = self.monitor.process_recon_data(recon_data, path_id)

            # (C) 🛡️ [最終防線]：攔截致命洩漏 (org_drift >= 2) 或連線失敗
            if not check_result.get("status") or (report and report.get("org_drift", 0) >= 2):
                print(f"🛑 [撤退] 偵測到身分洩漏風險 ({current_org}) 或連線失敗，任務終止。")
                return 

            # (D) 🧬 [人格重塑]：根據最終 IP 載入對應的歷史 Cookies
            current_ip = recon_data.get("ip", "?.?.?.?")
            best_cookies = self.monitor.match_best_footprint(squad_config['identity_hash'], current_ip)
            if best_cookies:
                nav.session.cookies.update(best_cookies)
                print(f"🧬 [人格重塑] 成功匹配 IP {mask_ip(current_ip)}，已載入 Cookies。")

            # =========================================================
            # 🚀 [溫養/實戰動態切換]：數位人格一致性優化手術
            # =========================================================
            if diagnostic_mode:
                print(f"✅ [診斷完畢] 模式：Diagnostic")
                return 

            # =========================================================
            # ⚙️ [控制面板]：溫養日輕度支援參數
            # 💡 若溫養日想消化任務，可將 limit 設為 1~2；設為 0 則僅巡邏不下載
            # =========================================================
            warmup_support_limit = 1 
 
            if squad_config.get("is_warmup"):
                print("💤 [溫養日] 啟動數位人格全域巡邏...")
                # 1. 🚀 獲取雲端所有 pending 任務以建立瀏覽指紋
                all_pending = self.supabase.table("global_missions").select("source_name, audio_url") \
                                  .eq("status", "pending").execute().data
                
                if all_pending:
                    print(f"📡 [偵察] 正在對 {len(all_pending)} 個目標執行人格溫養...")
                    for mission in all_pending:
                        try:
                            # 🧬 對「每一個」網址留下瀏覽指紋 (stream=True 節省流量) [cite: 2026-01-16]
                            nav.session.get(mission['audio_url'], timeout=10, stream=True)
                            print(f" └─ 👁️ 已留下足跡：{mission['source_name']}")
                            time.sleep(random.randint(5, 12)) 
                        except: pass

                    # 2. ⚖️ 執行輕度支援下載 [cite: 2026-01-16]
                    if warmup_support_limit > 0:
                        self._start_combat_flow(nav, squad_config, max_limit=warmup_support_limit)
                else:
                    nav.run_rest_warmup()

            else:
                # ⚔️ [實戰模式]：正規軍領命作戰 [cite: 2026-01-16]
                print("⚔️ [實戰日] 執行正規運輸任務...")
                nav.run_pre_combat_recon() 
                self._start_combat_flow(nav, squad_config, max_limit=2) 
                nav.run_pre_combat_recon()

            # ==============================================================================
            # 🛰️ [戰術拓展]：T+N 影子養護循環 (去地圖化修正)
            # ==============================================================================
            print("\n📡 [戰略預警] 啟動未來身分養護程序 (T+1 ~ T+2)...")
            # 💡 定義通用擬態目標清單 (當 self.sources 不存在時使用)
            public_recon_targets = [
                "https://podcasts.apple.com", "https://feeds.acast.com", 
                "https://www.bbc.com", "https://www.cnn.com", 
                "https://www.theguardian.com", "https://www.bloomberg.com",
                "https://www.washingtonpost.com", "https://www.reuters.com",
                "https://www.nytimes.com"
            ]

            for offset in [1, 2]:
                switch_delay = random.randint(200, 400)
                print(f"🕒 [擬態長假] 等待 {switch_delay // 60} 分鐘後切換至 T+{offset} 裝備...")
                time.sleep(switch_delay)

                future_ts = now_ts + (offset * 24 * 3600)
                f_squad = self.outfitter.get_squad_config(future_ts)
                
                if f_squad['path_id'] == squad_config['path_id']:
                    continue

                with NetworkNavigator(f_squad) as shadow_nav:
                    # ======================== [定位：影子養護內部迴圈] ========================
                    try:
                        if shadow_nav.run_pre_flight_check()["status"]:
                            shadow_nav.run_pre_combat_recon()
                            
                            # 🚀 [修正] 徹底刪除內部冗餘清單，直接調用外部 Master List
                            # 💡 這樣影子身分會從包含 Apple 與 8 家新聞媒體的名單中隨機抽選
                            target_url = random.choice(public_recon_targets)
                            
                            print(f" └─ 🧬 [影子維護] 模擬造訪：{target_url}")
                            shadow_nav.session.get(target_url, timeout=15, stream=True)
                            
                            self.monitor.update_identity_vault(shadow_nav.save_identity_state())
                            print(f"    ✅ [養護成功] T+{offset} 身分已同步。")
                    except: pass 
 
                    #--------------定位線(以上修正)---------------------                            
 

            # --- 📅 周戰略報告判斷 (社會時間對齊) ---
            if now_utc.weekday() == 6: # 週日
                print("📋 [戰報] 偵測到周日結算點，發起戰略彙整...")
                summary_data = self.monitor.get_weekly_summary() 
                final_report = self.ai_agent.generate_weekly_strategic_report(summary_data) 
                self.send_telegram_report(final_report)
                
        except Exception as e:
            print(f"❌ [異常] 任務執行期間發生錯誤: {str(e)}")
            raise e
        
        finally:
            if not diagnostic_mode:
                self._sync_local_to_cloud()
            
            # 🚀 [保險機制]：確認 nav 變數存在且不為空才執行關閉
            if 'nav' in locals() and nav:
                nav.close()
                print("🔌 [清理] 導航員連線已安全關閉。")

 
    def _start_combat_flow(self, nav, squad_config, max_limit=2):    
        """📡 [運輸兵] 執行雲端領命派工流程"""
        now_utc = datetime.now(timezone.utc)
        date_label = now_utc.strftime("%m.%d.%y")
        processed_count = 0

        while processed_count < max_limit:
            mission = self.fetch_cloud_mission() 
            if not mission:
                print("☕ [待命] 雲端目前無 pending 任務。")
                break

            source_name = mission.get("source_name", "Unknown Source")
            audio_url = mission.get("audio_url")
            # 🧬 構造 Mock 物件以相容舊流程
            mock_entry = type('MockEntry', (), {
                'title': mission.get('title', 'Cloud Mission Task'),
                'enclosures': [type('Enc', (), {'href': audio_url, 'type': 'audio/mpeg'})],
                'itunes_duration': '未知'
            })

            try:
                # 3. 🏆 [戰鬥] 執行處理，並確認是否「真成功」
                # 💡 關鍵修正：假設 _handle_gold_mission 失敗會拋出異常，
                # 或您在此檢查其下載狀態
                success = self._handle_gold_mission(mock_entry, {"name": source_name}, nav, date_label, squad_config)
                
                # 只有在 success 為 True 或未拋出異常的情況下才結案
                # -----(定位線)確保結案狀態與實戰結果掛鉤-----
                if success:
                    self.finalize_cloud_mission(mission["id"], "completed")
                    print(f"✅ [運輸成功] {source_name} 已標記完成。")
                else:
                    self.finalize_cloud_mission(mission["id"], "failed")
                    print(f"⚠️ [運輸未達] {source_name} 下載失敗，已標記 failed 供救援。")
                # ------------------------------------------

            except Exception as e:
                # 🚑 [戰損] 發生崩潰或嚴重錯誤
                self.finalize_cloud_mission(mission["id"], "failed")
                print(f"❌ [任務潰敗] {source_name} 發生系統錯誤: {str(e)}")

            processed_count += 1

            # 🚀 [擬態喘息] 邏輯保持正確
            if processed_count < max_limit: 
                rest_time = random.randint(600, 1200) 
                print(f"🕒 [擬態喘息] 等待 {rest_time // 60} 分鐘後領取下一則任務...")
                time.sleep(rest_time)

        print(f"🏁 [撤退] 今日行動結束，共完成 {processed_count} 筆運輸。")
    
    #===========================================================================

    def _handle_gold_mission(self, entry, source, nav, date_label, squad_config):
        """🏆 黃金等級：下載 + 深度分析流程 (閉合邏輯與全註解版) """
        
        # 1. 🛡️ 身分驗證：檢查當前 identity_hash 是否安全
        if not self.monitor.is_identity_safe(squad_config['identity_hash']): return False
          
        # 2. 🚀 資源定位：從 RSS Entry 中提取音檔網址
        audio_url = next((enc.href for enc in entry.enclosures if enc.type.startswith("audio")), "")
        if not audio_url: return False

        # 3. 📡 戰前預熱：執行低頻探路
        print(f"💎 [戰術] 正在對目標發起下載前的數位人格預熱...")
        warmup_res = nav.preflight_warmup(audio_url)

        # 4. 🕵️ 異常取證：捕捉 403 情報包裹
        if isinstance(warmup_res, dict):
            self.monitor.record_incident_report(squad_config['identity_hash'], audio_url.split('/')[2], warmup_res)
            self.monitor.record_event(squad_config['identity_hash'], 403, target_url=audio_url, task_type="scout")
            return False # 偵察受阻，視為失敗

        # 5. 🛑 熔斷檢查：若連線根本無法建立
        if not warmup_res:
            print("⚠️ [偵察失敗] 無法建立連線，中止本次運輸。")
            return False

        # 6. 🕒 戰鬥計時：啟動評估
        start_mission_time = time.time()
        title = getattr(entry, "title", "Untitled")
        raw_mp3, final_mp3 = "temp_raw.mp3", "temp_final.mp3"
        
        try:     
            # 7. ⬇️ 實戰運輸：執行音檔下載
            if nav.download_podcast(audio_url, raw_mp3):
                
                # 8. 🏁 下載完成：執行餘韻停留
                linger_time = random.uniform(5.0, 15.0)
                print(f"🏁 [運輸完成] 保持連線餘韻 {linger_time:.1f} 秒...")
                time.sleep(linger_time)

                # 9. 📊 效能結算與壓縮
                latency = (time.time() - start_mission_time) * 1000
                target = final_mp3 if self._compress_audio(raw_mp3, final_mp3) else raw_mp3
                
                # 10. ⏳ AI 消化延遲
                think_delay = random.randint(45, 90)
                print(f"⏳ [擬態思維] 預計 {think_delay} 秒後產出分析報告...")
                time.sleep(think_delay)
                
                # 11. 🔄 Ring 戰術：執行下載後回訪建立閉環
                print(f"🔄 [Ring 戰術] 執行下載後回訪...")
                nav.run_pre_combat_recon()

                # 12. 🧠 情報生成：調用 AI Agent
                analysis, q_score, duration = self.ai_agent.generate_gold_analysis(target)

                if analysis:
                    # 13. 📜 戰報彙整與發送
                    msg = self.ai_agent.format_mission_report(
                        "Gold", title, audio_url, analysis, date_label, 
                        duration, source["name"], audio_duration=getattr(entry, "itunes_duration", "未知")
                    )
                    self.send_telegram_report(msg)

                    # 14. 💾 閉環紀錄
                    self.monitor.record_event(squad_config['identity_hash'], 200, target_url=audio_url, task_type="mission")
                    self.monitor.record_performance(audio_url.split('/')[2], latency, True)
                    
                    return True # 🚀 關鍵修正：任務全面成功，回傳 True 觸發 Supabase 結案 [cite: 2026-02-15]

                return False # AI 分析未產出結果，標記為失敗以供未來重試

        except Exception as e:
            # 15. 🚑 戰損處理：任務崩潰診斷
            latency = (time.time() - start_mission_time) * 1000
            print(f"❌ [任務崩潰] 啟動自動掛號程序... 原因: {e}")
            self.monitor.add_pending_mission(source["name"], audio_url, mission_type="failed_retry")
            self.monitor.record_event(squad_config['identity_hash'], 500, target_url=audio_url, task_type="mission")
            self.monitor.record_performance(audio_url.split('/')[2], latency, False)
            return False # 遭遇異常，明確回傳失敗狀態
            
        finally:
            # 16. 🧹 戰場清理
            for f in [raw_mp3, final_mp3]:
                if os.path.exists(f): os.remove(f)


    def _handle_platinum_mission(self, entry, source, nav, date_label):
        """💿 白金等級：純文字簡介流程"""
        title = getattr(entry, "title", "Untitled")
        link = getattr(entry, "link", "")
        summary = getattr(entry, "summary", "")[:300]
        content = f"📋 [節目簡介]\n{summary}...\n\n(💡 系統備註: 48h 補追次新集)"
        
        msg = self.ai_agent.format_mission_report(
            "Platinum", title, link, content, date_label, 1, source["name"]
        )
        self.send_telegram_report(msg)

    def _compress_audio(self, input_f, output_f):
        """⚡ [FFmpeg] 16k/Mono 極限壓縮"""
        try:
            cmd = ["ffmpeg", "-i", input_f, "-ac", "1", "-ar", "8000", "-b:a", "16k", "-y", output_f]
            return subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
        except: return False


    # ================= [GCP後勤封裝區塊] =================
    def _sync_cloud_to_local(self):
        """[後勤] 啟動前同步：從雲端拉取記憶"""
        if self.gcp.download_memory(self.monitor.file_path):
            self.monitor.reload()
            return True
        return False

    def _sync_local_to_cloud(self):
        """[後勤] 結束後同步：回填最新指紋"""
        print(f"🚀 [GCP] 正在上傳記憶至愛荷華基地...")
        self.monitor.save()
        return self.gcp.upload_memory(self.monitor.file_path)
    # =======================================================

if __name__ == "__main__":
    # 解析命令列參數
    commander = PodcastProcessor()
    # 💡 若指令包含 --check，則啟動診斷模式
    is_diagnostic = "--check" in sys.argv
    commander.execute_daily_mission(diagnostic_mode=is_diagnostic)