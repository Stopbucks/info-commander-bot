# ---------------------------------------------------------
# S-Plan Fortress v1.1 (全能要塞：偵察、下載、回填、交接一體化)
# 優化：支援 POST 應門、強化任務領取邏輯。
# 適用平台：Render, HF, Northflank
# ---------------------------------------------------------
import os, time, json, requests, boto3, re, random, feedparser, threading
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify, request
from supabase import create_client, Client
from bs4 import BeautifulSoup
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

# === 🧩 核心配置區 (兵種識別) ===
CURRENT_WORKER_ID = "RENDER"
INTERVAL_HOURS = 4

def get_secret(key, default=None):
    vault_path = "/etc/secrets/render_secret_vault.json"
    if os.path.exists(vault_path):
        with open(vault_path, 'r') as f:
            v = json.load(f); return v.get("active_credentials", {}).get(key, default)
    return os.environ.get(key, default)

def get_sb(): return create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))
def get_s3():
    return boto3.client('s3', endpoint_url=get_secret("R2_ENDPOINT_URL"),
                        aws_access_key_id=get_secret("R2_ACCESS_KEY_ID"),
                        aws_secret_access_key=get_secret("R2_SECRET_ACCESS_KEY"), region_name="auto")

# === 🕵️ 偵察與下載一體化邏輯 ===
def run_integrated_mission():
    sb = get_sb(); now_iso = datetime.now(timezone.utc).isoformat()
    print(f"🚀 [{CURRENT_WORKER_ID}] 要塞巡邏啟動...")

    # 1. 輪值判定
    try:
        res = sb.table("pod_scra_tactics").select("*").eq("id", 1).execute()
        if not res.data: return
        tactic = res.data[0]
        
        # 邏輯 A：非我執勤，轉為靜默 (手動觸發時可略過此判定)
        if tactic['active_worker'] != CURRENT_WORKER_ID:
            print(f"🛌 [靜默] 當前由 {tactic['active_worker']} 執勤。"); return
        
        # 邏輯 B：執勤到期判定
        duty_start_str = tactic['duty_start_at'].replace('Z', '+00:00').replace(' ', 'T')
        duty_start = datetime.fromisoformat(duty_start_str)
        if datetime.now(timezone.utc) > duty_start + timedelta(hours=tactic['rotation_hours']):
            roster = ["RENDER", "KOYEB", "ZEABUR", "GITHUB", "HUGGINGFACE"]
            next_worker = roster[(roster.index(CURRENT_WORKER_ID) + 1) % len(roster)]
            print(f"⏰ [交接] 移交給 {next_worker}...");
            sb.table("pod_scra_tactics").update({"active_worker": next_worker, "duty_start_at": now_iso}).eq("id", 1).execute()
            return
    except Exception as e:
        print(f"⚠️ 輪值判定異常: {e}")

    # 2. 領取 2新 + 1舊 任務 (只要 status 為 pending 且時間已到就領取)
    query = sb.table("mission_queue").select("*, mission_program_master(*)").eq("status", "pending").lte("troop2_start_at", now_iso)
    
    new_m = query.order("created_at", desc=True).limit(2).execute()
    old_m = query.order("created_at", desc=False).limit(1).execute()
    missions = new_m.data + old_m.data
    if not missions: print("☕ 目前戰場無待處理任務。"); return

    s3 = get_s3(); bucket = get_secret("R2_BUCKET_NAME")
    
    for m in missions:
        task_id, slug, title = m['id'], str(m.get('podbay_slug') or "").strip(), m.get('episode_title', "")
        f_audio = m.get('audio_url') # 如果之前 Officer 已抓到網址，這裡直接沿用
        master = m.get('mission_program_master')
        print(f"🎯 [攻堅] {title[:20]}")

        # --- 第一階段：偵察 (僅在無網址時啟動) ---
        if not f_audio:
            if master and master.get('rss_feed_url'):
                try: # RSS 秒殺
                    feed = feedparser.parse(master['rss_feed_url'])
                    target = feed.entries[0] if "Manual Test" in title else next((e for e in feed.entries if e.title == title), None)
                    if target:
                        f_audio = next((enc.href for enc in target.enclosures if enc.type.startswith("audio")), None)
                        print("✅ [RSS 秒殺] 捕獲網址。")
                except: pass

            if not f_audio and slug: # HTML 攻堅
                try:
                    resp = requests.get(f"https://podbay.fm/p/{slug}", timeout=20)
                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.text, 'html.parser')
                        for a in soup.find_all('a', href=True):
                            hrf, txt = a['href'].lower(), a.get_text().upper()
                            if not f_audio and ('DOWNLOAD' in txt or 'MP3' in txt) and any(k in hrf for k in ['podtrac', 'megaphone', 'pdst', 'pscrb']):
                                f_audio = a['href']
                            if not master.get('rss_feed_url') and any(k in txt for k in ['RSS', 'FEED']) and 'podbay.fm' not in hrf:
                                sb.table("mission_program_master").update({"rss_feed_url": a['href']}).eq("podbay_slug", slug).execute()
                                print(f"💎 [戰利品] 捕獲 RSS: {a['href']}")
                except: pass

        # --- 第二階段：運輸 (下載並上傳 R2) ---
        if f_audio:
            try:
                file_name = f"{datetime.now().strftime('%Y%m%d')}_{task_id[:8]}.mp3"
                tmp_path = f"/tmp/{file_name}"
                print(f"🚛 [運輸] 正在搬運至 R2...")
                with requests.get(f_audio, stream=True, timeout=60) as r:
                    r.raise_for_status()
                    with open(tmp_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
                
                s3.upload_file(tmp_path, bucket, file_name)
                sb.table("mission_queue").update({
                    "status": "completed", 
                    "scrape_status": "success", 
                    "audio_url": f_audio, 
                    "r2_url": file_name, 
                    "recon_persona": f"{CURRENT_WORKER_ID}_Fortress_v1.1"
                }).eq("id", task_id).execute()
                print(f"✅ [成功] 任務 {task_id} 結案。")
                if os.path.exists(tmp_path): os.remove(tmp_path)
            except Exception as e: print(f"🚛 [運輸失敗]: {e}")

# === 📡 要塞入口 (Flask) ===
# 🚀 支援 GET 與 POST。解決 GitHub 用 curl -X POST 敲門的 405 錯誤
@app.route('/ping', methods=['GET', 'POST']) # 🚀 支援 POST 動員令
def manual_trigger():
    thread = threading.Thread(target=run_integrated_mission)
    thread.start()
    return f"📡 {CURRENT_WORKER_ID} Fortress: Manual Trigger Received.", 202

@app.route('/')
def health(): return "Fortress Online", 200

# === 🕒 要塞排程 ===
scheduler = BackgroundScheduler()
scheduler.add_job(func=run_integrated_mission, trigger="interval", hours=INTERVAL_HOURS)
scheduler.start()

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)