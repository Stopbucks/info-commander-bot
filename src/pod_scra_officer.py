# ---------------------------------------------------------
# 本程式碼：src/pod_scra_officer.py v7.2 (高良率決策版)
# 任務：3筆精準掃描、強制 HASDATA 住宅代理、多 Key 預留
# ---------------------------------------------------------
import os, requests, time, re, json
from supabase import create_client, Client
from bs4 import BeautifulSoup
from pod_scra_scanner import fetch_html 

# === 🛠️ 偵察控制面板 (最高指揮部) ===
SCAN_LIMIT = 3                # 指揮官命令：每次點射 3 筆，節約點數。
FORCE_PROVIDER = "HASDATA"    # 指揮官命令：觀察期強制使用住宅代理確保良率。
# =========================================

def get_secret(key, default=None):
    vault_path = "/etc/secrets/render_secret_vault.json"
    if os.path.exists(vault_path):
        with open(vault_path, 'r') as f:
            vault = json.load(f); return vault.get("active_credentials", {}).get(key, default)
    return os.environ.get(key, default)

def run_scra_officer():
    # 🚀 多帳號預留區：若有新申請的 ScraperAPI Key，請放入此 list
    scraper_keys = [get_secret("SCRAP_API_KEY")] 
    
    all_keys = {
        "SCRAPERAPI": scraper_keys, 
        "ZENROWS": get_secret("ZENROWS_API_KEY"),
        "HASDATA": get_secret("HASDATA_API_KEY"),
        "WEBSCRAP": get_secret("WEBSCRAP_API_KEY"),
        "SCRAPEDO": get_secret("SCRAPEDO_API_KEY")
    }
    
    sb = create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))
    
    print(f"🚀 [解碼官出擊] 採用特種模式: {FORCE_PROVIDER} | 掃描上限: {SCAN_LIMIT}")

    # 任務領取：2新 1舊 (確保歷史堆積也能被消化)
    new_m = sb.table("mission_queue").select("*").eq("scrape_status", "pending").order("created_at", desc=True).limit(2).execute()
    old_m = sb.table("mission_queue").select("*").eq("scrape_status", "pending").order("created_at", desc=False).limit(1).execute()
    
    for mission in (new_m.data + old_m.data):
        task_id = mission['id']
        podbay_slug = str(mission.get('podbay_slug') or "").strip()
        
        try:
            # 發動高強度偵察
            resp = fetch_html(FORCE_PROVIDER, f"https://podbay.fm/p/{podbay_slug}", all_keys)
            
            if resp and resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                # 穿透 Podbay 動態標籤提取內容
                audio_meta = soup.find('meta', property=re.compile(r'(og:audio|twitter:player:stream)'))
                final_url = audio_meta.get('content') if audio_meta else None
                
                if final_url:
                    sb.table("mission_queue").update({
                        "audio_url": final_url, "scrape_status": "success", "used_provider": FORCE_PROVIDER
                    }).eq("id", task_id).execute()
                    print(f"✅ [成功] {podbay_slug} 偵察完畢。")
                else:
                    sb.table("mission_queue").update({"scrape_status": "manual_check"}).eq("id", task_id).execute()
                    print(f"🔎 [解析失敗] {podbay_slug} 轉手動檢查。")
            else:
                print(f"⚠️ [通訊斷訊] {FORCE_PROVIDER} 響應異常: {resp.status_code if resp else 'N/A'}")
        
        except Exception as e:
            print(f"💥 [崩潰] 偵察過程發生錯誤: {e}")

if __name__ == "__main__":
    run_scra_officer()