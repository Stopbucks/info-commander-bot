
# ---------------------------------------------------------
# S-Plan Fortress v1.71  程式碼：app.py 佈署各平台
# 適用平台：Zeabur, Render, Koyeb (潛行交接版：合體心跳、交接、Jitter)
# ---------------------------------------------------------

import os, time, json, requests, boto3, re, random, feedparser, threading
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify, request
from supabase import create_client
from bs4 import BeautifulSoup
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

# === 🧩 戰術控制面板 ===
CONFIG = {
    "WORKER_ID": os.environ.get("WORKER_ID", "UNKNOWN_NODE"),
    "INTERVAL_HOURS": 2,          # 巡邏頻率
    "NEW_LIMIT": 2,               # 每次點火新任務數
    "OLD_LIMIT": 1,               # 每次點火舊任務數
    "JITTER_BASE_MIN": 180,       # 基礎休息下限 (3分)
    "JITTER_BASE_MAX": 360,       # 基礎休息上限 (6分)
    "CRON_SECRET": os.environ.get("CRON_SECRET")
}

# --- 核心工具 ---
def get_sb(): return create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))
def get_s3():
    return boto3.client('s3', endpoint_url=os.environ.get("R2_ENDPOINT_URL"),
                        aws_access_key_id=os.environ.get("R2_ACCESS_KEY_ID"),
                        aws_secret_access_key=os.environ.get("R2_SECRET_ACCESS_KEY"), region_name="auto")

