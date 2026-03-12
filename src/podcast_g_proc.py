# ---------------------------------------------------------
# podcast_g_proc.py ： 游擊 g-小隊指揮官 (進階節流與 Opus 版 V2)
# 戰術原則：1-3-5-7 出勤、8+1 IP 輪替、Opus 壓縮、Groq 深度摘要
#
# 戰略原則：單數日實戰下載、雙數日便衣溫養、看新聞積累 Cookie
# 核心戰技：專攻 T1 任務、強擬態破防、本地 Opus 壓縮、直上 R2 倉庫
# 修正說明：移除 Groq 摘要，導入 podcast_g_db_linker 雲端聯絡官
# ---------------------------------------------------------

import os
import sys
import time
import random
import subprocess
import boto3 # 🚀 新增：R2 兵工廠連線，負責將物資送回母港
from datetime import datetime, timezone
from podcast_processor import PodcastProcessor  # 繼承主力部隊核心
from podcast_navigator import NetworkNavigator
from podcast_g_db_linker import Troop1DBLinker # 🚀 新增：G-Squad 專屬雲端聯絡官

class GuerrillaProcessor(PodcastProcessor):
    def __init__(self):
        # 🚀 核心優化：直接在初始化父類別時就指定游擊專屬檔案
        # 這會一次性完成本地隔離與雲端路徑設定
        super().__init__(monitor_file="guerrilla_monitor.json")
        
        # 🚀 建立 T1 雲端聯絡官實例
        self.t1_linker = Troop1DBLinker()
        
        print("🪖 [g-小隊] 獨立人格已就緒，轉型為 T1 特戰物流官。")
        self.max_missions = 2  

    # ---------------------------------------------------------
    # 裝備部：Edge 擬態與 WBS 代理調度
    # ---------------------------------------------------------
    def _get_wbs_persona(self, index):
        """🚀 [軍事化裝備] 生成微幅差異的 Edge 擬態 Headers [cite: 2026-01-16]"""
        version = 121 + (index % 2)
        return {
            "ua": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{version}.0.0.0 Safari/537.36 Edg/{version}.0.0.0",
            "headers": {
                "Sec-Ch-Ua": f'"Not A(Brand";v="99", "Microsoft Edge";v="{version}", "Chromium";v="{version}"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
                "Accept": "application/json, text/plain, */*",
                "Sec-Fetch-Site": "same-site",
                "Sec-Fetch-Mode": "cors"
            }
        }

    def _get_guerrilla_proxies(self):
        """📡 [領取代理] 取得 Webshare 清單 (預期有 9-10 個 IP) [cite: 2026-01-16]"""
        raw_list = os.environ.get("WEBSHARE_LIST", "")
        if not raw_list: return []
        return [p.strip() for p in raw_list.split(",") if p.strip()]

    # ---------------------------------------------------------
    # 兵工廠：Opus 壓縮邏輯與 R2 倉儲
    # ---------------------------------------------------------
    def _compress_to_opus(self, input_f, output_f):
        """⚡ [FFmpeg] 將音檔轉為 16k Mono Opus (極限壓縮以利隱蔽傳輸) [cite: 2026-01-16]"""
        try:
            # 💡 30分鐘演講壓縮後僅約 3.5MB，極大節省上傳流量
            cmd = [
                "ffmpeg", "-i", input_f, 
                "-ac", "1", "-ar", "16000", 
                "-c:a", "libopus", "-b:a", "16k", "-vbr", "on", "-y", output_f
            ]
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return res.returncode == 0
        except: return False

    def upload_to_r2(self, local_path, filename):
        """📦 [後勤支援] 將壓縮好的 Opus 檔案送入 R2，交接給 T2 部隊 [新增功能]"""
        print(f"📦 [R2] 正在將戰利品 {filename} 送入雲端倉庫...")
        s3 = boto3.client('s3', 
                          endpoint_url=os.environ.get("R2_ENDPOINT_URL"),
                          aws_access_key_id=os.environ.get("R2_ACCESS_KEY_ID"),
                          aws_secret_access_key=os.environ.get("R2_SECRET_ACCESS_KEY"), 
                          region_name="auto")
        s3.upload_file(local_path, os.environ.get("R2_BUCKET_NAME"), filename)
        print(f"✅ [R2] 入庫成功。")

    # ---------------------------------------------------------
    # 偵察部：擬態閱讀新聞
    # ---------------------------------------------------------
    def _perform_news_mimicry(self, nav, stage="Combat"):
        """🎭 [數位擬態] 執行 Apple、BBC、CNN 巡航，累積正常人類 Cookie [cite: 2026-01-16]"""
        targets = ["https://podcasts.apple.com/", "https://www.bbc.com/news", "https://www.cnn.com/world"]
        random.shuffle(targets)
        print(f"🕵️ [{stage}] 執行新聞巡航建立真實人類指紋...")
        for url in targets:
            try:
                nav.session.get(url, timeout=10, stream=True)
                time.sleep(random.uniform(5, 10))
            except: pass

    # ---------------------------------------------------------
    # 指揮部：作戰流程 (分流：實戰下載 vs 便衣溫養)
    # ---------------------------------------------------------
    def execute_guerrilla_hit(self):
        """⚔️ [g-小隊行動] 依據星期決定「實戰」或「溫養」，並利用聯絡官派工"""
        now_utc = datetime.now(timezone.utc)
        weekday = now_utc.isoweekday() # 1=Mon, 3=Wed, 5=Fri, 7=Sun

        # 🚀 1. 戰略判定：1, 3, 5, 7 為實戰下載；2, 4, 6 為純擬態溫養
        if weekday in [1, 3, 5, 7]:
            combat_mode = True
            mission_type = "combat"
            print(f"⚔️ [戰略] 今日為實戰日 (UTC {weekday})，啟動 T1 破防與下載任務。")
        else:
            combat_mode = False
            mission_type = "warmup"
            print(f"💤 [戰略] 今日為溫養日 (UTC {weekday})，僅執行便衣巡航與指紋累積。")

        proxies = self._get_guerrilla_proxies()
        if len(proxies) < 9:
            print("❌ [錯誤] 代理數量不足 9 個，無法執行輪替邏輯。")
            return

        # 🚀 2. IP 輪替與備援邏輯 (8 個輪流，第 9 個為備援) [cite: 2026-01-16]
        week_num = now_utc.isocalendar()[1]
        rotation_idx = (week_num + weekday) % 8 
        backup_idx = 8 # 固定的備援索引 (第 9 個 IP)

        current_unit_idx = rotation_idx
        processed_count = 0
        
        worker_id = f"g_unit_{current_unit_idx}"
        
        # 📝 [T1 聯絡官]：執行部隊心跳打卡 (寫入 pod_scra_tactics 的 troop1 欄位)
        self.t1_linker.stamp_t1_heartbeat(worker_id)

        print(f"🕒 [隱蔽] 預計 40 分鐘內隨機發起突襲...")
        time.sleep(random.randint(0, 2400))

        while processed_count < self.max_missions:
            proxy_url = proxies[current_unit_idx]
            persona = self._get_wbs_persona(current_unit_idx)
            
            # 💡 戰術變更：徹底移除 headers 鍵值對，由 impersonate 接管指紋生成 [cite: 2026-01-16]
            g_config = {
                "squad_name": worker_id,
                "transport_proxy": proxy_url,
                "identity_hash": f"g_wbs_{current_unit_idx}",
                "path_id": "WBS_G",
                "curl_config": {
                    "headers": {}, 
                    "impersonate": "chrome110" 
                }
            }

            with NetworkNavigator(g_config) as nav:
                # 3. 戰前哨戒
                print(f"🕵️ [哨戒] 小隊 {current_unit_idx} 正在執行環境探路...")
                if not nav.run_pre_flight_check()["status"]:
                    print(f"⚠️ [塞車] IP {current_unit_idx} 連線異常，請求備援...")
                    current_unit_idx = backup_idx # 讓備援 IP 上場 [cite: 2026-01-16]
                    worker_id = f"g_unit_{current_unit_idx}" # 更新 worker_id
                    continue 

                # 🚀 4. 透過聯絡官領取任務 (會自動在 Supabase 留下 T1 偵察腳印)
                mission = self.t1_linker.fetch_t1_mission(worker_id, mode=mission_type)
                if not mission: break

                # 5. 根據模式分流：溫養日 vs 實戰日
                if not combat_mode:
                    # 💤 溫養日：帶著 Cookie 到處逛逛，不抓檔案
                    self._perform_news_mimicry(nav, "Warmup-Patrol")
                    self.t1_linker.s_log(worker_id, "WARMUP", "SUCCESS", f"已對 {mission['source_name']} 執行指紋溫養。")
                    print("🏁 [溫養結束] 巡航完畢，累積指紋成功，小隊撤退。")
                    break # 溫養日跑一次就結束

                # ⚔️ 實戰日：帶著 Cookie 先看新聞掩護，再抓檔案
                self._perform_news_mimicry(nav, "Pre-Combat")
                
                raw_mp3, opus_f = "g_raw.mp3", f"opt_{mission['id'][:8]}.opus"
                opus_local = f"/tmp/{opus_f}"
                
                try:
                    # 6. 執行破防下載
                    if nav.download_podcast(mission['audio_url'], raw_mp3):
                        # 7. 執行 Opus 16k Mono 壓縮 [cite: 2026-01-16]
                        if self._compress_to_opus(raw_mp3, opus_local):
                            print(f"🧬 [g-小隊] 壓縮完畢 ({os.path.getsize(opus_local)//1024} KB)，準備移交 T2...")
                            
                            # 8. 🚀 核心交接：上傳至 R2 倉庫
                            self.upload_to_r2(opus_local, opus_f)
                            
                            # 9. 📝 更新資料庫，正式將任務交接給 T2 (AI 部隊)
                            self.t1_linker.supabase.table("mission_queue").update({
                                "scrape_status": "completed",
                                "r2_url": opus_f,
                                "audio_ext": ".opus",
                                "recon_persona": f"[{worker_id}] 已完成 T1 運輸" # 🚀 留下 G-Squad 勝利印記
                            }).eq("id", mission["id"]).execute()
                            
                            self.t1_linker.s_log(worker_id, "LOGISTICS", "SUCCESS", f"壓縮完畢並成功上傳 R2: {opus_f}")
                            processed_count += 1
                            
                            print(f"🏁 [交接完成] {mission['source_name']} 已入庫，再次擬態造訪以掩蓋足跡...")
                            self._perform_news_mimicry(nav, "Post-Combat")
                        else:
                            raise Exception("本地 Opus 壓縮失敗")
                    else:
                        raise Exception("目標伺服器拒絕下載")
                        
                except Exception as e:
                    print(f"❌ [戰損] 任務失敗: {str(e)}")
                    # 任務失敗退回 pending，並清空 recon_persona 以供 T2 嘗試
                    self.t1_linker.supabase.table("mission_queue").update({
                        "scrape_status": "pending",
                        "recon_persona": f"[{worker_id}] T1 突擊失敗"
                    }).eq("id", mission["id"]).execute()
                    self.t1_linker.s_log(worker_id, "LOGISTICS", "ERROR", f"T1 運輸任務潰敗: {str(e)}")
                    break # 失敗後直接回報狀況，不接力

                # 清理現場
                for f in [raw_mp3, opus_local]:
                    if os.path.exists(f): os.remove(f)

            if processed_count < self.max_missions:
                time.sleep(random.randint(900, 1200)) # 任務間休息 15-20 分鐘

if __name__ == "__main__":
    commander = GuerrillaProcessor()
    commander.execute_guerrilla_hit()