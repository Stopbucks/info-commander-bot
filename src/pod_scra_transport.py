# ---------------------------------------------------------
# 本程式碼：src/pod_scra_transport.py v0.7 + Jitter
# 任務：全量下載 -> 串流上傳至 R2 (pod-scra-vault)
# 流程：領命 -> 下載 / Jitter -> 推 R2 -> 呼叫 AIAgent -> 發送 TG 戰報
# ---------------------------------------------------------


import os, requests, time, random, boto3, io
from supabase import create_client, Client
from datetime import datetime
from podcast_ai_agent import AIAgent 

def run_transport_and_report():
    # 1. 讀取補給金鑰
    sb_url = os.environ.get("SUPABASE_URL")
    sb_key = os.environ.get("SUPABASE_KEY")
    r2_id = os.environ.get("R2_ACCESS_KEY_ID")
    r2_secret = os.environ.get("R2_SECRET_ACCESS_KEY")
    r2_account_id = os.environ.get("R2_ACCOUNT_ID")
    
    if not all([sb_url, sb_key, r2_id, r2_secret, r2_account_id]):
        print("❌ [資安警報] 環境變數不齊全。")
        return

    # 初始化組件
    supabase: Client = create_client(sb_url, sb_key)
    ai_agent = AIAgent() 
    s3_client = boto3.client(
        's3',
        endpoint_url=f'https://{r2_account_id}.r2.cloudflarestorage.com',
        aws_access_key_id=r2_id,
        aws_secret_access_key=r2_secret, region_name='auto'
    )

    # 2. 領取任務
    missions = supabase.table("mission_queue").select("*") \
        .eq("scrape_status", "success") \
        .eq("status", "pending") \
        .limit(1) \
        .execute()
    
    if not missions.data:
        print("☕ [待命] 倉庫暫無待搬運物資。")
        return

    mission = missions.data[0]
    audio_url = mission.get('audio_url')
    source_name = mission.get('source_name', 'unknown')
    episode_title = mission.get('episode_title', 'Untitled')
    local_file = "temp_scout.mp3"
    r2_file_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{source_name}.mp3"

    try:
        # 一行註解：搬運工 Jitter。下載前隨機休眠 5~15 秒，降低 CDN 偵測風險。
        jitter_sleep = random.randint(5, 15)
        print(f"🕒 [偽裝休眠] 準備搬運，等待 {jitter_sleep} 秒...")
        time.sleep(jitter_sleep)

        # 3. 下載至 GitHub Runner 本機
        print(f"📥 [下載中] 正在從來源搬運音檔：{source_name}...")
        # 一行註解：增加流式下載處理，避免大檔案造成記憶體溢位。
        with requests.get(audio_url, stream=True, timeout=300) as r:
            r.raise_for_status()
            with open(local_file, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        
        if os.path.exists(local_file):
            # 4. 上傳至 R2
            print(f"🚀 [運輸中] 正在將檔案推向 R2 倉庫：{r2_file_name}")
            s3_client.upload_file(local_file, 'pod-scra-vault', r2_file_name, ExtraArgs={'ContentType': 'audio/mpeg'})
            
            # 5. 核心：發起 AI 摘要行動
            print(f"🧠 [AI 行動] 呼叫智囊團執行深度解碼摘要...")
            analysis, q_score, duration = ai_agent.generate_gold_analysis(local_file)

            if analysis:
                # 6. 發送 Telegram 戰報
                print(f"📡 [情報發布] 正在推送至 Telegram...")
                date_label = datetime.now().strftime("%m/%d/%y")
                report_msg = ai_agent.format_mission_report(
                    "Gold", episode_title, audio_url, analysis, date_label, duration, source_name
                )
                
                tg_token = os.environ.get("TELEGRAM_BOT_TOKEN")
                tg_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
                requests.post(f"https://api.telegram.org/bot{tg_token}/sendMessage", 
                               json={"chat_id": tg_chat_id, "text": report_msg, "parse_mode": "Markdown"})

            # 7. 更新資料庫
            supabase.table("mission_queue").update({
                "status": "completed",
                "r2_url": r2_file_name,
                "mission_type": "scout_finished_with_ai"
            }).eq("id", mission['id']).execute()
            print(f"🏆 [任務達成] 檔案入庫與 AI 摘要報送完成。")

    except Exception as e:
        print(f"❌ [任務潰敗] 錯誤細節：{str(e)}")
    finally:
        if os.path.exists(local_file): os.remove(local_file)

if __name__ == "__main__":
    run_transport_and_report()