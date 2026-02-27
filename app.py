# ---------------------------------------------------------
# S-Plan Fortress v1.6 (全能要塞：偵察、下載、回填、交接一體化)
# 優化：支援 POST 應門、強化安全 & 任務領取邏輯。 
# 適用平台：Render, HF, Northflank 統一 worker_ID 
# ---------------------------------------------------------

import os, time, json, requests, boto3, re, random, feedparser, threading
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify, request
from supabase import create_client, Client
from bs4 import BeautifulSoup
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

# === 🛡️ 憑證獲取器 (必須放在最前面，供後續變數呼叫) ===
def get_secret(key, default=None):
    vault_path = "/etc/secrets/render_secret_vault.json"
    if os.path.exists(vault_path):
        with open(vault_path, 'r') as f:
            v = json.load(f)
            return v.get("active_credentials", {}).get(key, default)
    return os.environ.get(key, default)

# === 🧩 核心配置區 (調整至函數定義之後) ===
CURRENT_WORKER_ID = get_secret("WORKER_ID", "UNKNOWN_NODE") 
INTERVAL_HOURS = 4

def get_sb(): return create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))
def get_s3():
    return boto3.client('s3', endpoint_url=get_secret("R2_ENDPOINT_URL"),
                        aws_access_key_id=get_secret("R2_ACCESS_KEY_ID"),
                        aws_secret_access_key=get_secret("R2_SECRET_ACCESS_KEY"), region_name="auto")

# === 🕵️ 偵察與下載一體化邏輯 (v1.6 強韌版：index 偏移量) ===
def run_integrated_mission():
    sb = get_sb(); now_iso = datetime.now(timezone.utc).isoformat()
    print(f"🚀 [{CURRENT_WORKER_ID}] 要塞巡邏啟動...")

    try:
        # 1. 取得 tactics 資料並執行 JSONB 心跳簽到
        res = sb.table("pod_scra_tactics").select("*").eq("id", 1).single().execute()
        if not res.data: return
        tactic = res.data
        
        # 🚀 [心跳] 更新 JSONB 點名冊
        health = tactic.get('workers_health', {}) or {}
        health[CURRENT_WORKER_ID] = now_iso
        sb.table("pod_scra_tactics").update({"last_heartbeat_at": now_iso, "workers_health": health}).eq("id", 1).execute()

        # 2. 獲取名單並判定是否輪值
        roster = tactic.get('worker_roster', ["RENDER", "ZEABUR", "GITHUB"])
        is_my_turn = (tactic['active_worker'] == CURRENT_WORKER_ID)
        
        # 3. 邏輯 B：交接判定 (精簡版)
        duty_start = datetime.fromisoformat(tactic['duty_start_at'].replace('Z', '+00:00'))
        is_expired = (datetime.now(timezone.utc) > duty_start + timedelta(hours=tactic['rotation_hours']))

        if is_my_turn and is_expired:
            # 🚀 精簡公式：一條龍算出接班人與預備役
            idx = roster.index(CURRENT_WORKER_ID) if CURRENT_WORKER_ID in roster else 0
            new_active = roster[(idx + 1) % len(roster)]
            new_next = roster[(idx + 2) % len(roster)]
            
            print(f"⏰ [交接] 執勤期滿。移交予: {new_active}, 預備役: {new_next}")
            sb.table("pod_scra_tactics").update({
                "active_worker": new_active, 
                "next_worker": new_next,        # 🚀 同步填入下一位
                "duty_start_at": now_iso,
                "consecutive_soft_failures": 0  # 🚀 交接時自動歸零
            }).eq("id", 1).execute()
            return
        
        if not is_my_turn:
            print(f"🛌 [靜默] 當前由 {tactic['active_worker']} 執勤。"); return

    except Exception as e:
        print(f"⚠️ 輪值判定異常: {e}"); return

    # --- 4. 領取任務 ---
    # === app.py 領取任務區 (修改為對接 scrape_status) ===
    # 領取策略：領取已經偵察官找到網址(success)但尚未完成下載的任務
    try:
        # 領取策略：領取已經偵察官找到網址(success)或尚未偵察(pending)但時間已到的任務
        query = sb.table("mission_queue").select("*, mission_program_master(*)") \
                  .in_("scrape_status", ["pending", "success"]).lte("troop2_start_at", now_iso)
        
        # 分開領取確保穩定性，並加上 or [] 防止 NoneType 報錯
        new_m = query.order("created_at", desc=True).limit(2).execute().data or []
        old_m = query.order("created_at", desc=False).limit(1).execute().data or []
        missions = new_m + old_m

        if not missions: 
            print("☕ 目前戰場無待處理任務。")
            return

        s3 = get_s3(); bucket = get_secret("R2_BUCKET_NAME")
        
        for m in missions:
            task_id = m['id']
            slug = str(m.get('podbay_slug') or "").strip()
            title = m.get('episode_title', "")
            f_audio = m.get('audio_url')
            master = m.get('mission_program_master')
            print(f"🎯 [攻堅] {title[:20]}")

            # --- 第一階段：偵察 (補齊網址) ---
            if not f_audio:
                # RSS 優先協議
                if master and master.get('rss_feed_url'):
                    try:
                        feed = feedparser.parse(master['rss_feed_url'])
                        target = feed.entries[0] if "Manual Test" in title else next((e for e in feed.entries if e.title == title), None)
                        if target:
                            f_audio = next((enc.href for enc in target.enclosures if enc.type.startswith("audio")), None)
                            print("✅ [RSS 秒殺] 捕獲網址。")
                    except: pass

                # Podbay HTML 攻堅
                if not f_audio and slug:
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
                    except: pass

            # --- 第二階段：運輸 (下載與回填) ---
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
                    
                    # 🚀 結案回報：統一使用 scrape_status，更新 Persona 為 v1.6
                    sb.table("mission_queue").update({
                        "scrape_status": "completed", 
                        "audio_url": f_audio, 
                        "r2_url": file_name, 
                        "recon_persona": f"{CURRENT_WORKER_ID}_Fortress_v1.6" 
                    }).eq("id", task_id).execute()

                    # 🚀 解除警報：成功結案後立刻歸零失敗次數
                    sb.table("pod_scra_tactics").update({"consecutive_soft_failures": 0}).eq("id", 1).execute()
                    
                    print(f"✅ [成功] 任務 {task_id} 結案，失敗計數歸零。")
                    if os.path.exists(tmp_path): os.remove(tmp_path)
                except Exception as e: print(f"🚛 [運輸失敗]: {e}")

    except Exception as e:
        print(f"⚠️ 任務總體循環異常: {e}") 

