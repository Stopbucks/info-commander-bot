# ---------------------------------------------------------
# 本程式碼：src/pod_scra_officer.py v8.6 (計時器過濾版)
# 任務：1-5 兵種切換、資料庫計時器驅動、極簡對位邏輯
# ---------------------------------------------------------
import os, requests, time, re, json, random
from datetime import datetime, timezone
from supabase import create_client, Client
from bs4 import BeautifulSoup
from pod_scra_scanner import fetch_html 

# === 🛠️ 偵察控制面板 ===
ACTIVE_STRATEGY = 5  # 👈 [1=Premium, 5=Ant]

STRATEGY_MAP = {
    1: {"provider": "SCRAPERAPI", "label": "Win11_Chrome_Premium", "key_name": "SCRAP_API_KEY_V2"},
    2: {"provider": "WEBSCRAPING", "label": "WebScraping_AI_JS", "key_name": "WEBSCRAP_API_KEY"},
    3: {"provider": "SCRAPEDO", "label": "ScrapeDo_Render_Ops", "key_name": "SCRAPEDO_API_KEY"},
    4: {"provider": "HASDATA", "label": "HasData_Residential", "key_name": "HASDATA_API_KEY"},
    5: {"provider": "SCRAPINGANT", "label": "Win11_Chrome_Ant", "key_name": "SCRAPINGANT_API_KEY"}
}

def get_secret(key, default=None):
    v_path = "/etc/secrets/render_secret_vault.json"
    if os.path.exists(v_path):
        with open(v_path, 'r') as f:
            v = json.load(f); return v.get("active_credentials", {}).get(key, default)
    return os.environ.get(key, default)

def run_scra_officer():
    conf = STRATEGY_MAP.get(ACTIVE_STRATEGY)
    provider, persona_label, api_key = conf["provider"], conf["label"], get_secret(conf["key_name"])
    sb = create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))
    
    # 🕒 獲取標準化 UTC 現在時間 (ISO 格式)
    now_iso = datetime.now(timezone.utc).isoformat()
    print(f"🚀 [自適性啟動] 策略: {ACTIVE_STRATEGY} | 兵種: {persona_label}")

    # === 🚧 戰術配額區 (小螢幕括號法) ===
    # 邏輯：只領取「已達部隊二接手日期 (troop2_start_at)」的 Pending 任務
    # -------------------------------------------------------
    new_m = (sb.table("mission_queue").select("*")
             .eq("scrape_status", "pending")
             .lte("troop2_start_at", now_iso) # 👈 [核心：現在時間 >= 預定日期]
             .order("created_at", desc=True)
             .limit(1).execute())

    old_m = (sb.table("mission_queue").select("*")
             .eq("scrape_status", "pending")
             .lte("troop2_start_at", now_iso) # 🚀 D = 1.5F + 2 公式已在資料庫層級生效
             .order("created_at", desc=False)
             .limit(1).execute())
    # ========================================================
    
    all_missions = new_m.data + old_m.data
    for idx, m in enumerate(all_missions):
        task_id, slug, history = m['id'], str(m.get('podbay_slug') or "").strip(), str(m.get('recon_persona') or "")
        
        # 🛡️ 履歷章制度：跳過失敗過的兵種
        if persona_label in history: continue

        print(f"📡 [偵察 {idx+1}/{len(all_missions)}] 攻堅 {slug}...")

        try:
            resp = fetch_html(provider, f"https://podbay.fm/p/{slug}", {provider: api_key})
            if resp and resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                f_audio, f_rss = None, None
                
                # 地毯式解析：音檔
                for a in soup.find_all('a', href=True):
                    hrf, txt = a['href'].lower(), a.get_text().upper()
                    if ('DOWNLOAD' in txt or 'MP3' in txt) and any(k in hrf for k in ['podtrac', 'megaphone', 'pdst', 'pscrb', 'akamaized']):
                        f_audio = a['href']; break
                
                # 地毯式解析：RSS (主表缺失時補位)
                rtag = soup.find('link', type='application/rss+xml', href=True)
                f_rss = rtag['href'] if rtag else None

                updated_history = history + (" | " if history else "") + persona_label
                upd = {"recon_persona": updated_history, "last_scraped_at": now_iso, "scrape_count": (m.get('scrape_count') or 0) + 1}
                
                if f_audio:
                    upd.update({"audio_url": f_audio, "scrape_status": "success", "used_provider": f"{provider}_{persona_label}"})
                    if f_rss: upd["podbay_url"] = f_rss
                    print(f"✅ [成功] 捕獲目標")
                else:
                    sb.table("mission_queue").update(upd).eq("id", task_id).execute()
                    print(f"🔎 [蓋章] 無標籤。")
        except Exception as e: print(f"💥 異常: {e}")

if __name__ == "__main__":
    run_scra_officer()


        # ---------------------------------------------------------
        # 🛡️ 補充：部隊 1 & 2 下載任務自適性緩衝計算 (Adaptive Buffer Logic)
        #    目前戰術判斷，由supabase 欄位第一時間偵查填入後，直接判斷。
        # D: 部隊二接手天數 (Transfer Threshold)
        # F: 節目更新頻率 (Frequency in Days)  公式設計：D = 1.5F + 2
        # ---------------------------------------------------------