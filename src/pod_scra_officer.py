# ---------------------------------------------------------
# 本程式碼：src/pod_scra_officer.py v7.9 (渲染演習版)
# 任務：5筆壓力測試、ScrapingAnt 渲染攻堅、Windows 聯軍擬態、自動換裝
# ---------------------------------------------------------# ---------------------------------------------------------
# 本程式碼：src/pod_scra_officer.py v8.0 (地毯掃描+履歷蓋章版)
# 任務：ScrapingAnt 攻堅、<a>標籤解析、不重複浪費、失敗蓋章紀錄
# ---------------------------------------------------------
import os, requests, time, re, json, random
from datetime import datetime, timezone
from supabase import create_client, Client
from bs4 import BeautifulSoup
from pod_scra_scanner import fetch_html 

# === 🛠️ 偵察控制面板 ===
SCAN_LIMIT = 1                 # 🚀 提醒：此變數目前僅供參考
FORCE_PROVIDER = "SCRAPINGANT" 
# =========================

def get_secret(key, default=None):
    vault_path = "/etc/secrets/render_secret_vault.json"
    if os.path.exists(vault_path):
        with open(vault_path, 'r') as f:
            vault = json.load(f); return vault.get("active_credentials", {}).get(key, default)
    return os.environ.get(key, default)

def run_scra_officer():
    # 🚀 裝備清單：確保金鑰名稱與 YAML/Secrets 100% 對位
    SCRAPER_PERSONAS = [
        {
            "label": "Win11_Chrome_Ant",
            "key": get_secret("SCRAPINGANT_API_KEY"),
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
                "Sec-Ch-Ua-Platform": '"Windows"',
                "Connection": "keep-alive"
            }
        }
    ]
    
    sb = create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))
    print(f"🚀 [地毯攻堅] 模式: {FORCE_PROVIDER} | 目標：突破 50%-70% 頑強份子")

 # === 🚧 戰術硬編碼注意區 (過渡時期手動調整處) ===
    # 這裡採用「括號換行法」，讓數字 (limit) 靠左對齊，方便修改
    
    # 🚀 任務 A：領取最新掛載的任務
    new_m = (
        sb.table("mission_queue")
        .select("*")
        .eq("scrape_status", "pending")
        .order("created_at", desc=True)
        .limit(1)    # 👈 [修改此數字] 控制新任務筆數
        .execute()
    )

    # 🚀 任務 B：領取積壓已久的舊任務
    old_m = (
        sb.table("mission_queue")
        .select("*")
        .eq("scrape_status", "pending")
        .order("created_at", desc=False)
        .limit(0)    # 👈 [修改此數字] 控制舊任務筆數
        .execute()
    )
    # =============================================
    
    all_missions = new_m.data + old_m.data
    total_count = len(all_missions)

    for idx, mission in enumerate(all_missions):
        task_id = mission['id']
        podbay_slug = str(mission.get('podbay_slug') or "").strip()
        current_count = (mission.get('scrape_count') or 0) + 1
        history = str(mission.get('recon_persona') or "") # 讀取蓋章紀錄
        now_iso = datetime.now(timezone.utc).isoformat()
        
        recon_success = False
        final_resp = None
        active_persona = None

        for persona in SCRAPER_PERSONAS:
            if not persona["key"]: continue
            
            # 🛡️ 避震：如果歷史記錄中已有此偵察兵，則跳過避免浪費點數
            if persona["label"] in history:
                print(f"⏭️ [跳過] {persona['label']} 曾偵察過 {podbay_slug}，換人試試...")
                continue
            
            active_persona = persona
            print(f"📡 [偵察 {idx+1}/{total_count}] 使用裝備: {active_persona['label']} 攻堅 {podbay_slug}...")
            
            current_all_keys = {FORCE_PROVIDER: [active_persona["key"]]}
            
            try:
                resp = fetch_html(FORCE_PROVIDER, f"https://podbay.fm/p/{podbay_slug}", current_all_keys)
                final_resp = resp
                if resp and resp.status_code == 200:
                    recon_success = True; break 
                elif resp and resp.status_code in [403, 429]:
                    time.sleep(random.randint(60, 180)); continue 
                else: break 
            except Exception as e:
                print(f"💥 異常: {e}"); break

        # --- 🚀 解析器升級：地毯搜索法 ---
        final_url = None
        if recon_success:
            soup = BeautifulSoup(final_resp.text, 'html.parser')
            # A. 傳統 Meta
            meta = soup.find('meta', property=re.compile(r'(og:audio|twitter:player:stream)'))
            final_url = meta.get('content') if meta else None
            
            # B. [新增] <a> 標籤地毯搜索 (您的偵察發現)
            if not final_url:
                for a_tag in soup.find_all('a', href=True):
                    txt = a_tag.get_text().upper()
                    hrf = a_tag['href'].lower()
                    if ('DOWNLOAD' in txt or 'MP3' in txt) and ('.mp3' in hrf or '.m4a' in hrf or 'mediaselector' in hrf):
                        final_url = a_tag['href']; break

        # --- 數據歸檔 (更新履歷章) ---
        new_stamp = active_persona['label'] if active_persona else "FAILED_RECON"
        updated_history = history + (" | " if history else "") + new_stamp

        if recon_success and final_url:
            sb.table("mission_queue").update({
                "audio_url": final_url, "scrape_status": "success", 
                "used_provider": f"{FORCE_PROVIDER}_{new_stamp}",
                "recon_persona": updated_history, "last_scraped_at": now_iso, "scrape_count": current_count
            }).eq("id", task_id).execute()
            print(f"✅ [成功] {podbay_slug}")
        else:
            # 偵察失敗也蓋章紀錄，並保持待命狀態
            sb.table("mission_queue").update({
                "recon_persona": updated_history, "last_scraped_at": now_iso, "scrape_count": current_count
            }).eq("id", task_id).execute()
            print(f"🔎 [未獲取網址] {podbay_slug} 已蓋章紀錄歷史")

        if idx < total_count - 1:
            time.sleep(random.randint(30, 60))

if __name__ == "__main__":
    run_scra_officer()