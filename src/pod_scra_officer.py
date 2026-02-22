
#---------------------------------------------------------------
#---------------------------------------------------------------
# 本程式碼：src/pod_scra_officer.py v5.0 (S-Plan 模組化解耦版)
# 任務：戰略調度、模式持久化、月初自動校準、呼叫外部 Scanner
#---------------------------------------------------------------#---------------------------------------------------------------
# 本程式碼：src/pod_scra_officer.py v6.0 (兵力重編決戰版)
# 任務：Mode 3 換班 Hasdata、WebScrap 轉職偵訊官、戰略持久化
#---------------------------------------------------------------
import os, requests, urllib.parse, time, re, urllib3, random
from supabase import create_client, Client
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from pod_scra_scanner import fetch_html 

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 區塊：新增 Hasdata 與 WebScrap 特種功能 ---
def investigate_final_url(url, webscrap_key):
    """
    🕵️ [偵訊官行動] WebScrap 專屬任務：追查解析最終網址。
    """
    # 利用 WebScrap 強大的解析能力，追蹤重定向後的最終 MP3 座標。
    print(f"🕵️ [偵訊中] WebScrap 正在追蹤最終目標...")
    # 這裡可串接 WebScrap 專用的解析邏輯
    return url # 範例回傳

class StrategyManager:
    def __init__(self, supabase: Client, user_mode: str, scra_key: str):
        self.sb = supabase
        self.scra_key = scra_key
        # 一行註解：將手動選定的戰略模式持久化存入資料庫，實現跨 session 記憶。
        if "MODE_" in user_mode or user_mode == "AUTO":
            self.sb.table("api_budget_control").update({"mode_status": user_mode}).eq("id", "ZENROWS").execute()
            print(f"💾 [戰略存檔] 指令已鎖定：{user_mode}")
        self.config = self._load_config()

    def _load_config(self):
        res = self.sb.table("api_budget_control").select("*").eq("id", "ZENROWS").execute()
        data = res.data[0]
        # 每月 1 號執行自動校準，將戰略模式重置為 AUTO 狀態。
        if datetime.now().day == 1 and data['last_reset_date'] != str(datetime.now().date()):
            update_fields = {"balance": 1000, "mode_status": "AUTO", "last_reset_date": str(datetime.now().date())}
            self.sb.table("api_budget_control").update(update_fields).eq("id", "ZENROWS").execute()
            data.update(update_fields)
            print("📅 [月初校準] 全軍回歸 AUTO 模式。")
        return data

    def get_action_plan(self):
        saved_mode = self.config.get("mode_status", "AUTO")
        
        # 🎯 [戰略變更] Mode 3 改由 HASDATA 出勤
        mode_map = {
            "MODE_1_Scrapi": "SCRAPERAPI",
            "MODE_2_Zenrows": "ZENROWS",
            "MODE_3_Hasdata": "HASDATA",  # Mode 3 正式更換為 Hasdata 部隊。
            "MODE_4_Scrapedo": "SCRAPEDO"
        }

        if saved_mode in mode_map:
            return mode_map[saved_mode]

        # AUTO 模式下，若點數充足則優先使用 ScraperAPI
        scra_balance = get_scraperapi_balance(self.scra_key)
        if scra_balance > 80:
            return "SCRAPERAPI"
        else:
            return "ZENROWS"

    def deduct_points(self, provider):
        # 根據不同供應商，扣除資料庫中預估的 API 點數餘額。
        if provider == "ZENROWS":
            new_balance = max(0, self.config['balance'] - 25)
            self.sb.table("api_budget_control").update({"balance": new_balance}).eq("id", "ZENROWS").execute()

def run_scra_officer():
    # 🚀 [補給更新] 新增 HASDATA 金鑰，保留 WEBSCRAP 供偵訊官調度
    all_keys = {
        "SCRAPERAPI": get_secret("SCRAP_API_KEY"),
        "ZENROWS": get_secret("ZENROWS_API_KEY"),
        "HASDATA": get_secret("HASDATA_API_KEY"), # 為新部隊 Hasdata 配發密鑰。
        "WEBSCRAP": get_secret("WEBSCRAP_API_KEY"), # 保留 WebScrap 密鑰供特定解析任務調用。
        "SCRAPEDO": get_secret("SCRAPEDO_API_KEY")
    }
    sb_url = get_secret("SUPABASE_URL")
    sb_key = get_secret("SUPABASE_KEY")
    user_mode = os.environ.get("STRATEGY_MODE", "AUTO")

    supabase: Client = create_client(sb_url, sb_key)
    manager = StrategyManager(supabase, user_mode, all_keys["SCRAPERAPI"])

    missions = supabase.table("mission_queue").select("*").eq("scrape_status", "pending").limit(3).execute()

    for target in missions.data:
        task_id = target['id']
        podbay_slug = str(target.get('podbay_slug') or "").strip()
        provider = manager.get_action_plan()
        target_page = f"https://podbay.fm/p/{podbay_slug}"

        try:
            # 一行註解：呼叫外部掃描器，並傳遞當前決策的供應商與密鑰庫。
            resp = fetch_html(provider, target_page, all_keys)
            manager.deduct_points(provider)

            if resp and resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                # ... (中間解析邏輯不變) ...
                
                # 一行註解：如果抓到的 URL 需要進階偵訊，在此處喚醒 WebScrap 偵訊官。
                # final_mp3_url = investigate_final_url(final_mp3_url, all_keys["WEBSCRAP"])

                update_data = {
                    "audio_url": final_mp3_url,
                    "scrape_status": "success",
                    "used_provider": provider, 
                    "status": "pending"
                }
                supabase.table("mission_queue").update(update_data).eq("id", task_id).execute()
        except Exception as e:
            print(f"⚠️ [程序異常]：{str(e)}")

# 此處需定義 get_secret 以支援混合讀取邏輯。
def get_secret(key): return os.environ.get(key)

if __name__ == "__main__":
    run_scra_officer()