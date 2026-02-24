# ---------------------------------------------------------
# 本程式碼：src/pod_scra_officer.py v7.9 (渲染演習版)
# 任務：5筆壓力測試、ScrapingAnt 渲染攻堅、Windows 聯軍擬態、自動換裝
# ---------------------------------------------------------
import os, requests, time, re, json, random
from datetime import datetime, timezone
from supabase import create_client, Client
from bs4 import BeautifulSoup
from pod_scra_scanner import fetch_html 

# === 🛠️ 偵察控制面板 ===
SCAN_LIMIT = 1                 
FORCE_PROVIDER = "SCRAPINGANT" # 🚀 演習目標：啟動真實瀏覽器渲染引擎
# =========================

def get_secret(key, default=None):
    vault_path = "/etc/secrets/render_secret_vault.json"
    if os.path.exists(vault_path):
        with open(vault_path, 'r') as f:
            vault = json.load(f); return vault.get("active_credentials", {}).get(key, default)
    return os.environ.get(key, default)

def run_scra_officer():
    # 🚀 擬態裝備庫：Windows 聯軍 (針對渲染引擎進行標頭優化)
    # 註：ScrapingAnt 通常會自動處理部分標頭，但手動注入一致性標頭可增加隱身權重
    SCRAPER_PERSONAS = [
        {
            "label": "Win11_Chrome_Ant", # 第一套裝備
            "key": get_secret("SCRAPINGANT_API_KEY"), # 🚀 修正：抓取正確的 Ant 金鑰
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
                "Sec-Ch-Ua-Platform": '"Windows"',
                "Connection": "keep-alive"
            }
        }
        # 如果您有第二組 ScrapingAnt 金鑰，可在此比照辦理新增 V2
    ]
    
    sb = create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))
    print(f"🚀 [渲染演習] 模式: {FORCE_PROVIDER} | 執行 5 筆 JS 強制渲染測試...")

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

        for persona in SCRAPER_PERSONAS:
            if not persona["key"]: 
                print(f"⚠️ 找不到 {FORCE_PROVIDER} 的金鑰，請檢查 Secrets 設定！")
                continue
            
            active_persona_label = persona["label"]
            print(f"📡 [偵察 {idx+1}/{total_count}] 使用裝備: {active_persona_label} 對位 {podbay_slug}...")
            
            # 🚀 關鍵修正：將金鑰標籤動態對位至 FORCE_PROVIDER
            current_all_keys = {FORCE_PROVIDER: [persona["key"]]}
            
            try:
                resp = fetch_html(FORCE_PROVIDER, f"https://podbay.fm/p/{podbay_slug}", current_all_keys)
                final_resp = resp

                if resp and resp.status_code == 200:
                    recon_success = True
                    break 
                elif resp and resp.status_code in [403, 429]:
                    wait_sec = random.randint(300, 600)
                    print(f"🛑 [Ant 火力中斷] 休眠 {wait_sec//60} 分鐘...")
                    time.sleep(wait_sec)
                    continue 
                else:
                    break 
            except Exception as e:
                print(f"💥 裝備異常: {e}")
                break

        # --- 數據歸檔 (寫入 recon_persona 欄位) ---
        if recon_success:
            soup = BeautifulSoup(final_resp.text, 'html.parser')
            # 💡 ScrapingAnt 渲染後的 HTML 通常包含展開後的音檔標籤
            audio_meta = soup.find('meta', property=re.compile(r'(og:audio|twitter:player:stream)'))
            final_url = audio_meta.get('content') if audio_meta else None
            
            status = "success" if final_url else "manual_check"
            sb.table("mission_queue").update({
                "audio_url": final_url, 
                "scrape_status": status, 
                "used_provider": f"{FORCE_PROVIDER}_{active_persona_label}",
                "recon_persona": active_persona_label, 
                "last_scraped_at": now_iso, 
                "scrape_count": current_count
            }).eq("id", task_id).execute()
            print(f"{'✅' if final_url else '🔎'} [完成] {podbay_slug} (使用:{active_persona_label})")
        else:
            status_code = final_resp.status_code if final_resp else 'N/A'
            sb.table("mission_queue").update({
                "last_scraped_at": now_iso, "scrape_count": current_count,
                "used_provider": f"{FORCE_PROVIDER}_ALL_FAIL_{status_code}",
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