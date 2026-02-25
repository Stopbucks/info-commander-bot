
# ---------------------------------------------------------#  
# 本程式碼：src/pod_scra_officer.py v8.1 (全域攻堅版)
# 任務：ScrapingAnt 渲染、全域正則掃描、<a>標籤解析、偵察員履歷蓋章
# ---------------------------------------------------------
import os, requests, time, re, json, random
from datetime import datetime, timezone
from supabase import create_client, Client
from bs4 import BeautifulSoup
from pod_scra_scanner import fetch_html 

FORCE_PROVIDER = "SCRAPINGANT" 

def get_secret(key, default=None):
    vault_path = "/etc/secrets/render_secret_vault.json"
    if os.path.exists(vault_path):
        with open(vault_path, 'r') as f:
            vault = json.load(f); return vault.get("active_credentials", {}).get(key, default)
    return os.environ.get(key, default)

def run_scra_officer():
    SCRAPER_PERSONAS = [
        {"label": "Win11_Chrome_Ant", "key": get_secret("SCRAPINGANT_API_KEY"), "headers": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36", "Sec-Ch-Ua-Platform": '"Windows"', "Connection": "keep-alive"}}
    ]
    
    sb = create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))
    print(f"🚀 [全域掃描啟動] 模式: {FORCE_PROVIDER} | JS 渲染模式")

    # === 🚧 戰術注意區：調整任務領取配額 (limit) ===
    new_m = (sb.table("mission_queue").select("*").eq("scrape_status", "pending")
             .order("created_at", desc=True)
             .limit(2)    # 👈 [修改此處：新任務筆數]
             .execute())

    old_m = (sb.table("mission_queue").select("*").eq("scrape_status", "pending")
             .order("created_at", desc=False)
             .limit(0)    # 👈 [修改此處：舊任務筆數]
             .execute())
    # =============================================
    
    all_missions = new_m.data + old_m.data
    total_count = len(all_missions)

    for idx, mission in enumerate(all_missions):
        task_id, podbay_slug, history = mission['id'], str(mission.get('podbay_slug') or "").strip(), str(mission.get('recon_persona') or "")
        current_count, now_iso = (mission.get('scrape_count') or 0) + 1, datetime.now(timezone.utc).isoformat()
        recon_success, final_resp, active_persona_label = False, None, "N/A"

        for persona in SCRAPER_PERSONAS:
            if not persona["key"] or (persona["label"] in history): continue
            active_persona_label = persona["label"]
            print(f"📡 [偵察 {idx+1}/{total_count}] 正在對位 {podbay_slug} (使用:{active_persona_label})...")
            
            try:
                resp = fetch_html(FORCE_PROVIDER, f"https://podbay.fm/p/{podbay_slug}", {FORCE_PROVIDER: [persona["key"]]})
                final_resp = resp
                if resp and resp.status_code == 200: recon_success = True; break
            except Exception as e:
                print(f"💥 異常: {e}"); break

        # --- 🚀 [地毯掃描解析器] ---
        final_url = None
        if recon_success:
            content = final_resp.text
            soup = BeautifulSoup(content, 'html.parser')
            # 1. 搜尋指揮官帶回的 <a> 標籤特徵 (Download + 特定域名)
            for a in soup.find_all('a', href=True):
                href, txt = a['href'], a.get_text().upper()
                if ('DOWNLOAD' in txt or 'MP3' in txt) and any(k in href.lower() for k in ['podtrac', 'megaphone', 'pdst', 'pscrb', 'akamaized']):
                    final_url = href; break
            # 2. 備援：Meta 標籤
            if not final_url:
                meta = soup.find('meta', property=re.compile(r'(og:audio|twitter:player:stream)'))
                final_url = meta.get('content') if meta else None
            # 3. 備援：全域正則掃描 (抓取 JS 殘留的長網址)
            if not final_url:
                patterns = [r'https?://[^\s"\'\>]+megaphone\.fm[^\s"\'\>]+\.mp3[^\s"\'\>]*', r'https?://[^\s"\'\>]+podtrac\.com[^\s"\'\>]+\.mp3[^\s"\'\>]*', r'https?://[^\s"\'\>]+akamaized\.net[^\s"\'\>]+\.mp3[^\s"\'\>]*']
                for p in patterns:
                    matches = re.findall(p, content)
                    if matches: final_url = matches[0]; break

        # --- 蓋章歸檔 ---
        new_stamp = active_persona_label if active_persona_label != "N/A" else "RECON_FAIL"
        updated_history = history + (" | " if history else "") + new_stamp
        if recon_success and final_url:
            sb.table("mission_queue").update({"audio_url": final_url, "scrape_status": "success", "used_provider": f"{FORCE_PROVIDER}_{new_stamp}", "recon_persona": updated_history, "last_scraped_at": now_iso, "scrape_count": current_count}).eq("id", task_id).execute()
            print(f"✅ [大捷] 成功捕獲網址！")
        else:
            sb.table("mission_queue").update({"recon_persona": updated_history, "last_scraped_at": now_iso, "scrape_count": current_count}).eq("id", task_id).execute()
            print(f"🔎 [蓋章] 偵察完成但無網址。")

        if idx < total_count - 1: time.sleep(random.randint(60, 120))

if __name__ == "__main__":
    run_scra_officer()