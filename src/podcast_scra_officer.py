
#---------------------------------------------------------------
# 本程式碼：podcast_scra_officer.py v2.11 (渲染攻堅 + LN 備援版)
# 修正：強制 URL 編碼、兩段式渲染破防、安全欄位提取
#---------------------------------------------------------------

import os, requests, urllib.parse, time, re, urllib3
from supabase import create_client, Client
from bs4 import BeautifulSoup

# 🚀 屏蔽不必要的安全警報
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def run_scra_officer():
    sb_url = os.environ.get("SUPABASE_URL")
    sb_key = os.environ.get("SUPABASE_KEY")
    scra_key = os.environ.get("SCRAP_API_KEY")
    supabase: Client = create_client(sb_url, sb_key)

    # 1. 領取任務 (處理 pending 狀態的任務)
    missions = supabase.table("mission_queue").select("*").eq("scrape_status", "pending").limit(2).execute()
    if not missions.data: return

    for target in missions.data:
        task_id = target['id']
        raw_title = target['episode_title']
        # 💡 若有 Podbay Slug 或 Listen Notes ID，將優先使用
        podbay_slug = target.get('podbay_slug') or "bloomberg-businessweek"
        ln_id = target.get('listen_notes_id') or "bloomberg-businessweek-bloomberg-yn5Mm7jSGBe"
        final_mp3_url = ""

        print(f"\n📡 [開始攻堅] 目標標題：{raw_title[:30]}...")

        # --- 戰場一：Podbay 渲染提取 (消耗較低，優先測試) ---
        try:
            program_home = f"https://podbay.fm/p/{podbay_slug}"
            # 🚀 關鍵：將整個網址進行編碼，並開啟 render=true
            podbay_api_url = f"https://api.scraperapi.com?api_key={scra_key}&url={urllib.parse.quote(program_home)}&render=true"
            print(f"🎯 [Podbay 渲染中]...")
            resp = requests.get(podbay_api_url, timeout=60, verify=False)
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # 在渲染後的頁面中尋找集數連結
            ep_tag = soup.find('a', href=re.compile(r'/p/.+/e/.*'))
            if ep_tag:
                full_ep_url = f"https://podbay.fm{ep_tag['href']}"
                print(f"✅ [鎖定 Podbay 集數]：{full_ep_url}")
                
                # 再次渲染集數頁以提取 MP3
                encoded_ep = urllib.parse.quote(full_ep_url)
                ep_res = requests.get(f"https://api.scraperapi.com?api_key={scra_key}&url={encoded_ep}&render=true", timeout=60)
                ep_soup = BeautifulSoup(ep_res.text, 'html.parser')
                audio_tag = ep_soup.find('meta', property="og:audio")
                if audio_tag: final_mp3_url = audio_tag.get('content')
        except Exception as e:
            print(f"⚠️ Podbay 故障：{str(e)[:50]}")

        # --- 戰場二：Listen Notes 備援 (若 Podbay 沒抓到，執行高階破防) ---
        if not final_mp3_url:
            print(f"🔄 [轉向備援] 嘗試從 Listen Notes 提取...")
            try:
                # 🎯 使用您提供的 Podcast ID 空降
                ln_url = f"https://www.listennotes.com/podcasts/{ln_id}/"
                encoded_ln = urllib.parse.quote(ln_url)
                # 🚀 Listen Notes 對 JS 依賴極重，必須開啟 render=true
                ln_api_url = f"https://api.scraperapi.com?api_key={scra_key}&url={encoded_ln}&render=true"
                ln_resp = requests.get(ln_api_url, timeout=60, verify=False)
                ln_soup = BeautifulSoup(ln_resp.text, 'html.parser')
                
                # 在渲染後尋找最新的音軌
                audio_tag = ln_soup.find('meta', property="og:audio")
                if audio_tag: 
                    final_mp3_url = audio_tag.get('content')
                    print(f"🎯 [LN 定位成功]")
            except Exception as e:
                print(f"⚠️ Listen Notes 故障：{str(e)[:50]}")

        # --- 回填結果 ---
        if final_mp3_url:
            supabase.table("mission_queue").update({"podbay_url": final_mp3_url, "scrape_status": "success"}).eq("id", task_id).execute()
            print(f"✅ [成功入庫] 門票：{final_mp3_url[:40]}...")
        else:
            supabase.table("mission_queue").update({"scrape_status": "failed"}).eq("id", task_id).execute()
        
        time.sleep(5) # 延長冷卻

if __name__ == "__main__":
    run_scra_officer()