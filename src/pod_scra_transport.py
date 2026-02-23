# ---------------------------------------------------------
# 本程式碼：src/pod_scra_transport.py v3.0 (情報轉型版)
# 任務：專注於已完成(completed)物資的 AI 摘要與 Telegram 報戰
# ---------------------------------------------------------
# ---------------------------------------------------------
# 本程式碼：src/pod_scra_transport.py v3.1 (階梯延時版)
# 任務：已入庫物資分析、Opus 極限壓縮、階梯式 Jitter 避震
# ---------------------------------------------------------

import os, requests, time, random, boto3, subprocess, json
from supabase import create_client, Client
from datetime import datetime, timezone, timedelta
from podcast_ai_agent import AIAgent 

def get_secret(key, default=None):
    vault_path = "/etc/secrets/render_secret_vault.json"
    if os.path.exists(vault_path):
        with open(vault_path, 'r') as f:
            vault = json.load(f); return vault.get("active_credentials", {}).get(key, default)
    return os.environ.get(key, default)

def run_transport_and_report():
    # === 🛠️ 情報部控制面板 ===
    INTEL_LIMIT = 3               # 每次處理 3 筆，防止 GitHub 3小時超時
    JITTER_BASE_MIN = 10          # 休息基數最小值 (10分鐘)
    JITTER_BASE_MAX = 20          # 休息基數最大值 (20分鐘)
    # =========================

    sb_url = get_secret("SUPABASE_URL")
    sb_key = get_secret("SUPABASE_KEY")
    r2_id = get_secret("R2_ACCESS_KEY_ID")
    r2_secret = get_secret("R2_SECRET_ACCESS_KEY")
    r2_acc = get_secret("R2_ACCOUNT_ID")
    r2_bucket = get_secret("R2_BUCKET_NAME", "pod-scra-vault")
    
    if not all([sb_url, sb_key, r2_id, r2_secret, r2_acc]):
        print("❌ [補給中斷] 憑證缺失。"); return
    
    supabase: Client = create_client(sb_url, sb_key)
    ai_agent = AIAgent()
    s3_client = boto3.client('s3', 
        endpoint_url=f'https://{r2_acc}.r2.cloudflarestorage.com',
        aws_access_key_id=r2_id, 
        aws_secret_access_key=r2_secret, 
        region_name='auto')

    # 🎯 領取 Worker 已完成但尚未分析的任務
    missions = supabase.table("mission_queue").select("*")\
        .eq("status", "completed")\
        .is_("summary", "null")\
        .order("created_at", desc=True).limit(INTEL_LIMIT).execute()

    if not missions.data:
        print("☕ [情報部] 暫無新入庫物資需要提煉。"); return

    total_tasks = len(missions.data)
    print(f"📦 [掃描雷達] 發現 {total_tasks} 筆情報待處理。")

    for idx, task in enumerate(missions.data):
        task_id = task['id']
        r2_file_key = task.get('r2_url')
        episode_title = task.get('episode_title', 'Untitled')
        
        local_raw = f"/tmp/raw_{idx}.m4a"
        local_opus = f"/tmp/proc_{idx}.opus"

        try:
            print(f"📡 [提領 {idx+1}/{total_tasks}] 從 R2 倉庫提取: {r2_file_key}")
            s3_client.download_file(r2_bucket, r2_file_key, local_raw)

            # ⚙️ 執行 Opus 技術壓縮 (必須保留 FFmpeg)
            print("⚙️ [處理] FFmpeg 啟動，執行音訊規格優化...")
            subprocess.run(['ffmpeg', '-y', '-i', local_raw, '-ar', '16000', '-ac', '1', '-c:a', 'libopus', '-b:a', '24k', local_opus], 
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # 🧠 調用 AI 智囊團
            print(f"🧠 [思考] Gemini/Groq 正在解構情報...")
            analysis, q_score, duration = ai_agent.generate_gold_analysis(local_opus)

            if analysis:
                # 📡 發送戰報
                report_msg = ai_agent.format_mission_report("Gold", episode_title, "N/A", analysis, 
                                                            datetime.now().strftime("%m/%d"), duration, task.get('source_name'))
                requests.post(f"https://api.telegram.org/bot{get_secret('TELEGRAM_BOT_TOKEN')}/sendMessage", 
                              json={"chat_id": get_secret("TELEGRAM_CHAT_ID"), "text": report_msg, "parse_mode": "Markdown"})

                # 🏆 任務存檔
                supabase.table("mission_queue").update({"summary": analysis}).eq("id", task_id).execute()
                print(f"✅ [成功] 任務 {task_id} 提煉完成。")

            # ⏳ 執行指揮官要求的「階梯式 Jitter」延時邏輯
            if idx < total_tasks - 1:
                # 休息時間 = (已處理個數) * random(10~20分鐘)
                # 例如傳完第 2 個 (idx=1), 休息 = 2 * random_min
                multiplier = idx + 1
                wait_mins = multiplier * random.randint(JITTER_BASE_MIN, JITTER_BASE_MAX)
                
                print(f"🚧 [階梯防護] 已處理 {multiplier} 筆任務。")
                print(f"⏳ 為防 API 封鎖，啟動冷卻機制：休眠 {wait_mins} 分鐘...")
                time.sleep(wait_mins * 60)

        except Exception as e:
            print(f"⚠️ [情報異常]：{e}")
        finally:
            for f in [local_raw, local_opus]:
                if os.path.exists(f): os.remove(f)

if __name__ == "__main__":
    run_transport_and_report()