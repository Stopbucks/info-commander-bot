# ---------------------------------------------------------
# 本程式碼：src/pod_scra_officer.py v7.6 (節奏大師版)
# 任務：5筆精準掃描、ScraperAPI 自動失效切換、固定身份對位、序列化任務間歇
# ---------------------------------------------------------
import os, requests, time, re, json, random
from datetime import datetime, timezone
from supabase import create_client, Client
from bs4 import BeautifulSoup
from pod_scra_scanner import fetch_html 

# === 🛠️ 偵察控制面板 (最高指揮部) ===
SCAN_LIMIT = 5                 # 提高至 5 筆，進行壓力測試
FORCE_PROVIDER = "SCRAPERAPI"  # 鎖定測試模式
# =========================================

def get_secret(key, default=None):
    vault_path = "/etc/secrets/render_secret_vault.json"
    if os.path.exists(vault_path):
        with open(vault_path, 'r') as f:
            vault = json.load(f); return vault.get("active_credentials", {}).get(key, default)
    return os.environ.get(key, default)

def run_scra_officer():
    # 🚀 隱身套裝：固定 Key 與 User-Agent 的配對 (維持行為一致性)
    SCRAPER_PERSONAS = [
        {
            "label": "V1_Apple_Safari",
            "key": get_secret("SCRAP_API_KEY"),
            "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15"
        },
        {
            "label": "V2_Windows_Chrome",
            "key": get_secret("SCRAP_API_KEY_V2"),
            "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
    ]
    
    sb = create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))
    print(f"🚀 [解碼官出擊] 模式: {FORCE_PROVIDER} | 上限: {SCAN_LIMIT} | 啟動序列化節奏模式")

    # 🎯 任務領取：調整為 3新 + 2舊 = 5筆
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
        used_persona_label = "N/A"

        # 🔄 [身份換裝循環]：Key 1 戰死則換 Key 2
        for persona in SCRAPER_PERSONAS:
            if not persona["key"]: continue
            
            used_persona_label = persona["label"]
            print(f"📡 [偵察 {idx+1}/{total_count}] 使用身份: {used_persona_label} 嘗試對位 {podbay_slug}...")
            
            current_all_keys = {"SCRAPERAPI": [persona["key"]]}
            
            try:
                # 🚀 發起請求：傳入固定身份的裝備
                resp = fetch_html(FORCE_PROVIDER, f"https://podbay.fm/p/{podbay_slug}", current_all_keys)
                final_resp = resp

                if resp and resp.status_code == 200:
                    recon_success = True
                    break # ✅ 成功，跳出換裝循環
                
                elif resp and resp.status_code in [403, 429]:
                    # ⚠️ 點數耗盡：執行長延遲擬態 (5~10分鐘)
                    wait_sec = random.randint(300, 600)
                    print(f"🛑 [點數枯竭] 身份 {used_persona_label} code: {resp.status_code}")
                    print(f"🕒 執行擬態避震，休眠 {wait_sec//60} 分鐘後切換下一個身份...")
                    time.sleep(wait_sec)
                    continue 
                else:
                    break 
            except Exception as e:
                print(f"💥 身份 {used_persona_label} 異常: {e}")
                break

        # --- 數據歸檔邏輯 ---
        if recon_success:
            soup = BeautifulSoup(final_resp.text, 'html.parser')
            audio_meta = soup.find('meta', property=re.compile(r'(og:audio|twitter:player:stream)'))
            final_url = audio_meta.get('content') if audio_meta else None
            
            status = "success" if final_url else "manual_check"
            sb.table("mission_queue").update({
                "audio_url": final_url, "scrape_status": status, 
                "used_provider": f"SCRAPER_{used_persona_label}",
                "last_scraped_at": now_iso, "scrape_count": current_count
            }).eq("id", task_id).execute()
            print(f"{'✅' if final_url else '🔎'} [處理完成] {podbay_slug} (第 {current_count} 次)")
        else:
            status_code = final_resp.status_code if final_resp else 'N/A'
            sb.table("mission_queue").update({
                "last_scraped_at": now_iso, "scrape_count": current_count,
                "used_provider": f"SCRAPER_ALL_FAIL_{status_code}"
            }).eq("id", task_id).execute()
            print(f"⚠️ [任務受阻] 狀態碼: {status_code}")

        # --- 🚀 [核心更新：序列化戰術間歇] ---
        # 如果還有下一個任務，則進行短時間休息 (1~3 分鐘)
        if idx < total_count - 1:
            task_gap = random.randint(60, 180)
            print(f"⏳ [節奏控制] 避免連續開火，休眠 {task_gap} 秒後處理下一筆目標...")
            time.sleep(task_gap)

if __name__ == "__main__":
    run_scra_officer()