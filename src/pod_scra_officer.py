# ---------------------------------------------------------
# 本程式碼：src/pod_scra_officer.py v6.2 (解碼官功能完備版)
# 任務：Hasdata 偵察、WebScrap 支援、徹底修復函式缺失與變數未定義
# ---------------------------------------------------------
import os, requests, time, re, urllib3, json
from supabase import create_client, Client
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from pod_scra_scanner import fetch_html 

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 一行註解：核心憑證識別器，優先讀取 Render 內部 Secret File。
def get_secret(key, default=None):
    vault_path = "/etc/secrets/render_secret_vault.json"
    if os.path.exists(vault_path):
        with open(vault_path, 'r') as f:
            vault = json.load(f)
            val = vault.get("active_credentials", {}).get(key)
            if val: return val
    return os.environ.get(key, default)

class StrategyManager:
    def __init__(self, supabase: Client, user_mode: str, scra_key: str):
        self.sb = supabase
        # 一行註解：將手動選定的模式持久化存入資料庫以供後續自動化調度。
        if "MODE_" in user_mode or user_mode == "AUTO":
            self.sb.table("api_budget_control").update({"mode_status": user_mode}).eq("id", "ZENROWS").execute()
        self.config = self._load_config()

    def _load_config(self):
        res = self.sb.table("api_budget_control").select("*").eq("id", "ZENROWS").execute()
        return res.data[0]

    def get_action_plan(self):
        # 一行註解：依據持久化記憶，將戰略映射至對應的偵察供應商。
        saved_mode = self.config.get("mode_status", "AUTO")
        mode_map = {
            "MODE_1_Scrapi": "SCRAPERAPI",
            "MODE_2_Zenrows": "ZENROWS",
            "MODE_3_Hasdata": "HASDATA",
            "MODE_4_Scrapedo": "SCRAPEDO"
        }
        return mode_map.get(saved_mode, "ZENROWS")

def run_scra_officer():
    # 一行註解：配發全能金鑰庫，Hasdata 與 WebScrap 同步就位。
    all_keys = {
        "SCRAPERAPI": get_secret("SCRAP_API_KEY"),
        "ZENROWS": get_secret("ZENROWS_API_KEY"),
        "HASDATA": get_secret("HASDATA_API_KEY"),
        "WEBSCRAP": get_secret("WEBSCRAP_API_KEY"),
        "SCRAPEDO": get_secret("SCRAPEDO_API_KEY")
    }
    sb_url, sb_key = get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY")
    user_mode = os.environ.get("STRATEGY_MODE", "AUTO")

    if not all([sb_url, sb_key]):
        print("❌ [中止] 憑證缺失。"); return

    supabase: Client = create_client(sb_url, sb_key)
    manager = StrategyManager(supabase, user_mode, all_keys["SCRAPERAPI"])

    # 一行註解：領取偵察派令，過濾待處理任務並進行小規模挖掘。
    missions = supabase.table("mission_queue").select("*").eq("scrape_status", "pending").limit(3).execute()
    print(f"📦 [掃描中] 發現 {len(missions.data)} 筆待處理任務。")

    for target in missions.data:
        task_id, podbay_slug = target['id'], str(target.get('podbay_slug') or "").strip()
        provider = manager.get_action_plan()
        final_mp3_url = None # 一行註解：初始化變數，根除 NameError 崩潰風險。
        
        try:
            # 一行註解：發動穿透請求，嘗試從 Podbay 提取音訊標籤。
            resp = fetch_html(provider, f"https://podbay.fm/p/{podbay_slug}", all_keys)
            if resp and resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                audio_meta = soup.find('meta', property=re.compile(r'(og:audio|twitter:player:stream)'))
                final_mp3_url = audio_meta.get('content') if audio_meta else None
                
                if final_mp3_url:
                    # 一行註解：偵察成功，回填物資位址並標記處理單位。
                    supabase.table("mission_queue").update({
                        "audio_url": final_mp3_url, "scrape_status": "success", "used_provider": provider
                    }).eq("id", task_id).execute()
                    print(f"✅ [入庫] {podbay_slug} via {provider}")
                else:
                    # 一行註解：解析失敗，轉交手動檢查並紀錄失敗供應商。
                    supabase.table("mission_queue").update({
                        "scrape_status": "manual_check", "used_provider": provider
                    }).eq("id", task_id).execute()
                    print(f"🔎 [未發現音檔] {podbay_slug}")
        except Exception as e:
            print(f"⚠️ [偵察異常]：{e}")

if __name__ == "__main__":
    run_scra_officer()