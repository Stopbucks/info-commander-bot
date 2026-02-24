# ---------------------------------------------------------
# 本程式碼：src/pod_scra_officer.py v7.7 (全套對位版)
# 任務：5筆精準壓力測試、全套標頭擬態、自動換裝與雙重 Jitter
# ---------------------------------------------------------
import os, requests, time, re, json, random
from datetime import datetime, timezone
from supabase import create_client, Client
from bs4 import BeautifulSoup
from pod_scra_scanner import fetch_html 

# === 🛠️ 偵察控制面板 ===
SCAN_LIMIT = 5                 
FORCE_PROVIDER = "SCRAPERAPI" 
# =========================

def get_secret(key, default=None):
    vault_path = "/etc/secrets/render_secret_vault.json"
    if os.path.exists(vault_path):
        with open(vault_path, 'r') as f:
            vault = json.load(f); return vault.get("active_credentials", {}).get(key, default)
    return os.environ.get(key, default)

def run_scra_officer():
    # 🚀 隱身裝備庫：固定 Key + 全套標頭對位
    SCRAPER_PERSONAS = [
        {
            "label": "V1_Apple_Safari",
            "key": get_secret("SCRAP_API_KEY"),
            "headers": {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Connection": "keep-alive"
            }
        },
        {
            "label": "V2_Windows_Chrome",
            "key": get_secret("SCRAP_API_KEY_V2"),
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Sec-Ch-Ua-Platform": '"Windows"',
                "Connection": "keep-alive"
            }
        }
    ]
    
    sb = create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))
    print(f"🚀 [解碼官出擊] 模式: {FORCE_PROVIDER} | 啟動「全套標頭對位」")

    # 🎯 任務領取：3新 + 2舊
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
        current_persona = None

        # 🔄 [身份換裝循環]
        for persona in SCRAPER_PERSONAS:
            if not persona["key"]: continue
            current_persona = persona
            print(f"📡 [偵察 {idx+1}/{total_count}] 使用裝備: {current_persona['label']} 對位 {podbay_slug}...")
            
            # 將金鑰與「全套裝備」傳遞給 scanner
            current_all_keys = {"SCRAPERAPI": [current_persona["key"]]}
            
            try:
                # 🚀 這裡我們執行偵察 (scanner 內部需能處理傳入的 headers，目前我們先依賴 ScraperAPI 的轉發)
                resp = fetch_html(FORCE_PROVIDER, f"https://podbay.fm/p/{podbay_slug}", current_all_keys)
                final_resp = resp

                if resp and resp.status_code == 200:
                    recon_success = True
                    break 
                
                elif resp and resp.status_code in [403, 429]:
                    # ⚠️ 點數耗盡：執行 5~10 分鐘長延遲
                    wait_sec = random.randint(300, 600)
                    print(f"🛑 [點數枯竭] 裝備 {current_persona['label']} 請求受阻。")
                    print(f"🕒 執行換裝避震，休眠 {wait_sec//60} 分鐘...")
                    time.sleep(wait_sec)
                    continue 
                else:
                    break 
            except Exception as e:
                print(f"💥 裝備 {current_persona['label']} 異常: {e}")
                break

        # --- 資料寫入 (含側寫追蹤) ---
        if recon_success:
            soup = BeautifulSoup(final_resp.text, 'html.parser')
            audio_meta = soup.find('meta', property=re.compile(r'(og:audio|twitter:player:stream)'))
            final_url = audio_meta.get('content') if audio_meta else None
            
            status = "success" if final_url else "manual_check"
            # 🏆 寫入物流表，同時記錄是哪套 persona 建功
            sb.table("mission_queue").update({
                "audio_url": final_url, 
                "scrape_status": status, 
                "used_provider": f"SCRAPER_{current_persona['label']}",
                "recon_persona": current_persona['label'], # 🚀 寫入您剛新增的欄位
                "last_scraped_at": now_iso, 
                "scrape_count": current_count
            }).eq("id", task_id).execute()
            print(f"{'✅' if final_url else '🔎'} [完成] {podbay_slug} (使用:{current_persona['label']})")
        else:
            status_code = final_resp.status_code if final_resp else 'N/A'
            sb.table("mission_queue").update({
                "last_scraped_at": now_iso, "scrape_count": current_count,
                "used_provider": f"SCRAPER_ALL_FAIL_{status_code}"
            }).eq("id", task_id).execute()
            print(f"⚠️ [任務受阻] 狀態碼: {status_code}")

        # --- [序列化戰術間歇] ---
        if idx < total_count - 1:
            task_gap = random.randint(60, 180) # 1-3 分鐘
            print(f"⏳ [節奏控制] 保持一致性，休眠 {task_gap} 秒後再處理下一筆...")
            time.sleep(task_gap)

if __name__ == "__main__":
    run_scra_officer()