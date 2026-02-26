# ---------------------------------------------------------
# S-Plan Fortress v1.0 (全能要塞：偵察、下載、回填、交接一體化)
# 適用平台：Render, Hugging Face, Northflank
# ---------------------------------------------------------
import os, time, json, requests, boto3, re, random, feedparser, threading
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify, request
from supabase import create_client, Client
from bs4 import BeautifulSoup
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

# === 🧩 核心配置區 (兵種識別) ===
CURRENT_WORKER_ID = "RENDER"  # 👈 部署至 HF 時改為 "HUGGINGFACE"
INTERVAL_HOURS = 4            # 👈 每 4 小時巡邏一次，確保每日含手動可達 6 次

# === 🛡️ 憑證獲取器 (跨環境相容) ===
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

# === 🕵️ 偵察與下載一體化邏輯 (The Integrated Mission) ===
def run_integrated_mission():
    sb = get_sb(); now_iso = datetime.now(timezone.utc).isoformat()
    print(f"🚀 [{CURRENT_WORKER_ID}] 要塞巡邏啟動...")

    # 1. 輪值判定
    res = sb.table("pod_scra_tactics").select("*").eq("id", 1).execute()
    if not res.data: return
    tactic = res.data[0]
    
    # 邏輯 A：非我執勤，轉為靜默
    if tactic['active_worker'] != CURRENT_WORKER_ID:
        print(f"🛌 [靜默] 當前由 {tactic['active_worker']} 執勤，轉為熱機備援。"); return
    
    # 邏輯 B：執勤到期，自動交接 (RENDER -> KOYEB -> ZEABUR -> GITHUB -> HF)
    duty_start = datetime.fromisoformat(tactic['duty_start_at'].replace('Z', '+00:00'))
    if datetime.now(timezone.utc) > duty_start + timedelta(hours=tactic['rotation_hours']):
        roster = ["RENDER", "KOYEB", "ZEABUR", "GITHUB", "HUGGINGFACE"]
        next_worker = roster[(roster.index(CURRENT_WORKER_ID) + 1) % len(roster)]
        print(f"⏰ [交接] 執勤期滿，移交給 {next_worker}...");
        sb.table("pod_scra_tactics").update({"active_worker": next_worker, "duty_start_at": now_iso}).eq("id", 1).execute()
        return

    # 2. 領取 2新 + 1舊 任務 (過濾已達開火時間者)
    new_m = sb.table("mission_queue").select("*, mission_program_master(*)").eq("scrape_status", "pending").lte("troop2_start_at", now_iso)\
        .order("created_at", desc=True)\
        .limit(2).execute()             # 新任務次數
    old_m = sb.table("mission_queue").select("*, mission_program_master(*)").eq("scrape_status", "pending").lte("troop2_start_at", now_iso)\
        .order("created_at", desc=False)\
        .limit(1).execute()             # 舊任務次數
    missions = new_m.data + old_m.data
    if not missions: print("☕ 目前戰場無待處理任務。"); return

    s3 = get_s3(); bucket = get_secret("R2_BUCKET_NAME")
    
    for m in missions:
        task_id, slug, title = m['id'], str(m.get('podbay_slug') or "").strip(), m.get('episode_title', "")
        f_audio = m.get('audio_url')
        master = m.get('mission_program_master')
        print(f"🎯 [攻堅] {title[:20]} | Slug: {slug}")

        # --- 第一階段：偵察官 (獲取網址 + 順手牽羊) ---
        if not f_audio and master and master.get('rss_feed_url'):
            try: # RSS 秒殺
                feed = feedparser.parse(master['rss_feed_url'])
                target = feed.entries[0] if "Manual Test" in title else next((e for e in feed.entries if e.title == title), None)
                if target:
                    f_audio = next((enc.href for enc in target.enclosures if enc.type.startswith("audio")), None)
                    print("✅ [RSS 秒殺] 捕獲網址。")
            except: pass

        if not f_audio and slug: # HTML 攻堅
            try:
                # 這裡使用簡單 requests 模擬，若 Render 環境有封鎖，建議維持原本 fetch_html
                resp = requests.get(f"https://podbay.fm/p/{slug}", timeout=20)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    for a in soup.find_all('a', href=True):
                        hrf, txt = a['href'].lower(), a.get_text().upper()
                        if not f_audio and ('DOWNLOAD' in txt or 'MP3' in txt) and any(k in hrf for k in ['podtrac', 'megaphone', 'pdst', 'pscrb']):
                            f_audio = a['href']
                        if not master.get('rss_feed_url') and any(k in txt for k in ['RSS', 'FEED']):
                            if 'podbay.fm' not in hrf: # 戰利品歸庫
                                sb.table("mission_program_master").update({"rss_feed_url": a['href']}).eq("podbay_slug", slug).execute()
                                print(f"💎 [戰利品] 捕獲 RSS: {a['href']}")
            except Exception as e: print(f"💥 偵察報錯: {e}")

        # --- 第二階段：運輸兵 (下載並上傳 R2) ---
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
                sb.table("mission_queue").update({"status": "completed", "scrape_status": "success", "audio_url": f_audio, "r2_url": file_name, "recon_persona": f"{CURRENT_WORKER_ID}_Fortress"}).eq("id", task_id).execute()
                print(f"✅ [成功] 任務 {task_id} 結案。")
                if os.path.exists(tmp_path): os.remove(tmp_path)
            except Exception as e: print(f"🚛 [運輸失敗]: {e}")

# === 📡 要塞入口 (Flask) ===
@app.route('/ping')
def manual_trigger():
    # 手動測試路由：點擊網址直接在背景發動一次
    thread = threading.Thread(target=run_integrated_mission)
    thread.start()
    return f"📡 {CURRENT_WORKER_ID} Fortress: Manual Trigger Received.", 202

@app.route('/')
def health(): return "Fortress Online", 200

# === 🕒 要塞排程 (4 小時巡邏制) ===
scheduler = BackgroundScheduler()
scheduler.add_job(func=run_integrated_mission, trigger="interval", hours=INTERVAL_HOURS)
scheduler.start()

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)