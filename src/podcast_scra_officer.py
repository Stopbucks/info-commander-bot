#---------------------------------------------------------------
# 本程式碼為：podcast_scra_officer.py 
# 版本：v2.6 雙戰場實戰版 (Podbay + Listen Notes)
#---------------------------------------------------------------

import os, requests, urllib.parse, time, re, urllib3
from supabase import create_client, Client
from bs4 import BeautifulSoup

# 🚀 關閉安全警告，讓日誌更乾淨
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def clean_search_query(source_name, episode_title):
    # 戰術洗滌：合併節目名稱與前 5 個單字，提高精確度 [cite: 2026-02-16]
    source_clean = re.sub(r'\(.*?\)', '', source_name).strip()
    ep_words = episode_title.split()
    ep_clean = " ".join(ep_words[:5])
    return re.sub(r'[^\w\s]', ' ', f"{source_clean} {ep_clean}").strip()

def run_scra_officer():
    sb_url = os.environ.get("SUPABASE_URL")
    sb_key = os.environ.get("SUPABASE_KEY")
    scra_key = os.environ.get("SCRAP_API_KEY")

    if not all([sb_url, sb_key, scra_key]):
        print("❌ [憑證遺失]")
        return

    supabase: Client = create_client(sb_url, sb_key)
    proxy_url = f"http://scraperapi:{scra_key}@proxy-server.scraperapi.com:8001"
    proxies = {"http": proxy_url, "https": proxy_url}

    # 領取 3 筆待處理任務
    missions = supabase.table("mission_queue").select("*").eq("scrape_status", "pending").limit(3).execute()

    if not missions.data:
        print("☕ [庫存清空] 沒有 pending 任務。")
        return

    for target in missions.data:
        task_id = target['id']
        raw_title = target['episode_title']
        source_name = target.get('source_name', '')
        search_query = clean_search_query(source_name, raw_title)
        final_mp3_url = ""

        print(f"\n📡 [任務啟動] 節目：{source_name} | 關鍵字：{search_query}")

        # --- 戰場一：Podbay 攻堅 ---
        try:
            encoded_query = urllib.parse.quote(search_query)
            podbay_url = f"https://podbay.fm/search?q={encoded_query}"
            
            # 💡 已修正：使用 podbay_url 並將超時延至 60 秒 [cite: 2026-02-16]
            resp = requests.get(podbay_url, proxies=proxies, timeout=60, verify=False)
            soup = BeautifulSoup(resp.text, 'html.parser')
            ep_link_tag = soup.find('a', href=re.compile(r'/p/.+/e/.*'))
            
            if ep_link_tag:
                full_ep_url = f"https://podbay.fm{ep_link_tag['href']}"
                print(f"🎯 [Podbay 發現]：{full_ep_url}")
                ep_resp = requests.get(full_ep_url, proxies=proxies, timeout=30, verify=False)
                audio_tag = BeautifulSoup(ep_resp.text, 'html.parser').find('meta', property="og:audio")
                final_mp3_url = audio_tag['content'] if audio_tag else ""
        except Exception as e:
            print(f"⚠️ Podbay 故障：{str(e)[:50]}")

        # --- 戰場二：Listen Notes 備援 (若 Podbay 沒抓到) --- [cite: 2026-02-16]
        if not final_mp3_url:
            print(f"🔄 [啟動備援] 轉向 Listen Notes 攻堅...")
            try:
                ln_search = f"https://www.listennotes.com/search/?q={encoded_query}&scope=episode"
                resp = requests.get(ln_search, proxies=proxies, timeout=60, verify=False)
                soup = BeautifulSoup(resp.text, 'html.parser')
                # Listen Notes 的集數連結特徵 [cite: 2026-02-16]
                ln_link = soup.find('a', href=re.compile(r'/podcasts/.+/.+'))
                
                if ln_link:
                    ln_url = f"https://www.listennotes.com{ln_link['href']}"
                    print(f"🎯 [LN 定位成功]：{ln_url}")
                    ln_resp = requests.get(ln_url, proxies=proxies, timeout=30, verify=False)
                    audio_tag = BeautifulSoup(ln_resp.text, 'html.parser').find('meta', property="og:audio")
                    final_mp3_url = audio_tag['content'] if audio_tag else ""
            except Exception as e:
                print(f"⚠️ Listen Notes 故障：{str(e)[:50]}")

        # --- 回填結果 ---
        if final_mp3_url:
            supabase.table("mission_queue").update({
                "podbay_url": final_mp3_url,
                "scrape_status": "success"
            }).eq("id", task_id).execute()
            print(f"✅ [入庫成功] MP3 網址已帶回。")
        else:
            print(f"❌ [全面失守] Podbay 與 LN 均無法解碼：{search_query}")
            supabase.table("mission_queue").update({"scrape_status": "failed"}).eq("id", task_id).execute()

        time.sleep(3) # 戰術休息

if __name__ == "__main__":
    run_scra_officer()