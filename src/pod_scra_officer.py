
#---------------------------------------------------------------
#---------------------------------------------------------------
# 本程式碼：src/pod_scra_officer.py v5.0 (S-Plan 模組化解耦版)
# 任務：戰略調度、模式持久化、月初自動校準、呼叫外部 Scanner
#---------------------------------------------------------------
import os, requests, urllib.parse, time, re, urllib3, random
from supabase import create_client, Client
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from pod_scra_scanner import fetch_html # 🚀 導入外部掃描器

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_scraperapi_balance(api_key):
    """即時遙測：獲取 ScraperAPI 剩餘點數"""
    try:
        res = requests.get(f"https://api.scraperapi.com/account?api_key={api_key}", timeout=10)
        if res.status_code == 200:
            data = res.json()
            return data.get('requests_available', 78)
    except Exception as e:
        print(f"⚠️ [遙測失敗]: {e}")
    return 78

class StrategyManager:
    """戰略管理器：負責多軌切換與點數持久化控制"""
    def __init__(self, supabase: Client, user_mode: str, scra_key: str):
        self.sb = supabase
        self.scra_key = scra_key
        # 若有手動輸入模式，優先持久化寫入 DB 記憶
        if "MODE_" in user_mode or user_mode == "AUTO":
            self.sb.table("api_budget_control").update({"mode_status": user_mode}).eq("id", "ZENROWS").execute()
            print(f"💾 [戰略存檔] 模式設定鎖定為：{user_mode}")
        self.config = self._load_config()

    def _load_config(self):
        """月初自動校準與載入設定"""
        res = self.sb.table("api_budget_control").select("*").eq("id", "ZENROWS").execute()
        data = res.data[0]
        if datetime.now().day == 1 and data['last_reset_date'] != str(datetime.now().date()):
            update_fields = {"balance": 1000, "mode_status": "AUTO", "last_reset_date": str(datetime.now().date())}
            self.sb.table("api_budget_control").update(update_fields).eq("id", "ZENROWS").execute()
            data.update(update_fields)
            print("📅 [月初校準] 點數已重置，戰略回歸 AUTO 模式。")
        return data

    def get_action_plan(self):
        """核心決策邏輯：根據 DB 記憶或即時點數決定供應商"""
        saved_mode = self.config.get("mode_status", "AUTO")
        
        # 映射表：將 YAML 選單標籤轉為 Scanner 識別碼
        mode_map = {
            "MODE_1_Scrapi": "SCRAPERAPI",
            "MODE_2_Zenrows": "ZENROWS",
            "MODE_3_Webscrap": "WEBSCRAPING",
            "MODE_4_Scrapedo": "SCRAPEDO"
        }

        # 1. 處理手動指定的固定模式
        if saved_mode in mode_map:
            print(f"🕹️ [手動模式] 指揮官指令：採用 {mode_map[saved_mode]}")
            return mode_map[saved_mode]

        # 2. 處理 AUTO 自動模式邏輯 (3/3 前優先使用 Zenrows 試用)
        scra_balance = get_scraperapi_balance(self.scra_key)
        print(f"📊 ScraperAPI 即時庫存：{scra_balance} 點")
        if scra_balance > 80:
            return "SCRAPERAPI"
        else:
            print(f"🚨 [自動避險] ScraperAPI 不足，切換至主力備援 ZENROWS")
            return "ZENROWS"

    def deduct_points(self, provider):
        """根據不同供應商扣除 DB 中的預估點數 (統一暫估每次 25 點)"""
        # 僅 ZENROWS 目前有在 DB 紀錄 balance，其餘 provider 暫為紀錄性質
        if provider == "ZENROWS":
            new_balance = max(0, self.config['balance'] - 25)
            self.sb.table("api_budget_control").update({"balance": new_balance}).eq("id", "ZENROWS").execute()
            print(f"📉 [扣點] {provider} 預估餘額：{new_balance}")

def run_scra_officer():
    # 1. 讀取戰略金鑰
    all_keys = {
        "SCRAPERAPI": os.environ.get("SCRAP_API_KEY"),
        "ZENROWS": os.environ.get("ZENROWS_API_KEY"),
        "WEBSCRAP": os.environ.get("WEBSCRAP_API_KEY"),
        "SCRAPEDO": os.environ.get("SCRAPEDO_API_KEY")
    }
    sb_url = os.environ.get("SUPABASE_URL")
    sb_key = os.environ.get("SUPABASE_KEY")
    user_mode = os.environ.get("STRATEGY_MODE", "AUTO")

    if not all([sb_url, sb_key, all_keys["SCRAPERAPI"], all_keys["ZENROWS"]]):
        print("❌ [資安警報] 缺少關鍵環境變數。")
        return

    supabase: Client = create_client(sb_url, sb_key)
    manager = StrategyManager(supabase, user_mode, all_keys["SCRAPERAPI"])

    # 戰術休眠：模擬真人行為
    start_delay = random.randint(600, 2400)
    print(f"🕒 [戰術等待] 隨機休眠 {start_delay//60} 分鐘...")
    time.sleep(start_delay)

    # 2. 領取偵察任務
    missions = supabase.table("mission_queue").select("*") \
        .eq("scrape_status", "pending") \
        .limit(3).execute()

    for target in missions.data:
        task_id = target['id']
        podbay_slug = str(target.get('podbay_slug') or "").strip()

        if not podbay_slug or podbay_slug.isdigit():
            print(f"⚠️ [數據異常] Slug {podbay_slug} 無效，標記手動檢查。")
            supabase.table("mission_queue").update({"scrape_status": "manual_check"}).eq("id", task_id).execute()
            continue

        # 3. 獲取作戰計畫並呼叫掃描器
        provider = manager.get_action_plan()
        target_page = f"https://podbay.fm/p/{podbay_slug}"
        print(f"🎯 [執行中] 供應商：{provider} | 目標：{podbay_slug}")

        try:
            # 🚀 解耦核心：一行調用外部掃描器，不再管參數細節
            resp = fetch_html(provider, target_page, all_keys)
            manager.deduct_points(provider)

            if resp and resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                audio_meta = soup.find('meta', property=re.compile(r'(og:audio|twitter:player:stream)'))
                final_mp3_url = audio_meta.get('content') if audio_meta else None
                
                if not final_mp3_url:
                    mp3_link = soup.find('a', href=re.compile(r'\.mp3'))
                    final_mp3_url = mp3_link['href'] if mp3_link else None

                if final_mp3_url:
                    # 4. 物資入庫
                    update_data = {
                        "audio_url": final_mp3_url,
                        "scrape_status": "success",
                        "used_provider": provider, 
                        "status": "pending",
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }
                    supabase.table("mission_queue").update(update_data).eq("id", task_id).execute()
                    print(f"✅ [成功] 物資已入庫，標籤為：{provider}")
                else:
                    print(f"🔎 [未發現音檔] 網頁解析成功但無 MP3，標記手動檢查。")
                    supabase.table("mission_queue").update({"scrape_status": "manual_check"}).eq("id", task_id).execute()
            else:
                print(f"❌ [請求失敗] 供應商回報狀態碼：{resp.status_code if resp else 'No Resp'}")

        except Exception as e:
            print(f"⚠️ [程序異常]：{str(e)}")

if __name__ == "__main__":
    run_scra_officer()