# --- 🕵️ 核心一體化邏輯 ---
def run_integrated_mission():
    sb = get_sb(); now = datetime.now(timezone.utc); now_iso = now.isoformat()
    print(f"🚀 [{CONFIG['WORKER_ID']}] 潛行巡邏啟動...")

    try:
        # 1. 取得 tactics 資料
        res = sb.table("pod_scra_tactics").select("*").eq("id", 1).single().execute()
        if not res.data: return
        tactic = res.data
        
        # 🚀 [功能一：心跳簽到]
        health = tactic.get('workers_health', {}) or {}
        health[CONFIG['WORKER_ID']] = now_iso
        sb.table("pod_scra_tactics").update({"last_heartbeat_at": now_iso, "workers_health": health}).eq("id", 1).execute()
        print(f"💓 [{CONFIG['WORKER_ID']}] 心跳簽到完成。")

        # 🚀 [功能二：值勤與交接判定]
        roster = tactic.get('worker_roster', ["RENDER", "ZEABUR", "GITHUB", "HuggingFace"])
        is_my_turn = (tactic['active_worker'] == CONFIG['WORKER_ID'])
        
        # 檢查是否過期
        duty_start_str = tactic.get('duty_start_at', now_iso).replace('Z', '+00:00')
        duty_start = datetime.fromisoformat(duty_start_str)
        rotation_hours = tactic.get('rotation_hours', 4)
        is_expired = (now > duty_start + timedelta(hours=rotation_hours))

        # A. 如果輪到我但過期了：執行交接
        if is_my_turn and is_expired:
            idx = roster.index(CONFIG['WORKER_ID']) if CONFIG['WORKER_ID'] in roster else 0
            new_active = roster[(idx + 1) % len(roster)]
            new_next = roster[(idx + 2) % len(roster)]
            
            print(f"⏰ [交接] 執勤期滿。移交予: {new_active}, 預備役: {new_next}")
            sb.table("pod_scra_tactics").update({
                "active_worker": new_active, 
                "next_worker": new_next,
                "duty_start_at": now_iso,
                "consecutive_soft_failures": 0 
            }).eq("id", 1).execute()
            return # 交接完畢，讓位

        # B. 如果根本沒輪到我：繼續睡覺
        if not is_my_turn:
            print(f"睡覺 [靜默] 目前由 {tactic['active_worker']} 執勤。"); return

        # 🚀 [功能三：領取與執行任務] (2 新 + 1 舊)
        query_base = sb.table("mission_queue").select("*, mission_program_master(*)") \
                       .in_("scrape_status", ["pending", "success"]).lte("troop2_start_at", now_iso)

        new_tasks = query_base.order("created_at", desc=True).limit(CONFIG['NEW_LIMIT']).execute().data or []
        excluded_ids = [t['id'] for t in new_tasks]
        old_tasks = query_base.not_.in_("id", excluded_ids).order("created_at", desc=False).limit(CONFIG['OLD_LIMIT']).execute().data or []
        
        missions = new_tasks + old_tasks
        if not missions: 
            print("☕ 戰場清空，無待處理任務。"); return

        s3 = get_s3(); bucket = os.environ.get("R2_BUCKET_NAME")

        for idx, m in enumerate(missions):
            task_id = m['id']; title = m.get('episode_title', ""); f_audio = m.get('audio_url')
            slug = str(m.get('podbay_slug') or "").strip()
            master = m.get('mission_program_master')
            print(f"🎯 [攻堅 {idx+1}/{len(missions)}] {title[:20]}")

            # --- 偵察與補齊邏輯 (RSS/Podbay) ---
            if not f_audio:
                try:
                    if master and master.get('rss_feed_url'):
                        feed = feedparser.parse(master['rss_feed_url'])
                        target = next((e for e in feed.entries if e.title == title), None)
                        if target:
                            f_audio = next((enc.href for enc in target.enclosures if enc.type.startswith("audio")), None)
                    
                    if not f_audio and slug:
                        resp = requests.get(f"https://podbay.fm/p/{slug}", timeout=20)
                        if resp.status_code == 200:
                            soup = BeautifulSoup(resp.text, 'html.parser')
                            for a in soup.find_all('a', href=True):
                                hrf, txt = a['href'].lower(), a.get_text().upper()
                                if not f_audio and ('DOWNLOAD' in txt or 'MP3' in txt) and any(k in hrf for k in ['podtrac', 'megaphone', 'pdst', 'pscrb']):
                                    f_audio = a['href']
                except: pass

            # --- 下載與 R2 運輸 ---
            if f_audio:
                try:
                    file_name = f"{now.strftime('%Y%m%d')}_{task_id[:8]}.mp3"
                    tmp_path = f"/tmp/{file_name}"
                    with requests.get(f_audio, stream=True, timeout=120) as r:
                        r.raise_for_status()
                        with open(tmp_path, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
                    
                    s3.upload_file(tmp_path, bucket, file_name)
                    sb.table("mission_queue").update({
                        "scrape_status": "completed", "audio_url": f_audio, "r2_url": file_name, 
                        "recon_persona": f"{CONFIG['WORKER_ID']}_v1.71_Stealth" 
                    }).eq("id", task_id).execute()
                    
                    print(f"✅ [成功] {file_name} 入庫。")
                    if os.path.exists(tmp_path): os.remove(tmp_path)
                    sb.table("pod_scra_tactics").update({"consecutive_soft_failures": 0}).eq("id", 1).execute()
                except Exception as e: print(f"🚛 [運輸失敗]: {e}")

            # 🚀 [功能四：累進式 Jitter 潛行]
            if idx < len(missions) - 1:
                multiplier = idx + 1 
                wait = random.randint(CONFIG['JITTER_BASE_MIN'] * multiplier, CONFIG['JITTER_BASE_MAX'] * multiplier)
                print(f"⏳ [潛行] 完成第 {idx+1} 筆，隨機喘息 {wait} 秒 ({multiplier}x)...")
                time.sleep(wait)

    except Exception as e: print(f"⚠️ 巡邏異常: {e}")

# --- 📡 門禁與入口 ---
@app.route('/ping')
def trigger():
    token = request.args.get('token')
    if not token or token != CONFIG['CRON_SECRET']: return "Unauthorized", 401
    threading.Thread(target=run_integrated_mission).start()
    return f"📡 {CONFIG['WORKER_ID']} Fortress: Mission Triggered.", 202

@app.route('/')
def health(): return f"Fortress {CONFIG['WORKER_ID']} v1.71 Online", 200

# --- 🕒 排程器 ---
scheduler = BackgroundScheduler()
scheduler.add_job(func=run_integrated_mission, trigger="interval", hours=CONFIG["INTERVAL_HOURS"])
scheduler.start()

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)