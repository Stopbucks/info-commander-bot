# ---------------------------------------------------------
# 本程式碼：src/pod_scra_officer.py v7.8 (完全擬態版)
# 任務：5筆壓力測試、Windows 聯軍擬態、自動換裝、雙重節律控時
# ---------------------------------------------------------
import os, requests, time, re, json, random
from datetime import datetime, timezone
from supabase import create_client, Client
from bs4 import BeautifulSoup
from pod_scra_scanner import fetch_html 

# === 🛠️ 偵察控制面板 ===
SCAN_LIMIT = 5                 # 5 筆壓力測試模式
FORCE_PROVIDER =  "SCRAPINGANT"   #其他模式有："SCRAPERAPI"、...待補
# =========================

def get_secret(key, default=None):
    vault_path = "/etc/secrets/render_secret_vault.json"
    if os.path.exists(vault_path):
        with open(vault_path, 'r') as f:
            vault = json.load(f); return vault.get("active_credentials", {}).get(key, default)
    return os.environ.get(key, default)

def run_scra_officer():
    # 🚀 擬態裝備庫：Windows 聯軍 (Chrome + Edge)
    # 這裡的標頭已經過「一致性」校驗，包含 Sec-Ch-Ua 等新型指紋標籤
    SCRAPER_PERSONAS = [
        {
            "label": "Win11_Chrome_Standard",
            "key": get_secret("SCRAP_API_KEY"),
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Sec-Ch-Ua": '"Not A(Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
                "Sec-Ch-Ua-Platform": '"Windows"',
                "Connection": "keep-alive"
            }
        },
        {
            "label": "Win10_Edge_Workstation",
            "key": get_secret("SCRAP_API_KEY_V2"),
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.3800.70",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-GB,en;q=0.9",
                "Sec-Ch-Ua": '"Not A(Brand";v="99", "Microsoft Edge";v="145", "Chromium";v="145"',
                "Sec-Ch-Ua-Platform": '"Windows"',
                "Connection": "keep-alive"
            }
        }
    ]
    
    sb = create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))
    print(f"🚀 [解碼官出擊] 模式: {FORCE_PROVIDER} | 執行 5 筆序列化滲透...")

    # 🎯 任務領取：對位 SCAN_LIMIT
    new_m = sb.table("mission_queue").select("*").eq("scrape_status", "pending").order("created_at", desc=True).limit(3).execute()
    old_m = sb.table("mission_queue").select("*").eq("scrape_status", "pending").order("created_at", desc=False).limit(2).execute()
    
    all_missions = new_m.data + old_m.data
    total_count = len(all_missions)

    for idx, mission in enumerate(all_missions):
        task_id = mission['id']
        podbay_slug = str(mission.get('podbay_slug') or "").strip()
        current_count = (mission.get('scrape_count') or 0) + 1
        now_iso = datetime.now(timezone.utc).isoformat()
        
        recon_success = False
        final_resp = None
        active_persona_label = "N/A"

        # 🔄 身份換裝循環 (Waterfall Failover)
        for persona in SCRAPER_PERSONAS:
            if not persona["key"]: continue
            active_persona_label = persona["label"]
            
            print(f"📡 [偵察 {idx+1}/{total_count}] 使用裝備: {active_persona_label} 對位 {podbay_slug}...")
            
            # 將單一金鑰封裝，維持 scanner 的介面相容
            current_all_keys = {"SCRAPERAPI": [persona["key"]]}
            
            try:
                # 🚀 執行發射
                resp = fetch_html(FORCE_PROVIDER, f"https://podbay.fm/p/{podbay_slug}", current_all_keys)
                final_resp = resp

                if resp and resp.status_code == 200:
                    recon_success = True
                    break 
                
                elif resp and resp.status_code in [403, 429]:
                    # ⚠️ 子彈耗盡，進入 5~10 分鐘擬態冷卻
                    wait_sec = random.randint(300, 600)
                    print(f"🛑 [點數枯竭] 裝備 {active_persona_label} 受阻 (403/429)。")
                    print(f"🕒 執行擬態避震，休眠 {wait_sec//60} 分鐘後換裝...")
                    time.sleep(wait_sec)
                    continue 
                else:
                    break 
            except Exception as e:
                print(f"💥 裝備 {active_persona_label} 異常: {e}")
                break

        # --- 數據歸檔 (寫入 recon_persona 欄位) ---
        if recon_success:
            soup = BeautifulSoup(final_resp.text, 'html.parser')
            audio_meta = soup.find('meta', property=re.compile(r'(og:audio|twitter:player:stream)'))
            final_url = audio_meta.get('content') if audio_meta else None
            
            status = "success" if final_url else "manual_check"
            sb.table("mission_queue").update({
                "audio_url": final_url, 
                "scrape_status": status, 
                "used_provider": f"SCRAPER_{active_persona_label}",
                "recon_persona": active_persona_label, 
                "last_scraped_at": now_iso, 
                "scrape_count": current_count
            }).eq("id", task_id).execute()
            print(f"{'✅' if final_url else '🔎'} [完成] {podbay_slug} (使用:{active_persona_label})")
        else:
            status_code = final_resp.status_code if final_resp else 'N/A'
            sb.table("mission_queue").update({
                "last_scraped_at": now_iso, "scrape_count": current_count,
                "used_provider": f"SCRAPER_ALL_FAIL_{status_code}",
                "recon_persona": "ALL_FAILED"
            }).eq("id", task_id).execute()
            print(f"⚠️ [任務受阻] 狀態碼: {status_code}")

        # --- [序列化戰術間歇] ---
        if idx < total_count - 1:
            task_gap = random.randint(60, 180) 
            print(f"⏳ [節奏控制] 休眠 {task_gap} 秒後處理下一筆任務...")
            time.sleep(task_gap)

if __name__ == "__main__":
    run_scra_officer()

# ---------------------------------------------------------
# 📦 裝備庫存區 (備援使用)
# ---------------------------------------------------------
# {
#     "label": "V1_Apple_Safari_Legacy",
#     "key": get_secret("SCRAP_API_KEY"),
#     "headers": {
#         "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
#         "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
#         "Accept-Language": "en-US,en;q=0.9",
#         "Connection": "keep-alive"
#     }
# }
# ---------------------------------------------------------