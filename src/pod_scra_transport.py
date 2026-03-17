# ---------------------------------------------------------
# 本程式碼：src/pod_scra_transport.py v3.6 ( T1部隊 二代大腦備援版)
# 任務：1. 避開新產線任務 2. AI 提煉 (Gemini 2.5) 3. 寫入新版 mission_intel 
# [工作流程] 掃描已下載(completed)且具備實體檔案的 T2 任務，接手提煉摘要。
# [工作流程] 發現任務正由主產線 (Sum.-proc/pre/ready) 處理時，自動執行戰術退讓。
# [任務定位] 擔任 T2 產線的終極後備軍，確保物資入庫後絕對不會因為主節點異常而卡死。
# [版本修正] 1. 修復 pending_intel 迴圈邏輯漏洞，確保有效過濾並承接無紀錄任務。
# [版本修正] 2. 新增 assigned_troop == "T2" 防線，嚴格遵守雙軌分流，絕不誤觸 T1 專屬物資。
# [版本修正] 3. 新增 r2_url 實體檔案校驗，避免處理未確實上傳的幽靈資料。
# ---------------------------------------------------------
import os, requests, time, random, boto3, subprocess, json, re
from datetime import datetime, timezone
from supabase import create_client, Client
from podcast_ai_agent import AIAgent 

def get_secret(key, default=None):
    vault_path = "/etc/secrets/render_secret_vault.json"
    if os.path.exists(vault_path):
        with open(vault_path, 'r') as f:
            vault = json.load(f); return vault.get("active_credentials", {}).get(key, default)
    return os.environ.get(key, default)

def parse_intel_metrics(text):
    """從 AI 文本中提取量化指標"""
    metrics = {"score": 0, "stated": 0, "inferred": 0, "subjective": 0, "evidence": 0}
    try:
        s_match = re.search(r"綜合情報分 \(Total Score\): (\d+)", text)
        if s_match: metrics["score"] = int(s_match.group(1))
        e_match = re.search(r"關鍵實證數：(\d+)", text)
        if e_match: metrics["evidence"] = int(e_match.group(1))
        v_match = re.findall(r": (\d+) 分", text)
        if len(v_match) >= 3:
            metrics["stated"], metrics["inferred"], metrics["subjective"] = map(int, v_match[:3])
    except: pass
    return metrics

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
        # 防呆：避免處理到沒有網址的無效紀錄
        if not m.get('r2_url'): continue
            
        # 🕵️ [關鍵排他判定]：檢查情報表狀態
        check = sb.table("mission_intel").select("id, intel_status").eq("task_id", m['id']).execute()
        
        # 1. 若完全無紀錄：代表主產線連 STT 都還沒跑完，GHA 獲准介入
        if not check.data:
            pending_intel.append(m)
            
        else:
            status = check.data[0].get('intel_status')
            # 2. 若狀態為 proc, pre, ready：代表新產線 (Zeabur/Koyeb) 正在作業中，GHA 必須保持靜默退讓
            if status in ["Sum.-proc", "Sum.-pre", "Sum.-ready"]:
                print(f"🛌 [身分：{MY_ID}] 任務 {m['id'][:8]} 正由新產線處理，GHA 執行戰術退讓。")
            
            # 3. 若已發送或歸檔：也跳過
            elif status in ["Sum.-sent", "Sum.-archived"]:
                continue
                
        # 🚀 達到收集上限就提早結束迴圈
        if len(pending_intel) >= INTEL_LIMIT: 
            break

    if not pending_intel:
        print("☕ [情報部] 戰場任務皆已由主產線佔領或完成。")
        return

    print(f"📦 [備援啟動] 發現 {len(pending_intel)} 筆漏網之魚，GHA 開始提煉。")

    for idx, task in enumerate(pending_intel):
        task_id = task['id']
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
                metrics = parse_intel_metrics(analysis)
                
                # 📡 [寫入]：與新版 mission_intel 表對齊
                sb.table("mission_intel").insert({
                    "task_id": task_id,
                    "summary_text": analysis,
                    "intel_status": "Sum.-sent",        # 標記為已發送，供 HF 搬運
                    "ai_provider": "GEMINI",            # 欄位對齊
                    "report_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    "total_score": metrics["score"],
                    "evidence_count": metrics["evidence"],
                    "stated_value": metrics["stated"],
                    "inferred_trust": metrics["inferred"],
                    "subjective_value": metrics["subjective"]
                }).execute()

                # 📡 [報戰發布]
                report_msg = ai_agent.format_mission_report(
                    "Gold", task.get('episode_title'), task.get('audio_url'), analysis, 
                    datetime.now().strftime("%m/%d"), duration, task.get('source_name')
                )
                requests.post(f"https://api.telegram.org/bot{tg_token}/sendMessage", 
                              json={"chat_id": tg_chat_id, "text": report_msg, "parse_mode": "Markdown"})
                
                print(f"✅ [成功] GHA 補位完成：任務 {task_id[:8]}")

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