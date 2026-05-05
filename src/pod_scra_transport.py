# ---------------------------------------------------------
# 本程式碼：src/pod_scra_transport.py v3.7 ( T1部隊 鐵壁解耦版)
# 任務：1. 避開新產線任務 2. AI 提煉 (Gemini 2.5) 3. 寫入新版 mission_intel 
# [V3.7 升級] 1. 移除計分機制 (parse_intel_metrics)，杜絕 Regex 解析崩潰。
# [V3.7 升級] 2. 嚴格實施「先 DB 後 TG」兩階段提交，消滅幽靈迴圈。
# [V3.7 升級] 3. Telegram 標題強制鑲嵌 [任務ID前8碼]，精準對位 HF 歸檔。
# ---------------------------------------------------------
import os, requests, time, random, boto3, subprocess, json
from datetime import datetime, timezone
from supabase import create_client, Client
from podcast_ai_agent import AIAgent 

def get_secret(key, default=None):
    vault_path = "/etc/secrets/render_secret_vault.json"
    if os.path.exists(vault_path):
        with open(vault_path, 'r') as f:
            vault = json.load(f); return vault.get("active_credentials", {}).get(key, default)
    return os.environ.get(key, default)

def run_transport_and_report():
    # === 🛠️ 備援部隊控制面板 ===
    INTEL_LIMIT = 3               # 每次處理 3 筆，作為主產線故障時的備援
    JITTER_BASE_MIN, JITTER_BASE_MAX = 30, 60 # 備援部隊建議冷卻時間設長，避免與主產線搶 API
    MY_ID = get_secret("WORKER_ID", "GITHUB_ACTIONS")
    # =========================

    sb_url, sb_key = get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY")
    r2_id, r2_secret = get_secret("R2_ACCESS_KEY_ID"), get_secret("R2_SECRET_ACCESS_KEY")
    r2_acc, r2_bucket = get_secret("R2_ACCOUNT_ID"), get_secret("R2_BUCKET_NAME", "pod-scra-vault")
    tg_token, tg_chat_id = get_secret("TELEGRAM_BOT_TOKEN"), get_secret("TELEGRAM_CHAT_ID")

    sb: Client = create_client(sb_url, sb_key)
    ai_agent = AIAgent()
    s3 = boto3.client('s3', endpoint_url=f'https://{r2_acc}.r2.cloudflarestorage.com',
                      aws_access_key_id=r2_id, aws_secret_access_key=r2_secret, region_name='auto')

    # 🎯 篩選：已完成下載 (completed) 且擁有實體檔案 (r2_url 不為空) 且屬於 T2 產線的任務，按時間降序
    res = sb.table("mission_queue").select("id, r2_url, episode_title, source_name, audio_url")\
            .eq("scrape_status", "completed")\
            .neq("r2_url", "null")\
            .eq("assigned_troop", "T2")\
            .order("created_at", desc=True).limit(20).execute()
    
    pending_intel = []
    for m in res.data:
        if not m.get('r2_url'): continue
            
        check = sb.table("mission_intel").select("id, intel_status").eq("task_id", m['id']).execute()
        
        if not check.data:
            pending_intel.append(m)
        else:
            status = check.data[0].get('intel_status')
            if status in ["Sum.-proc", "Sum.-pre", "Sum.-ready"]:
                print(f"🛌 [身分：{MY_ID}] 任務 {m['id'][:8]} 正由新產線處理，GHA 執行戰術退讓。")
            elif status in ["Sum.-sent", "Sum.-archived"]:
                continue
                
        if len(pending_intel) >= INTEL_LIMIT: 
            break

    if not pending_intel:
        print("☕ [情報部] 戰場任務皆已由主產線佔領或完成。")
        return

    print(f"📦 [備援啟動] 發現 {len(pending_intel)} 筆漏網之魚，GHA 開始提煉。")

    for idx, task in enumerate(pending_intel):
        task_id = str(task['id'])
        r2_key = task.get('r2_url')
        local_raw, local_opus = f"/tmp/raw_{idx}.m4a", f"/tmp/proc_{idx}.opus"

        try:
            print(f"📡 [提取] 正在提取物資: {r2_key}")
            s3.download_file(r2_bucket, r2_key, local_raw)

            # 轉碼為輕量 Opus
            subprocess.run(['ffmpeg', '-y', '-i', local_raw, '-ar', '16000', '-ac', '1', '-c:a', 'libopus', '-b:a', '24k', local_opus], 
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            print(f"🧠 [摘要] 智囊團 (Gemini 2.5 Flash) 煉金中...")
            analysis, q_score, duration = ai_agent.generate_gold_analysis(local_opus)

            if analysis:
                # 🔐 1. 鐵律：先存檔，鎖定勝局 (拔除計分機制，全塞 0)
                try:
                    print(f"💾 [{MY_ID}] 摘要完成，優先寫入資料庫確保資料不遺失...")
                    sb.table("mission_intel").insert({
                        "task_id": task_id,
                        "summary_text": analysis,
                        "intel_status": "Sum.-sent",        
                        "ai_provider": "GEMINI",            
                        "report_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                        "total_score": 0,
                        "evidence_count": 0,
                        "stated_score": 0,       
                        "inferred_score": 0,   
                        "subjective_score": 0
                    }).execute()
                    print(f"✅ [{MY_ID}] 資料庫結案完成！任務 {task_id[:8]}")
                except Exception as db_e:
                    print(f"💥 [{MY_ID}] 資料庫寫入失敗，為避免幽靈迴圈，跳過 TG 發送！錯誤: {db_e}")
                    continue # 🛑 寫入資料庫失敗就跳過發送 TG，下次還能重做
                
                # 📢 2. 後發報，並附上歸檔 ID 
                try:
                    display_title = f"[{task_id[:8]}] {task.get('episode_title', '未知')}"
                    report_msg = ai_agent.format_mission_report(
                        "Gold", display_title, task.get('audio_url'), analysis, 
                        datetime.now().strftime("%m/%d"), duration, task.get('source_name')
                    )
                    requests.post(f"https://api.telegram.org/bot{tg_token}/sendMessage", 
                                  json={"chat_id": tg_chat_id, "text": report_msg, "parse_mode": "Markdown"}, timeout=30)
                    print(f"🎉 [{MY_ID}] Telegram 戰報空投成功！")
                except Exception as tg_e:
                    print(f"⚠️ [{MY_ID}] Telegram 戰報空投失敗，但資料庫已安全結案。錯誤: {tg_e}")

            if idx < len(pending_intel) - 1:
                wait_sec = random.randint(JITTER_BASE_MIN, JITTER_BASE_MAX)
                print(f"🕒 [避震] 冷卻 {wait_sec} 秒...")
                time.sleep(wait_sec)

        except Exception as e:
            print(f"💥 [崩潰]: {e}")
        finally:
            for f in [local_raw, local_opus]:
                if os.path.exists(f): os.remove(f)

if __name__ == "__main__":
    run_transport_and_report()