# === 📡 要塞入口 (Flask加固門禁版) ===
@app.route('/ping', methods=['GET', 'POST'])
def manual_trigger():
    # 1. 取得環境變數中的正確密碼
    correct_secret = get_secret("CRON_SECRET")
    
    # 🚀 安全補丁：如果伺服器端根本沒設密碼，直接拒絕所有請求
    if not correct_secret:
        print("🚨 [嚴重警告] 伺服器未設定 CRON_SECRET，為了安全已拒絕所有外部指令！")
        return jsonify({"status": "error", "message": "Server security configuration missing"}), 500
    
    # 2. 獲取來訪者提供的密碼
    provided_token = request.headers.get('X-Cron-Secret') or request.args.get('token')
    
    # 3. 判斷是否放行
    if not provided_token or provided_token != correct_secret:
        print(f"🚫 [拒絕存取] 身分驗證失敗。收到 Token: {provided_token}")
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    # 🔓 驗證通過，執行任務
    thread = threading.Thread(target=run_integrated_mission)
    thread.start()
    return f"📡 {CURRENT_WORKER_ID} Fortress: Manual Trigger Authorized.", 202

@app.route('/')
def health(): 
    return f"Fortress {CURRENT_WORKER_ID} Online", 200

# === 🕒 要塞排程 ===
scheduler = BackgroundScheduler()
scheduler.add_job(func=run_integrated_mission, trigger="interval", hours=INTERVAL_HOURS)
scheduler.start()

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)