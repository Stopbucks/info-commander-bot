# ---------------------------------------------------------
# 本程式碼：src/pod_scra_transport.py v0.8 + Multi-Task
# 任務：領取最多 3 筆成功任務 -> 循環搬運、摘要與報戰
# 流程：領命 -> 進入迴圈 -> 下載 Jitter -> 推 R2 -> AI 摘要 -> TG 報報
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

    # 2. 領取任務 (設定 limit 為 3，確保一次處理多筆)
    missions = supabase.table("mission_queue").select("*") \
        .eq("scrape_status", "success") \
        .eq("status", "pending") \
        .limit(3) \
        .execute()
    
    if not missions.data:
        print("☕ [待命] 倉庫暫無待搬運物資。")
        return

    # 🚀 啟動多任務處理流水線
    # 技術說明：此迴圈確保所有領取到的任務都會被獨立執行。
    for index, mission_data in enumerate(missions.data):
        # A. 執行任務間抖動 (每集間隔 2~5 分鐘)
        if index > 0:
            task_gap = random.randint(120, 300)
            print(f"⏳ [休息] 為保護線路穩定，等待 {task_gap//60} 分鐘後搬運下一集...")
            time.sleep(task_gap)

        source_name = mission_data.get('source_name', 'unknown')
        audio_url = mission_data.get('audio_url')
        episode_title = mission_data.get('episode_title', 'Untitled')
        provider_info = mission_data.get('used_provider', 'Legacy/Unknown')
        
        # 加上 index 後綴，確保 local 檔案不衝突
        local_file = f"temp_scout_{index}.mp3"
        r2_file_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{source_name}.mp3"

        try:
            # 🚀 搬運工 Jitter：每次下載前的微小隨機等待
            jitter_sleep = random.randint(5, 15)
            print(f"🕒 [偽裝休眠] 正在搬運由 {provider_info} 偵得的物資，等待 {jitter_sleep} 秒...")
            time.sleep(jitter_sleep)

            # 3. 流式下載處理
            print(f"📥 [下載中] 正在搬運音檔：{source_name}...")
            with requests.get(audio_url, stream=True, timeout=300) as r:
                r.raise_for_status()
                with open(local_file, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            
            if os.path.exists(local_file):
                # 4. 推向 R2
                print(f"🚀 [運輸中] 正在將檔案推向 R2 倉庫：{r2_file_name}")
                s3_client.upload_file(local_file, 'pod-scra-vault', r2_file_name, ExtraArgs={'ContentType': 'audio/mpeg'})
                
                # 5. AI 分析
                print(f"🧠 [AI 行動] 呼叫智囊團執行摘要...")
                analysis, q_score, duration = ai_agent.generate_gold_analysis(local_file)

                if analysis:
                    # 6. Telegram 報戰
                    print(f"📡 [情報發布] 正在推送戰報...")
                    date_label = datetime.now().strftime("%m/%d/%y")
                    report_msg = ai_agent.format_mission_report(
                        "Gold", episode_title, audio_url, analysis, date_label, duration, source_name
                    )
                    
                    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN")
                    tg_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
                    requests.post(f"https://api.telegram.org/bot{tg_token}/sendMessage", 
                                   json={"chat_id": tg_chat_id, "text": report_msg, "parse_mode": "Markdown"})

                # 7. 更新資料庫為已完成
                supabase.table("mission_queue").update({
                    "status": "completed",
                    "r2_url": r2_file_name,
                    "mission_type": "scout_finished_with_ai"
                }).eq("id", mission_data['id']).execute()
                print(f"🏆 [任務達成] {episode_title[:15]}... 報送完成。")

        except Exception as e:
            print(f"❌ [任務潰敗] 目前任務發生錯誤：{str(e)}")
        finally:
            # 每集處理完後清理對應的暫存檔
            if os.path.exists(local_file): 
                os.remove(local_file)
                print(f"🧹 [清理] 暫存檔 {local_file} 已安全回收。")

if __name__ == "__main__":
    run_transport_and_report()