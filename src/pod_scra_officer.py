
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
    sb_url = os.environ.get("SUPABASE_URL")
    sb_key = os.environ.get("SUPABASE_KEY")
    scra_key = os.environ.get("SCRAP_API_KEY")
    supabase: Client = create_client(sb_url, sb_key)

    # 🚀 彈藥管制：每次僅提取 2 筆待處理任務，嚴格控制 ScraperAPI 點數消耗
    missions = supabase.table("mission_queue").select("*").eq("scrape_status", "pending").limit(2).execute()
    if not missions.data: 
        print("☕ [待命] 暫無待處理任務。")
        return

    for target in missions.data:
        task_id = target['id']
        raw_title = target['episode_title']
        podbay_slug = target.get('podbay_slug') or "bloomberg-businessweek"
        final_mp3_url = ""

        print(f"📡 [偵察開始]：{raw_title[:20]}...")

        # --- 戰場一：Podbay 輕量偵察 ---
        try:
            program_home = f"https://podbay.fm/p/{podbay_slug}"
            # 🚀 節流優化：不開啟 render=true 僅消耗 1 點
            home_url = f"https://api.scraperapi.com?api_key={scra_key}&url={urllib.parse.quote(program_home)}"
            resp = requests.get(home_url, timeout=30, verify=False)
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # 尋找集數連結
            ep_tag = soup.find('a', href=re.compile(r'/p/.+/e/.*'))
            if ep_tag:
                full_ep_url = f"https://podbay.fm{ep_tag['href']}"
                
                # 🚀 精準打擊：僅在確定有集數頁時才使用渲染(消耗 5 點以上) [cite: 2026-02-16]
                ep_encoded = urllib.parse.quote(full_ep_url)
                ep_res = requests.get(f"https://api.scraperapi.com?api_key={scra_key}&url={ep_encoded}&render=true", timeout=60)
                ep_soup = BeautifulSoup(ep_res.text, 'html.parser')
                
                # 廣域掃描音訊標籤
                audio_meta = ep_soup.find('meta', property=re.compile(r'(og:audio|twitter:player:stream)'))
                if audio_meta:
                    final_mp3_url = audio_meta.get('content')
                else:
                    # 備援：搜尋 .mp3 連結
                    mp3_link = ep_soup.find('a', href=re.compile(r'\.mp3'))
                    if mp3_link: final_mp3_url = mp3_link['href']
        except Exception as e:
            print(f"⚠️ [解析異常]：{str(e)}")

        # --- 最終結算 (接力轉型) ---
        if final_mp3_url:
            # 🚀 修正重點：同時回填 podbay_url 與 audio_url，確保運輸兵不會抓空
            update_data = {
                "podbay_url": final_mp3_url,
                "audio_url": final_mp3_url, # 確保運輸兵抓取此欄位
                "scrape_status": "success",
                "status": "pending", 
                "created_at": datetime.now(timezone.utc).isoformat() 
            }
            supabase.table("mission_queue").update(update_data).eq("id", task_id).execute()
            print(f"✅ [成功入庫] 門票發放：{final_mp3_url[:50]}...")
        else:
            supabase.table("mission_queue").update({
                "scrape_status": "failed",
                "status": "failed"
            }).eq("id", task_id).execute()
            print(f"❌ [失敗] 無法取得連結。")

if __name__ == "__main__":
    run_scra_officer()