
#---------------------------------------------------------------
# 本程式碼：src/pod_scra_officer.py v6.1 (兵力重編修復版)
# 任務：Hasdata 接手 Mode 3、WebScrap 轉職、修復變數未定義錯誤
#---------------------------------------------------------------
import os, requests, time, re, urllib3, json
from supabase import create_client, Client
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from pod_scra_scanner import fetch_html 

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def investigate_final_url(url, webscrap_key):
    # 調用 WebScrap 執行高難度追蹤，穿透重定向獲取最終 MP3。
    print(f"🕵️ [偵訊官] WebScrap 正在追蹤最終目標...")
    return url # 預留擴充空間

class StrategyManager:
    def __init__(self, supabase: Client, user_mode: str, scra_key: str):
        self.sb = supabase
        #  將指揮官的手動選定模式持久化至資料庫。
        if "MODE_" in user_mode or user_mode == "AUTO":
            self.sb.table("api_budget_control").update({"mode_status": user_mode}).eq("id", "ZENROWS").execute()
        self.config = self._load_config()

    def _load_config(self):
        res = self.sb.table("api_budget_control").select("*").eq("id", "ZENROWS").execute()
        return res.data[0]

    def get_action_plan(self):
        #  讀取持久化記憶，決定由哪支偵察部隊出動。
        saved_mode = self.config.get("mode_status", "AUTO")
        mode_map = {
            "MODE_1_Scrapi": "SCRAPERAPI",
            "MODE_2_Zenrows": "ZENROWS",
            "MODE_3_Hasdata": "HASDATA",  #  Mode 3 正式由 Hasdata 擔任。
            "MODE_4_Scrapedo": "SCRAPEDO"
        }
        return mode_map.get(saved_mode, "ZENROWS") # 預設回退至 Zenrows

def run_scra_officer():
    #  配發全新彈藥，Hasdata 進入序列，WebScrap 轉為支援。
    all_keys = {
        "SCRAPERAPI": os.environ.get("SCRAP_API_KEY"),
        "ZENROWS": os.environ.get("ZENROWS_API_KEY"),
        "HASDATA": os.environ.get("HASDATA_API_KEY"),
        "WEBSCRAP": os.environ.get("WEBSCRAP_API_KEY"),
        "SCRAPEDO": os.environ.get("SCRAPEDO_API_KEY")
    }
    sb_url, sb_key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY")
    user_mode = os.environ.get("STRATEGY_MODE", "AUTO")

    supabase: Client = create_client(sb_url, sb_key)
    manager = StrategyManager(supabase, user_mode, all_keys["SCRAPERAPI"])

    missions = supabase.table("mission_queue").select("*").eq("scrape_status", "pending").limit(3).execute()

    for target in missions.data:
        task_id = target['id']
        podbay_slug = str(target.get('podbay_slug') or "").strip()
        provider = manager.get_action_plan()
        
        # 🎯 重要修復：初始化變數，避免 NameError 崩潰。
        final_mp3_url = None 
        
        try:
            resp = fetch_html(provider, f"https://podbay.fm/p/{podbay_slug}", all_keys)
            if resp and resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                # 一行註解：執行多標籤掃描，尋找隱藏的音訊資源。
                audio_meta = soup.find('meta', property=re.compile(r'(og:audio|twitter:player:stream)'))
                final_mp3_url = audio_meta.get('content') if audio_meta else None
                
                if final_mp3_url:
                    # 一行註解：若發現目標，立即回填庫存並更新偵察狀態。
                    supabase.table("mission_queue").update({
                        "audio_url": final_mp3_url, "scrape_status": "success", "used_provider": provider
                    }).eq("id", task_id).execute()
                    print(f"✅ [入庫] {podbay_slug}")
                else:
                    supabase.table("mission_queue").update({"scrape_status": "manual_check"}).eq("id", task_id).execute()
        except Exception as e:
            print(f"⚠️ [異常]：{e}")

if __name__ == "__main__":
    run_scra_officer()