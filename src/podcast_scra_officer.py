
#---------------------------------------------------------------
# 本程式碼：podcast_scra_officer.py v2.12 (高 CP 廣域提取版)
# 修正：取消主頁渲染(省點數)、廣域掃描 MP3 標籤、安全備援
#---------------------------------------------------------------

import os, requests, urllib.parse, time, re, urllib3
from supabase import create_client, Client
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def run_scra_officer():
    sb_url = os.environ.get("SUPABASE_URL")
    sb_key = os.environ.get("SUPABASE_KEY")
    scra_key = os.environ.get("SCRAP_API_KEY")
    supabase: Client = create_client(sb_url, sb_key)

    missions = supabase.table("mission_queue").select("*").eq("scrape_status", "pending").limit(2).execute()
    if not missions.data: return

    for target in missions.data:
        task_id = target['id']
        raw_title = target['episode_title']
        podbay_slug = target.get('podbay_slug') or "bloomberg-businessweek"
        final_mp3_url = ""

        # --- 戰場一：Podbay 輕量偵察 ---
        try:
            program_home = f"https://podbay.fm/p/{podbay_slug}"
            # 🚀 優化 1：主頁不使用 render=true，節省點數 [cite: 2026-02-16]
            home_url = f"https://api.scraperapi.com?api_key={scra_key}&url={urllib.parse.quote(program_home)}"
            resp = requests.get(home_url, timeout=30, verify=False)
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            ep_tag = soup.find('a', href=re.compile(r'/p/.+/e/.*'))
            if ep_tag:
                full_ep_url = f"https://podbay.fm{ep_tag['href']}"
                print(f"✅ [發現集數]：{full_ep_url}")
                
                # 🚀 優化 2：僅在集數頁使用渲染提取 MP3 [cite: 2026-02-16]
                ep_encoded = urllib.parse.quote(full_ep_url)
                ep_res = requests.get(f"https://api.scraperapi.com?api_key={scra_key}&url={ep_encoded}&render=true", timeout=60)
                ep_soup = BeautifulSoup(ep_res.text, 'html.parser')
                
                # 🚀 優化 3：廣域掃描多種音訊標籤 (og, twitter, or a-href) [cite: 2026-02-16]
                audio_meta = ep_soup.find('meta', property=re.compile(r'(og:audio|twitter:player:stream)'))
                if audio_meta:
                    final_mp3_url = audio_meta.get('content')
                else:
                    # 最後一搏：直接在 HTML 裡找任何包含 .mp3 的連結
                    mp3_link = ep_soup.find('a', href=re.compile(r'\.mp3'))
                    if mp3_link: final_mp3_url = mp3_link['href']
        except: pass

        # --- 最終結算 ---
        if final_mp3_url:
            supabase.table("mission_queue").update({"podbay_url": final_mp3_url, "scrape_status": "success"}).eq("id", task_id).execute()
            print(f"🚀 [大捷] 成功取得門票：{final_mp3_url[:40]}...")
        else:
            supabase.table("mission_queue").update({"scrape_status": "failed"}).eq("id", task_id).execute()
            print(f"❌ [失敗] 標題：{raw_title[:20]}")
        
        time.sleep(3)

if __name__ == "__main__":
    run_scra_officer()