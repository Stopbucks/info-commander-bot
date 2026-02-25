
# ---------------------------------------------------------
# 本程式碼：src/pod_scra_officer.py v8.3 (情報密碼版)
# 任務：1-5 兵種切換、地毯式音檔+RSS雙掃瞄、不重複履歷蓋章
# ---------------------------------------------------------
import os, requests, time, re, json, random
from datetime import datetime, timezone
from supabase import create_client, Client
from bs4 import BeautifulSoup
from pod_scra_scanner import fetch_html 

# === 🛠️ 偵察控制面板 (策略中樞) ===
# 1=SCRAPERAPI, 2=WEBSCRAPING, 3=SCRAPEDO, 4=HASDATA, 5=SCRAPINGANT
ACTIVE_STRATEGY = 1  # 🚀 [明日測試：1，今日演習：5]

STRATEGY_MAP = {
    1: {"provider": "SCRAPERAPI", "label": "Win11_Chrome_Premium", "key_name": "SCRAP_API_KEY_V2"},
    2: {"provider": "WEBSCRAPING", "label": "WebScraping_AI_JS", "key_name": "WEBSCRAP_API_KEY"},
    3: {"provider": "SCRAPEDO", "label": "ScrapeDo_Render_Ops", "key_name": "SCRAPEDO_API_KEY"},
    4: {"provider": "HASDATA", "label": "HasData_Residential", "key_name": "HASDATA_API_KEY"},
    5: {"provider": "SCRAPINGANT", "label": "Win11_Chrome_Ant", "key_name": "SCRAPINGANT_API_KEY"}
}
# =========================

def get_secret(key, default=None):
    vault_path = "/etc/secrets/render_secret_vault.json"
    if os.path.exists(vault_path):
        with open(vault_path, 'r') as f:
            vault = json.load(f); return vault.get("active_credentials", {}).get(key, default)
    return os.environ.get(key, default)

def run_scra_officer():
    conf = STRATEGY_MAP.get(ACTIVE_STRATEGY)
    provider, persona_label, api_key = conf["provider"], conf["label"], get_secret(conf["key_name"])
    
    sb = create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))
    print(f"🚀 [行動啟動] 策略: {ACTIVE_STRATEGY} | 兵種: {persona_label}")

    # === 🚧 戰術注意區：調整任務領取配額 ===
    # 硬編碼區  (小螢幕括號法)
    # ---------------------------------------
    new_m = (sb.table("mission_queue").select("*").eq("scrape_status", "pending")
             .order("created_at", desc=True)
             .limit(1)    # 👈 [新任務配額]
             .execute())

    old_m = (sb.table("mission_queue").select("*").eq("scrape_status", "pending")
             .order("created_at", desc=False)
             .limit(1)    # 👈 [舊任務配額]
             .execute())
    # ===================================================
    
    all_missions = new_m.data + old_m.data
    for idx, mission in enumerate(all_missions):
        task_id, podbay_slug, history = mission['id'], str(mission.get('podbay_slug') or "").strip(), str(mission.get('recon_persona') or "")
        current_count, now_iso = (mission.get('scrape_count') or 0) + 1, datetime.now(timezone.utc).isoformat()
        
        # 🛡️ 履歷章制度：跳過已失敗兵種
        if persona_label in history:
            print(f"⏭️ [跳過] {persona_label} 曾偵察過 {podbay_slug}"); continue

        print(f"📡 [偵察 {idx+1}/{len(all_missions)}] 攻堅 {podbay_slug}...")
        
        try:
            resp = fetch_html(provider, f"https://podbay.fm/p/{podbay_slug}", {provider: api_key})
            if resp and resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                final_audio_url, final_rss_url = None, None

                # 🚀 1. [地毯搜索：音檔連結]
                # A. <a> 標籤特徵定位 (您的偵察發現)
                for a in soup.find_all('a', href=True):
                    href, txt = a['href'].lower(), a.get_text().upper()
                    if ('DOWNLOAD' in txt or 'MP3' in txt) and any(k in href for k in ['podtrac', 'megaphone', 'pdst', 'pscrb', 'akamaized']):
                        final_audio_url = a['href']; break
                
                # B. 備援：Meta 標籤
                if not final_audio_url:
                    meta = soup.find('meta', property=re.compile(r'(og:audio|twitter:player:stream)'))
                    final_audio_url = meta.get('content') if meta else None

                # C. 備援：全域 Regex 音檔掃描
                if not final_audio_url:
                    m_patterns = [r'https?://[^\s"\'\>]+megaphone\.fm[^\s"\'\>]+\.mp3[^\s"\'\>]*', r'https?://[^\s"\'\>]+podtrac\.com[^\s"\'\>]+\.mp3[^\s"\'\>]*']
                    for p in m_patterns:
                        matches = re.findall(p, resp.text)
                        if matches: final_audio_url = matches[0]; break

                # 🚀 2. [地毯搜索：RSS FEED 連結] —— 指揮官強烈建議
                # A. 找 <link> 標籤
                rss_tag = soup.find('link', type='application/rss+xml', href=True)
                if rss_tag: final_rss_url = rss_tag['href']
                
                # B. 找 <a> 標籤文字包含 RSS
                if not final_rss_url:
                    for a in soup.find_all('a', href=True):
                        if 'RSS' in a.get_text().upper():
                            final_rss_url = a['href']; break
                
                # C. 備援：Regex RSS 掃描
                if not final_rss_url:
                    r_matches = re.findall(r'https?://[^\s"\'\>]+/(?:rss|feed|xml)[^\s"\'\>]*', resp.text)
                    if r_matches: final_rss_url = r_matches[0]

                # --- 數據歸檔 (更新履歷章) ---
                updated_history = history + (" | " if history else "") + persona_label
                update_data = {"recon_persona": updated_history, "last_scraped_at": now_iso, "scrape_count": current_count}
                
                if final_audio_url:
                    update_data.update({"audio_url": final_audio_url, "scrape_status": "success", "used_provider": f"{provider}_{persona_label}"})
                    if final_rss_url: update_data["podbay_url"] = final_rss_url # 將 RSS 存在 podbay_url 備查
                    print(f"✅ [大捷] 音檔捕獲成功！" + (f" (附帶 RSS: {final_rss_url})" if final_rss_url else ""))
                else:
                    sb.table("mission_queue").update(update_data).eq("id", task_id).execute()
                    print(f"🔎 [蓋章] 偵察完成但無音檔。")
            else:
                print(f"⚠️ [連線受阻] 狀態碼: {resp.status_code if resp else 'N/A'}")
        except Exception as e:
            print(f"💥 異常: {e}")

        if idx < total_count - 1: time.sleep(random.randint(60, 120))

if __name__ == "__main__":
    run_scra_officer()