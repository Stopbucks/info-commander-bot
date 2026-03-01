# ---------------------------------------------------------
# 本程式碼：src/pod_scra_transport.py v3.4 (情報入庫版)
# 任務：領取已入庫物資 -> AI 提煉 -> 寫入 mission_intel 新表 -> TG 報戰
# ---------------------------------------------------------
import os, requests, time, random, boto3, subprocess, json, re
from datetime import datetime
from supabase import create_client, Client
from podcast_ai_agent import AIAgent 

def get_secret(key, default=None):
    vault_path = "/etc/secrets/render_secret_vault.json"
    if os.path.exists(vault_path):
        with open(vault_path, 'r') as f:
            vault = json.load(f); return vault.get("active_credentials", {}).get(key, default)
    return os.environ.get(key, default)

def parse_intel_metrics(text):
    """從 AI 文本中提取量化指標 (用於填寫 mission_intel 欄位)"""
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
    # === 🛠️ 戰區控制面板 ===
    INTEL_LIMIT = 5               # 每次處理 2 筆/0301更改，處理堆積
    JITTER_BASE_MIN, JITTER_BASE_MAX = 10, 20
    # =========================

    sb_url, sb_key = get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY")
    r2_id, r2_secret = get_secret("R2_ACCESS_KEY_ID"), get_secret("R2_SECRET_ACCESS_KEY")
    r2_acc, r2_bucket = get_secret("R2_ACCOUNT_ID"), get_secret("R2_BUCKET_NAME", "pod-scra-vault")
    tg_token, tg_chat_id = get_secret("TELEGRAM_BOT_TOKEN"), get_secret("TELEGRAM_CHAT_ID")

    sb: Client = create_client(sb_url, sb_key)
    ai_agent = AIAgent()
    s3 = boto3.client('s3', endpoint_url=f'https://{r2_acc}.r2.cloudflarestorage.com',
                      aws_access_key_id=r2_id, aws_secret_access_key=r2_secret, region_name='auto')

    # 🎯 [關鍵改動]：改為檢查 mission_intel 表，若該任務 ID 不在其中，代表尚未產出摘要
    res = sb.table("mission_queue").select("id, r2_url, episode_title, source_name, audio_url")\
            .eq("status", "completed").order("created_at", desc=True).limit(20).execute()
    
    # 篩選出尚未在 mission_intel 中建立檔案的任務
    pending_intel = []
    for m in res.data:
        check = sb.table("mission_intel").select("id").eq("task_id", m['id']).execute()
        if not check.data: pending_intel.append(m)
        if len(pending_intel) >= INTEL_LIMIT: break

    if not pending_intel:
        print("☕ [情報部] 檔案館已滿載，暫無待提煉物資。"); return

    print(f"📦 [掃描雷達] 發現 {len(pending_intel)} 筆情報待入庫。")

    for idx, task in enumerate(pending_intel):
        task_id = task['id']
        r2_key = task.get('r2_url')
        local_raw, local_opus = f"/tmp/raw_{idx}.m4a", f"/tmp/proc_{idx}.opus"

        try:
            print(f"📡 [提取] 正在從金庫提取物資: {r2_key}")
            s3.download_file(r2_bucket, r2_key, local_raw)

            subprocess.run(['ffmpeg', '-y', '-i', local_raw, '-ar', '16000', '-ac', '1', '-c:a', 'libopus', '-b:a', '24k', local_opus], 
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            print(f"🧠 [摘要] AI 智囊團正在煉金...")
            analysis, q_score, duration = ai_agent.generate_gold_analysis(local_opus)

            if analysis:
                metrics = parse_intel_metrics(analysis)
                
                # 📡 [情報存儲]：將摘要寫入獨立的 mission_intel 表，保持主表清爽
                sb.table("mission_intel").insert({
                    "task_id": task_id,
                    "summary_text": analysis,
                    "total_score": metrics["score"],
                    "evidence_count": metrics["evidence"],
                    "stated_value": metrics["stated"],
                    "inferred_trust": metrics["inferred"],
                    "subjective_value": metrics["subjective"],
                    "ai_model": "Gemini-1.5-Pro",
                    "report_date": datetime.now().strftime("%m/%d/%y")
                }).execute()

                # 📡 [報戰發布]
                report_msg = ai_agent.format_mission_report(
                    "Gold", task.get('episode_title'), task.get('audio_url'), analysis, 
                    datetime.now().strftime("%m/%d"), duration, task.get('source_name')
                )
                requests.post(f"https://api.telegram.org/bot{tg_token}/sendMessage", 
                              json={"chat_id": tg_chat_id, "text": report_msg, "parse_mode": "Markdown"})
                
                print(f"✅ [成功] 任務 {task_id} 情報已入庫並發布。")

            if idx < len(pending_intel) - 1:
                wait_mins = (idx + 1) * random.randint(JITTER_BASE_MIN, JITTER_BASE_MAX)
                print(f"🕒 [避震] 冷卻 {wait_mins} 分鐘...")
                time.sleep(wait_mins * 60)

        except Exception as e:
            print(f"💥 [崩潰]: {e}")
        finally:
            for f in [local_raw, local_opus]:
                if os.path.exists(f): os.remove(f)

if __name__ == "__main__":
    run_transport_and_report()