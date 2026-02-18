
#---------------------------------------------------------------
# 本程式碼：src/pod_scra_officer.py v4.6 (S-Plan 自適性偵察加固版)
# 任務：實作即時 API 餘額偵測、永久模式記憶、及月初優先校準
# 流程：初始化 -> 月初重置校準 -> 戰術休眠 -> 執行任務 (max 3)
#---------------------------------------------------------------
import os, requests, urllib.parse, time, re, urllib3, random
from supabase import create_client, Client
from bs4 import BeautifulSoup
from datetime import datetime, timezone

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_scraperapi_balance(api_key):
    """技術用語：即時遙測。修正解析邏輯，增加容錯性"""
    try:
        res = requests.get(f"https://api.scraperapi.com/account?api_key={api_key}", timeout=10)
        if res.status_code == 200:
            data = res.json()
            return data.get('requests_available', data.get('request_limit', 78)) 
    except Exception as e:
        print(f"⚠️ [遙測失敗]: {e}")
    return 78

class StrategyManager:
    """戰略管理器：負責雙軌切換、模式持久化及月初自動校準"""
    def __init__(self, supabase: Client, user_mode: str, scra_key: str):
        self.sb = supabase
        self.scra_key = scra_key
        if user_mode in ["MODE_1", "MODE_2", "AUTO"]:
            self.sb.table("api_budget_control").update({"mode_status": user_mode}).eq("id", "ZENROWS").execute()
            print(f"💾 [戰略存檔] 模式設定鎖定為：{user_mode}")
        self.config = self._load_config()

    def _load_config(self):
        res = self.sb.table("api_budget_control").select("*").eq("id", "ZENROWS").execute()
        data = res.data[0]
        if datetime.now().day == 1 and data['last_reset_date'] != str(datetime.now().date()):
            update_fields = {
                "balance": 1000, 
                "mode_status": "AUTO", 
                "last_reset_date": str(datetime.now().date())
            }
            self.sb.table("api_budget_control").update(update_fields).eq("id", "ZENROWS").execute()
            data.update(update_fields)
            print("📅 [月初校準] 點數已重置，戰略回歸 AUTO 模式。")
        return data
    
    #------------------------------------------------
    # 模式一 & 二：scraperAPI 點數閥值_最低轉換值 (80)
    #------------------------------------------------

    def get_provider(self):
        saved_mode = self.config.get("mode_status", "AUTO")
        if saved_mode == "MODE_1": return "SCRAPERAPI"
        if saved_mode == "MODE_2": return "ZENROWS"
        scra_balance = get_scraperapi_balance(self.scra_key)
        print(f"📊 ScraperAPI 即時庫存：{scra_balance} 點")
        if scra_balance < 80:
            return "ZENROWS"
        return "SCRAPERAPI"

    def deduct_zenrows(self):
        new_balance = max(0, self.config['balance'] - 25)
        self.sb.table("api_budget_control").update({"balance": new_balance}).eq("id", "ZENROWS").execute()
        print(f"📉 [扣點] ZenRows 預估餘額：{new_balance}")

def run_scra_officer():
    sb_url = os.environ.get("SUPABASE_URL")
    sb_key = os.environ.get("SUPABASE_KEY")
    scra_key = os.environ.get("SCRAP_API_KEY")
    zen_key = os.environ.get("ZENROWS_API_KEY")
    user_mode = os.environ.get("STRATEGY_MODE", "AUTO")

    if not all([sb_url, sb_key, scra_key, zen_key]):
        print("❌ [資安警報] 缺少必要環境變數。")
        return

    supabase: Client = create_client(sb_url, sb_key)
    manager = StrategyManager(supabase, user_mode, scra_key)

    start_delay = random.randint(600, 2400)
    print(f"🕒 [戰術等待] 已完成預先校準，啟動隨機休眠 {start_delay//60} 分鐘...")
    time.sleep(start_delay)

    #--- 定位線區塊 ---#
    missions = supabase.table("mission_queue").select("*") \
        .not_.is_("scrape_status", "null") \
        .eq("scrape_status", "pending") \
        .limit(3).execute()

    for target in missions.data:
        task_id = target['id']
        podbay_slug = str(target.get('podbay_slug') or "").strip()
        safe_title = urllib.parse.quote(target.get('episode_title', ''))

        if not podbay_slug or podbay_slug.isdigit():
            print(f"⚠️ [數據異常] ID {task_id} 的 Slug 無效，跳過。")
            supabase.table("mission_queue").update({"scrape_status": "manual_check"}).eq("id", task_id).execute()
            continue

        final_mp3_url = "" 
        provider = manager.get_provider()
        target_page = f"https://podbay.fm/p/{podbay_slug}"
        print(f"🎯 [處理中] {target['episode_title'][:20]}... 採用：{provider}")
    #--- 定位線結束 ---#

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
                    "used_provider": provider, 
                    "status": "pending",
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
                supabase.table("mission_queue").update(update_data).eq("id", task_id).execute()
                print(f"✅ [入庫成功] 門票發放成功。")
            except Exception as e:
                print(f"❌ [寫入失敗]：{str(e)}")

if __name__ == "__main__":
    run_scra_officer()