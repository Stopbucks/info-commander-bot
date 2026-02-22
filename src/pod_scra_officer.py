
#---------------------------------------------------------------
# 本程式碼：src/pod_scra_officer.py v6.1 (兵力重編修復版)-測試Render
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
# -----(定位線)以下修改偵察執行邏輯----

def run_scra_officer():
    # 一行註解：初始化全域金鑰庫，Hasdata 正式進入作戰序列。
    all_keys = {
        "SCRAPERAPI": get_secret("SCRAP_API_KEY"),
        "ZENROWS": get_secret("ZENROWS_API_KEY"),
        "HASDATA": get_secret("HASDATA_API_KEY"), # 一行註解：配發 Hasdata 專屬子彈。
        "WEBSCRAP": get_secret("WEBSCRAP_API_KEY"),
        "SCRAPEDO": get_secret("SCRAPEDO_API_KEY")
    }
    sb_url, sb_key = get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY")
    user_mode = os.environ.get("STRATEGY_MODE", "AUTO")

    # 一行註解：執行戰前憑證掃描，確保資料庫連線無礙。
    if not all([sb_url, sb_key]):
        print("❌ [中止] 關鍵後勤憑證缺失。"); return

    supabase: Client = create_client(sb_url, sb_key)
    manager = StrategyManager(supabase, user_mode, all_keys["SCRAPERAPI"])

    # 一行註解：領取偵察派令，鎖定 pending 狀態的物資進行挖掘。
    missions = supabase.table("mission_queue").select("*").eq("scrape_status", "pending").limit(3).execute()
    print(f"📦 [掃描中] 發現 {len(missions.data)} 筆待處理任務。")

    for target in missions.data:
        task_id = target['id']
        podbay_slug = str(target.get('podbay_slug') or "").strip()
        provider = manager.get_action_plan()
        
        # 🎯 核心修復：初始化變數，徹底根除 NameError 崩潰風險。
        final_mp3_url = None 
        
        try:
            # 一行註解：調用外部掃描器發動請求，並傳遞當前決策的供應商與密鑰庫。
            resp = fetch_html(provider, f"https://podbay.fm/p/{podbay_slug}", all_keys)
            
            if resp and resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                # 一行註解：執行多標籤掃描，從 HTML 中鎖定音訊串流位址。
                audio_meta = soup.find('meta', property=re.compile(r'(og:audio|twitter:player:stream)'))
                final_mp3_url = audio_meta.get('content') if audio_meta else None
                
                if final_mp3_url:
                    # 一行註解：物資採集成功，回填資料庫並標記功勞單位（供應商）。
                    supabase.table("mission_queue").update({
                        "audio_url": final_mp3_url, 
                        "scrape_status": "success", 
                        "used_provider": provider
                    }).eq("id", task_id).execute()
                    print(f"✅ [成功入庫] {podbay_slug} via {provider}")
                else:
                    # 🚀 戰術修正：失敗轉手動檢查時，亦同步紀錄供應商名稱，以便事後計算點數轉化率。
                    supabase.table("mission_queue").update({
                        "scrape_status": "manual_check",
                        "used_provider": provider # 一行註解：填補統計漏洞，紀錄是誰偵察失敗。
                    }).eq("id", task_id).execute()
                    print(f"🔎 [未發現音檔] {podbay_slug} 已標記手動檢查，供應商：{provider}")
        except Exception as e:
            print(f"⚠️ [偵察異常] 供應商 {provider} 遭遇攔截：{e}")


if __name__ == "__main__":
    run_scra_officer()