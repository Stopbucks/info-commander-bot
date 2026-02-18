
# ---------------------------------------------------------
# 本程式碼：src/pod_scra_transport.py v0.6(AI 戰報整合版)
# 任務：全量下載 -> 串流上傳至 R2 (pod-scra-vault)
# 流程：領命 -> 下載 -> 推 R2 -> 呼叫 AIAgent (Gemini) -> 發送 TG 戰報
# ---------------------------------------------------------

# ---------------------------------------------------------
# 本程式碼：src/pod_scra_transport.py v0.6 (AI 整合版)
# 任務：R2 入庫 -> 呼叫 AIAgent (Gemini) -> 發送 TG 戰報
# ---------------------------------------------------------
import os, requests, time, random, boto3, io
from supabase import create_client, Client
from datetime import datetime
from podcast_ai_agent import AIAgent  # 🚀 修正：對齊實體檔名

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
    ai_agent = AIAgent()  # 💡 實例化智囊團
    s3_client = boto3.client(
        's3',
        endpoint_url=f'https://{r2_account_id}.r2.cloudflarestorage.com',
        aws_access_key_id=r2_id,
        aws_secret_access_key=r2_secret, region_name='auto'
    )

    # 2. 領取任務 (維持 limit 1 確保單發精準度)
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
        # 3. 下載至 GitHub Runner 本機 (供 AI 讀取)
        print(f"📥 [下載中] 正在下載音檔：{source_name}...")
        resp = requests.get(audio_url, timeout=300)
        
        if resp.status_code == 200:
            with open(local_file, "wb") as f:
                f.write(resp.content)
            
            # 4. 上傳至 R2
            print(f"🚀 [運輸中] 正在將檔案推向 R2 倉庫...")
            s3_client.upload_file(local_file, 'pod-scra-vault', r2_file_name, ExtraArgs={'ContentType': 'audio/mpeg'})
            
            # 5. 🚀 核心：發起 AI 摘要行動
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
        print(f"❌ [任務潰敗]：{str(e)}")
    finally:
        if os.path.exists(local_file): os.remove(local_file)

if __name__ == "__main__":
    run_transport_and_report()