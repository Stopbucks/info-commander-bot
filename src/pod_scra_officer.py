# ---------------------------------------------------------
# 本程式碼：src/pod_scra_officer.py v7.4 (審計強化版)
# 任務：3筆精準掃描、HASDATA 住宅代理、全自動偵察審計紀錄
# ---------------------------------------------------------
import os, requests, time, re, json
from datetime import datetime, timezone  # 🚀 補回遺失的日期模組
from supabase import create_client, Client
from bs4 import BeautifulSoup
from pod_scra_scanner import fetch_html 

# === 🛠️ 偵察控制面板 (最高指揮部) ===
SCAN_LIMIT = 3                # 每次點射 3 筆，節約點數。
FORCE_PROVIDER = "HASDATA"    # 觀察期強制使用住宅代理確保良率。
# =========================================

def get_secret(key, default=None):
    vault_path = "/etc/secrets/render_secret_vault.json"
    if os.path.exists(vault_path):
        with open(vault_path, 'r') as f:
            vault = json.load(f); return vault.get("active_credentials", {}).get(key, default)
    return os.environ.get(key, default)

def run_scra_officer():
    # 🚀 多帳號預留區
    scraper_keys = [get_secret("SCRAP_API_KEY")] 
    
    all_keys = {
        "SCRAPERAPI": scraper_keys, 
        "ZENROWS": get_secret("ZENROWS_API_KEY"),
        "HASDATA": get_secret("HASDATA_API_KEY"),
        "WEBSCRAP": get_secret("WEBSCRAP_API_KEY"),
        "SCRAPEDO": get_secret("SCRAPEDO_API_KEY"),
        "SCRAPINGANT": get_secret("SCRAPINGANT_API_KEY")
    }
    
    sb = create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))
    print(f"🚀 [解碼官出擊] 模式: {FORCE_PROVIDER} | 上限: {SCAN_LIMIT}")

    # 🎯 任務領取：2新 1舊 (確保累積物資也能被消化)
    new_m = sb.table("mission_queue").select("*").eq("scrape_status", "pending").order("created_at", desc=True).limit(2).execute()
    old_m = sb.table("mission_queue").select("*").eq("scrape_status", "pending").order("created_at", desc=False).limit(1).execute()
    
    for mission in (new_m.data + old_m.data):
        task_id = mission['id']
        podbay_slug = str(mission.get('podbay_slug') or "").strip()
        
        # 🛡️ [審計準備]：累加次數與時間戳記
        current_count = (mission.get('scrape_count') or 0) + 1
        now_iso = datetime.now(timezone.utc).isoformat()
        
        try:
            resp = fetch_html(FORCE_PROVIDER, f"https://podbay.fm/p/{podbay_slug}", all_keys)
            
            if resp and resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                audio_meta = soup.find('meta', property=re.compile(r'(og:audio|twitter:player:stream)'))
                final_url = audio_meta.get('content') if audio_meta else None
                
                if final_url:
                    # ✅ [偵察成功] 回填資訊並紀錄次數
                    sb.table("mission_queue").update({
                        "audio_url": final_url, 
                        "scrape_status": "success", 
                        "used_provider": FORCE_PROVIDER,
                        "last_scraped_at": now_iso,
                        "scrape_count": current_count
                    }).eq("id", task_id).execute()
                    print(f"✅ [成功] {podbay_slug} (第 {current_count} 次)")
                else:
                    # 🔎 [解析失敗] 紀錄失敗紀錄供分析
                    sb.table("mission_queue").update({
                        "scrape_status": "manual_check",
                        "used_provider": FORCE_PROVIDER,
                        "last_scraped_at": now_iso,
                        "scrape_count": current_count
                    }).eq("id", task_id).execute()
                    print(f"🔎 [解析失敗] {podbay_slug} (第 {current_count} 次)")
            else:
                # ⚠️ [通訊異常] 紀錄錯誤代碼
                status_code = resp.status_code if resp else 'N/A'
                sb.table("mission_queue").update({
                    "last_scraped_at": now_iso,
                    "scrape_count": current_count,
                    "used_provider": f"{FORCE_PROVIDER}_FAIL_{status_code}"
                }).eq("id", task_id).execute()
                print(f"⚠️ [斷訊] {FORCE_PROVIDER} 狀態碼: {status_code}")
        
        except Exception as e:
            # 💥 [崩潰保險] 發生程式錯誤時至少要加到次數，避免死循環
            sb.table("mission_queue").update({
                "last_scraped_at": datetime.now(timezone.utc).isoformat(),
                "scrape_count": current_count
            }).eq("id", task_id).execute()
            print(f"💥 [程式報錯] {podbay_slug}: {e}")

if __name__ == "__main__":
    run_scra_officer()