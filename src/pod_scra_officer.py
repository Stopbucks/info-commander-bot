
#---------------------------------------------------------------
# 本程式碼：src/pod_scra_officer.py v3.1 (精準節流加固版)
# 任務：限制點數消耗 (limit 2) -> 雙向填入網址 -> 強化解析
# 流程：透過scraperAPI、廣域掃描 MP3 標籤、安全備援
#---------------------------------------------------------------
import os, requests, urllib.parse, time, re, urllib3
from supabase import create_client, Client
from bs4 import BeautifulSoup
from datetime import datetime, timezone

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def run_scra_officer():
    # 資安守則：嚴格從環境變數讀取金鑰
    sb_url = os.environ.get("SUPABASE_URL")
    sb_key = os.environ.get("SUPABASE_KEY")
    scra_key = os.environ.get("SCRAP_API_KEY")
    
    if not all([sb_url, sb_key, scra_key]):
        print("❌ [資安警報] 缺少必要環境變數，終止行動。")
        return

    supabase: Client = create_client(sb_url, sb_key)

    # 🚀 極限節流：每次僅提取 1 筆待處理任務，確保剩餘 145 點能支撐最後 5 次核心測試
    missions = supabase.table("mission_queue").select("*").eq("scrape_status", "pending").limit(1).execute()
    
    if not missions.data: 
        print(f"☕ [{datetime.now().strftime('%H:%M:%S')}] 待命：目前無待處理任務。")
        return

    for target in missions.data:
        task_id = target['id']
        raw_title = target['episode_title']
        podbay_slug = target.get('podbay_slug') or "bloomberg-businessweek"
        final_mp3_url = ""

        print(f"🎯 [精準狙擊] 目標集數：{raw_title[:30]}...")

        try:
            # 戰場一：Podbay 輕量偵察 (不渲染，省點數)
            program_home = f"https://podbay.fm/p/{podbay_slug}"
            home_url = f"https://api.scraperapi.com?api_key={scra_key}&url={urllib.parse.quote(program_home)}"
            resp = requests.get(home_url, timeout=30, verify=False)
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            ep_tag = soup.find('a', href=re.compile(r'/p/.+/e/.*'))
            if ep_tag:
                full_ep_url = f"https://podbay.fm{ep_tag['href']}"
                
                # 戰場二：深度解碼 (開啟渲染，預計消耗約 22 點)
                ep_encoded = urllib.parse.quote(full_ep_url)
                print(f"🔍 [執行渲染] 正在提取 MP3 直連門票...")
                ep_res = requests.get(f"https://api.scraperapi.com?api_key={scra_key}&url={ep_encoded}&render=true", timeout=60)
                ep_soup = BeautifulSoup(ep_res.text, 'html.parser')
                
                # 廣域掃描音訊標籤
                audio_meta = ep_soup.find('meta', property=re.compile(r'(og:audio|twitter:player:stream)'))
                if audio_meta:
                    final_mp3_url = audio_meta.get('content')
                else:
                    mp3_link = ep_soup.find('a', href=re.compile(r'\.mp3'))
                    if mp3_link: final_mp3_url = mp3_link['href']
        except Exception as e:
            print(f"⚠️ [偵察異常]：{str(e)}")

        # --- 最終結算 ---
        if final_mp3_url:
            # 💡 加固：同時更新 audio_url 與 podbay_url，徹底解決運輸兵抓不到資料的問題
            update_data = {
                "podbay_url": final_mp3_url,
                "audio_url": final_mp3_url,
                "scrape_status": "success",
                "status": "pending", 
                "created_at": datetime.now(timezone.utc).isoformat() 
            }
            supabase.table("mission_queue").update(update_data).eq("id", task_id).execute()
            print(f"✅ [入庫成功] 門票發放：{final_mp3_url[:60]}...")
        else:
            # 若失敗則標記，避免重複浪費點數
            supabase.table("mission_queue").update({
                "scrape_status": "failed",
                "status": "failed"
            }).eq("id", task_id).execute()
            print(f"❌ [任務失敗] 無法獲取 MP3 連結。")

if __name__ == "__main__":
    run_scra_officer()