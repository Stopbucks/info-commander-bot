# ---------------------------------------------------------
# podcast_g_proc.py ： 游擊 g-小隊指揮官 (進階節流與 Opus 版)
# 戰術原則：1-3-5-7 出勤、8+1 IP 輪替、Opus 壓縮、Groq 深度摘要
# ---------------------------------------------------------

import os
import sys
import time
import random
import subprocess
from datetime import datetime, timezone
from podcast_processor import PodcastProcessor  # 繼承主力部隊核心
from podcast_navigator import NetworkNavigator



class GuerrillaProcessor(PodcastProcessor):
    def __init__(self):
        # 🚀 核心優化：直接在初始化父類別時就指定游擊專屬檔案
        # 這會一次性完成本地隔離與雲端路徑設定
        super().__init__(monitor_file="guerrilla_monitor.json")
        
        print("🪖 [g-小隊] 獨立人格已就緒，所有指紋與任務進度將隔離至專屬檔案。")
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
    # 技術部：Opus 壓縮邏輯
    # ---------------------------------------------------------
    def _compress_to_opus(self, input_f, output_f):
        """⚡ [FFmpeg] 將音檔轉為 16k Mono Opus (人聲最佳化) [cite: 2026-01-16]"""
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

    # ---------------------------------------------------------
    # 偵察部：擬態閱讀新聞
    # ---------------------------------------------------------
    def _perform_news_mimicry(self, nav, stage="Combat"):
        """🎭 [數位擬態] 執行 Apple、BBC、CNN 巡航 [cite: 2026-01-16]"""
        targets = ["https://podcasts.apple.com/", "https://www.bbc.com/news", "https://www.cnn.com/world"]
        random.shuffle(targets)
        print(f"🕵️ [{stage}] 執行新聞巡航建立指紋...")
        for url in targets:
            try:
                nav.session.get(url, timeout=10, stream=True)
                time.sleep(random.uniform(5, 10))
            except: pass

    # ---------------------------------------------------------
    # 指揮部：作戰流程 (加入 Groq 摘要)
    # ---------------------------------------------------------
    def execute_guerrilla_hit(self):
        """⚔️ [g-小隊行動] 輪流上場、失敗熔斷、Groq 摘要 [cite: 2026-01-16]"""
        now_utc = datetime.now(timezone.utc)
        weekday = now_utc.isoweekday() # 1=Mon, 3=Wed, 5=Fri, 7=Sun

        # 🚀 1. 出勤判斷：僅在 1, 3, 5, 7 執行 [cite: 2026-01-16]
        #if weekday not in [1, 3, 5, 7]:
        if weekday not in [1, 3, 5, 7]:

            print(f"☕ [休整] 今日非出勤日 (UTC {weekday})，小隊待命。")
            return

        proxies = self._get_guerrilla_proxies()
        if len(proxies) < 9:
            print("❌ [錯誤] 代理數量不足 9 個，無法執行輪替邏輯。")
            return

        # 🚀 2. IP 輪替與備援邏輯 (8 個輪流，第 9 個為備援) [cite: 2026-01-16]
        # 簡單邏輯：根據周數與出勤日決定索引
        week_num = now_utc.isocalendar()[1]
        rotation_idx = (week_num + weekday) % 8 
        backup_idx = 8 # 固定的備援索引 (第 9 個 IP)

        current_unit_idx = rotation_idx
        processed_count = 0

        print(f"🕒 [隱蔽] 預計 40 分鐘內隨機發起突襲...")
        time.sleep(random.randint(0, 2400))

        while processed_count < self.max_missions:
            proxy_url = proxies[current_unit_idx]
            persona = self._get_wbs_persona(current_unit_idx)
        # 尋找 execute_guerrilla_hit 內的 g_config 區塊並替換：
        # 💡 戰術變更：徹底移除 headers 鍵值對，避免與擬態引擎衝突  
            g_config = {
                "squad_name": f"g_unit_{current_unit_idx}",
                "transport_proxy": proxy_url,
                "identity_hash": f"g_wbs_{current_unit_idx}",
                "path_id": "WBS_G",
                "curl_config": {
                    # 💡 放回標籤，但內容留空，由 impersonate 接管指紋生成
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
                    continue 

                self._perform_news_mimicry(nav, "Pre-Combat")
                mission = self.fetch_cloud_mission()
                if not mission: break

                raw_mp3, opus_f = "g_raw.mp3", "g_final.opus"
                try:
                    # 4. 下載與壓縮
                    if nav.download_podcast(mission['audio_url'], raw_mp3):
                        # 執行 Opus 16k Mono 壓縮 (符合 Groq 偏好) [cite: 2026-01-16]
                        if self._compress_to_opus(raw_mp3, opus_f):
                            print(f"🧬 [g-小隊] 壓縮完畢 ({os.path.getsize(opus_f)//1024} KB)，交付 Groq...")
                            
                            # 🚀 雙階段交付：轉寫 -> 摘要 [cite: 2026-01-16]
                            analysis = self.ai_agent.generate_groq_summary(opus_f)
                            
                           
                            if analysis:
                                msg = f"📡 [g-小隊情報]\n目標：{mission['source_name']}\n\n{analysis}"
                                self.send_webhook(nav, {"tier": "Guerrilla", "title": mission['source_name'], "content": msg})
                                self.finalize_cloud_mission(mission["id"], "completed")
                                processed_count += 1
                                print("🏁 [完成] 任務回報完畢，再次擬態造訪...")
                                self._perform_news_mimicry(nav, "Post-Combat")
                        
                except Exception as e:
                    print(f"❌ [戰損] 任務失敗: {str(e)}")
                    self.finalize_cloud_mission(mission["id"], "failed")
                    break # 失敗後直接回報狀況，不接力

                # 清理現場
                for f in [raw_mp3, opus_f]:
                    if os.path.exists(f): os.remove(f)

            if processed_count < self.max_missions:
                time.sleep(random.randint(900, 1200)) # 任務間休息 15-20 分鐘

if __name__ == "__main__":
    commander = GuerrillaProcessor()
    commander.execute_guerrilla_hit()