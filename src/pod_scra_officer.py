
#---------------------------------------------------------------
# 本程式碼：src/pod_scra_officer.py v4.5 (S-Plan 自適性偵察版)
# 任務：實作即時 API 餘額偵測、永久模式記憶、及月初自動回歸
# 流程：Jitter 啟動 -> 查詢 ScraperAPI 餘額 -> 決定武器 -> 執行任務
#---------------------------------------------------------------
import os, requests, urllib.parse, time, re, urllib3, random
from supabase import create_client, Client
from bs4 import BeautifulSoup
from datetime import datetime, timezone

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_scraperapi_balance(api_key):
    """技術用語：即時遙測。直接從 ScraperAPI 帳戶端點獲取最新剩餘點數"""
    try:
        res = requests.get(f"https://api.scraperapi.com/account?api_key={api_key}", timeout=10)
        if res.status_code == 200:
            data = res.json()
            # 剩餘點數 = 總額度 - 已使用
            return data['request_limit'] - data['request_count']
    except Exception as e:
        print(f"⚠️ [遙測失敗] 無法獲取 ScraperAPI 餘額: {e}")
    return 78  # 失敗時回傳安全保守值

class StrategyManager:
    """戰略管理器：負責雙軌切換、模式持久化及月初自動校準"""
    def __init__(self, supabase: Client, user_mode: str, scra_key: str):
        self.sb = supabase
        self.scra_key = scra_key
        
        # 若使用者手動從面板選擇模式，則將該設定寫入 Supabase 實現「永久記憶」
        if user_mode in ["MODE_1", "MODE_2", "AUTO"]:
            self.sb.table("api_budget_control").update({"mode_status": user_mode}).eq("id", "ZENROWS").execute()
            print(f"💾 [戰略存檔] 當前模式已鎖定為：{user_mode}")
        
        self.config = self._load_config()

    def _load_config(self):
        res = self.sb.table("api_budget_control").select("*").eq("id", "ZENROWS").execute()
        data = res.data[0]
        
        # 模式二與自適性校準：每月 1 號強制恢復 1000 點，並回歸 AUTO 模式
        if datetime.now().day == 1 and data['last_reset_date'] != str(datetime.now().date()):
            update_fields = {
                "balance": 1000, 
                "mode_status": "AUTO", 
                "last_reset_date": str(datetime.now().date())
            }
            self.sb.table("api_budget_control").update(update_fields).eq("id", "ZENROWS").execute()
            data.update(update_fields)
            print("📅 [月初校準] 點數重置完成，戰略回歸 AUTO 模式。")
        return data

    def get_provider(self):
        # 優先讀取資料庫存檔的模式
        saved_mode = self.config.get("mode_status", "AUTO")
        
        if saved_mode == "MODE_1": return "SCRAPERAPI"
        if saved_mode == "MODE_2": return "ZENROWS"
        
        # 若為 AUTO，則根據 ScraperAPI 即時點數進行自適性切換
        scra_balance = get_scraperapi_balance(self.scra_key)
        print(f"📊 ScraperAPI 即時庫存：{scra_balance} 點")
        
        # 風險提醒：若 ScraperAPI 低於 50 點，自動切換至 ZenRows 備援
        if scra_balance < 50:
            return "ZENROWS"
        return "SCRAPERAPI"

    def deduct_zenrows(self):
        # 模擬扣點：根據 ZenRows 規則，Podbay 渲染扣除 25 點
        new_balance = max(0, self.config['balance'] - 25)
        self.sb.table("api_budget_control").update({"balance": new_balance}).eq("id", "ZENROWS").execute()
        print(f"📉 [扣點] ZenRows 剩餘預估：{new_balance}")

def run_scra_officer():
    # 戰術 Jitter：隨機啟動延遲 10~40 分鐘
    start_delay = random.randint(600, 2400)
    print(f"🕒 [戰術等待] 啟動隨機休眠 {start_delay//60} 分鐘...")
    time.sleep(start_delay)

    sb_url = os.environ.get("SUPABASE_URL")
    sb_key = os.environ.get("SUPABASE_KEY")
    scra_key = os.environ.get("SCRAP_API_KEY")
    zen_key = os.environ.get("ZENROWS_API_KEY")
    # 讀取 GitHub 面板輸入
    user_mode = os.environ.get("STRATEGY_MODE", "AUTO")

    if not all([sb_url, sb_key, scra_key, zen_key]):
        print("❌ [資安警報] 缺少必要環境變數。")
        return

    supabase: Client = create_client(sb_url, sb_key)
    manager = StrategyManager(supabase, user_mode, scra_key)
    
    # 區塊化設計：每次處理不超過 3 筆，維護資源容易
    missions = supabase.table("mission_queue").select("*").eq("scrape_status", "pending").limit(3).execute()
    
    if not missions.data:
        print("☕ 目前無待處理任務。")
        return

    for index, target in enumerate(missions.data):
        # 任務間隨機間隔 3~10 分鐘，模擬真人瀏覽
        if index > 0:
            interval = random.randint(180, 600)
            print(f"⏳ [任務間隔] 休眠 {interval//60} 分鐘...")
            time.sleep(interval)

        task_id = target['id']
        podbay_slug = target.get('podbay_slug') or "bloomberg-businessweek"
        final_mp3_url = ""
        
        # 呼叫自適性判斷
        provider = manager.get_provider()
        target_page = f"https://podbay.fm/p/{podbay_slug}"
        print(f"🎯 [處理中] {target['episode_title'][:20]}... 採用：{provider}")

        try:
            if provider == "ZENROWS":
                params = {'api_key': zen_key, 'url': target_page, 'js_render': 'true', 'premium_proxy': 'true'}
                resp = requests.get('https://api.zenrows.com/v1/', params=params, timeout=60)
                manager.deduct_zenrows()
            else:
                api_url = f"https://api.scraperapi.com?api_key={scra_key}&url={urllib.parse.quote(target_page)}&render=true"
                resp = requests.get(api_url, timeout=60)

            soup = BeautifulSoup(resp.text, 'html.parser')
            audio_meta = soup.find('meta', property=re.compile(r'(og:audio|twitter:player:stream)'))
            if audio_meta:
                final_mp3_url = audio_meta.get('content')
            else:
                mp3_link = soup.find('a', href=re.compile(r'\.mp3'))
                if mp3_link: final_mp3_url = mp3_link['href']

        except Exception as e:
            print(f"⚠️ [抓取異常]：{str(e)}")

        if final_mp3_url:
            try:
                update_data = {
                    "audio_url": final_mp3_url,
                    "scrape_status": "success",
                    "status": "pending",
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
                supabase.table("mission_queue").update(update_data).eq("id", task_id).execute()
                print(f"✅ [入庫成功] 門票發放。")
            except Exception as e:
                print(f"❌ [寫入失敗]：{str(e)}")

if __name__ == "__main__":
    run_scra_officer()