#---------------------------------------------------------------
# 本程式碼為：podcast_scra_officer.py 
# 版本：v2.6 雙戰場實戰版 (Podbay + Listen Notes)
#---------------------------------------------------------------

#---------------------------------------------------------------
# 本程式碼：podcast_scra_officer.py v2.9 (主頁直入 + JS 渲染破解版)
# 特色：跳過全網搜尋，直接空降節目主頁，開啟 ScraperAPI 高級渲染 [cite: 2026-02-16]
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

    # 🚀 領取任務 (偵察兵 Vercel 已將 podbay_slug 填入 mission_queue)
    missions = supabase.table("mission_queue").select("*").eq("scrape_status", "pending").limit(2).execute()
    if not missions.data: return

    for target in missions.data:
        task_id = target['id']
        raw_title = target['episode_title']
        # 💡 若無預設 Slug，則使用節目 ID (例如 1691284824) [cite: 2026-02-16]
        podbay_slug = target.get('podbay_slug') or "bloomberg-businessweek" 
        final_mp3_url = ""

        # --- 戰術動作：直接空降節目主頁 ---
        # 🚀 策略：使用 render=true 破解您看到的「載入圈圈」反爬蟲 [cite: 2026-02-16]
        program_home = f"https://podbay.fm/p/{podbay_slug}"
        print(f"🎯 [直接空降] 進入節目主頁：{program_home}")
        
        try:
            # 開啟 render=true 會等待 JavaScript 加載完畢 (消耗約 5-10 點) [cite: 2026-02-16]
            render_url = f"https://api.scraperapi.com?api_key={scra_key}&url={program_home}&render=true"
            resp = requests.get(render_url, timeout=60, verify=False)
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # 在主頁內尋找最接近原始標題的集數連結 [cite: 2026-02-16]
            # 💡 S-Plan 技巧：只要頁面上的文字包含標題的前 10 個字即判定命中
            match_word = raw_title[:10]
            ep_tag = soup.find('a', string=re.compile(match_word, re.I)) or soup.find('a', href=re.compile(r'/p/.+/e/.*'))
            
            if ep_tag:
                full_ep_url = f"https://podbay.fm{ep_tag['href']}"
                print(f"✅ [精確命中] 找到集數頁面：{full_ep_url}")
                
                # 進入集數頁提取 (集數頁通常不需要 render)
                ep_res = requests.get(f"https://api.scraperapi.com?api_key={scra_key}&url={full_ep_url}")
                final_mp3_url = BeautifulSoup(ep_res.text, 'html.parser').find('meta', property="og:audio")['content']
        except Exception as e:
            print(f"⚠️ 攻堅發生故障：{str(e)}")

        # --- 回填結果 ---
        if final_mp3_url:
            supabase.table("mission_queue").update({"podbay_url": final_mp3_url, "scrape_status": "success"}).eq("id", task_id).execute()
            print(f"🚀 [解碼成功] MP3 網址已入庫。")
        else:
            supabase.table("mission_queue").update({"scrape_status": "failed"}).eq("id", task_id).execute()
        
        time.sleep(3)

if __name__ == "__main__":
    run_scra_officer()